from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.catalog import CompetitionEditionLite


class TeamInfoResponse(BaseModel):
    id: int
    name: str
    abbr: str
    img: str | None = None
    country: str


class MatchEventResponse(BaseModel):
    type: str
    minute: int | str | None = None
    timeStr: str | int | None = None
    isHome: bool | None = None
    kind: str | None = None
    side: str | None = None
    title: str | None = None
    subtitle: str | None = None
    detail: str | None = None
    isCancelled: bool | None = None
    score: dict[str, int | None] | None = None
    isPenaltyShootout: bool | None = None
    player: str | None = None
    playerId: int | None = None
    assist: str | None = None
    ownGoal: bool | None = None
    isPenalty: bool | None = None
    cardType: str | None = None
    playerIn: str | None = None
    playerOut: str | None = None
    playerInId: int | None = None
    playerOutId: int | None = None
    label: str | None = None


class MatchResponse(BaseModel):
    id: int
    status: str
    result: str
    kickoff: str
    kickoffIso: str | None = None
    minute: str | None = None
    homeId: int
    awayId: int
    competitionid: int
    sportId: int
    round: str | None = None
    homeTeam: TeamInfoResponse
    awayTeam: TeamInfoResponse
    country: str
    edition: CompetitionEditionLite | None = None
    events: list[MatchEventResponse] = Field(default_factory=list)


class BracketLegResponse(BaseModel):
    eventId: int
    kickoff: str
    kickoffIso: str | None = None
    status: str
    minute: str | None = None
    result: str
    leg: int
    homeTeam: TeamInfoResponse
    awayTeam: TeamInfoResponse


class BracketTieResponse(BaseModel):
    id: str
    roundId: str
    roundName: str
    order: int
    homeTeam: TeamInfoResponse
    awayTeam: TeamInfoResponse
    aggregateHomeScore: int | None = None
    aggregateAwayScore: int | None = None
    winnerParticipantId: int | None = None
    isTwoLegged: bool = False
    legs: list[BracketLegResponse] = Field(default_factory=list)


class BracketRoundResponse(BaseModel):
    id: str
    name: str
    order: int
    ties: list[BracketTieResponse] = Field(default_factory=list)


class CompetitionStageGroupResponse(BaseModel):
    id: str
    name: str
    order: int


class CompetitionStageResponse(BaseModel):
    id: str
    name: str
    stageType: str
    order: int
    roundLabels: list[str] = Field(default_factory=list)
    groups: list[CompetitionStageGroupResponse] = Field(default_factory=list)


class CompetitionDataResponse(BaseModel):
    id: str
    name: str
    fullName: str
    badge: str
    country: str | None = None
    formatKind: str | None = None
    edition: CompetitionEditionLite | None = None
    stages: list[CompetitionStageResponse] = Field(default_factory=list)
    matches: list[MatchResponse] = Field(default_factory=list)


class LastFiveMatchResponse(BaseModel):
    result: str
    match_id: str
    result_code: int


class TeamStandingResponse(BaseModel):
    id: str
    position: int
    name: str
    badge: str
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    goalsFor: int
    goalsAgainst: int
    goalDifference: int
    form: list[LastFiveMatchResponse] = Field(default_factory=list)


class StandingsGroupResponse(BaseModel):
    id: str
    name: str
    order: int
    teams: list[TeamStandingResponse] = Field(default_factory=list)


class CompetitionStandingsSnapshotResponse(BaseModel):
    competitionId: int
    stageId: str
    stageName: str
    stageType: str
    edition: CompetitionEditionLite | None = None
    groups: list[StandingsGroupResponse] = Field(default_factory=list)


class CompetitionStructureResponse(BaseModel):
    competitionId: int
    name: str
    badge: str
    country: str | None = None
    formatKind: str
    edition: CompetitionEditionLite | None = None
    stages: list[CompetitionStageResponse] = Field(default_factory=list)


