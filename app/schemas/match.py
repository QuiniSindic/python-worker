from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field


# Usamos IntEnum para que al serializar a JSON salga el número, igual que en TS
class MatchEventType(IntEnum):
    Goal = 36
    FailedPenalty = 40
    PenaltyGoal = 41
    YellowCard = 43
    RedCard = 45
    HalfTime = 46
    FinalTime = 47
    Overtime = 48
    None_ = 0


class TeamInfo(BaseModel):
    id: int
    name: str
    abbr: str
    img: str | None = None
    country: str


class MatchEvent(BaseModel):
    type: MatchEventType
    minute: int | str | None = None
    extraMinute: int | None = None
    team: int | None = None
    playerName: str | None = None
    score: str | None = None
    extra: str | None = None


class Odds(BaseModel):
    id: str
    matchId: int
    homeOdd: float
    awayOdd: float
    drawOdd: float


# Validamos que el status sea uno de los permitidos
class MatchStatus(StrEnum):
    NS = "NS"
    HT = "HT"
    FT = "FT"
    OT = "OT"
    AET = "AET"
    AP = "AP"
    CANC = "Canc."
    LIVE = "LIVE"  # Añado LIVE por si acaso


class MatchData(BaseModel):
    id: int  # En TS es number
    status: MatchStatus
    result: str
    kickoff: str
    kickoff_iso: str | None = None
    minute: str | None = None
    round: str | None = None
    events: list[MatchEvent] = []
    homeId: int
    awayId: int
    competitionid: int
    homeTeam: TeamInfo
    awayTeam: TeamInfo
    country: str
    odds: Odds | None = Field(default=None, alias="Odds")

    model_config = {"populate_by_name": True}


class CompetitionData(BaseModel):
    id: str
    name: str
    fullName: str
    badge: str
    matches: list[MatchData] = []

    class Config:
        # Buena práctica: permite popular el modelo desde objetos ORM en el futuro
        from_attributes = True
