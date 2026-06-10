from __future__ import annotations

from app.domains.football_v2.pickem_repository import PickemRepository
from app.domains.football_v2.pickem_scoring import DEFAULT_PICKEM_SCORING_CONFIG


class PickemBootstrapService:
    def __init__(self, repository: PickemRepository | None = None) -> None:
        self.repository = repository or PickemRepository()

    def ensure_world_cup_contest(self, season_row: dict) -> dict | None:
        first_match_start_at = self.repository.get_first_match_start_at(season_row["id"])
        if not first_match_start_at:
            return None

        return self.repository.upsert_contest(
            {
                "competition_season_id": season_row["id"],
                "slug": "fifa-world-cup-2026",
                "name": "Pick'em Mundial 2026",
                "group_deadline": first_match_start_at,
                "awards_deadline": first_match_start_at,
                "scoring_config": DEFAULT_PICKEM_SCORING_CONFIG,
                "is_active": True,
            }
        )
