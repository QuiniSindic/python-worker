from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from supabase import Client

from app.core.supabase import get_service_client


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str) or not any(marker in value for marker in ("Ã", "Â")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def _chunked(values: list[int], size: int = 500) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _season_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "season_key": row.get("slug"),
        "season_label": row.get("name"),
        "season_type": "calendar_year",
        "format_kind": "groups_knockout",
        "start_at": row.get("start_date"),
        "end_at": row.get("end_date"),
    }


def _competition_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {**row, "provider_competition_id": row.get("provider_id")}


def _contest_to_legacy(
    row: dict, season: dict | None = None, competition: dict | None = None
) -> dict:
    season = _season_to_legacy(season) if season else row.get("season")
    competition = _competition_to_legacy(competition) if competition else row.get("competition")
    return {
        **row,
        "competition_season_id": row["season_id"],
        "group_deadline": row["group_deadline"],
        "awards_deadline": row["awards_deadline"],
        "scoring_config": row.get("scoring_config") or {},
        "season": season,
        "competition": competition,
    }


def _phase_to_legacy(row: dict) -> dict:
    return {**row, "competition_season_id": row["season_id"], "key": row["slug"]}


def _group_to_legacy(row: dict) -> dict:
    return {**row, "competition_phase_id": row["phase_id"], "key": row["slug"]}


def _competitor_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "code": row.get("short_name"),
        "metadata": {"provider_team_id": int(row["provider_id"])}
        if str(row.get("provider_id") or "").isdigit()
        else {"provider_team_id": row.get("provider_id")},
    }


def _standing_to_legacy(row: dict) -> dict:
    return {
        **row,
        "competition_season_id": row["season_id"],
        "competition_phase_id": row["phase_id"],
        "phase_group_id": row["group_id"],
        "participant_id": row["competitor_id"],
        "goal_difference": row["goal_difference"],
    }


def _match_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "competition_season_id": row["season_id"],
        "competition_phase_id": row.get("phase_id"),
        "phase_group_id": row.get("group_id"),
        "provider_event_id": row.get("provider_id"),
        "start_at": row.get("kickoff_at"),
    }


def _pickem_player_to_candidate(row: dict, award_key: str) -> dict:
    team_name = _clean_text(row.get("team_name"))
    return {
        "id": row["id"],
        "award_key": award_key,
        "display_name": _clean_text(row["display_name"]),
        "participant_id": row["competitor_id"],
        "metadata": {
            "player_id": row["id"],
            "squad_player_id": row["id"],
            "team_name": team_name,
            "position_desc": row.get("position"),
            "is_goalkeeper": row.get("position") == "GK",
        },
        "is_active": row.get("is_active", True),
    }


