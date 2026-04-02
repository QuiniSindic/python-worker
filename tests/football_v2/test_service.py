from __future__ import annotations

from unittest import TestCase

from app.domains.football_v2.service import FootballV2Service


class _FakeRepository:
    def list_sports(self) -> list[dict]:
        return [{"id": 1, "slug": "football", "name": "Football"}]

    def list_competitions_by_sport(self, sport_id: int) -> list[dict]:
        return [
            {
                "id": 42,
                "name": "UEFA Champions League",
                "country_code": None,
                "current_season": {
                    "id": 9,
                    "season_key": "2025-2026",
                    "season_label": "2025/26",
                    "is_current": True,
                },
            }
        ]


class _StandingsRepository:
    def get_current_season_by_competition(self, competition_id: int) -> dict:
        return {
            "id": 9,
            "competition_id": competition_id,
            "season_key": "2025-2026",
            "season_label": "2025/26",
            "is_current": True,
        }

    def list_phases_for_season(self, season_id: int) -> list[dict]:
        return [
            {
                "id": 1,
                "key": "group_stage",
                "name": "Fase de grupos",
                "phase_type": "group_stage",
                "is_standings_phase": True,
            }
        ]

    def list_groups_for_phase_ids(self, phase_ids: list[int]) -> list[dict]:
        return [
            {
                "id": 10,
                "competition_phase_id": 1,
                "key": "group_a",
                "name": "Grupo A",
                "order_index": 0,
            },
            {
                "id": 11,
                "competition_phase_id": 1,
                "key": "group_b",
                "name": "Grupo B",
                "order_index": 1,
            },
        ]

    def list_standings_rows(
        self,
        season_id: int,
        phase_id: int | None = None,
        group_id: int | None = None,
    ) -> list[dict]:
        rows = [
            {
                "participant_id": 100,
                "phase_group_id": 10,
                "position": 1,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "form": [],
            },
            {
                "participant_id": 101,
                "phase_group_id": 11,
                "position": 1,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "form": [],
            },
        ]
        if group_id is None:
            return rows
        return [row for row in rows if row["phase_group_id"] == group_id]

    def list_participants(self, participant_ids: list[int]) -> list[dict]:
        return [
            {"id": 100, "name": "Czechia", "badge_url": "czechia.png"},
            {"id": 101, "name": "Mexico", "badge_url": "mexico.png"},
        ]


