from __future__ import annotations

from supabase import Client

from app.core.supabase import get_service_client


class UsersRepository:
    def __init__(self, supabase: Client | None = None) -> None:
        self.supabase = supabase or get_service_client()

    def get_profiles_map(self, user_ids: list[str]) -> dict[str, dict]:
        if not user_ids:
            return {}

        rows = (
            self.supabase.table("profiles")
            .select("id, username, email, avatar_url")
            .in_("id", user_ids)
            .execute()
            .data
            or []
        )
        return {row["id"]: row for row in rows if isinstance(row, dict) and row.get("id")}

    def get_profile(self, user_id: str) -> dict | None:
        rows = (
            self.supabase.table("profiles")
            .select("id, username, email, avatar_url")
            .eq("id", user_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