class PickemRepository:
    def __init__(self, supabase: Client | None = None) -> None:
        self.supabase = supabase or get_service_client()

    def get_current_contest(self, competition_slug: str) -> dict | None:
        competitions = (
            self.supabase.table("competitions")
            .select("*")
            .eq("slug", competition_slug)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not competitions:
            return None
        seasons = (
            self.supabase.table("seasons")
            .select("*")
            .eq("competition_id", competitions[0]["id"])
            .eq("is_current", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not seasons:
            return None
        rows = (
            self.supabase.table("pickems")
            .select("*")
            .eq("season_id", seasons[0]["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _contest_to_legacy(rows[0], seasons[0], competitions[0]) if rows else None

    def upsert_contest(self, payload: dict[str, Any]) -> dict:
        rows = (
            self.supabase.table("pickems")
            .upsert(
                {
                    "season_id": payload["competition_season_id"],
                    "slug": payload["slug"],
                    "name": payload["name"],
                    "group_deadline": payload["group_deadline"],
                    "awards_deadline": payload["awards_deadline"],
                    "scoring_config": payload.get("scoring_config") or {},
                    "is_active": payload.get("is_active", True),
                    "updated_at": _utc_now_iso(),
                },
                on_conflict="slug",
            )
            .execute()
            .data
            or []
        )
        return _contest_to_legacy(rows[0])

    def get_first_match_start_at(self, season_id: int) -> str | None:
        rows = (
            self.supabase.table("football_matches")
            .select("kickoff_at")
            .eq("season_id", season_id)
            .order("kickoff_at")
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0]["kickoff_at"] if rows else None

    def get_contest(self, contest_id: int) -> dict | None:
        contests = (
            self.supabase.table("pickems").select("*").eq("id", contest_id).limit(1).execute().data
            or []
        )
        if not contests:
            return None
        season = (
            self.supabase.table("seasons")
            .select("*")
            .eq("id", contests[0]["season_id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        competition = []
        if season:
            competition = (
                self.supabase.table("competitions")
                .select("*")
                .eq("id", season[0]["competition_id"])
                .limit(1)
                .execute()
                .data
                or []
            )
        return _contest_to_legacy(
            contests[0], season[0] if season else None, competition[0] if competition else None
        )

    def list_group_phase_rows(self, season_id: int) -> list[dict]:
        return [
            _phase_to_legacy(row)
            for row in (
                self.supabase.table("phases")
                .select("*")
                .eq("season_id", season_id)
                .eq("phase_type", "group_stage")
                .order("order_index")
                .execute()
                .data
                or []
            )
        ]

    def list_groups_for_phase_ids(self, phase_ids: list[int]) -> list[dict]:
        if not phase_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(phase_ids):
            rows.extend(
                self.supabase.table("groups")
                .select("*")
                .in_("phase_id", chunk)
                .order("order_index")
                .execute()
                .data
                or []
            )
        return [_group_to_legacy(row) for row in rows]

    def list_standings_rows(self, season_id: int) -> list[dict]:
        return [
            _standing_to_legacy(row)
            for row in (
                self.supabase.table("standings")
                .select("*")
                .eq("season_id", season_id)
                .order("position")
                .execute()
                .data
                or []
            )
        ]

    def list_group_matches(self, season_id: int, group_id: int) -> list[dict]:
        return [
            _match_to_legacy(row)
            for row in (
                self.supabase.table("football_matches")
                .select("*")
                .eq("season_id", season_id)
                .eq("group_id", group_id)
                .execute()
                .data
                or []
            )
        ]

    def list_competitors(self, competitor_ids: list[int]) -> list[dict]:
        if not competitor_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(sorted(set(competitor_ids))):
            rows.extend(
                self.supabase.table("competitors").select("*").in_("id", chunk).execute().data or []
            )
        return [_competitor_to_legacy(row) for row in rows]

    def list_award_candidates(self, contest_id: int) -> list[dict]:
        rows: list[dict] = []
        page_size = 1000
        offset = 0
        while True:
            page = (
                self.supabase.table("pickem_players")
                .select("*")
                .eq("pickem_id", contest_id)
                .eq("is_active", True)
                .order("name")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
                or []
            )
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        competitors_by_id = {
            row["id"]: row
            for row in self.list_competitors(
                [row["competitor_id"] for row in rows if row.get("competitor_id") is not None]
            )
        }
        candidates: list[dict] = []
        for row in rows:
            player_name = _clean_text(row["name"])
            team_name = _clean_text(
                competitors_by_id.get(row.get("competitor_id"), {}).get("name", "Equipo")
            )
            display_row = {
                **row,
                "name": player_name,
                "team_name": team_name,
                "display_name": f"{player_name} ({team_name})",
            }
            candidates.append(_pickem_player_to_candidate(display_row, "mvp"))
            if row.get("position") == "GK":
                candidates.append(_pickem_player_to_candidate(display_row, "best_goalkeeper"))
            else:
                candidates.append(_pickem_player_to_candidate(display_row, "top_scorer"))
        return candidates

    def upsert_pickem_players(self, pickem_id: int, players: list[dict]) -> list[dict]:
        if not players:
            return []
        payloads = [
            {
                **player,
                "pickem_id": pickem_id,
                "updated_at": _utc_now_iso(),
            }
            for player in players
        ]
        return (
            self.supabase.table("pickem_players")
            .upsert(payloads, on_conflict="pickem_id,provider_name,provider_id")
            .execute()
            .data
            or []
        )

    def deactivate_missing_pickem_players(
        self,
        pickem_id: int,
        active_provider_ids: set[str],
        synced_competitor_ids: set[int],
    ) -> int:
        if not synced_competitor_ids:
            return 0

        rows: list[dict] = []
        page_size = 1000
        for competitor_chunk in _chunked(sorted(synced_competitor_ids)):
            offset = 0
            while True:
                page = (
                    self.supabase.table("pickem_players")
                    .select("id, provider_id")
                    .eq("pickem_id", pickem_id)
                    .eq("provider_name", "fotmob")
                    .eq("is_active", True)
                    .in_("competitor_id", competitor_chunk)
                    .range(offset, offset + page_size - 1)
                    .execute()
                    .data
                    or []
                )
                rows.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size

        stale_ids = [
            row["id"] for row in rows if str(row.get("provider_id")) not in active_provider_ids
        ]
        for chunk in _chunked(stale_ids):
            (
                self.supabase.table("pickem_players")
                .update({"is_active": False, "updated_at": _utc_now_iso()})
                .in_("id", chunk)
                .execute()
            )
        return len(stale_ids)

    def upsert_award_results(self, contest_id: int, results: list[dict]) -> list[dict]:
        payloads = [
            {
                "pickem_id": contest_id,
                "award_key": result["award_key"],
                "pickem_player_id": result.get("candidate_id"),
                "competitor_id": result.get("participant_id"),
                "updated_at": _utc_now_iso(),
            }
            for result in results
        ]
        if not payloads:
            return []
        return (
            self.supabase.table("pickem_award_results")
            .upsert(payloads, on_conflict="pickem_id,award_key")
            .execute()
            .data
            or []
        )

    def list_award_results(self, contest_id: int) -> list[dict]:
        rows = (
            self.supabase.table("pickem_award_results")
            .select("*")
            .eq("pickem_id", contest_id)
            .execute()
            .data
            or []
        )
        return [
            {
                **row,
                "contest_id": row["pickem_id"],
                "candidate_id": row.get("pickem_player_id"),
                "participant_id": row.get("competitor_id"),
            }
            for row in rows
        ]

    def get_or_create_entry(self, contest_id: int, user_id: str) -> dict:
        rows = (
            self.supabase.table("user_pickems")
            .select("*")
            .eq("pickem_id", contest_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return self._entry_to_legacy(rows[0])
        created = (
            self.supabase.table("user_pickems")
            .insert({"pickem_id": contest_id, "user_id": user_id, "updated_at": _utc_now_iso()})
            .execute()
            .data
            or []
        )
        return self._entry_to_legacy(created[0])

    def list_entries(self, contest_id: int) -> list[dict]:
        return [
            self._entry_to_legacy(row)
            for row in (
                self.supabase.table("user_pickems")
                .select("*")
                .eq("pickem_id", contest_id)
                .order("total_points", desc=True)
                .execute()
                .data
                or []
            )
        ]

    def update_entry_scores(self, entry_id: str, payload: dict[str, Any]) -> None:
        self.supabase.table("user_pickems").update(
            {**payload, "scored_at": _utc_now_iso(), "updated_at": _utc_now_iso()}
        ).eq("id", entry_id).execute()

    def list_group_picks(self, entry_id: str) -> list[dict]:
        rows = (
            self.supabase.table("pickem_group_picks")
            .select("*")
            .eq("user_pickem_id", entry_id)
            .order("group_id")
            .order("predicted_position")
            .execute()
            .data
            or []
        )
        return [
            {
                **row,
                "entry_id": row["user_pickem_id"],
                "phase_group_id": row["group_id"],
                "participant_id": row["competitor_id"],
            }
            for row in rows
        ]

    def replace_group_picks(self, entry_id: str, picks: list[dict]) -> list[dict]:
        self.supabase.table("pickem_group_picks").delete().eq("user_pickem_id", entry_id).execute()
        payloads = [
            {
                "user_pickem_id": entry_id,
                "group_id": pick["phase_group_id"],
                "competitor_id": pick["participant_id"],
                "predicted_position": pick["predicted_position"],
                "updated_at": _utc_now_iso(),
            }
            for pick in picks
        ]
        if not payloads:
            return []
        return self.supabase.table("pickem_group_picks").insert(payloads).execute().data or []

    def update_group_pick_scores(self, updates: list[dict]) -> None:
        for update in updates:
            self.supabase.table("pickem_group_picks").update(
                {
                    "points": update["points"],
                    "is_exact": update["is_exact"],
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", update["id"]).execute()

    def list_award_picks(self, entry_id: str) -> list[dict]:
        rows = (
            self.supabase.table("pickem_award_picks")
            .select("*")
            .eq("user_pickem_id", entry_id)
            .order("award_key")
            .execute()
            .data
            or []
        )
        return [
            {
                **row,
                "entry_id": row["user_pickem_id"],
                "candidate_id": row.get("pickem_player_id"),
                "participant_id": row.get("competitor_id"),
            }
            for row in rows
        ]

    def replace_award_picks(self, entry_id: str, picks: list[dict]) -> list[dict]:
        self.supabase.table("pickem_award_picks").delete().eq("user_pickem_id", entry_id).execute()
        payloads = [
            {
                "user_pickem_id": entry_id,
                "award_key": pick["award_key"],
                "pickem_player_id": pick.get("candidate_id"),
                "competitor_id": pick.get("participant_id"),
                "updated_at": _utc_now_iso(),
            }
            for pick in picks
        ]
        return self.supabase.table("pickem_award_picks").insert(payloads).execute().data or []

    def update_award_pick_scores(self, updates: list[dict]) -> None:
        for update in updates:
            self.supabase.table("pickem_award_picks").update(
                {
                    "points": update["points"],
                    "is_hit": update["is_hit"],
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", update["id"]).execute()

    def get_match(self, event_id: int) -> dict | None:
        rows = (
            self.supabase.table("football_matches")
            .select("*")
            .eq("id", event_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _match_to_legacy(rows[0]) if rows else None

    def list_match_competitors(self, event_id: int) -> list[dict]:
        event = self.get_match(event_id)
        if event is None:
            return []
        return [
            {"participant_id": event.get("home_competitor_id"), "slot_key": "home"},
            {"participant_id": event.get("away_competitor_id"), "slot_key": "away"},
        ]

    def get_football_match_details(self, event_id: int) -> dict | None:
        event = self.get_match(event_id)
        if event is None:
            return None
        return {
            "event_id": event["id"],
            "home_score": event.get("home_score"),
            "away_score": event.get("away_score"),
            "winner_participant_id": event.get("winner_competitor_id"),
            "round_key": event.get("round_key"),
            "round_label": event.get("round_label"),
        }

    def get_phase(self, phase_id: int | None) -> dict | None:
        if phase_id is None:
            return None
        rows = (
            self.supabase.table("phases").select("*").eq("id", phase_id).limit(1).execute().data
            or []
        )
        return _phase_to_legacy(rows[0]) if rows else None

    def upsert_match_pick(self, entry_id: str, event_id: int, payload: dict) -> dict:
        rows = (
            self.supabase.table("pickem_match_picks")
            .upsert(
                {
                    "user_pickem_id": entry_id,
                    "football_match_id": event_id,
                    "winner_competitor_id": payload["winner_participant_id"],
                    "home_score": payload.get("home_score"),
                    "away_score": payload.get("away_score"),
                    "updated_at": _utc_now_iso(),
                },
                on_conflict="user_pickem_id,football_match_id",
            )
            .execute()
            .data
            or []
        )
        return self._match_pick_to_legacy(rows[0])

    def list_match_picks(self, entry_id: str) -> list[dict]:
        return [
            self._match_pick_to_legacy(row)
            for row in (
                self.supabase.table("pickem_match_picks")
                .select("*")
                .eq("user_pickem_id", entry_id)
                .order("football_match_id")
                .execute()
                .data
                or []
            )
        ]

    def update_match_pick_scores(self, updates: list[dict]) -> None:
        for update in updates:
            self.supabase.table("pickem_match_picks").update(
                {
                    "points": update["points"],
                    "winner_points": update["winner_points"],
                    "exact_score_points": update["exact_score_points"],
                    "is_winner_hit": update["is_winner_hit"],
                    "is_exact_score": update["is_exact_score"],
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", update["id"]).execute()

    def get_profiles(self, user_ids: list[str]) -> list[dict]:
        if not user_ids:
            return []
        return self.supabase.table("profiles").select("*").in_("id", user_ids).execute().data or []

    def _entry_to_legacy(self, row: dict) -> dict:
        return {**row, "contest_id": row["pickem_id"]}

    def _match_pick_to_legacy(self, row: dict) -> dict:
        return {
            **row,
            "entry_id": row["user_pickem_id"],
            "event_id": row["football_match_id"],
            "winner_participant_id": row["winner_competitor_id"],
        }
