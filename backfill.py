import asyncio
import sys
import os

# Aseguramos que Python encuentre el módulo 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.scraper import ScraperService
from app.services.database import DatabaseService

# --- CONFIGURACIÓN ---
TARGET_DATE = "20260131"  # Fecha a corregir
# ---------------------

def normalize_status(raw_status):
    """Convierte cualquier formato de status (Enum, Dict, Str) a string simple 'FT', 'NS', etc."""
    # 1. Si es un Enum (tiene .value o .name)
    if hasattr(raw_status, 'value'): 
        # Algunos Enums devuelven "MatchStatus.FT", queremos solo "FT"
        return str(raw_status.value).split('.')[-1]
    
    # 2. Si es un Diccionario (lo que devuelve FotMob a veces)
    if isinstance(raw_status, dict):
        return raw_status.get("short", "NS")
    
    # 3. Si ya es String
    s = str(raw_status)
    # Limpiamos "MatchStatus." si aparece
    return s.replace("MatchStatus.", "")

async def run_backfill():
    print(f"🛠️  Iniciando Backfill para fecha: {TARGET_DATE}")
    
    scraper = ScraperService()
    db = DatabaseService()

    # 1. Bajar partidos
    print("📥 Descargando partidos...")
    matches_data = await scraper.get_live_matches_fotmob(target_date=TARGET_DATE)
    
    if not matches_data:
        print("❌ No se encontraron datos.")
        return

    # 2. Guardar estructura base
    db.save_matches(matches_data)
    print(f"✅ Base guardada ({len(matches_data)} ligas).")

    # 3. Filtrar candidatos
    matches_to_update = []
    
    print("\n🔍 Analizando estados de partidos:")
    for league in matches_data:
        # Acceso seguro a matches
        matches = league.matches if hasattr(league, 'matches') else league.get('matches', [])
        
        for match in matches:
            mid = match.id if hasattr(match, 'id') else match.get('id')
            raw_status = match.status if hasattr(match, 'status') else match.get('status')
            
            # Usamos la función normalizadora
            status = normalize_status(raw_status)

            # DEBUG: Imprimir el estado que vemos para entender por qué falla/funciona
            # print(f"   - Partido {mid}: {status}")

            # Filtramos: Queremos Finalizados (FT), Prórrogas, Penaltis o En Juego
            if status in ["FT", "AET", "Pen", "HT"] or "LIVE" in status or "1H" in status or "2H" in status:
                matches_to_update.append(mid)

    print(f"\n✅ Se encontraron {len(matches_to_update)} partidos válidos para procesar.")

    # 4. Descargar detalles
    for i, mid in enumerate(matches_to_update):
        print(f"⏳ [{i+1}/{len(matches_to_update)}] Bajando eventos partido {mid}...", end="\r")
        
        try:
            events = await scraper.get_match_details(mid)
            if events:
                # Guardamos solo si hay eventos
                db.save_match_events(mid, events)
            else:
                # Opcional: Si devuelve vacío, quizás el partido fue muy aburrido 0-0 sin tarjetas
                pass
            
            await asyncio.sleep(1) # Pausa
            
        except Exception as e:
            print(f"\n❌ Error en partido {mid}: {e}")

    print("\n\n✨ ¡Backfill completado!")

if __name__ == "__main__":
    asyncio.run(run_backfill())