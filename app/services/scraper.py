import httpx
from datetime import datetime
from typing import List
from app.schemas.match import MatchData, TeamInfo, MatchStatus, CompetitionData
from app.core.config import FOTMOB_TARGET_LEAGUE_IDS

class ScraperService:
    def __init__(self):
        # Inicializamos con caché configurado para no ser bloqueados
        # data_dir define donde se guardan los logs/cache
        pass
    
    def _extract_round(self, match_data: dict) -> str:
        # Prioridad 1: Campo 'round' (Suele ser el código: "1/8", "playoff", "1")
        if "round" in match_data:
            val = match_data["round"]
            if isinstance(val, str): return val
            if isinstance(val, int): return str(val)
            if isinstance(val, dict): return val.get("name") # Por si acaso viene anidado
        
        # Prioridad 2: Campo 'roundName' (A veces es int: 1)
        if "roundName" in match_data:
            return str(match_data["roundName"])
            
        return None

    async def get_live_matches_fotmob(self, target_date: str = None) -> List[CompetitionData]:
        # Usamos la fecha de hoy
        date_str = target_date if target_date else datetime.now().strftime("%Y%m%d")

        url = f"https://www.fotmob.com/api/data/matches?date={date_str}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            data = response.json()


            # FotMob devuelve una estructura compleja, hay que navegarla
            leagues_data = data.get("leagues", [])
                 
            target_leagues_ids = FOTMOB_TARGET_LEAGUE_IDS

            result_competitions: List[CompetitionData] = []


            for league in leagues_data:
                # Filtramos solo ligas principales (puedes ajustar los IDs)
                if league["primaryId"] in target_leagues_ids:
                    parsed_matches = []
                    for match in league.get("matches", []):
                        status_obj = match.get("status", {})

                        match_status = MatchStatus.NS # Por defecto Not Started

                        if status_obj.get("cancelled"):
                            match_status = MatchStatus.CANC
                        elif status_obj.get("finished"):
                            match_status = MatchStatus.FT
                        elif status_obj.get("started"):
                            match_status = MatchStatus.LIVE

                        kickoff_str = match.get("time", "") # Fallback
                        utc_time = status_obj.get("utcTime")
                        minute_str = None

                        if match_status == MatchStatus.LIVE:
                            live_time = status_obj.get("liveTime", {})
                            # FotMob suele poner el minuto en 'short' o 'timeStr'
                            if isinstance(live_time, dict):
                                minute_str = live_time.get("short") or live_time.get("long")

                        if utc_time:
                            try:
                                # Parseamos ISO format (quitamos la Z para compatibilidad simple)
                                dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
                                # Formateamos al estilo que le gusta a tu Frontend
                                kickoff_str = dt.strftime("%H:%M %d/%m/%Y") 
                            except ValueError:
                                pass
                        
                        # 3. Equipos
                        home = match.get("home", {})
                        away = match.get("away", {})

                        round_name = self._extract_round(match)

                        m_data = MatchData(
                            id=match["id"],
                            status=match_status,
                            # Usamos 'scoreStr' ("0 - 0") o construimos manual si falla
                            result=status_obj.get("scoreStr", f"{home.get('score',0)}-{away.get('score',0)}"),
                            kickoff=kickoff_str,
                            kickoff_iso=utc_time,
                            minute=minute_str,
                            round=round_name,
                            homeId=home.get("id"),
                            awayId=away.get("id"),
                            competitionid=league["primaryId"],
                            country=league.get("ccode", ""),
                            homeTeam=TeamInfo(
                                id=home.get("id"),
                                name=home.get("name"),
                                abbr=home.get("name")[:3].upper(), # FotMob no da abbr corto, lo generamos
                                img=f"https://images.fotmob.com/image_resources/logo/teamlogo/{home.get("id")}.png",
                                country=league.get("ccode", "")
                            ),
                            awayTeam=TeamInfo(
                                id=away.get("id"),
                                name=away.get("name"),
                                abbr=away.get("name")[:3].upper(),
                                img=f"https://images.fotmob.com/image_resources/logo/teamlogo/{away.get("id")}.png",
                                country=league.get("ccode", "")
                            ),
                            events=[] # Los eventos detallados (goles, tarjetas) requieren otra llamada
                        )
                        parsed_matches.append(m_data)

                    # Creamos el objeto de la competición con sus partidos
                    if parsed_matches:
                        comp_data = CompetitionData(
                            id=str(league["primaryId"]),
                            name=league["name"],
                            fullName=league["name"], # FotMob no distingue longName en la lista principal
                            badge=f"https://images.fotmob.com/image_resources/logo/leaguelogo/{league['primaryId']}.png",
                            matches=parsed_matches
                        )
                        result_competitions.append(comp_data)

            return result_competitions
    
    async def get_standings(self, league_id: int):
        """
        Obtiene la clasificación de una liga específica desde FotMob
        """
        url = f"https://www.fotmob.com/api/data/tltable?leagueId={league_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                raw_data = response.json() # [{data:{}}]

                if isinstance(raw_data, list) and len(raw_data) > 0:
                    data_block = raw_data[0].get("data", {})
                else:
                    data_block = raw_data.get("data", {})

                table_all = []

                if "tables" in data_block and isinstance(data_block["tables"], list) and len(data_block["tables"]) > 0:
                    # Normalmente la primera tabla es la general (League phase)
                    first_table_group = data_block["tables"][0]
                    table_container = first_table_group.get("table", {})
                    table_all = table_container.get("all", [])
                    print(f"   ℹ️ Detectado formato 'tables' (Champions) con {len(table_all)} filas.")

                elif "table" in data_block:
                    table_container = data_block.get("table", {})
                    table_all = table_container.get("all", [])

                elif "composite" in data_block and isinstance(data_block["composite"], list):
                     table_all = data_block["composite"]

                if not table_all:
                    print(f"⚠️ [Scraper] No se encontraron datos de tabla para Liga {league_id}")
                    return []

                team_form_map = data_block.get("teamForm", {})
                processed_standings = []

                for team in table_all:
                    team_id = team.get("id")
                    team_id_str = str(team_id)

                    goals_for = 0
                    goals_against = 0

                    scores_str = team.get("scoresStr", "")

                    if scores_str and "-" in scores_str:
                        try:
                            parts = team["scoresStr"].split("-")
                            goals_for = int(parts[0])
                            goals_against = int(parts[1])
                        except:
                            pass
                    
                    form_raw = team_form_map.get(team_id_str, [])

                    clean_team = {
                        "position": team.get("idx"),
                        "id": team.get("id"),
                        "name": team.get("name"),
                        "shortName": team.get("shortName"),
                        "badge": f"{team.get('id')}.png", # Pre-calculamos la imagen
                        "played": team.get("played"),
                        "wins": team.get("wins"),
                        "draws": team.get("draws"),
                        "losses": team.get("losses"),
                        "points": team.get("pts"),
                        "goalsFor": goals_for,
                        "goalsAgainst": goals_against,
                        "goalDifference": team.get("goalConDiff"),
                        "form": form_raw # Guardamos la lista de partidos recientes completa
                    }
                    processed_standings.append(clean_team)
                
                return processed_standings

            except Exception as e:
                print(f"Error fetching standings for {league_id}: {e}")
                return []
    
    async def get_match_details(self, match_id: int):
        """
        Obtiene los eventos detallados (goles, tarjetas, cambios) parseando
        el JSON complejo de matchFacts de FotMob.
        """
        url = f"https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                data = response.json()
                
                # 1. Localizar el contenedor de eventos
                # La estructura suele ser content -> matchFacts -> events -> events
                # A veces puede variar, así que usamos .get() encadenados con seguridad
                content = data.get("content", {})
                match_facts = content.get("matchFacts", {})
                
                # Si no está en content, a veces está en general (depende de la versión de la API)
                if not match_facts:
                    match_facts = data.get("general", {}).get("matchFacts", {})

                events_container = match_facts.get("events", {})
                raw_events = events_container.get("events", [])
                
                processed_events = []
                
                for event in raw_events:
                    event_type = event.get("type")
                    new_score_list = event.get("newScore")

                    if new_score_list and len(new_score_list) >= 2:
                        home_s = new_score_list[0]
                        away_s = new_score_list[1]
                    else:
                        home_s = event.get('homeScore')
                        away_s = event.get('awayScore')
                    
                    # Estructura base común
                    clean_event = {
                        "type": event_type,
                        "minute": event.get("time"),
                        "timeStr": event.get("timeStr"), # A veces es "45+2"
                        "isHome": event.get("isHome"),
                        "score": {
                            "home": home_s,
                            "away": away_s
                        },
                        "isPenaltyShootout": event.get("isPenaltyShootoutEvent", False)
                    }

                    # --- Lógica específica por tipo de evento ---
                    
                    # 1. GOLES
                    if event_type == "Goal":
                        player = event.get("player", {}) or {}
                        clean_event["player"] = player.get("name")
                        clean_event["playerId"] = player.get("id")
                        clean_event["assist"] = event.get("assistInput") # "Dani Olmo"
                        clean_event["ownGoal"] = event.get("ownGoal", False)
                        
                        # Si es tanda de penaltis, suele venir marcado
                        if event.get("isPenaltyShootoutEvent"):
                            clean_event["isPenalty"] = True

                    # 2. TARJETAS
                    elif event_type == "Card":
                        player = event.get("player", {}) or {}
                        clean_event["player"] = player.get("name")
                        clean_event["playerId"] = player.get("id")
                        clean_event["cardType"] = event.get("card") # "Yellow" o "Red"
                    
                    # 3. CAMBIOS (Substitution)
                    elif event_type == "Substitution":
                        # "swap" es una lista: [ {Saliente}, {Entrante} ] o viceversa
                        # Normalmente el primero [0] es el que sale y el [1] el que entra
                        swap = event.get("swap", [])
                        if len(swap) >= 2:
                            clean_event["playerOut"] = swap[0].get("name")
                            clean_event["playerIn"] = swap[1].get("name")
                            clean_event["playerOutId"] = swap[0].get("id")
                            clean_event["playerInId"] = swap[1].get("id")
                    
                    # 4. EXTRAS (Descanso, Final, Tiempo añadido)
                    # Opcional: Si quieres guardar cuando pitan el final o el descanso
                    elif event_type in ["Half", "AddedTime"]:
                        # Puedes guardarlos o ignorarlos. 
                        # Si es "Half", event.get("halfStrShort") suele ser "HT" o "FT"
                        clean_event["label"] = event.get("halfStrShort") or event.get("minutesAddedStr")

                    processed_events.append(clean_event)
                
                # Devolvemos la lista limpia, lista para guardar en el JSONB de Supabase
                return processed_events

            except Exception as e:
                print(f"⚠️ Error fetching details for match {match_id}: {e}")
                return []
    
    async def get_all_season_matches(self, league_id: int) -> List[CompetitionData]:
        """
        Obtiene EL CALENDARIO COMPLETO (pasado y futuro) de una liga.
        Ideal para el script de 'seeding'.
        """
        # Endpoint de liga: trae clasificación, partidos, estadísticas, etc.
        url = f"https://www.fotmob.com/api/data/leagues?id={league_id}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                data = response.json()
                
                # Estructura: data -> matches -> allMatches
                fixtures = data.get("fixtures", {})
                all_matches_raw = fixtures.get("allMatches", [])
                
                # Datos generales de la liga (nombre, país)
                # A veces están en 'details' o en la raíz
                details = data.get("details", {})
                league_id = details.get("id")
                league_name = details.get("name", "Unknown League")
                country_code = details.get("country", "") #ESP

                parsed_matches = []
                
                for match in all_matches_raw:
                    status_obj = match.get("status", {})
                    
                    # Mapeo de status
                    match_status = MatchStatus.NS
                    if status_obj.get("cancelled"):
                        match_status = MatchStatus.CANC
                    elif status_obj.get("finished"):
                        match_status = MatchStatus.FT
                    elif status_obj.get("started"):
                        match_status = MatchStatus.LIVE
                    
                    # Parsear fecha
                    utc_time = status_obj.get("utcTime")
                    kickoff_str = ""
                    if utc_time:
                        try:
                            dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
                            kickoff_str = dt.strftime("%H:%M %d/%m/%Y")
                        except:
                            pass
                    
                    home = match.get("home", {})
                    away = match.get("away", {})

                    round_name = self._extract_round(match)

                    # Construir MatchData
                    m_data = MatchData(
                        id=match["id"],
                        status=match_status,
                        result=status_obj.get("scoreStr", "vs"),
                        kickoff=kickoff_str,
                        kickoff_iso=utc_time,
                        round=round_name,
                        # round=match.get("round"), # Si quisieras guardar la jornada
                        minute=None, # En calendario global no suele venir el minuto exacto en vivo
                        homeId=home.get("id"),
                        awayId=away.get("id"),
                        competitionid=league_id,
                        country=country_code,
                        homeTeam=TeamInfo(
                            id=home.get("id"),
                            name=home.get("name"),
                            abbr=home.get("name")[:3].upper(),
                            img=f"https://images.fotmob.com/image_resources/logo/teamlogo/{home.get('id')}.png",
                            country=country_code
                        ),
                        awayTeam=TeamInfo(
                            id=away.get("id"),
                            name=away.get("name"),
                            abbr=away.get("name")[:3].upper(),
                            img=f"https://images.fotmob.com/image_resources/logo/teamlogo/{away.get('id')}.png",
                            country=country_code
                        ),
                        events=[]
                    )
                    parsed_matches.append(m_data)

                # Devolvemos una lista con un solo objeto CompetitionData lleno de partidos
                if parsed_matches:
                    return [CompetitionData(
                        id=str(league_id),
                        name=league_name,
                        fullName=league_name,
                        badge=f"https://images.fotmob.com/image_resources/logo/leaguelogo/{league_id}.png",
                        matches=parsed_matches
                    )]
                
                return []

            except Exception as e:
                print(f"Error fetching full season for league {league_id}: {e}")
                return []
