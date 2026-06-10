from __future__ import annotations

from fastapi import APIRouter, Query

from app.domains.football_v2 import FootballV2Service
from app.schemas.catalog import CompetitionOption, SportOption

router = APIRouter()
service = FootballV2Service()


@router.get("/sports", response_model=list[SportOption])
def get_sports() -> list[SportOption]:
    return service.get_sports()


@router.get("/competitions", response_model=list[CompetitionOption])
def get_competitions(sport_id: int = Query(..., gt=0)) -> list[CompetitionOption]:
    return service.get_competitions(sport_id)
