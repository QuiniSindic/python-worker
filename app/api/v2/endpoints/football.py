from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.domains.football_v2 import FootballV2Service
from app.schemas.auth import AuthenticatedUser
from app.schemas.catalog import CompetitionEditionLite
from app.schemas.football import (
    BracketRoundResponse,
    CompetitionDataResponse,
    CompetitionStandingsSnapshotResponse,
    CompetitionStructureResponse,
    MatchResponse,
    PredictionFeedItemResponse,
    PredictionRowResponse,
    PredictionUpdatePayload,
    PredictionUpsertPayload,
)

router = APIRouter()
service = FootballV2Service()


@router.get("/events/live", response_model=list[CompetitionDataResponse])
def get_live_events(
    competition_id: int | None = Query(default=None, gt=0),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> list[CompetitionDataResponse]:
    return service.get_event_feed(
        bucket="live",
        competition_id=competition_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


@router.get("/events/results", response_model=list[CompetitionDataResponse])
def get_result_events(
    competition_id: int | None = Query(default=None, gt=0),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> list[CompetitionDataResponse]:
    return service.get_event_feed(
        bucket="results",
        competition_id=competition_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


@router.get("/events/{event_id}", response_model=MatchResponse)
def get_event(event_id: int) -> MatchResponse:
    return service.get_event(event_id)


@router.get("/events/{event_id}/predictions", response_model=list[PredictionRowResponse])
def get_event_predictions(event_id: int) -> list[PredictionRowResponse]:
    return service.get_event_predictions(event_id)


@router.get("/events/{event_id}/predictions/me", response_model=PredictionRowResponse | None)
def get_event_prediction_me(
    event_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PredictionRowResponse | None:
    return service.get_user_prediction(event_id, user)


@router.post("/events/{event_id}/predictions", response_model=PredictionRowResponse)
def save_event_prediction(
    event_id: int,
    payload: PredictionUpsertPayload,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PredictionRowResponse:
    return service.save_prediction(event_id, payload, user)


@router.put("/events/{event_id}/predictions", response_model=PredictionRowResponse)
def update_event_prediction(
    event_id: int,
    payload: PredictionUpdatePayload,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PredictionRowResponse:
    return service.update_prediction(event_id, payload.home_score, payload.away_score, user)


@router.get("/predictions/feed", response_model=list[PredictionFeedItemResponse])
def get_prediction_feed() -> list[PredictionFeedItemResponse]:
    return service.get_prediction_feed()


@router.get("/competitions/{competition_id}/current-season", response_model=CompetitionEditionLite)
def get_current_season(competition_id: int) -> CompetitionEditionLite:
    return service.get_current_season(competition_id)


@router.get("/seasons/{season_id}/overview", response_model=CompetitionStructureResponse)
def get_season_overview(season_id: int) -> CompetitionStructureResponse:
    return service.get_structure(season_id)


@router.get("/seasons/{season_id}/events", response_model=list[MatchResponse])
def get_season_events(
    season_id: int,
    bucket: str = Query(default="live"),
) -> list[MatchResponse]:
    if bucket == "results":
        groups = service.get_event_feed(bucket="results")
    else:
        groups = service.get_event_feed(bucket="live")
    matches: list[MatchResponse] = []
    for group in groups:
        for match in group.matches:
            if match.edition and match.edition.id == season_id:
                matches.append(match)
    return matches


@router.get("/seasons/{season_id}/bracket", response_model=list[BracketRoundResponse])
def get_season_bracket(season_id: int) -> list[BracketRoundResponse]:
    return service.get_bracket(season_id)


@router.get("/events/bracket/{competition_id}", response_model=list[BracketRoundResponse])
def get_current_bracket(competition_id: int) -> list[BracketRoundResponse]:
    season = service.get_current_season(competition_id)
    return service.get_bracket(season.id)


@router.get("/standings/{competition_id}", response_model=CompetitionStandingsSnapshotResponse)
def get_standings(
    competition_id: int,
    stage_id: str | None = Query(default=None),
    group_id: str | None = Query(default=None),
) -> CompetitionStandingsSnapshotResponse:
    return service.get_standings(competition_id, stage_id, group_id)
