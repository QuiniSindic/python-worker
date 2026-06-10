from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user, require_internal_access
from app.domains.football_v2.pickem_service import PickemService
from app.schemas.auth import AuthenticatedUser
from app.schemas.pickem import (
    PickemAwardPicksPayload,
    PickemAwardResultsPayload,
    PickemContestResponse,
    PickemEntryResponse,
    PickemGroupOrderPicksPayload,
    PickemLeaderboardEntry,
    PickemMatchPickPayload,
    PickemMatchPickResponse,
    PickemSquadImportStats,
)

router = APIRouter()
service = PickemService()


@router.get("/contests/current", response_model=PickemContestResponse)
def get_current_contest(
    competition_slug: str = Query(default="fifa-world-cup"),
) -> PickemContestResponse:
    return service.get_current_contest(competition_slug)


@router.get("/contests/{contest_id}/me", response_model=PickemEntryResponse)
def get_my_entry(
    contest_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PickemEntryResponse:
    return service.get_entry(contest_id, user)


@router.put("/contests/{contest_id}/groups", response_model=PickemEntryResponse)
def save_group_picks(
    contest_id: int,
    payload: PickemGroupOrderPicksPayload,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PickemEntryResponse:
    return service.save_group_picks(contest_id, payload, user)


@router.put("/contests/{contest_id}/awards", response_model=PickemEntryResponse)
def save_award_picks(
    contest_id: int,
    payload: PickemAwardPicksPayload,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PickemEntryResponse:
    return service.save_award_picks(contest_id, payload, user)


@router.put(
    "/contests/{contest_id}/matches/{event_id}",
    response_model=PickemMatchPickResponse,
)
def save_match_pick(
    contest_id: int,
    event_id: int,
    payload: PickemMatchPickPayload,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PickemMatchPickResponse:
    return service.save_match_pick(contest_id, event_id, payload, user)


@router.get("/contests/{contest_id}/leaderboard", response_model=list[PickemLeaderboardEntry])
def get_leaderboard(contest_id: int) -> list[PickemLeaderboardEntry]:
    return service.get_leaderboard(contest_id)


@router.post(
    "/internal/contests/{contest_id}/squads/fotmob",
    response_model=PickemSquadImportStats,
    dependencies=[Depends(require_internal_access)],
)
async def sync_pickem_squads_from_fotmob(contest_id: int) -> PickemSquadImportStats:
    return await service.sync_squads_from_fotmob(contest_id)


@router.put(
    "/internal/contests/{contest_id}/award-results",
    status_code=204,
    dependencies=[Depends(require_internal_access)],
)
def save_award_results(contest_id: int, payload: PickemAwardResultsPayload) -> None:
    service.save_award_results(contest_id, payload)


@router.post(
    "/internal/contests/{contest_id}/score",
    status_code=204,
    dependencies=[Depends(require_internal_access)],
)
def score_contest(contest_id: int) -> None:
    service.score_contest(contest_id)
