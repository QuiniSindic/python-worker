from __future__ import annotations

from unittest import TestCase

from app.domains.football_v2.pickem_scoring import (
    DEFAULT_PICKEM_SCORING_CONFIG,
    score_award_pick,
    score_group_order_pick,
    score_match_pick,
)


class PickemScoringTests(TestCase):
    def test_group_order_scores_exact_positions_and_perfect_bonus(self) -> None:
        score = score_group_order_pick([10, 20, 30, 40], {10: 1, 20: 2, 30: 3, 40: 4})

        self.assertEqual(score.total_points, 7)
        self.assertTrue(score.is_perfect_group)
        self.assertEqual(score.points_by_participant_id[10], 1)

    def test_group_order_scores_partial_hits_without_bonus(self) -> None:
        score = score_group_order_pick([20, 10, 30, 40], {10: 1, 20: 2, 30: 4, 40: 3})

        self.assertEqual(score.total_points, 0)
        self.assertFalse(score.is_perfect_group)

    def test_match_pick_scores_winner_and_exact_score_bonus(self) -> None:
        config = DEFAULT_PICKEM_SCORING_CONFIG
        score = score_match_pick(
            predicted_winner_id=1,
            actual_winner_id=1,
            round_key="round_of_32",
            predicted_home_score=2,
            predicted_away_score=1,
            actual_home_score=2,
            actual_away_score=1,
            winner_points_by_round=config["knockout_winner_points"],
            exact_score_bonus=config["exact_score_bonus"],
        )

        self.assertEqual(score.points, 5)
        self.assertEqual(score.winner_points, 3)
        self.assertEqual(score.exact_score_points, 2)
        self.assertTrue(score.is_exact_score)

    def test_match_pick_does_not_award_exact_score_without_winner(self) -> None:
        config = DEFAULT_PICKEM_SCORING_CONFIG
        score = score_match_pick(
            predicted_winner_id=2,
            actual_winner_id=1,
            round_key="final",
            predicted_home_score=1,
            predicted_away_score=1,
            actual_home_score=1,
            actual_away_score=1,
            winner_points_by_round=config["knockout_winner_points"],
            exact_score_bonus=config["exact_score_bonus"],
        )

        self.assertEqual(score.points, 0)
        self.assertFalse(score.is_exact_score)

    def test_award_pick_scores_champion_by_participant(self) -> None:
        points, is_hit = score_award_pick(
            award_key="champion",
            candidate_id=None,
            participant_id=77,
            result_candidate_id=None,
            result_participant_id=77,
            award_points=DEFAULT_PICKEM_SCORING_CONFIG["award_points"],
        )

        self.assertEqual(points, 20)
        self.assertTrue(is_hit)
