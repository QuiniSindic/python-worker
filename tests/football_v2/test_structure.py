from __future__ import annotations

from unittest import TestCase

from app.domains.football_v2.competition_structure_service import (
    FootballCompetitionStructureService,
    get_knockout_round_meta,
)
from app.schemas.football import CompetitionStandingsSnapshotResponse, StandingsGroupResponse


class FootballV2StructureServiceTests(TestCase):
    def test_get_knockout_round_meta_matches_round_of_32(self) -> None:
        meta = get_knockout_round_meta("Round of 32")

        self.assertIsNotNone(meta)
        self.assertEqual(meta.id, "round_of_32")
        self.assertEqual(meta.name, "Dieciseisavos")

    def test_build_stages_combines_standings_and_knockout_rounds(self) -> None:
        service = FootballCompetitionStructureService()
        standings = CompetitionStandingsSnapshotResponse(
            competitionId=78,
            stageId="group_stage",
            stageName="Fase de grupos",
            stageType="group",
            groups=[
                StandingsGroupResponse(id="group_a", name="Grupo A", order=0, teams=[]),
                StandingsGroupResponse(id="group_b", name="Grupo B", order=1, teams=[]),
            ],
        )

        stages = service.build_stages(
            78,
            [{"round": "Round of 16"}, {"round": "Semi-finals"}],
            standings,
        )

        self.assertEqual(
            [stage.id for stage in stages],
            ["group_stage", "round_of_16", "semifinals"],
        )
        self.assertEqual(stages[0].groups[0].id, "group_a")
