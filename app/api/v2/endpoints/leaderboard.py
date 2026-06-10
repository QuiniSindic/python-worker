from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.domains.football_v2 import FootballV2Service
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardFilterOptions

router = APIRouter()
service = FootballV2Service()


@router.get("", response_model=list[LeaderboardEntry])
def get_leaderboard(
    scope: Literal["global", "sport", "competition"] = Query(default="global"),
    filter_id: int | None = Query(default=None, gt=0),
) -> list[LeaderboardEntry]:
    return service.get_leaderboard(scope, filter_id)


@router.get("/filters", response_model=LeaderboardFilterOptions)
def get_leaderboard_filters() -> LeaderboardFilterOptions:
    return service.get_leaderboard_filters()
