from __future__ import annotations

from unittest import TestCase

from app.domains.football_v2.pickem_scoring import DEFAULT_PICKEM_SCORING_CONFIG
from app.domains.football_v2.pickem_service import PickemService


class _GroupScoringRepository:
    def __init__(self, matches: list[dict]) -> None:
        self.matches = matches
        self.updated_group_scores: list[dict] = []

    def list_group_picks(self, entry_id: str) -> list[dict]:
        return [
            {
                "id": "pick-1",
                "phase_group_id": 10,
                "participant_id": 100,
                "predicted_position": 1,
            },
            {
                "id": "pick-2",
                "phase_group_id": 10,
                "participant_id": 101,
                "predicted_position": 2,
            },
            {
                "id": "pick-3",
                "phase_group_id": 10,
                "participant_id": 102,
                "predicted_position": 3,
            },
            {
                "id": "pick-4",
                "phase_group_id": 10,
                "participant_id": 103,
                "predicted_position": 4,
            },
        ]

    def list_group_matches(self, season_id: int, group_id: int) -> list[dict]:
        return self.matches

    def update_group_pick_scores(self, updates: list[dict]) -> None:
        self.updated_group_scores = updates


def _standings_rows() -> dict[int, list[dict]]:
    return {
        10: [
            {"phase_group_id": 10, "participant_id": 100, "position": 1},
            {"phase_group_id": 10, "participant_id": 101, "position": 2},
            {"phase_group_id": 10, "participant_id": 102, "position": 3},
            {"phase_group_id": 10, "participant_id": 103, "position": 4},
        ]
    }


class PickemServiceScoringTests(TestCase):
    def test_group_scoring_waits_until_all_group_matches_are_finished(self) -> None:
        repository = _GroupScoringRepository(
            matches=[
                {"id": 1, "status": "scheduled"},
                {"id": 2, "status": "scheduled"},
                {"id": 3, "status": "scheduled"},
                {"id": 4, "status": "scheduled"},
                {"id": 5, "status": "scheduled"},
                {"id": 6, "status": "scheduled"},
            ]
        )
        service = PickemService(repository=repository)

        points, perfect_groups = service._score_entry_groups(
            "entry-1",
            1,
            _standings_rows(),
            DEFAULT_PICKEM_SCORING_CONFIG,
        )

        self.assertEqual(points, 0)
        self.assertEqual(perfect_groups, 0)
        self.assertEqual(
            repository.updated_group_scores,
            [
                {"id": "pick-1", "points": 0, "is_exact": False},
                {"id": "pick-2", "points": 0, "is_exact": False},
                {"id": "pick-3", "points": 0, "is_exact": False},
                {"id": "pick-4", "points": 0, "is_exact": False},
            ],
        )

    def test_group_scoring_uses_standings_after_all_group_matches_are_finished(self) -> None:
        repository = _GroupScoringRepository(
            matches=[
                {"id": 1, "status": "finished"},
                {"id": 2, "status": "finished"},
                {"id": 3, "status": "finished"},
                {"id": 4, "status": "finished"},
                {"id": 5, "status": "finished"},
                {"id": 6, "status": "finished"},
            ]
        )
        service = PickemService(repository=repository)

        points, perfect_groups = service._score_entry_groups(
            "entry-1",
            1,
            _standings_rows(),
            DEFAULT_PICKEM_SCORING_CONFIG,
        )

        self.assertEqual(points, 7)
        self.assertEqual(perfect_groups, 1)
        self.assertEqual(
            [update["points"] for update in repository.updated_group_scores],
            [1, 1, 1, 1],
        )
