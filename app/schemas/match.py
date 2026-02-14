from enum import IntEnum, Enum
from typing import List, Optional, Union
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
    img: Optional[str] = None
    country: str

class MatchEvent(BaseModel):
    type: MatchEventType
    minute: Optional[Union[int, str]] = None
    extraMinute: Optional[int] = None
    team: Optional[int] = None
    playerName: Optional[str] = None
    score: Optional[str] = None
    extra: Optional[str] = None

class Odds(BaseModel):
    id: str
    matchId: int
    homeOdd: float
    awayOdd: float
    drawOdd: float

# Validamos que el status sea uno de los permitidos
class MatchStatus(str, Enum):
    NS = 'NS'
    HT = 'HT'
    FT = 'FT'
    OT = 'OT'
    AET = 'AET'
    AP = 'AP'
    CANC = 'Canc.'
    LIVE = 'LIVE' # Añado LIVE por si acaso

class MatchData(BaseModel):
    id: int # En TS es number
    status: MatchStatus
    result: str
    kickoff: str
    kickoff_iso: Optional[str] = None
    minute: Optional[str] = None
    round: Optional[str] = None
    events: List[MatchEvent] = []
    homeId: int
    awayId: int
    competitionid: int
    homeTeam: TeamInfo
    awayTeam: TeamInfo
    country: str
    Odds: Optional[Odds] = None

class CompetitionData(BaseModel):
    id: str
    name: str
    fullName: str
    badge: str
    matches: List[MatchData] = []

    class Config:
        # Buena práctica: permite popular el modelo desde objetos ORM en el futuro
        from_attributes = True