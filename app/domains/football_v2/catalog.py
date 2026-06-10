from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SeasonType = Literal["split_year", "calendar_year"]
FormatKind = Literal[
    "league",
    "knockout",
    "groups_knockout",
    "league_phase_knockout",
]
CompetitionKind = Literal["league", "cup", "team_tournament"]
ParticipantScope = Literal["club", "national_team"]


@dataclass(frozen=True)
class FootballCompetitionDefinition:
    fotmob_id: int
    slug: str
    name: str
    short_name: str
    country_code: str | None
    competition_kind: CompetitionKind
    participant_scope: ParticipantScope
    season_type: SeasonType
    format_kind: FormatKind
    season_start_month: int = 7


FOOTBALL_COMPETITIONS: tuple[FootballCompetitionDefinition, ...] = (
    FootballCompetitionDefinition(
        54, "bundesliga", "Bundesliga", "Bundesliga", "DE", "league", "club", "split_year", "league"
    ),
    FootballCompetitionDefinition(
        209, "dfb-pokal", "DFB Pokal", "DFB Pokal", "DE", "cup", "club", "split_year", "knockout"
    ),
    FootballCompetitionDefinition(
        8924,
        "dfl-supercup",
        "DFL Supercup",
        "Supercup",
        "DE",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        87, "laliga", "LaLiga", "LaLiga", "ES", "league", "club", "split_year", "league"
    ),
    FootballCompetitionDefinition(
        138,
        "copa-del-rey",
        "Copa del Rey",
        "Copa del Rey",
        "ES",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        139,
        "supercopa-de-espana",
        "Supercopa de Espana",
        "Supercopa",
        "ES",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        53, "ligue-1", "Ligue 1", "Ligue 1", "FR", "league", "club", "split_year", "league"
    ),
    FootballCompetitionDefinition(
        134,
        "coupe-de-france",
        "Coupe de France",
        "Coupe de France",
        "FR",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        207,
        "trophee-des-champions",
        "Trophee des Champions",
        "Trophee des Champions",
        "FR",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        47,
        "premier-league",
        "Premier League",
        "Premier League",
        "GB",
        "league",
        "club",
        "split_year",
        "league",
    ),
    FootballCompetitionDefinition(
        132, "fa-cup", "FA Cup", "FA Cup", "GB", "cup", "club", "split_year", "knockout"
    ),
    FootballCompetitionDefinition(
        133, "efl-cup", "EFL Cup", "EFL Cup", "GB", "cup", "club", "split_year", "knockout"
    ),
    FootballCompetitionDefinition(
        247,
        "community-shield",
        "Community Shield",
        "Community Shield",
        "GB",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        55, "serie-a", "Serie A", "Serie A", "IT", "league", "club", "split_year", "league"
    ),
    FootballCompetitionDefinition(
        141,
        "coppa-italia",
        "Coppa Italia",
        "Coppa Italia",
        "IT",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        222,
        "supercoppa-italiana",
        "Supercoppa Italiana",
        "Supercoppa",
        "IT",
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        42,
        "uefa-champions-league",
        "UEFA Champions League",
        "Champions League",
        None,
        "team_tournament",
        "club",
        "split_year",
        "league_phase_knockout",
    ),
    FootballCompetitionDefinition(
        73,
        "uefa-europa-league",
        "UEFA Europa League",
        "Europa League",
        None,
        "team_tournament",
        "club",
        "split_year",
        "league_phase_knockout",
    ),
    FootballCompetitionDefinition(
        10216,
        "uefa-conference-league",
        "UEFA Conference League",
        "Conference League",
        None,
        "team_tournament",
        "club",
        "split_year",
        "league_phase_knockout",
    ),
    FootballCompetitionDefinition(
        74,
        "uefa-super-cup",
        "UEFA Super Cup",
        "UEFA Super Cup",
        None,
        "cup",
        "club",
        "split_year",
        "knockout",
    ),
    FootballCompetitionDefinition(
        50,
        "uefa-euro",
        "UEFA Euro",
        "Euro",
        None,
        "team_tournament",
        "national_team",
        "calendar_year",
        "groups_knockout",
        1,
    ),
    FootballCompetitionDefinition(
        9806,
        "uefa-nations-league-a",
        "UEFA Nations League A",
        "Nations League",
        None,
        "team_tournament",
        "national_team",
        "calendar_year",
        "groups_knockout",
        1,
    ),
    FootballCompetitionDefinition(
        45,
        "copa-libertadores",
        "Copa Libertadores",
        "Libertadores",
        None,
        "team_tournament",
        "club",
        "calendar_year",
        "groups_knockout",
        1,
    ),
    FootballCompetitionDefinition(
        44,
        "copa-america",
        "Copa America",
        "Copa America",
        None,
        "team_tournament",
        "national_team",
        "calendar_year",
        "groups_knockout",
        1,
    ),
    FootballCompetitionDefinition(
        78,
        "fifa-club-world-cup",
        "FIFA Club World Cup",
        "Club World Cup",
        None,
        "team_tournament",
        "club",
        "calendar_year",
        "groups_knockout",
        1,
    ),
    FootballCompetitionDefinition(
        10703,
        "fifa-intercontinental-cup",
        "FIFA Intercontinental Cup",
        "Intercontinental Cup",
        None,
        "cup",
        "club",
        "calendar_year",
        "knockout",
        1,
    ),
    FootballCompetitionDefinition(
        10304,
        "finalissima",
        "Finalissima",
        "Finalissima",
        None,
        "cup",
        "national_team",
        "calendar_year",
        "knockout",
        1,
    ),
    FootballCompetitionDefinition(
        66,
        "olympic-football-men",
        "Olympic Football Men",
        "Olympic Football",
        None,
        "team_tournament",
        "national_team",
        "calendar_year",
        "groups_knockout",
        1,
    ),
    FootballCompetitionDefinition(
        77,
        "fifa-world-cup",
        "FIFA World Cup",
        "World Cup",
        None,
        "team_tournament",
        "national_team",
        "calendar_year",
        "groups_knockout",
        1,
    ),
)

COMPETITIONS_BY_FOTMOB_ID = {item.fotmob_id: item for item in FOOTBALL_COMPETITIONS}
