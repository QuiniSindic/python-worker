from supabase import create_client, Client
from app.core.config import settings
from app.schemas.match import MatchData, CompetitionData

class DatabaseService:
    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def save_matches(self, competitions: list[CompetitionData]):
        """
        Guarda (Upsert) competiciones y partidos en la DB.
        """
        total_matches = 0

        SOCCER_SPORT_ID = 1

        for comp in competitions:
            # 1. Guardar Competición (si no existe)
            comp_data = {
                "id": int(comp.id),
                "name": comp.name,
                "badge": comp.badge,
                "sport_id": SOCCER_SPORT_ID,
                # "country": ... (si lo tuvieras en el objeto competition)
            }
            # upsert: inserta o actualiza si ya existe
            self.supabase.table("competitions").upsert(comp_data).execute()

            # 2. Guardar Partidos
            matches_to_upsert = []
            for match in comp.matches:
                # Preparamos el objeto para Supabase
                # Parseamos el string de kickoff a objeto datetime si es necesario, 
                # o dejamos que Postgres lo haga si el formato es ISO correcto.
                
                # Convertimos tus modelos Pydantic a dict para JSONB
                home_team_json = match.homeTeam.model_dump()
                away_team_json = match.awayTeam.model_dump()
                
                # Extraemos el score numérico del string "2-1" si es necesario
                # (Asumo que tu scraper ya maneja lógica de score, sino aquí lo refinas)
                h_score, a_score = 0, 0
                try:
                    parts = match.result.split("-")
                    if len(parts) == 2:
                        h_score = int(parts[0])
                        a_score = int(parts[1])
                except:
                    pass

                row = {
                    "id": match.id,
                    "competition_id": int(comp.id),
                    "sport_id": SOCCER_SPORT_ID,
                    "status": match.status,
                    "kickoff": match.kickoff_iso, # NECESITAS pasar fecha ISO aquí, no "HH:MM"
                    "minute": match.minute,
                    "round": match.round,
                    "home_team_id": match.homeId,
                    "away_team_id": match.awayId,
                    "home_score": h_score,
                    "away_score": a_score,
                    "home_team_data": home_team_json,
                    "away_team_data": away_team_json,
                    "updated_at": "now()"
                }
                matches_to_upsert.append(row)
                total_matches += 1
            
            if matches_to_upsert:
                # Insertamos en bloque para eficiencia
                self.supabase.table("matches").upsert(matches_to_upsert).execute()

        print(f"✅ Guardados datos de {len(competitions)} competiciones.")
        return total_matches

    def save_standings(self, league_id: int, standings_data: list):
        if not standings_data:
            return
            
        self.supabase.table("competitions").update({
            "standings": standings_data,
            "updated_at": "now()"
        }).eq("id", league_id).execute() 

    def save_match_events(self, match_id: int, events_data: list):
        if not events_data:
            return

        self.supabase.table("matches").update({
            "events": events_data,
            "updated_at": "now()" # Descomenta si creaste esta columna
        }).eq("id", match_id).execute()   

    def calculate_predictions_score(self, match_id: int, home_goals: int, away_goals: int):
        """
        Calcula los puntos para TODAS las predicciones de un partido terminado.
        Al ser solo usuarios logueados, actualizamos sus registros directamente.
        
        Sistema de Puntuación:
        - 3 Puntos: Marcador Exacto (Pleno).
        - 1 Punto:  Signo Correcto (Ganador/Empate) pero marcador incorrecto.
        - 0 Puntos: Fallo total.
        """
        print(f"🧮 Calculando quiniela para partido {match_id} (Resultado: {home_goals}-{away_goals})...")
        
        # 1. Buscamos todas las predicciones de este partido
        response = self.supabase.table("predictions").select("*").eq("match_id", match_id).execute()
        predictions = response.data
        
        if not predictions:
            print(f"   -> No hay predicciones registradas para el partido {match_id}.")
            return

        updates = []

        real_sign = "1" if home_goals > away_goals else ("2" if away_goals > home_goals else "X")


        # 3. Evaluamos cada predicción usuario por usuario
        for pred in predictions:
            p_home, p_away = int(pred["home_score"]), int(pred["away_score"])
            points = 0
            status = "lose"

           

            # --- CASO A: PLENO (Marcador Exacto) ---
            if p_home == home_goals and p_away == away_goals:
                points = 3
                status = "hit"  # Verde
            
            # --- CASO B: ACIERTO DE SIGNO (Ganador/Empate) ---
            else:
               pred_sign = "1" if p_home > p_away else ("2" if p_away > p_home else "X")
               if pred_sign == real_sign:
                    points = 1
                    status = "partial" # SIGNO

            # Preparamos el objeto para actualizar
            updates.append({
                "id": pred["id"],
                "points": points,
                "status": status,
                "updated_at": "now()"
            })

        # 4. Guardamos los cambios en lote (Upsert)
        if updates:
            # Upsert actualiza basándose en el ID
            self.supabase.table("predictions").upsert(updates).execute()
            print(f"✅ Puntos repartidos a {len(updates)} usuarios en el partido {match_id}.")
