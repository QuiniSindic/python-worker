from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from supabase import Client

from app.core.supabase import get_service_client


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _chunked(values: list[int], size: int = 500) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


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
        competitions = (
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
            for row in self.list_current_seasons([row["id"] for row in competitions])
        }
        for row in competitions:
            row["current_season"] = seasons_by_competition.get(row["id"])
        return competitions

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
        return rows[0] if rows else None

    def list_current_seasons(self, competition_ids: list[int] | None = None) -> list[dict]:
        query = self.supabase.table("competition_seasons").select("*").eq("is_current", True)
        if competition_ids:
            query = query.in_("competition_id", competition_ids)
        return query.execute().data or []

    def get_current_season_by_competition(self, competition_id: int) -> dict | None:
        rows = (
            self.supabase.table("competition_seasons")
            .select("*")
            .eq("competition_id", competition_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def get_season(self, season_id: int) -> dict | None:
        rows = (
            self.supabase.table("competition_seasons")
            .select("*")
            .eq("id", season_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def list_events_for_seasons(
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
            self.supabase.table("events")
            .select("*")
            .in_("competition_season_id", season_ids)
            .in_("status", statuses)
        )
        if from_date:
            query = query.gte("start_at", f"{from_date}T00:00:00+00:00")
        if to_date:
            query = query.lte("start_at", f"{to_date}T23:59:59+00:00")
        if limit is not None:
            query = query.limit(limit)
        return query.order("start_at", desc=bucket == "results").execute().data or []

    def list_recoverable_live_events(
        self,
        provider_name: str,
        *,
        started_after: str,
        started_before: str,
        limit: int | None = None,
    ) -> list[dict]:
        query = (
            self.supabase.table("events")
            .select("id,provider_event_id,start_at,status")
            .eq("provider_name", provider_name)
            .eq("event_type", "match")
            .eq("status", "live")
            .gte("start_at", started_after)
            .lte("start_at", started_before)
            .order("start_at")
        )
        if limit is not None:
            query = query.limit(limit)
        return query.execute().data or []

    def get_event(self, event_id: int) -> dict | None:
        rows = (
            self.supabase.table("events").select("*").eq("id", event_id).limit(1).execute().data
            or []
        )
        return rows[0] if rows else None

    def list_events_by_ids(self, event_ids: list[int]) -> list[dict]:
        if not event_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(event_ids):
            rows.extend(
                self.supabase.table("events").select("*").in_("id", chunk).execute().data or []
            )
        return rows

    def list_events_by_provider_event_ids(
        self,
        provider_name: str,
        provider_event_ids: list[str],
    ) -> list[dict]:
        if not provider_event_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked([int(item) for item in provider_event_ids if str(item).isdigit()]):
            rows.extend(
                self.supabase.table("events")
                .select("*")
                .eq("provider_name", provider_name)
                .in_("provider_event_id", [str(item) for item in chunk])
                .execute()
                .data
                or []
            )
        return rows

    def list_event_participants(self, event_ids: list[int]) -> list[dict]:
        if not event_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(event_ids):
            rows.extend(
                self.supabase.table("event_participants")
                .select("*")
                .in_("event_id", chunk)
                .order("slot_order")
                .execute()
                .data
                or []
            )
        return rows

    def list_football_event_rows(self, event_ids: list[int]) -> list[dict]:
        if not event_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(event_ids):
            rows.extend(
                self.supabase.table("football_events")
                .select("*")
                .in_("event_id", chunk)
                .execute()
                .data
                or []
            )
        return rows

    def list_participants(self, participant_ids: list[int]) -> list[dict]:
        if not participant_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(participant_ids):
            rows.extend(
                self.supabase.table("participants").select("*").in_("id", chunk).execute().data
                or []
            )
        return rows

    def list_competitions(self, competition_ids: list[int]) -> list[dict]:
        if not competition_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(competition_ids):
            rows.extend(
                self.supabase.table("competitions").select("*").in_("id", chunk).execute().data
                or []
            )
        return rows

    def list_seasons(self, season_ids: list[int]) -> list[dict]:
        if not season_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(season_ids):
            rows.extend(
                self.supabase.table("competition_seasons")
                .select("*")
                .in_("id", chunk)
                .execute()
                .data
                or []
            )
        return rows

    def list_phases_for_season(self, season_id: int) -> list[dict]:
        return (
            self.supabase.table("competition_phases")
            .select("*")
            .eq("competition_season_id", season_id)
            .order("order_index")
            .execute()
            .data
            or []
        )

    def list_groups_for_phase_ids(self, phase_ids: list[int]) -> list[dict]:
        if not phase_ids:
            return []
        rows: list[dict] = []
        for chunk in _chunked(phase_ids):
            rows.extend(
                self.supabase.table("phase_groups")
                .select("*")
                .in_("competition_phase_id", chunk)
                .order("order_index")
                .execute()
                .data
                or []
            )
        return rows

    def list_standings_rows(
        self,
        season_id: int,
        phase_id: int | None = None,
        group_id: int | None = None,
    ) -> list[dict]:
        query = (
            self.supabase.table("football_standings_rows")
            .select("*")
            .eq("competition_season_id", season_id)
        )
        if phase_id is not None:
            query = query.eq("competition_phase_id", phase_id)
        if group_id is not None:
            query = query.eq("phase_group_id", group_id)
        return query.order("position").execute().data or []

    def list_predictions_for_event(self, event_id: int) -> list[dict]:
        prediction_rows = (
            self.supabase.table("predictions")
            .select("*")
            .eq("event_id", event_id)
            .order("created_at")
            .execute()
            .data
            or []
        )
        if not prediction_rows:
            return []
        details = (
            self.supabase.table("football_predictions")
            .select("*")
            .in_("prediction_id", [row["id"] for row in prediction_rows])
            .execute()
            .data
            or []
        )
        details_by_id = {row["prediction_id"]: row for row in details}
        return [
            {**row, **details_by_id.get(row["id"], {}), "match_id": row["event_id"]}
            for row in prediction_rows
        ]

    def get_user_prediction_for_event(self, event_id: int, user_id: str) -> dict | None:
        rows = (
            self.supabase.table("predictions")
            .select("*")
            .eq("event_id", event_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        prediction = rows[0]
        details = (
            self.supabase.table("football_predictions")
            .select("*")
            .eq("prediction_id", prediction["id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        return {**prediction, **(details[0] if details else {}), "match_id": prediction["event_id"]}

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
            "sport_id": sport_id,
            "competition_id": competition_id,
            "competition_season_id": season_id,
            "event_id": event_id,
            "prediction_type": "score",
            "status": "open",
            "updated_at": _utc_now_iso(),
        }
        if prediction_id:
            payload["id"] = prediction_id
        prediction_rows = (
            self.supabase.table("predictions")
            .upsert(payload, on_conflict="user_id,event_id,prediction_type")
            .execute()
            .data
            or []
        )
        prediction = prediction_rows[0]
        detail_rows = (
            self.supabase.table("football_predictions")
            .upsert(
                {
                    "prediction_id": prediction["id"],
                    "home_score": home_score,
                    "away_score": away_score,
                    "metadata": {},
                },
                on_conflict="prediction_id",
            )
            .execute()
            .data
            or []
        )
        return {
            **prediction,
            **(detail_rows[0] if detail_rows else {}),
            "match_id": prediction["event_id"],
        }

    def get_profiles(self, user_ids: list[str]) -> list[dict]:
        if not user_ids:
            return []
        return self.supabase.table("profiles").select("*").in_("id", user_ids).execute().data or []

    def upsert_competition(self, payload: dict[str, Any]) -> dict:
        rows = (
            self.supabase.table("competitions")
            .upsert(payload, on_conflict="provider_name,provider_competition_id")
            .execute()
            .data
            or []
        )
        return rows[0]

    def upsert_season(self, payload: dict[str, Any]) -> dict:
        rows = (
            self.supabase.table("competition_seasons")
            .upsert(payload, on_conflict="competition_id,season_key")
            .execute()
            .data
            or []
        )
        season = rows[0]
        if payload.get("is_current"):
            self.supabase.table("competition_seasons").update({"is_current": False}).eq(
                "competition_id", season["competition_id"]
            ).neq("id", season["id"]).execute()
        return season

    def upsert_phases(self, phase_payloads: list[dict[str, Any]]) -> list[dict]:
        if not phase_payloads:
            return []
        return (
            self.supabase.table("competition_phases")
            .upsert(phase_payloads, on_conflict="competition_season_id,key")
            .execute()
            .data
            or []
        )

    def upsert_groups(self, group_payloads: list[dict[str, Any]]) -> list[dict]:
        if not group_payloads:
            return []
        return (
            self.supabase.table("phase_groups")
            .upsert(group_payloads, on_conflict="competition_phase_id,key")
            .execute()
            .data
            or []
        )

    def upsert_participants(self, participant_payloads: list[dict[str, Any]]) -> list[dict]:
        if not participant_payloads:
            return []
        return (
            self.supabase.table("participants")
            .upsert(participant_payloads, on_conflict="sport_id,slug")
            .execute()
            .data
            or []
        )

    def upsert_season_participants(self, payloads: list[dict[str, Any]]) -> None:
        if payloads:
            self.supabase.table("competition_season_participants").upsert(
                payloads, on_conflict="competition_season_id,participant_id"
            ).execute()

    def upsert_events(self, event_payloads: list[dict[str, Any]]) -> list[dict]:
        if not event_payloads:
            return []
        return (
            self.supabase.table("events")
            .upsert(event_payloads, on_conflict="provider_name,provider_event_id")
            .execute()
            .data
            or []
        )

    def upsert_event_participants(self, payloads: list[dict[str, Any]]) -> None:
        if payloads:
            self.supabase.table("event_participants").upsert(
                payloads, on_conflict="event_id,slot_key,slot_order"
            ).execute()

    def upsert_football_events(self, payloads: list[dict[str, Any]]) -> None:
        if payloads:
            self.supabase.table("football_events").upsert(
                payloads, on_conflict="event_id"
            ).execute()

    def replace_standings(self, season_id: int, payloads: list[dict[str, Any]]) -> None:
        self.supabase.table("football_standings_rows").delete().eq(
            "competition_season_id", season_id
        ).execute()
        if payloads:
            self.supabase.table("football_standings_rows").insert(payloads).execute()

    def upsert_provider_refs(self, payloads: list[dict[str, Any]]) -> None:
        if payloads:
            self.supabase.table("provider_refs").upsert(
                payloads, on_conflict="provider_name,resource_type,external_id"
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
