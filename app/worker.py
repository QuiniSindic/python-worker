import asyncio
import time
import logging
import traceback
# Importamos httpx para poder silenciar su logger
import httpx 

from app.services.scraper import ScraperService
from app.services.database import DatabaseService
from app.services.points import PointsService

# 1. CONFIGURACIÓN DE LOGGING (Menos ruido)
# Silenciamos librerías ruidosas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Worker")

class SoccerWorker:
    def __init__(self):
        self.scraper = ScraperService()
        self.db = DatabaseService()
        self.points_calculator = PointsService()
        
        # Estado interno
        self.last_full_update = 0
        self.FULL_UPDATE_INTERVAL = 3600  # 1 hora
        
    def _get_val(self, obj, attr_name, default=None):
        """Helper para obtener valores de objetos Pydantic o Diccionarios indistintamente."""
        if hasattr(obj, attr_name):
            val = getattr(obj, attr_name)
            return val if val is not None else default
        elif isinstance(obj, dict):
            return obj.get(attr_name, default)
        return default

    def _normalize_status(self, status_raw):
        """Normaliza el estado del partido a string de forma robusta."""
        # Caso 1: Es un Enum (MatchStatus.FT), accedemos a su valor real
        if hasattr(status_raw, 'value'):
            return str(status_raw.value)
        # Caso 2: Objeto con propiedad short (ej. objeto raw de FotMob)
        if hasattr(status_raw, 'short'):
            return str(status_raw.short)
        # Caso 3: Diccionario
        elif isinstance(status_raw, dict):
            return str(status_raw.get("short", "NS"))
        # Caso 4: String directo o fallback
        return str(status_raw)

    async def step_fetch_live_data(self):
        """Paso 1: Descargar partidos en vivo y guardar estructura base."""
        logger.info("📡 Buscando partidos en vivo...")
        matches_data = await self.scraper.get_live_matches_fotmob()
        
        if matches_data:
            # Upsert masivo (guardar competiciones y partidos)
            # Nota: Esto genera logs HTTP POST internos, pero ya no los verás en consola
            self.db.save_matches(matches_data)
            logger.info(f"✅ Datos base guardados: {len(matches_data)} ligas detectadas.")
            return matches_data
        
        logger.warning("⚠️ No se recibieron datos de partidos (lista vacía).")
        return []

    async def step_update_details(self, matches_data):
        """Paso 2: Detectar qué partidos necesitan detalles (eventos) y actualizarlos."""
        active_matches_ids = []
        leagues_active = set()

        for league in matches_data:
            l_id = self._get_val(league, 'id')
            matches = self._get_val(league, 'matches', [])
            
            league_has_activity = False
            for match in matches:
                m_id = self._get_val(match, 'id')
                status_raw = self._get_val(match, 'status')
                status = self._normalize_status(status_raw)

                # Si NO está (No empezado, Cancelado, Suspendido) -> Está vivo o terminó reciente
                # "FT" entra aquí para actualizar eventos finales (tarjetas post-partido, etc)
                if status not in ["NS", "Canc.", "Susp."]:
                    active_matches_ids.append(m_id)
                    league_has_activity = True
            
            if league_has_activity:
                leagues_active.add(l_id)

        if active_matches_ids:
            logger.info(f"🔍 Actualizando detalle (goles/tarjetas) de {len(active_matches_ids)} partidos activos.")
            for mid in active_matches_ids:
                events = await self.scraper.get_match_details(mid)
                if events:
                    self.db.save_match_events(mid, events)
                await asyncio.sleep(0.2) # Pausa reducida para ir más rápido
        else:
            logger.info("ℹ️ No hay partidos en juego que requieran detalles.")
            
        return leagues_active

    async def step_update_standings(self, leagues_active):
        """Paso 3: Actualizar tablas de clasificación si es necesario."""
        current_time = time.time()
        force_update = (current_time - self.last_full_update) > self.FULL_UPDATE_INTERVAL
        
        leagues_to_update = set(leagues_active)
        
        if force_update:
            logger.info("⏰ Ejecutando actualización periódica de clasificaciones...")
            leagues_to_update.update([47, 87, 53, 54, 55, 42])
            self.last_full_update = current_time

        if leagues_to_update:
            logger.info(f"📊 Actualizando tablas de {len(leagues_to_update)} ligas...")
            for lid in leagues_to_update:
                try:
                    standings = await self.scraper.get_standings(lid)
                    if standings:
                        self.db.save_standings(lid, standings)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"   ⚠️ Fallo en tabla liga {lid}: {e}")
        else:
            logger.info("💤 Las clasificaciones están al día.")

    async def step_process_finished(self, matches_data):
        """Paso 4: El Juez. Verificar partidos terminados y repartir puntos."""
        logger.info("⚖️ Verificando partidos terminados para puntuar...")
        
        count_checks = 0
        for league in matches_data:
            matches = self._get_val(league, 'matches', [])
            for match in matches:
                m_id = self._get_val(match, 'id')
                status_raw = self._get_val(match, 'status')
                status = self._normalize_status(status_raw)
                result_str = self._get_val(match, 'result')

                # --- DEBUG ESPECÍFICO PARA TU PARTIDO ---
                # Esto imprimirá la razón exacta por la que se salta tu partido
                if str(m_id) == "4813622":
                    logger.info(f"👀 DEPURANDO PARTIDO 4813622 | Status: '{status}' | Result: '{result_str}'")
                # ----------------------------------------

                # Verificamos si es Final Time (FT), Prórroga (AET) o Penaltis (AP)
                if status in ["FT", "AET", "AP"]:
                    try:
                        if result_str and "-" in result_str:
                            parts = result_str.split("-")
                            home = int(parts[0].strip())
                            away = int(parts[1].strip())
                            
                            # Llamada al servicio de puntos
                            # Este servicio internamente verifica si ya tiene puntos asignados
                            await self.points_calculator.calculate_match_points(m_id, home, away)
                            count_checks += 1
                        else:
                            # Si el partido acabó pero no tenemos resultado válido (ej: "vs")
                            if str(m_id) == "4813622":
                                logger.warning(f"⚠️ El partido 4813622 está FT pero el resultado es '{result_str}'")

                    except Exception as e:
                        logger.error(f"Error procesando resultado partido {m_id}: {e}")
        
        if count_checks == 0:
            logger.info("ℹ️ Ningún partido finalizado requería revisión en este ciclo.")

    async def run(self):
        logger.info("🚀 INICIANDO WORKER DE FÚTBOL INTELIGENTE")
        
        while True:
            start_time = time.time()
            logger.info("\n--- 🔄 INICIANDO CICLO ---")
            
            try:
                # 1. Obtener datos
                matches_data = await self.step_fetch_live_data()
                
                if matches_data:
                    # 2. Detalles de eventos
                    leagues_active = await self.step_update_details(matches_data)
                    
                    # 3. Clasificaciones
                    await self.step_update_standings(leagues_active)
                    
                    # 4. Puntuaciones (Juez)
                    await self.step_process_finished(matches_data)
                
            except Exception as e:
                logger.critical(f"❌ ERROR CRÍTICO EN EL WORKER: {e}")
                traceback.print_exc()
            
            # Cálculo del tiempo de espera
            elapsed = time.time() - start_time
            sleep_time = max(10, 60 - elapsed) # Mínimo 10 segundos
            logger.info(f"💤 Ciclo terminado en {elapsed:.2f}s. Durmiendo {sleep_time:.2f}s...")
            
            await asyncio.sleep(sleep_time)

# Punto de entrada
def main():
    worker = SoccerWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("\n🛑 Worker detenido manualmente.")


if __name__ == "__main__":
    main()
