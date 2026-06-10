from __future__ import annotations

from datetime import date
from unittest import TestCase

from app.domains.football_v2.season import SeasonRule, resolve_current_season


class ResolveCurrentSeasonTests(TestCase):
    def test_split_year_uses_previous_year_before_start_month(self) -> None:
        season = resolve_current_season(
            SeasonRule(season_type="split_year", season_start_month=7),
            reference_at=date(2026, 4, 2),
        )

        self.assertEqual(season.season_key, "2025-2026")
        self.assertEqual(season.season_label, "2025/26")

    def test_calendar_year_uses_same_year(self) -> None:
        season = resolve_current_season(
            SeasonRule(season_type="calendar_year", season_start_month=1),
            reference_at=date(2026, 8, 15),
        )

        self.assertEqual(season.season_key, "2026")
        self.assertEqual(season.season_label, "2026")