class PredictionRowResponse(BaseModel):
    id: str
    user_id: str
    match_id: int
    competition_id: int | None = None
    edition_id: int | None = None
    sport_id: int | None = None
    home_score: int
    away_score: int
    points: int | None = None
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PredictionFeedItemResponse(BaseModel):
    id: str
    userId: str
    username: str
    matchId: int
    kickoff: str
    kickoffIso: str | None = None
    matchStatus: str
    homeTeam: str
    awayTeam: str
    predicted: str
    homeScore: int | None = None
    awayScore: int | None = None
    minute: str | None = None
    sportId: int
    sportName: str
    competitionId: int
    competitionName: str
    edition: CompetitionEditionLite | None = None
    points: int | None = None
    createdAt: str


class PredictionUpsertPayload(BaseModel):
    competition_id: int
    sport_id: int
    event_id: int
    home_score: int
    away_score: int


class PredictionUpdatePayload(BaseModel):
    home_score: int
    away_score: int


class TournamentTeamOption(BaseModel):
    id: int
    name: str
    badge: str | None = None
    country: str | None = None


class TournamentGroupOption(BaseModel):
    id: str
    name: str
    order: int
    teams: list[TournamentTeamOption] = Field(default_factory=list)


class TournamentAwardCandidate(BaseModel):
    id: int
    name: str
    teamId: int | None = None
    teamName: str | None = None
    badge: str | None = None
    country: str | None = None


class TournamentScoringRules(BaseModel):
    groupPosition: int = 1
    groupPerfectBonus: int = 3
    qualifiedThird: int = 2
    knockoutByRound: dict[str, int] = Field(
        default_factory=lambda: {
            "round_of_32": 5,
            "round_of_16": 10,
            "quarterfinals": 12,
            "semifinals": 15,
            "third_place": 20,
            "final": 25,
        }
    )
    champion: int = 0
    awards: dict[str, int] = Field(
        default_factory=lambda: {"mvp": 0, "bestGoalkeeper": 0, "topScorer": 0}
    )


class TournamentLocks(BaseModel):
    groupsLocked: bool = False
    awardsLocked: bool = False
    championLocked: bool = False
    lockedEventIds: list[int] = Field(default_factory=list)


class TournamentGroupPrediction(BaseModel):
    groupId: str
    orderedParticipantIds: list[int] = Field(default_factory=list)


class TournamentKnockoutPrediction(BaseModel):
    eventId: int
    homeScore: int
    awayScore: int
    winnerParticipantId: int
    wonOnPenalties: bool = False


class TournamentAwardsPrediction(BaseModel):
    mvpParticipantId: int | None = None
    bestGoalkeeperParticipantId: int | None = None
    topScorerParticipantId: int | None = None


class TournamentPredictionPayload(BaseModel):
    groupPredictions: list[TournamentGroupPrediction] = Field(default_factory=list)
    qualifiedThirdParticipantIds: list[int] = Field(default_factory=list)
    knockoutPredictions: list[TournamentKnockoutPrediction] = Field(default_factory=list)
    awards: TournamentAwardsPrediction = Field(default_factory=TournamentAwardsPrediction)
    championParticipantId: int | None = None


class TournamentPredictionOptionsResponse(BaseModel):
    season: CompetitionEditionLite
    groups: list[TournamentGroupOption] = Field(default_factory=list)
    bracket: list[BracketRoundResponse] = Field(default_factory=list)
    awardCandidates: list[TournamentAwardCandidate] = Field(default_factory=list)
    rules: TournamentScoringRules = Field(default_factory=TournamentScoringRules)
    locks: TournamentLocks = Field(default_factory=TournamentLocks)


class TournamentPredictionResponse(BaseModel):
    id: str | None = None
    user_id: str
    competition_id: int
    edition_id: int
    sport_id: int
    status: str
    payload: TournamentPredictionPayload
    points: int | None = None
    pointsBreakdown: dict[str, int] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    options: TournamentPredictionOptionsResponse
