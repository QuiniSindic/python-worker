from __future__ import annotations

from unittest import TestCase

from fastapi import HTTPException

from app.domains.football_v2.service import FootballV2Service
from app.schemas.auth import AuthenticatedUser
from app.schemas.football import TournamentPredictionPayload


class _FakeRepository:
    def __init__(self) -> None:
        self.last_limit: int | None = None

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

    def list_events_for_seasons(
        self,
        season_ids: list[int],
        bucket: str,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        self.last_limit = limit
        if bucket == "results":
            return [
                {
                    "id": 2,
                    "sport_id": 1,
                    "competition_id": 55,
                    "competition_season_id": 12,
                    "start_at": "2026-04-03T20:00:00+00:00",
                    "status": "finished",
                },
                {
                    "id": 1,
                    "sport_id": 1,
                    "competition_id": 42,
                    "competition_season_id": 11,
                    "start_at": "2026-04-02T20:00:00+00:00",
                    "status": "finished",
                },
            ]

        return [
            {
                "id": 1,
                "sport_id": 1,
                "competition_id": 42,
                "competition_season_id": 11,
                "start_at": "2026-04-05T20:00:00+00:00",
                "status": "scheduled",
            },
            {
                "id": 2,
                "sport_id": 1,
                "competition_id": 55,
                "competition_season_id": 12,
                "start_at": "2026-04-04T20:00:00+00:00",
                "status": "scheduled",
            },
        ]

    def list_football_event_rows(self, event_ids: list[int]) -> list[dict]:
        return [
            {
                "event_id": event_id,
                "round_key": None,
                "round_label": None,
                "leg": None,
                "home_score": None,
                "away_score": None,
                "minute": None,
                "timeline": [],
            }
            for event_id in event_ids
        ]

    def list_event_participants(self, event_ids: list[int]) -> list[dict]:
        rows: list[dict] = []
        for event_id in event_ids:
            rows.extend(
                [
                    {
                        "event_id": event_id,
                        "slot_key": "home",
                        "participant_id": 100 + event_id,
                        "placeholder_label": None,
                    },
                    {
                        "event_id": event_id,
                        "slot_key": "away",
                        "participant_id": 200 + event_id,
                        "placeholder_label": None,
                    },
                ]
            )
        return rows

    def list_participants(self, participant_ids: list[int]) -> list[dict]:
        return [
            {
                "id": participant_id,
                "name": f"Team {participant_id}",
                "badge_url": None,
                "code": None,
                "country_code": "ES",
            }
            for participant_id in participant_ids
        ]

    def list_competitions(self, competition_ids: list[int]) -> list[dict]:
        base = {
            42: {
                "id": 42,
                "name": "UEFA Champions League",
                "country_code": None,
                "provider_competition_id": "42",
            },
            55: {
                "id": 55,
                "name": "Serie A",
                "country_code": "IT",
                "provider_competition_id": "55",
            },
        }
        return [base[item] for item in competition_ids if item in base]

    def list_current_seasons(self, competition_ids: list[int] | None = None) -> list[dict]:
        rows = [
            {
                "id": 11,
                "competition_id": 42,
                "season_key": "2025-2026",
                "season_label": "2025/26",
                "is_current": True,
                "format_kind": "league_phase_knockout",
            },
            {
                "id": 12,
                "competition_id": 55,
                "season_key": "2025-2026",
                "season_label": "2025/26",
                "is_current": True,
                "format_kind": "league",
            },
        ]
        if competition_ids is None:
            return rows
        return [row for row in rows if row["competition_id"] in competition_ids]

    def get_current_season_by_competition(self, competition_id: int) -> dict | None:
        rows = self.list_current_seasons([competition_id])
        return rows[0] if rows else None

    def list_seasons(self, season_ids: list[int]) -> list[dict]:
        return [row for row in self.list_current_seasons() if row["id"] in season_ids]


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


class _TournamentRepository:
    def __init__(self) -> None:
        self.saved_payload: dict | None = None

    def get_season(self, season_id: int) -> dict:
        return {
            "id": season_id,
            "competition_id": 77,
            "season_key": "2026",
            "season_label": "2026",
            "is_current": True,
            "format_kind": "groups_knockout",
        }

    def get_competition(self, competition_id: int) -> dict:
        return {
            "id": competition_id,
            "sport_id": 1,
            "name": "FIFA World Cup",
            "country_code": None,
            "provider_competition_id": "77",
        }

    def list_phases_for_season(self, season_id: int) -> list[dict]:
        return [
            {
                "id": 1,
                "key": "group_stage",
                "name": "Fase de grupos",
                "phase_type": "group_stage",
                "is_standings_phase": True,
                "is_bracket_phase": False,
                "order_index": 0,
            },
            {
                "id": 2,
                "key": "round_of_16",
                "name": "Octavos",
                "phase_type": "knockout_round",
                "is_standings_phase": False,
                "is_bracket_phase": True,
                "order_index": 20,
            },
        ]

    def list_groups_for_phase_ids(self, phase_ids: list[int]) -> list[dict]:
        if 1 not in phase_ids:
            return []
        return [
            {
                "id": 10,
                "competition_phase_id": 1,
                "key": "group_a",
                "name": "Grupo A",
                "order_index": 0,
            }
        ]

    def list_standings_rows(
        self,
        season_id: int,
        phase_id: int | None = None,
        group_id: int | None = None,
    ) -> list[dict]:
        return [
            {
                "participant_id": 1,
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
                "participant_id": 2,
                "phase_group_id": 10,
                "position": 2,
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
                "participant_id": 3,
                "phase_group_id": 10,
                "position": 3,
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

    def list_participants(self, participant_ids: list[int]) -> list[dict]:
        rows = {
            1: {"id": 1, "kind": "team", "name": "Spain", "badge_url": None, "country_code": "ES"},
            2: {"id": 2, "kind": "team", "name": "France", "badge_url": None, "country_code": "FR"},
            3: {"id": 3, "kind": "team", "name": "Brazil", "badge_url": None, "country_code": "BR"},
            101: {
                "id": 101,
                "kind": "player",
                "name": "Player One",
                "badge_url": None,
                "country_code": "ES",
            },
        }
        return [rows[item] for item in participant_ids if item in rows]

    def list_events_for_seasons(
        self,
        season_ids: list[int],
        bucket: str,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        if bucket == "results":
            return []
        return [
            {
                "id": 900,
                "sport_id": 1,
                "competition_id": 77,
                "competition_season_id": season_ids[0],
                "competition_phase_id": 2,
                "start_at": "2099-07-01T20:00:00+00:00",
                "status": "scheduled",
            }
        ]

    def list_football_event_rows(self, event_ids: list[int]) -> list[dict]:
        return [
            {
                "event_id": 900,
                "round_key": "round_of_16",
                "round_label": "Octavos",
                "leg": None,
                "home_score": None,
                "away_score": None,
                "minute": None,
                "timeline": [],
            }
        ]

    def list_event_participants(self, event_ids: list[int]) -> list[dict]:
        return [
            {"event_id": 900, "slot_key": "home", "participant_id": 1, "placeholder_label": None},
            {"event_id": 900, "slot_key": "away", "participant_id": 2, "placeholder_label": None},
        ]

    def list_season_participants(self, season_id: int) -> list[dict]:
        return [{"participant_id": 1}, {"participant_id": 2}, {"participant_id": 3}]

    def list_participant_members(self, parent_participant_ids: list[int]) -> list[dict]:
        return [{"parent_participant_id": 1, "member_participant_id": 101}]

    def get_tournament_prediction_rules(self, season_id: int) -> dict | None:
        return None

    def get_tournament_prediction(self, season_id: int, user_id: str) -> dict | None:
        return None

    def upsert_tournament_prediction(
        self,
        *,
        user_id: str,
        sport_id: int,
        competition_id: int,
        season_id: int,
        payload: dict,
        prediction_id: str | None = None,
    ) -> dict:
        self.saved_payload = payload
        return {
            "id": "tp-1",
            "user_id": user_id,
            "sport_id": sport_id,
            "competition_id": competition_id,
            "competition_season_id": season_id,
            "status": "open",
            "payload": payload,
            "points": None,
            "points_breakdown": {},
            "created_at": "2026-05-10T10:00:00+00:00",
            "updated_at": "2026-05-10T10:00:00+00:00",
        }

    def get_tournament_results(self, season_id: int) -> dict | None:
        return None


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

    def test_get_event_feed_orders_competitions_by_temporal_proximity(self) -> None:
        repository = _FakeRepository()
        service = FootballV2Service(repository=repository)  # type: ignore[arg-type]

        live_feed = service.get_event_feed(bucket="live")
        results_feed = service.get_event_feed(bucket="results")

        self.assertEqual([item.name for item in live_feed], ["Serie A", "UEFA Champions League"])
        self.assertEqual(
            [item.name for item in results_feed],
            ["Serie A", "UEFA Champions League"],
        )
        self.assertEqual(repository.last_limit, 30)

    def test_get_event_feed_uses_competition_default_limit(self) -> None:
        repository = _FakeRepository()
        service = FootballV2Service(repository=repository)  # type: ignore[arg-type]

        service.get_event_feed(bucket="live", competition_id=42)

        self.assertEqual(repository.last_limit, 50)

    def test_get_event_feed_caps_explicit_limit(self) -> None:
        repository = _FakeRepository()
        service = FootballV2Service(repository=repository)  # type: ignore[arg-type]

        service.get_event_feed(bucket="results", limit=250)

        self.assertEqual(repository.last_limit, 100)

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

    def test_save_tournament_prediction_rejects_invalid_qualified_third(self) -> None:
        service = FootballV2Service(repository=_TournamentRepository())  # type: ignore[arg-type]
        user = AuthenticatedUser(id="user-1", email=None, username="elian")
        payload = TournamentPredictionPayload(
            groupPredictions=[{"groupId": "group_a", "orderedParticipantIds": [1, 2, 3]}],
            qualifiedThirdParticipantIds=[2],
        )

        with self.assertRaises(HTTPException):
            service.save_tournament_prediction(10, payload, user)

    def test_save_tournament_prediction_persists_valid_document(self) -> None:
        repository = _TournamentRepository()
        service = FootballV2Service(repository=repository)  # type: ignore[arg-type]
        user = AuthenticatedUser(id="user-1", email=None, username="elian")
        payload = TournamentPredictionPayload(
            groupPredictions=[{"groupId": "group_a", "orderedParticipantIds": [1, 2, 3]}],
            qualifiedThirdParticipantIds=[3],
            knockoutPredictions=[
                {
                    "eventId": 900,
                    "homeScore": 2,
                    "awayScore": 1,
                    "winnerParticipantId": 1,
                }
            ],
            awards={"mvpParticipantId": 101},
            championParticipantId=1,
        )

        response = service.save_tournament_prediction(10, payload, user)

        self.assertEqual(response.id, "tp-1")
        self.assertEqual(repository.saved_payload["championParticipantId"], 1)
