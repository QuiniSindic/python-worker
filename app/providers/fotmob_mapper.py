from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from app.schemas.match import CompetitionData, MatchData, MatchStatus, TeamInfo

logger = logging.getLogger(__name__)


class FotmobMapper:
    _BEST_THIRD_PATTERN = re.compile(r"\b(?:3rd|third|tercer(?:os?)?)\b", re.IGNORECASE)

    @staticmethod
    def _group_letter(index: int) -> str:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if 0 <= index < len(letters):
            return letters[index]
        return str(index + 1)

    @classmethod
    def _normalize_group_identity(
        cls, raw_name: str | None, index: int, total_groups: int
    ) -> tuple[str, str]:
        normalized = str(raw_name or "").strip()
        normalized_lower = normalized.lower()

        if cls._BEST_THIRD_PATTERN.search(normalized_lower):
            return "best_third_placed", "Mejores terceros"

        if normalized:
            compact = normalized.replace("-", " ").replace("_", " ").strip()
            parts = [part for part in compact.split() if part]
            if parts:
                last_token = parts[-1]
                if len(last_token) == 1 and last_token.isalpha():
                    letter = last_token.upper()
                    return f"group_{letter.lower()}", f"Grupo {letter}"
                if last_token.isdigit():
                    numeric_index = int(last_token)
                    if 1 <= numeric_index <= 26 and total_groups > 1:
                        letter = cls._group_letter(numeric_index - 1)
                        return f"group_{letter.lower()}", f"Grupo {letter}"

        if total_groups > 1:
            letter = cls._group_letter(index)
            return f"group_{letter.lower()}", f"Grupo {letter}"

        return "overall", "Tabla general"

    @staticmethod
    def _extract_round(match_data: dict[str, Any]) -> str | None:
        value = match_data.get("round")
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        if isinstance(value, dict):
            nested_name = value.get("name")
            return str(nested_name) if nested_name is not None else None

        round_name = match_data.get("roundName")
        if round_name is None:
            return None
        return str(round_name)

    @staticmethod
    def _normalize_status(status_obj: dict[str, Any] | None) -> MatchStatus:
        status_obj = status_obj or {}
        if status_obj.get("cancelled"):
            return MatchStatus.CANC
        if status_obj.get("finished"):
            return MatchStatus.FT
        if status_obj.get("started"):
            return MatchStatus.LIVE
        return MatchStatus.NS

    @staticmethod
    def _format_kickoff(utc_time: str | None, fallback: str = "") -> str:
        if not utc_time:
            return fallback
        try:
            dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        except ValueError:
            logger.debug("Invalid FotMob utcTime: %s", utc_time)
            return fallback
        return dt.strftime("%H:%M %d/%m/%Y")

    @staticmethod
    def _team_abbr(name: str | None) -> str:
        compact = (name or "").strip()
        return compact[:3].upper() if compact else "---"

    @staticmethod
    def _team_logo(team_id: int | None) -> str | None:
        if team_id is None:
            return None
        return f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"

    @staticmethod
    def _competition_logo(competition_id: int | None) -> str | None:
        if competition_id is None:
            return None
        return f"https://images.fotmob.com/image_resources/logo/leaguelogo/{competition_id}.png"

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None

        text = str(value).strip()
        return text or None

    @classmethod
    def _event_side(cls, event: dict[str, Any]) -> str:
        is_home = event.get("isHome")
        if is_home is True:
            return "home"
        if is_home is False:
            return "away"
        return "neutral"

    @classmethod
    def _event_title_candidates(cls, event: dict[str, Any]) -> list[str]:
        player = event.get("player")
        player_name = player.get("name") if isinstance(player, dict) else None
        return [
            value
            for value in (
                player_name,
                event.get("text"),
                event.get("description"),
                event.get("name"),
            )
            if cls._clean_text(value) is not None
        ]

    @staticmethod
    def _normalize_event_type(raw_type: Any) -> str:
        normalized = str(raw_type or "").strip().lower()
        mapping = {
            "goal": "Goal",
            "penaltygoal": "PenaltyGoal",
            "missedpenalty": "MissedPenalty",
            "failedpenalty": "FailedPenalty",
            "card": "Card",
            "substitution": "Substitution",
            "addedtime": "AddedTime",
            "half": "Half",
            "var": "Var",
        }
        return mapping.get(normalized, str(raw_type or "Other"))

    @staticmethod
    def _normalize_card_type(raw_card_type: Any) -> str | None:
        normalized = str(raw_card_type or "").strip()
        if not normalized:
            return None

        compact = normalized.lower().replace("-", "").replace("_", "")
        if compact in {"yellow"}:
            return "Yellow"
        if compact in {"red"}:
            return "Red"
        if compact in {"yellowred", "secondyellow", "secondyellowred"}:
            return "YellowRed"
        return normalized

    @classmethod
    def _is_penalty_goal_event(cls, event: dict[str, Any]) -> bool:
        goal_description = cls._clean_text(event.get("goalDescription"))
        goal_description_key = cls._clean_text(event.get("goalDescriptionKey"))
        suffix = cls._clean_text(event.get("suffix"))
        suffix_key = cls._clean_text(event.get("suffixKey"))
        shotmap_event = event.get("shotmapEvent")
        shot_situation = None
        if isinstance(shotmap_event, dict):
            shot_situation = cls._clean_text(shotmap_event.get("situation"))

        return any(
            (
                goal_description == "Penalty",
                goal_description_key == "penalty",
                suffix == "Pen",
                suffix_key == "penalties_short",
                shot_situation == "Penalty",
            )
        )

    @staticmethod
    def _translate_var_decision(decision_key: str | None, decision_value: str | None) -> str | None:
        mapping = {
            "var_yellow_card_removed": "Tarjeta amarilla cancelada",
            "var_red_card_removed": "Tarjeta roja anulada",
        }

        if decision_key and decision_key in mapping:
            return mapping[decision_key]

        if decision_value:
            return decision_value

        return None

    @classmethod
    def _build_var_decision(
        cls,
        event: dict[str, Any],
        clean_event: dict[str, Any],
        is_cancelled: bool,
    ) -> tuple[str | None, str | None, str | None]:
        player_name = cls._clean_text(clean_event.get("player"))
        var_decision = event.get("VAR") if isinstance(event.get("VAR"), dict) else {}
        decision_block = (
            var_decision.get("decision") if isinstance(var_decision.get("decision"), dict) else {}
        )
        decision_key = None
        if isinstance(decision_block.get("key"), list) and decision_block.get("key"):
            decision_key = cls._clean_text(decision_block["key"][0])
        decision_value = None
        if isinstance(decision_block.get("value"), list) and decision_block.get("value"):
            decision_value = cls._clean_text(decision_block["value"][0])

        decision = cls._clean_text(
            cls._translate_var_decision(decision_key, decision_value)
            or event.get("text")
            or event.get("decision")
            or event.get("description")
            or event.get("name")
        )
        reason = cls._clean_text(
            event.get("reason") or event.get("incidentClass") or event.get("varReason")
        )

        if not decision and is_cancelled:
            card_type = cls._clean_text(clean_event.get("cardType"))
            if card_type == "Red":
                decision = "Tarjeta roja anulada"
            elif card_type == "Yellow":
                decision = "Tarjeta amarilla anulada"

        if not decision:
            decision = "Revisión VAR"

        if reason and reason.casefold() == decision.casefold():
            reason = None

        return decision, player_name, reason

    @classmethod
    def _normalize_event_payload(
        cls,
        event: dict[str, Any],
        clean_event: dict[str, Any],
    ) -> dict[str, Any]:
        event_type = cls._normalize_event_type(clean_event.get("type") or event.get("type"))
        kind = "other"
        side = cls._event_side(event)
        title: str | None = None
        subtitle: str | None = None
        detail: str | None = None
        is_cancelled = bool(event.get("cancelled") or event.get("isCancelled"))

        if event_type in {"Goal", "PenaltyGoal"}:
            kind = "goal"
            title = clean_event.get("player") or next(
                iter(cls._event_title_candidates(event)),
                None,
            )
            details: list[str] = []
            if clean_event.get("assist"):
                details.append(f"Asist. {clean_event['assist']}")
            if clean_event.get("ownGoal"):
                details.append("Gol en propia")
            if clean_event.get("isPenalty") and not clean_event.get("isPenaltyShootout"):
                details.append("De penalti")
            if clean_event.get("isPenaltyShootout"):
                subtitle = "Tanda de penaltis"
            detail = " · ".join(details) or None
        elif event_type in {"MissedPenalty", "FailedPenalty"}:
            kind = "missed_penalty"
            title = clean_event.get("player") or next(
                iter(cls._event_title_candidates(event)),
                None,
            )
            detail = "Penalti fallado"
        elif event_type == "Card":
            kind = "card"
            title = clean_event.get("player") or next(
                iter(cls._event_title_candidates(event)),
                None,
            )
            card_type = clean_event.get("cardType")
            if card_type == "Red":
                detail = "Tarjeta roja"
            elif card_type == "YellowRed":
                detail = "Doble amarilla"
            elif card_type == "Yellow":
                detail = "Tarjeta amarilla"
            else:
                detail = "Tarjeta"
        elif event_type == "Substitution":
            kind = "substitution"
            title = clean_event.get("playerIn") or "Cambio"
            if clean_event.get("playerOut"):
                detail = f"Sale {clean_event['playerOut']}"
        elif event_type == "AddedTime":
            kind = "added_time"
            side = "neutral"
            title = clean_event.get("label") or "Tiempo añadido"
        elif event_type == "Half":
            kind = "period"
            side = "neutral"
            label = clean_event.get("label")
            title = {
                "HT": "Descanso",
                "FT": "Final",
                "AET": "Final prórroga",
                "AP": "Final penaltis",
            }.get(label or "", label or "Parte")
        elif event_type == "Var":
            kind = "var"
            title, subtitle, detail = cls._build_var_decision(
                event,
                clean_event,
                is_cancelled,
            )
        else:
            title = next(iter(cls._event_title_candidates(event)), None) or event_type
            detail = cls._clean_text(event.get("incidentClass") or event.get("reason"))

        if is_cancelled:
            if kind == "card":
                detail = f"{detail or 'Tarjeta'} anulada"
            elif kind == "goal":
                detail = f"{detail} · Acción anulada" if detail else "Acción anulada"
            elif kind == "var":
                detail = detail
            else:
                detail = detail or "Acción anulada"

        return {
            "kind": kind,
            "side": side,
            "title": title,
            "subtitle": subtitle,
            "detail": detail,
            "isCancelled": is_cancelled,
        }

    @classmethod
    def _map_team(cls, team: dict[str, Any], country_code: str) -> TeamInfo:
        team_id = team.get("id")
        team_name = team.get("name") or "Unknown Team"
        return TeamInfo(
            id=team_id or 0,
            name=team_name,
            abbr=cls._team_abbr(team_name),
            img=cls._team_logo(team_id),
            country=country_code,
        )

    @classmethod
    def _map_match(
        cls,
        match: dict[str, Any],
        competition_id: int,
        country_code: str,
    ) -> MatchData:
        status_obj = match.get("status", {})
        match_status = cls._normalize_status(status_obj)
        utc_time = status_obj.get("utcTime")
        home = match.get("home", {})
        away = match.get("away", {})

        minute_str = None
        if match_status == MatchStatus.LIVE:
            live_time = status_obj.get("liveTime", {})
            if isinstance(live_time, dict):
                minute_str = live_time.get("short") or live_time.get("long")

        result = status_obj.get("scoreStr")
        if result is None:
            result = f"{home.get('score', 0)}-{away.get('score', 0)}"

        return MatchData(
            id=match["id"],
            status=match_status,
            result=result,
            kickoff=cls._format_kickoff(utc_time, fallback=match.get("time", "")),
            kickoff_iso=utc_time,
            minute=minute_str,
            round=cls._extract_round(match),
            homeId=home.get("id") or 0,
            awayId=away.get("id") or 0,
            competitionid=competition_id,
            country=country_code,
            homeTeam=cls._map_team(home, country_code),
            awayTeam=cls._map_team(away, country_code),
            events=[],
        )

    def map_live_matches_payload(
        self,
        payload: dict[str, Any],
        target_league_ids: set[int] | list[int],
    ) -> list[CompetitionData]:
        leagues_data = payload.get("leagues", []) if isinstance(payload, dict) else []
        target_ids = {int(value) for value in target_league_ids}
        competitions: list[CompetitionData] = []

        for league in leagues_data:
            primary_id = league.get("primaryId")
            if primary_id not in target_ids:
                continue

            parsed_matches = [
                self._map_match(
                    match, competition_id=primary_id, country_code=league.get("ccode", "")
                )
                for match in league.get("matches", [])
                if isinstance(match, dict) and match.get("id") is not None
            ]
            if not parsed_matches:
                continue

            competitions.append(
                CompetitionData(
                    id=str(primary_id),
                    name=league.get("name") or "Unknown League",
                    fullName=league.get("name") or "Unknown League",
                    badge=self._competition_logo(primary_id) or "",
                    matches=parsed_matches,
                )
            )

        return competitions

    def _map_standing_row(
        self, team: dict[str, Any], team_form_map: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not isinstance(team, dict):
            return None

        team_id = team.get("id")
        scores_str = team.get("scoresStr", "")
        goals_for = 0
        goals_against = 0
        if scores_str and "-" in scores_str:
            try:
                left, right = str(scores_str).split("-", maxsplit=1)
                goals_for = int(left)
                goals_against = int(right)
            except ValueError:
                logger.debug("Invalid scoresStr in standings: %s", scores_str)

        return {
            "position": team.get("idx"),
            "id": team_id,
            "name": team.get("name"),
            "shortName": team.get("shortName"),
            "badge": f"{team_id}.png" if team_id is not None else None,
            "played": team.get("played"),
            "wins": team.get("wins"),
            "draws": team.get("draws"),
            "losses": team.get("losses"),
            "points": team.get("pts"),
            "goalsFor": goals_for,
            "goalsAgainst": goals_against,
            "goalDifference": team.get("goalConDiff"),
            "form": team_form_map.get(str(team_id), []),
        }

    def map_standings_payload(
        self, payload: dict[str, Any] | list, league_id: int
    ) -> dict[str, Any] | None:
        if isinstance(payload, list):
            data_block = payload[0].get("data", {}) if payload else {}
        elif isinstance(payload, dict):
            data_block = payload.get("data", {})
        else:
            data_block = {}

        team_form_map = data_block.get("teamForm", {}) if isinstance(data_block, dict) else {}

        if isinstance(data_block.get("tables"), list) and data_block["tables"]:
            groups: list[dict[str, Any]] = []
            total_tables = len(data_block["tables"])
            for index, table_group in enumerate(data_block["tables"]):
                if not isinstance(table_group, dict):
                    continue
                table_all = table_group.get("table", {}).get("all", [])
                rows = [
                    row
                    for row in (self._map_standing_row(team, team_form_map) for team in table_all)
                    if row is not None
                ]
                if not rows:
                    continue
                raw_name = (
                    table_group.get("name")
                    or table_group.get("groupName")
                    or table_group.get("title")
                    or f"Grupo {index + 1}"
                )
                group_id, group_name = self._normalize_group_identity(
                    str(raw_name), index, total_tables
                )
                groups.append(
                    {
                        "id": group_id,
                        "name": group_name,
                        "order": index,
                        "teams": rows,
                    }
                )

            if not groups:
                logger.warning("No standings groups found for league %s", league_id)
                return None

            logger.info("Detected FotMob 'tables' standings format for league %s", league_id)
            if len(groups) == 1:
                return {
                    "stageId": "league_table",
                    "stageName": "Clasificacion",
                    "stageType": "league_table",
                    "groups": [
                        {
                            "id": "overall",
                            "name": "Tabla general",
                            "order": 0,
                            "teams": groups[0]["teams"],
                        }
                    ],
                }
            return {
                "stageId": "group_stage",
                "stageName": "Fase de grupos",
                "stageType": "group",
                "groups": groups,
            }

        if isinstance(data_block.get("tables"), list) and data_block["tables"]:
            table_all = []
        elif isinstance(data_block.get("table"), dict):
            table_all = data_block.get("table", {}).get("all", [])
        elif isinstance(data_block.get("composite"), list):
            table_all = data_block.get("composite", [])
        else:
            table_all = []

        if not table_all:
            logger.warning("No standings rows found for league %s", league_id)
            return None

        processed = [
            row
            for row in (self._map_standing_row(team, team_form_map) for team in table_all)
            if row is not None
        ]
        return {
            "stageId": "league_table",
            "stageName": "Clasificacion",
            "stageType": "league_table",
            "groups": [
                {
                    "id": "overall",
                    "name": "Tabla general",
                    "order": 0,
                    "teams": processed,
                }
            ],
        }

    def map_match_details_payload(
        self, payload: dict[str, Any], match_id: int
    ) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            logger.warning("Unexpected FotMob matchDetails payload for match %s", match_id)
            return []

        content = payload.get("content", {})
        match_facts = content.get("matchFacts", {})
        if not match_facts:
            match_facts = payload.get("general", {}).get("matchFacts", {})

        raw_events = match_facts.get("events", {}).get("events", [])
        if not isinstance(raw_events, list):
            return []

        processed: list[dict[str, Any]] = []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            new_score = event.get("newScore")
            if isinstance(new_score, list) and len(new_score) >= 2:
                home_score = new_score[0]
                away_score = new_score[1]
            else:
                home_score = event.get("homeScore")
                away_score = event.get("awayScore")

            event_type = self._normalize_event_type(event.get("type"))
            if event_type == "Goal" and self._is_penalty_goal_event(event):
                event_type = "PenaltyGoal"

            clean_event: dict[str, Any] = {
                "type": event_type,
                "minute": event.get("time"),
                "timeStr": event.get("timeStr"),
                "isHome": event.get("isHome"),
                "score": {"home": home_score, "away": away_score},
                "isPenaltyShootout": event.get("isPenaltyShootoutEvent", False),
            }

            if event_type in {"Goal", "PenaltyGoal", "MissedPenalty", "FailedPenalty", "Var"}:
                player = event.get("player", {}) or {}
                clean_event["player"] = player.get("name")
                clean_event["playerId"] = player.get("id")
                if event_type == "Var":
                    clean_event["cardType"] = self._normalize_card_type(event.get("card"))

            if event_type in {"Goal", "PenaltyGoal"}:
                clean_event["assist"] = event.get("assistInput")
                clean_event["ownGoal"] = event.get("ownGoal", False)
                if event.get("isPenaltyShootoutEvent") or event_type == "PenaltyGoal":
                    clean_event["isPenalty"] = True
            elif event_type == "Card":
                player = event.get("player", {}) or {}
                clean_event["player"] = player.get("name")
                clean_event["playerId"] = player.get("id")
                clean_event["cardType"] = self._normalize_card_type(event.get("card"))
            elif event_type == "Substitution":
                swap = event.get("swap", [])
                if len(swap) >= 2:
                    clean_event["playerIn"] = swap[0].get("name")
                    clean_event["playerOut"] = swap[1].get("name")
                    clean_event["playerInId"] = swap[0].get("id")
                    clean_event["playerOutId"] = swap[1].get("id")
            elif event_type in {"Half", "AddedTime"}:
                clean_event["label"] = event.get("halfStrShort") or event.get("minutesAddedStr")

            clean_event.update(self._normalize_event_payload(event, clean_event))
            processed.append(clean_event)
        return processed

    def map_team_squad_payload(self, payload: dict[str, Any], team_id: int) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            logger.warning("Unexpected FotMob team payload for team %s", team_id)
            return []

        team_details = (
            payload.get("details", {}) if isinstance(payload.get("details"), dict) else {}
        )
        team_name = team_details.get("name")
        squad_block = payload.get("squad", {})
        groups = squad_block.get("squad", []) if isinstance(squad_block, dict) else []
        players: list[dict[str, Any]] = []

        for group in groups:
            if not isinstance(group, dict):
                continue
            group_title = str(group.get("title") or "")
            if group_title == "coach":
                continue
            members = group.get("members", [])
            if not isinstance(members, list):
                continue
            for member in members:
                if not isinstance(member, dict) or member.get("excludeFromRanking"):
                    continue
                player_id = member.get("id")
                player_name = self._clean_text(member.get("name"))
                if player_id is None or not player_name:
                    continue
                role = member.get("role") if isinstance(member.get("role"), dict) else {}
                players.append(
                    {
                        "player_id": int(player_id),
                        "name": player_name,
                        "team_id": team_id,
                        "team_name": team_name,
                        "group": group_title,
                        "role_key": role.get("key"),
                        "role": role.get("fallback"),
                        "position_id": member.get("positionId"),
                        "position_ids": member.get("positionIds"),
                        "position_ids_desc": member.get("positionIdsDesc"),
                        "shirt_number": member.get("shirtNumber"),
                        "club_name": member.get("cname"),
                        "age": member.get("age"),
                        "date_of_birth": member.get("dateOfBirth"),
                    }
                )

        return players

    def map_season_matches_payload(self, payload: dict[str, Any]) -> list[CompetitionData]:
        if not isinstance(payload, dict):
            return []

        fixtures = payload.get("fixtures", {})
        all_matches_raw = fixtures.get("allMatches", []) if isinstance(fixtures, dict) else []
        details = payload.get("details", {}) if isinstance(payload.get("details"), dict) else {}
        competition_id = details.get("id")
        if competition_id is None:
            return []

        league_name = details.get("name", "Unknown League")
        country_code = details.get("country", "")
        parsed_matches = [
            self._map_season_match(
                match, competition_id=int(competition_id), country_code=country_code
            )
            for match in all_matches_raw
            if isinstance(match, dict) and match.get("id") is not None
        ]
        if not parsed_matches:
            return []

        return [
            CompetitionData(
                id=str(competition_id),
                name=league_name,
                fullName=league_name,
                badge=self._competition_logo(int(competition_id)) or "",
                matches=parsed_matches,
            )
        ]

    def _map_season_match(
        self, match: dict[str, Any], competition_id: int, country_code: str
    ) -> MatchData:
        status_obj = match.get("status", {})
        utc_time = status_obj.get("utcTime")
        home = match.get("home", {})
        away = match.get("away", {})
        return MatchData(
            id=match["id"],
            status=self._normalize_status(status_obj),
            result=status_obj.get("scoreStr", "vs"),
            kickoff=self._format_kickoff(utc_time),
            kickoff_iso=utc_time,
            minute=None,
            round=self._extract_round(match),
            homeId=home.get("id") or 0,
            awayId=away.get("id") or 0,
            competitionid=competition_id,
            country=country_code,
            homeTeam=self._map_team(home, country_code),
            awayTeam=self._map_team(away, country_code),
            events=[],
        )
