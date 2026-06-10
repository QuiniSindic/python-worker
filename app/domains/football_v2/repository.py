from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from supabase import Client

from app.core.supabase import get_service_client


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _chunked[T](values: list[T], size: int = 500) -> Iterable[list[T]]:
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
        "format_kind": row.get("format_kind") or "groups_knockout",
        "start_at": row.get("start_date"),
        "end_at": row.get("end_date"),
    }


def _competition_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "provider_competition_id": row.get("provider_id"),
        "competition_kind": row.get("kind"),
        "participant_scope": "national_team",
    }


def _phase_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "competition_season_id": row.get("season_id"),
        "key": row.get("slug"),
    }


def _group_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "competition_phase_id": row.get("phase_id"),
        "key": row.get("slug"),
    }


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


def _match_to_legacy(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        **row,
        "competition_season_id": row.get("season_id"),
        "competition_phase_id": row.get("phase_id"),
        "phase_group_id": row.get("group_id"),
        "provider_event_id": row.get("provider_id"),
        "start_at": row.get("kickoff_at"),
        "event_type": "match",
        "title": row.get("title"),
        "is_placeholder": row.get("home_competitor_id") is None
        or row.get("away_competitor_id") is None,
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


class FootballV2Repository:
    def __init__(self, supabase: Client | None = None) -> None:
        self.supabase = supabase or get_service_client()

    def get_sport_by_slug(self, slug: str) -> dict | None:
        rows = (
            self.supabase.table("sports").select("*").eq("slug", slug).limit(1).execute().data or []
        )
        return rows[0] if rows else None

    def list_sports(self) -> list[dict]:
        return (
            self.supabase.table("sports")
            .select("*")
            .eq("is_active", True)
            .order("id")
            .execute()
            .data
            or []
        )

    def list_competitions_by_sport(self, sport_id: int) -> list[dict]:
        rows = (
            self.supabase.table("competitions")
            .select("*")
            .eq("sport_id", sport_id)
            .eq("is_active", True)
            .order("name")
            .execute()
            .data
            or []
        )
        seasons_by_competition = {
            row["competition_id"]: row
            for row in self.list_current_seasons([row["id"] for row in rows])
        }
        return [
            {
                **_competition_to_legacy(row),
                "current_season": seasons_by_competition.get(row["id"]),
            }
            for row in rows
        ]

    def get_competition(self, competition_id: int) -> dict | None:
        rows = (
            self.supabase.table("competitions")
            .select("*")
            .eq("id", competition_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _competition_to_legacy(rows[0]) if rows else None

    def list_current_seasons(self, competition_ids: list[int] | None = None) -> list[dict]:
        query = self.supabase.table("seasons").select("*").eq("is_current", True)
        if competition_ids:
            query = query.in_("competition_id", competition_ids)
        return [_season_to_legacy(row) for row in (query.execute().data or [])]

    def get_current_season_by_competition(self, competition_id: int) -> dict | None:
        rows = (
            self.supabase.table("seasons")
            .select("*")
            .eq("competition_id", competition_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _season_to_legacy(rows[0]) if rows else None

    def get_season(self, season_id: int) -> dict | None:
        rows = (
            self.supabase.table("seasons").select("*").eq("id", season_id).limit(1).execute().data
            or []
        )
        return _season_to_legacy(rows[0]) if rows else None

    def list_matches_for_seasons(
        self,
        season_ids: list[int],
        bucket: str,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        if not season_ids:
            return []
        statuses = ["scheduled", "live"] if bucket == "live" else ["finished"]
        query = (
            self.supabase.table("football_matches")
            .select("*")
            .in_("season_id", season_ids)
            .in_("status", statuses)
        )
        if from_date:
            query = query.gte("kickoff_at", f"{from_date}T00:00:00+00:00")
        if to_date:
            query = query.lte("kickoff_at", f"{to_date}T23:59:59+00:00")
        if limit is not None:
            query = query.limit(limit)
        return [
            _match_to_legacy(row)
            for row in (query.order("kickoff_at", desc=bucket == "results").execute().data or [])
        ]

    def list_recoverable_live_matches(
        self,
        provider_name: str,
        *,
        started_after: str,
        started_before: str,
        limit: int | None = None,
    ) -> list[dict]:
        query = (
            self.supabase.table("football_matches")
            .select("id,provider_id,kickoff_at,status")
            .eq("provider_name", provider_name)
            .eq("status", "live")
            .gte("kickoff_at", started_after)
            .lte("kickoff_at", started_before)
            .order("kickoff_at")
        )
        if limit is not None:
            query = query.limit(limit)
        return [_match_to_legacy(row) for row in (query.execute().data or [])]

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

    def list_matches_by_ids(self, event_ids: list[int]) -> list[dict]:
        if not event_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(event_ids):
            rows.extend(
                self.supabase.table("football_matches").select("*").in_("id", chunk).execute().data
                or []
            )
        return [_match_to_legacy(row) for row in rows]

    def list_matches_by_provider_ids(
        self,
        provider_name: str,
        provider_event_ids: list[str],
    ) -> list[dict]:
        if not provider_event_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked([int(item) for item in provider_event_ids if str(item).isdigit()]):
            rows.extend(
                self.supabase.table("football_matches")
                .select("*")
                .eq("provider_name", provider_name)
                .in_("provider_id", [str(item) for item in chunk])
                .execute()
                .data
                or []
            )
        return [_match_to_legacy(row) for row in rows]

    def list_match_competitors(self, event_ids: list[int]) -> list[dict]:
        if not event_ids:
            return []
        if isinstance(event_ids, int):
            event_ids = [event_ids]
        matches = self.list_matches_by_ids(event_ids)
        rows: list[dict] = []
        for match in matches:
            rows.extend(
                [
                    {
                        "event_id": match["id"],
                        "participant_id": match.get("home_competitor_id"),
                        "slot_key": "home",
                        "slot_order": 0,
                        "placeholder_label": match.get("home_placeholder_label"),
                    },
                    {
                        "event_id": match["id"],
                        "participant_id": match.get("away_competitor_id"),
                        "slot_key": "away",
                        "slot_order": 1,
                        "placeholder_label": match.get("away_placeholder_label"),
                    },
                ]
            )
        return rows

    def list_football_match_details(self, event_ids: list[int]) -> list[dict]:
        if not event_ids:
            return []
        matches = self.list_matches_by_ids(event_ids)
        timelines = self.list_football_match_events(event_ids)
        return [
            {
                "event_id": match["id"],
                "minute": match.get("minute"),
                "round_key": match.get("round_key"),
                "round_label": match.get("round_label"),
                "home_score": match.get("home_score"),
                "away_score": match.get("away_score"),
                "penalties_home": match.get("penalties_home"),
                "penalties_away": match.get("penalties_away"),
                "aggregate_home_score": match.get("aggregate_home_score"),
                "aggregate_away_score": match.get("aggregate_away_score"),
                "winner_participant_id": match.get("winner_competitor_id"),
                "timeline": timelines.get(match["id"], []),
            }
            for match in matches
        ]

    def list_football_match_events(self, event_ids: list[int]) -> dict[int, list[dict]]:
        rows: list[dict] = []
        for chunk in _chunked(event_ids):
            rows.extend(
                self.supabase.table("football_match_events")
                .select("*")
                .in_("football_match_id", chunk)
                .order("event_order")
                .execute()
                .data
                or []
            )
        grouped: dict[int, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["football_match_id"], []).append(row.get("raw") or row)
        return grouped

    def list_competitors(self, competitor_ids: list[int]) -> list[dict]:
        if not competitor_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(competitor_ids):
            rows.extend(
                self.supabase.table("competitors").select("*").in_("id", chunk).execute().data or []
            )
        return [_competitor_to_legacy(row) for row in rows]

    def list_competitions(self, competition_ids: list[int]) -> list[dict]:
        if not competition_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(competition_ids):
            rows.extend(
                self.supabase.table("competitions").select("*").in_("id", chunk).execute().data
                or []
            )
        return [_competition_to_legacy(row) for row in rows]

    def list_seasons(self, season_ids: list[int]) -> list[dict]:
        if not season_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(season_ids):
            rows.extend(
                self.supabase.table("seasons").select("*").in_("id", chunk).execute().data or []
            )
        return [_season_to_legacy(row) for row in rows]

    def list_phases_for_season(self, season_id: int) -> list[dict]:
        return [
            _phase_to_legacy(row)
            for row in (
                self.supabase.table("phases")
                .select("*")
                .eq("season_id", season_id)
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

    def list_standings_rows(
        self,
        season_id: int,
        phase_id: int | None = None,
        group_id: int | None = None,
    ) -> list[dict]:
        query = self.supabase.table("standings").select("*").eq("season_id", season_id)
        if phase_id is not None:
            query = query.eq("phase_id", phase_id)
        if group_id is not None:
            query = query.eq("group_id", group_id)
        return [_standing_to_legacy(row) for row in (query.order("position").execute().data or [])]

    def list_predictions_for_event(self, event_id: int) -> list[dict]:
        return [
            {**row, "event_id": row["football_match_id"], "match_id": row["football_match_id"]}
            for row in (
                self.supabase.table("match_predictions")
                .select("*")
                .eq("football_match_id", event_id)
                .order("created_at")
                .execute()
                .data
                or []
            )
        ]

    def list_all_predictions(self) -> list[dict]:
        return [
            {**row, "event_id": row["football_match_id"], "match_id": row["football_match_id"]}
            for row in (
                self.supabase.table("match_predictions")
                .select("*")
                .order("created_at", desc=True)
                .execute()
                .data
                or []
            )
        ]

    def get_user_prediction_for_event(self, event_id: int, user_id: str) -> dict | None:
        rows = (
            self.supabase.table("match_predictions")
            .select("*")
            .eq("football_match_id", event_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return (
            {
                **rows[0],
                "event_id": rows[0]["football_match_id"],
                "match_id": rows[0]["football_match_id"],
            }
            if rows
            else None
        )

    def upsert_prediction(
        self,
        *,
        user_id: str,
        sport_id: int,
        competition_id: int,
        season_id: int,
        event_id: int,
        home_score: int,
        away_score: int,
        prediction_id: str | None = None,
    ) -> dict:
        payload = {
            "user_id": user_id,
            "football_match_id": event_id,
            "home_score": home_score,
            "away_score": away_score,
            "status": "open",
            "updated_at": _utc_now_iso(),
        }
        if prediction_id:
            payload["id"] = prediction_id
        rows = (
            self.supabase.table("match_predictions")
            .upsert(payload, on_conflict="user_id,football_match_id")
            .execute()
            .data
            or []
        )
        row = rows[0]
        return {**row, "event_id": row["football_match_id"], "match_id": row["football_match_id"]}

    def get_profiles(self, user_ids: list[str]) -> list[dict]:
        if not user_ids:
            return []
        return self.supabase.table("profiles").select("*").in_("id", user_ids).execute().data or []

    def upsert_competition(self, payload: dict[str, Any]) -> dict:
        rows = (
            self.supabase.table("competitions")
            .upsert(
                {
                    "sport_id": payload["sport_id"],
                    "slug": payload["slug"],
                    "name": payload["name"],
                    "short_name": payload.get("short_name"),
                    "country_code": payload.get("country_code"),
                    "kind": payload.get("competition_kind") or payload.get("kind") or "competition",
                    "provider_name": payload["provider_name"],
                    "provider_id": str(
                        payload.get("provider_competition_id") or payload["provider_id"]
                    ),
                    "is_active": payload.get("is_active", True),
                    "updated_at": _utc_now_iso(),
                },
                on_conflict="provider_name,provider_id",
            )
            .execute()
            .data
            or []
        )
        return _competition_to_legacy(rows[0])

    def upsert_season(self, payload: dict[str, Any]) -> dict:
        rows = (
            self.supabase.table("seasons")
            .upsert(
                {
                    "competition_id": payload["competition_id"],
                    "slug": payload.get("season_key") or payload["slug"],
                    "name": payload.get("season_label") or payload["name"],
                    "start_date": payload.get("start_at") or payload["start_date"],
                    "end_date": payload.get("end_at") or payload["end_date"],
                    "is_current": payload.get("is_current", False),
                    "updated_at": _utc_now_iso(),
                },
                on_conflict="competition_id,slug",
            )
            .execute()
            .data
            or []
        )
        season = rows[0]
        if payload.get("is_current"):
            self.supabase.table("seasons").update({"is_current": False}).eq(
                "competition_id", season["competition_id"]
            ).neq("id", season["id"]).execute()
        return _season_to_legacy(season)

    def upsert_phases(self, phase_payloads: list[dict[str, Any]]) -> list[dict]:
        if not phase_payloads:
            return []
        payloads = [
            {
                "season_id": row["competition_season_id"],
                "slug": row["key"],
                "name": row["name"],
                "phase_type": row["phase_type"],
                "order_index": row["order_index"],
                "is_standings_phase": row.get("is_standings_phase", False),
                "is_bracket_phase": row.get("is_bracket_phase", False),
                "updated_at": _utc_now_iso(),
            }
            for row in phase_payloads
        ]
        return [
            _phase_to_legacy(row)
            for row in (
                self.supabase.table("phases")
                .upsert(payloads, on_conflict="season_id,slug")
                .execute()
                .data
                or []
            )
        ]

    def upsert_groups(self, group_payloads: list[dict[str, Any]]) -> list[dict]:
        if not group_payloads:
            return []
        payloads = [
            {
                "phase_id": row["competition_phase_id"],
                "slug": row["key"],
                "name": row["name"],
                "order_index": row["order_index"],
                "updated_at": _utc_now_iso(),
            }
            for row in group_payloads
        ]
        return [
            _group_to_legacy(row)
            for row in (
                self.supabase.table("groups")
                .upsert(payloads, on_conflict="phase_id,slug")
                .execute()
                .data
                or []
            )
        ]

    def upsert_competitors(self, competitor_payloads: list[dict[str, Any]]) -> list[dict]:
        if not competitor_payloads:
            return []
        payloads = []
        for row in competitor_payloads:
            provider_id = (row.get("metadata") or {}).get("provider_team_id") or row.get(
                "provider_id"
            )
            payloads.append(
                {
                    "sport_id": row["sport_id"],
                    "kind": "national_team"
                    if row.get("kind") == "team"
                    else row.get("kind", "club"),
                    "slug": row["slug"],
                    "name": row["name"],
                    "short_name": row.get("code") or row.get("short_name"),
                    "country_code": row.get("country_code"),
                    "badge_url": row.get("badge_url"),
                    "provider_name": row.get("provider_name", "fotmob"),
                    "provider_id": str(provider_id),
                    "updated_at": _utc_now_iso(),
                }
            )
        return [
            _competitor_to_legacy(row)
            for row in (
                self.supabase.table("competitors")
                .upsert(payloads, on_conflict="provider_name,provider_id")
                .execute()
                .data
                or []
            )
        ]

    def upsert_group_competitors(self, payloads: list[dict[str, Any]]) -> None:
        if payloads:
            self.supabase.table("group_competitors").upsert(
                payloads, on_conflict="group_id,competitor_id"
            ).execute()

    def _football_matches_by_ids(self, event_ids: list[int]) -> dict[int, dict]:
        rows: list[dict] = []
        for chunk in _chunked(sorted(set(event_ids))):
            rows.extend(
                self.supabase.table("football_matches").select("*").in_("id", chunk).execute().data
                or []
            )
        return {row["id"]: row for row in rows}

    def upsert_matches(self, match_payloads: list[dict[str, Any]]) -> list[dict]:
        if not match_payloads:
            return []
        payloads = [
            {
                "sport_id": row["sport_id"],
                "competition_id": row["competition_id"],
                "season_id": row["competition_season_id"],
                "phase_id": row.get("competition_phase_id"),
                "group_id": row.get("phase_group_id"),
                "provider_name": row["provider_name"],
                "provider_id": str(row["provider_event_id"]),
                "kickoff_at": row["start_at"],
                "status": row["status"],
                "round_key": None,
                "round_label": None,
                "home_placeholder_label": "Por decidir",
                "away_placeholder_label": "Por decidir",
                "last_synced_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
            for row in match_payloads
        ]
        return [
            _match_to_legacy(row)
            for row in (
                self.supabase.table("football_matches")
                .upsert(payloads, on_conflict="provider_name,provider_id")
                .execute()
                .data
                or []
            )
        ]

    def upsert_match_competitors(self, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return
        matches_by_id = self._football_matches_by_ids([row["event_id"] for row in payloads])
        updates_by_id: dict[int, dict[str, Any]] = {}
        for row in payloads:
            event_id = row["event_id"]
            field_prefix = "home" if row["slot_key"] == "home" else "away"
            updates_by_id.setdefault(event_id, {}).update(
                {
                    f"{field_prefix}_competitor_id": row.get("participant_id"),
                    f"{field_prefix}_placeholder_label": row.get("placeholder_label")
                    or "Por decidir",
                    "updated_at": _utc_now_iso(),
                }
            )
        rows = [
            {**matches_by_id[event_id], **updates}
            for event_id, updates in updates_by_id.items()
            if event_id in matches_by_id
        ]
        for chunk in _chunked(rows):
            self.supabase.table("football_matches").upsert(chunk, on_conflict="id").execute()

    def upsert_football_match_details(self, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return
        matches_by_id = self._football_matches_by_ids([row["event_id"] for row in payloads])
        rows = []
        for row in payloads:
            event_id = row["event_id"]
            if event_id in matches_by_id:
                rows.append(
                    {
                        **matches_by_id[event_id],
                        "minute": row.get("minute"),
                        "round_key": row.get("round_key"),
                        "round_label": row.get("round_label"),
                        "home_score": row.get("home_score"),
                        "away_score": row.get("away_score"),
                        "penalties_home": row.get("penalties_home"),
                        "penalties_away": row.get("penalties_away"),
                        "aggregate_home_score": row.get("aggregate_home_score"),
                        "aggregate_away_score": row.get("aggregate_away_score"),
                        "winner_competitor_id": row.get("winner_participant_id"),
                        "updated_at": _utc_now_iso(),
                    }
                )
            timeline = row.get("timeline") or []
            if timeline:
                self.replace_football_match_events(event_id, timeline)
        for chunk in _chunked(rows):
            self.supabase.table("football_matches").upsert(chunk, on_conflict="id").execute()

    def replace_football_match_events(self, event_id: int, timeline: list[dict]) -> None:
        if not timeline:
            return
        self.supabase.table("football_match_events").delete().eq(
            "football_match_id", event_id
        ).execute()
        payloads = [
            {
                "football_match_id": event_id,
                "event_order": index,
                "minute": item.get("timeStr") or str(item.get("time") or ""),
                "kind": item.get("kind") or item.get("type") or "event",
                "side": item.get("side"),
                "player_name": item.get("player"),
                "assist_name": item.get("assist"),
                "title": item.get("title"),
                "detail": item.get("detail"),
                "score": item.get("score"),
                "is_cancelled": bool(item.get("isCancelled")),
                "raw": item,
            }
            for index, item in enumerate(timeline)
            if isinstance(item, dict)
        ]
        if payloads:
            self.supabase.table("football_match_events").insert(payloads).execute()

    def replace_standings(self, season_id: int, payloads: list[dict[str, Any]]) -> None:
        self.supabase.table("standings").delete().eq("season_id", season_id).execute()
        if not payloads:
            return
        rows = [
            {
                "season_id": row["competition_season_id"],
                "phase_id": row["competition_phase_id"],
                "group_id": row["phase_group_id"],
                "competitor_id": row["participant_id"],
                "position": row["position"],
                "played": row["played"],
                "wins": row["wins"],
                "draws": row["draws"],
                "losses": row["losses"],
                "points": row["points"],
                "goals_for": row["goals_for"],
                "goals_against": row["goals_against"],
                "goal_difference": row["goal_difference"],
                "form": row.get("form") or [],
                "updated_at": _utc_now_iso(),
            }
            for row in payloads
        ]
        self.supabase.table("standings").insert(rows).execute()
        self.upsert_group_competitors(
            [
                {"group_id": row["phase_group_id"], "competitor_id": row["participant_id"]}
                for row in payloads
            ]
        )

    def upsert_provider_refs(self, payloads: list[dict[str, Any]]) -> None:
        if payloads:
            rows = [
                {
                    "provider_name": row["provider_name"],
                    "resource_type": row["resource_type"],
                    "external_id": row["external_id"],
                    "internal_table": row["internal_table"],
                    "internal_id": row["internal_id"],
                    "updated_at": _utc_now_iso(),
                }
                for row in payloads
            ]
            self.supabase.table("provider_refs").upsert(
                rows, on_conflict="provider_name,resource_type,external_id"
            ).execute()

    def upsert_sync_state(
        self,
        provider_name: str,
        scope_ref: str,
        state_key: str,
        state_value: dict[str, Any],
    ) -> None:
        self.supabase.table("sync_state").upsert(
            {
                "provider_name": provider_name,
                "scope_ref": scope_ref,
                "state_key": state_key,
                "state_value": state_value,
                "last_success_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            },
            on_conflict="provider_name,scope_ref,state_key",
        ).execute()
