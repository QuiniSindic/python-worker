from __future__ import annotations

from pydantic import BaseModel, Field


class PickemTeamResponse(BaseModel):
    id: int
    name: str
    abbr: str
    badge: str | None = None
    country: str | None = None


class PickemGroupTeamResponse(PickemTeamResponse):
    position: int


class PickemGroupResponse(BaseModel):
    id: int
    key: str
    name: str
    order: int
    teams: list[PickemGroupTeamResponse] = Field(default_factory=list)


class PickemAwardCandidateResponse(BaseModel):
    id: int
    award_key: str
    display_name: str
    participant_id: int | None = None
    player_id: int | None = None
    squad_player_id: int | None = None
    team_id: int | None = None
    team_name: str | None = None
    position_desc: str | None = None
    is_goalkeeper: bool | None = None
    is_active: bool = True


class PickemContestResponse(BaseModel):
    id: int
    slug: str
    name: str
    competition_id: int
    competition_season_id: int
    group_deadline: str
    awards_deadline: str
    scoring_config: dict
    groups: list[PickemGroupResponse] = Field(default_factory=list)
    award_candidates: list[PickemAwardCandidateResponse] = Field(default_factory=list)
    champion_candidates: list[PickemTeamResponse] = Field(default_factory=list)


class PickemGroupOrderPickInput(BaseModel):
    group_id: int
    participant_ids: list[int]


class PickemGroupOrderPicksPayload(BaseModel):
    groups: list[PickemGroupOrderPickInput]


class PickemAwardPicksPayload(BaseModel):
    mvp_candidate_id: int
    top_scorer_candidate_id: int
    best_goalkeeper_candidate_id: int
    champion_participant_id: int


class PickemMatchPickPayload(BaseModel):
    winner_participant_id: int
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)


class PickemGroupPickResponse(BaseModel):
    group_id: int
    participant_id: int
    predicted_position: int
    points: int | None = None
    is_exact: bool | None = None


class PickemAwardPickResponse(BaseModel):
    award_key: str
    candidate_id: int | None = None
    participant_id: int | None = None
    points: int | None = None
    is_hit: bool | None = None


class PickemMatchPickResponse(BaseModel):
    event_id: int
    winner_participant_id: int
    home_score: int | None = None
    away_score: int | None = None
    points: int | None = None
    winner_points: int | None = None
    exact_score_points: int | None = None
    is_winner_hit: bool | None = None
    is_exact_score: bool | None = None


class PickemEntryResponse(BaseModel):
    id: str
    contest_id: int
    user_id: str
    total_points: int
    group_points: int
    knockout_points: int
    award_points: int
    perfect_groups: int
    exact_scores: int
    group_picks: list[PickemGroupPickResponse] = Field(default_factory=list)
    award_picks: list[PickemAwardPickResponse] = Field(default_factory=list)
    match_picks: list[PickemMatchPickResponse] = Field(default_factory=list)


class PickemLeaderboardEntry(BaseModel):
    user_id: str
    username: str
    avatar_url: str | None = None
    total_points: int
    group_points: int
    knockout_points: int
    award_points: int
    perfect_groups: int
    exact_scores: int


class PickemAwardResultInput(BaseModel):
    award_key: str
    candidate_id: int | None = None
    participant_id: int | None = None


class PickemAwardResultsPayload(BaseModel):
    results: list[PickemAwardResultInput]


class PickemSquadImportStats(BaseModel):
    teams_processed: int
    players_upserted: int
    squad_players_upserted: int
    candidates_upserted: int
