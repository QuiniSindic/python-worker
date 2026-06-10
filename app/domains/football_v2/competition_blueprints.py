from __future__ import annotations

from dataclasses import dataclass

from app.domains.football_v2.season import SeasonRule


@dataclass(frozen=True)
class FootballCompetitionBlueprint:
    format_kind: str
    standings_stage_id: str | None
    standings_stage_name: str | None
    standings_stage_type: str | None
    season_rule: SeasonRule


DEFAULT_BLUEPRINT = FootballCompetitionBlueprint(
    format_kind="league",
    standings_stage_id="league_table",
    standings_stage_name="Clasificacion",
    standings_stage_type="league_table",
    season_rule=SeasonRule(season_type="split_year", season_start_month=7),
)

KNOCKOUT_BLUEPRINT = FootballCompetitionBlueprint(
    format_kind="knockout",
    standings_stage_id=None,
    standings_stage_name=None,
    standings_stage_type=None,
    season_rule=SeasonRule(season_type="split_year", season_start_month=7),
)

GROUPS_KNOCKOUT_BLUEPRINT = FootballCompetitionBlueprint(
    format_kind="groups_knockout",
    standings_stage_id="group_stage",
    standings_stage_name="Fase de grupos",
    standings_stage_type="group",
    season_rule=SeasonRule(season_type="calendar_year", season_start_month=1),
)

LEAGUE_PHASE_KNOCKOUT_BLUEPRINT = FootballCompetitionBlueprint(
    format_kind="league_phase_knockout",
    standings_stage_id="league_phase",
    standings_stage_name="League phase",
    standings_stage_type="league_table",
    season_rule=SeasonRule(season_type="split_year", season_start_month=7),
)


BLUEPRINTS_BY_COMPETITION_ID: dict[int, FootballCompetitionBlueprint] = {
    42: LEAGUE_PHASE_KNOCKOUT_BLUEPRINT,
    44: GROUPS_KNOCKOUT_BLUEPRINT,
    45: GROUPS_KNOCKOUT_BLUEPRINT,
    50: GROUPS_KNOCKOUT_BLUEPRINT,
    73: LEAGUE_PHASE_KNOCKOUT_BLUEPRINT,
    77: GROUPS_KNOCKOUT_BLUEPRINT,
    78: GROUPS_KNOCKOUT_BLUEPRINT,
    132: KNOCKOUT_BLUEPRINT,
    133: KNOCKOUT_BLUEPRINT,
    134: KNOCKOUT_BLUEPRINT,
    138: KNOCKOUT_BLUEPRINT,
    141: KNOCKOUT_BLUEPRINT,
    209: KNOCKOUT_BLUEPRINT,
    10216: LEAGUE_PHASE_KNOCKOUT_BLUEPRINT,
}


def get_competition_blueprint(competition_id: int | None) -> FootballCompetitionBlueprint:
    if competition_id is None:
        return DEFAULT_BLUEPRINT
    return BLUEPRINTS_BY_COMPETITION_ID.get(int(competition_id), DEFAULT_BLUEPRINT)