class _BracketFallbackRepository:
    def get_season(self, season_id: int) -> dict:
        return {
            "id": season_id,
            "competition_id": 138,
            "season_key": "2025-2026",
            "season_label": "2025/26",
            "is_current": True,
        }

    def list_phases_for_season(self, season_id: int) -> list[dict]:
        return []

    def list_events_for_seasons(
        self,
        season_ids: list[int],
        bucket: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        if bucket == "results":
            return []
        return [
            {
                "id": 501,
                "sport_id": 1,
                "competition_id": 138,
                "competition_season_id": season_ids[0],
                "competition_phase_id": None,
                "start_at": "2026-04-01T20:00:00+00:00",
                "status": "scheduled",
            }
        ]

    def list_football_event_rows(self, event_ids: list[int]) -> list[dict]:
        return [
            {
                "event_id": 501,
                "round_key": "final",
                "round_label": "Final",
                "leg": None,
                "home_score": None,
                "away_score": None,
                "minute": None,
                "timeline": [],
            }
        ]

    def list_event_participants(self, event_ids: list[int]) -> list[dict]:
        return [
            {
                "event_id": 501,
                "slot_key": "home",
                "participant_id": None,
                "placeholder_label": "Team A",
            },
            {
                "event_id": 501,
                "slot_key": "away",
                "participant_id": None,
                "placeholder_label": "Team B",
            },
        ]

    def list_participants(self, participant_ids: list[int]) -> list[dict]:
        return []

    def list_competitions(self, competition_ids: list[int]) -> list[dict]:
        return [
            {
                "id": 138,
                "name": "Copa del Rey",
                "country_code": "ES",
                "provider_competition_id": "138",
            }
        ]

    def list_seasons(self, season_ids: list[int]) -> list[dict]:
        return [
            {
                "id": season_ids[0],
                "season_key": "2025-2026",
                "season_label": "2025/26",
                "is_current": True,
            }
        ]


class FootballV2ServiceTests(TestCase):
    def test_get_sports_maps_display_name(self) -> None:
        service = FootballV2Service(repository=_FakeRepository())  # type: ignore[arg-type]

        sports = service.get_sports()

        self.assertEqual(len(sports), 1)
        self.assertEqual(sports[0].displayName, "Football")

    def test_get_competitions_maps_current_edition(self) -> None:
        service = FootballV2Service(repository=_FakeRepository())  # type: ignore[arg-type]

        competitions = service.get_competitions(1)

        self.assertEqual(len(competitions), 1)
        self.assertEqual(competitions[0].current_edition.season_key, "2025-2026")

    def test_get_standings_returns_all_groups_when_no_group_filter(self) -> None:
        service = FootballV2Service(repository=_StandingsRepository())  # type: ignore[arg-type]

        snapshot = service.get_standings(77)

        self.assertEqual(len(snapshot.groups), 2)
        self.assertEqual(snapshot.groups[0].id, "group_a")
        self.assertEqual(snapshot.groups[1].id, "group_b")

    def test_get_bracket_falls_back_to_round_labeled_events(self) -> None:
        service = FootballV2Service(repository=_BracketFallbackRepository())  # type: ignore[arg-type]

        bracket = service.get_bracket(9)

        self.assertEqual(len(bracket), 1)
        self.assertEqual(bracket[0].id, "final")
        self.assertEqual(len(bracket[0].ties), 1)
        self.assertEqual(bracket[0].ties[0].roundName, "Final")
        self.assertEqual(bracket[0].ties[0].legs[0].eventId, 501)

    def test_get_bracket_groups_two_legs_into_one_tie(self) -> None:
        class _TwoLegRepository(_BracketFallbackRepository):
            def list_phases_for_season(self, season_id: int) -> list[dict]:
                return [
                    {
                        "id": 21,
                        "key": "round_of_16",
                        "name": "Octavos",
                        "phase_type": "knockout_round",
                        "is_bracket_phase": True,
                        "order_index": 20,
                    }
                ]

            def list_events_for_seasons(
                self,
                season_ids: list[int],
                bucket: str,
                from_date: str | None = None,
                to_date: str | None = None,
            ) -> list[dict]:
                if bucket == "results":
                    return [
                        {
                            "id": 502,
                            "sport_id": 1,
                            "competition_id": 138,
                            "competition_season_id": season_ids[0],
                            "competition_phase_id": 21,
                            "start_at": "2026-02-01T20:00:00+00:00",
                            "status": "finished",
                        },
                        {
                            "id": 503,
                            "sport_id": 1,
                            "competition_id": 138,
                            "competition_season_id": season_ids[0],
                            "competition_phase_id": 21,
                            "start_at": "2026-02-08T20:00:00+00:00",
                            "status": "finished",
                        },
                    ]
                return []

            def list_football_event_rows(self, event_ids: list[int]) -> list[dict]:
                return [
                    {
                        "event_id": 502,
                        "round_key": "round_of_16",
                        "round_label": "1/8",
                        "leg": 1,
                        "home_score": 1,
                        "away_score": 0,
                        "minute": None,
                        "timeline": [],
                    },
                    {
                        "event_id": 503,
                        "round_key": "round_of_16",
                        "round_label": "1/8",
                        "leg": 2,
                        "home_score": 2,
                        "away_score": 0,
                        "minute": None,
                        "timeline": [],
                    },
                ]

            def list_event_participants(self, event_ids: list[int]) -> list[dict]:
                return [
                    {
                        "event_id": 502,
                        "slot_key": "home",
                        "participant_id": 1,
                        "placeholder_label": None,
                    },
                    {
                        "event_id": 502,
                        "slot_key": "away",
                        "participant_id": 2,
                        "placeholder_label": None,
                    },
                    {
                        "event_id": 503,
                        "slot_key": "home",
                        "participant_id": 2,
                        "placeholder_label": None,
                    },
                    {
                        "event_id": 503,
                        "slot_key": "away",
                        "participant_id": 1,
                        "placeholder_label": None,
                    },
                ]

            def list_participants(self, participant_ids: list[int]) -> list[dict]:
                return [
                    {
                        "id": 1,
                        "name": "Team A",
                        "code": "A",
                        "badge_url": None,
                        "country_code": "ES",
                    },
                    {
                        "id": 2,
                        "name": "Team B",
                        "code": "B",
                        "badge_url": None,
                        "country_code": "IT",
                    },
                ]

        service = FootballV2Service(repository=_TwoLegRepository())  # type: ignore[arg-type]

        bracket = service.get_bracket(9)

        self.assertEqual(len(bracket), 1)
        self.assertEqual(len(bracket[0].ties), 1)
        self.assertTrue(bracket[0].ties[0].isTwoLegged)
        self.assertEqual(bracket[0].ties[0].aggregateHomeScore, 1)
        self.assertEqual(bracket[0].ties[0].aggregateAwayScore, 2)
        self.assertEqual(len(bracket[0].ties[0].legs), 2)
