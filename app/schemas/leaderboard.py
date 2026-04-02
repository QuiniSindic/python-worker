from __future__ import annotations

from pydantic import BaseModel

from app.schemas.catalog import CompetitionOption, SportOption


class LeaderboardEntry(BaseModel):
    user_id: str
    username: str
    avatar_url: str | None = None
    total_points: int
    predictions_count: int
    exact_hits: int


class LeaderboardFilterOptions(BaseModel):
    sports: list[SportOption]
    competitions: list[CompetitionOption]
