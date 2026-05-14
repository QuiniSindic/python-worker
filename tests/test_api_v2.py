from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v2.endpoints import catalog, football, leaderboard, users
from app.main import app
from app.schemas.auth import AuthenticatedUser
from app.schemas.catalog import CompetitionEditionLite


def _edition() -> dict:
    return {
        "id": 10,
        "season_key": "2025-2026",
        "season_label": "2025/26",
        "is_current": True,
    }


def _team(team_id: int, name: str, country: str = "ES") -> dict:
    return {
        "id": team_id,
        "name": name,
        "abbr": name[:3].upper(),
        "img": None,
        "country": country,
    }


def _match(event_id: int = 501) -> dict:
    return {
        "id": event_id,
        "status": "NS",
        "result": "-",
        "kickoff": "20:00 01/04/2026",
        "minute": None,
        "homeId": 1,
        "awayId": 2,
        "competitionid": 42,
        "sportId": 1,
        "round": "Semi-finals",
        "homeTeam": _team(1, "Barcelona"),
        "awayTeam": _team(2, "Real Madrid"),
        "country": "ES",
        "edition": _edition(),
        "events": [],
    }


class _FakeFootballService:
    def get_sports(self) -> list[dict]:
        return [
            {
                "id": 1,
                "slug": "football",
                "name": "Football",
                "displayName": "Football",
            }
        ]

    def get_competitions(self, sport_id: int) -> list[dict]:
        return [
            {
                "id": 42,
                "name": "UEFA Champions League",
                "country": None,
                "current_edition": _edition(),
            }
        ]

    def get_current_season(self, competition_id: int) -> dict:
        return CompetitionEditionLite(**_edition())

    def get_event_feed(
        self,
        *,
        bucket: str,
        competition_id: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return [
            {
                "id": "42",
                "name": "UEFA Champions League",
                "fullName": "UEFA Champions League",
                "badge": "badge.png",
                "country": None,
                "formatKind": "league_phase_knockout",
                "edition": _edition(),
                "stages": [
                    {
                        "id": "league_phase",
                        "name": "Clasificacion",
                        "stageType": "league_table",
                        "order": 0,
                        "roundLabels": [],
                        "groups": [],
                    }
                ],
                "matches": [_match(900 if bucket == "results" else 501)],
            }
        ]

    def get_event(self, event_id: int) -> dict:
        return _match(event_id)

    def get_event_predictions(self, event_id: int) -> list[dict]:
        return [
            {
                "id": "pred-1",
                "user_id": "user-1",
                "match_id": event_id,
                "competition_id": 42,
                "edition_id": 10,
                "sport_id": 1,
                "home_score": 2,
                "away_score": 1,
                "points": 3,
                "status": "scored",
                "created_at": "2026-04-03T10:00:00+00:00",
                "updated_at": "2026-04-03T10:00:00+00:00",
            }
        ]

    def get_user_prediction(self, event_id: int, user: AuthenticatedUser) -> dict:
        return {
            "id": "pred-me",
            "user_id": user.id,
            "match_id": event_id,
            "competition_id": 42,
            "edition_id": 10,
            "sport_id": 1,
            "home_score": 1,
            "away_score": 0,
            "points": None,
            "status": "open",
            "created_at": "2026-04-03T10:00:00+00:00",
            "updated_at": "2026-04-03T10:00:00+00:00",
        }

    def save_prediction(self, event_id: int, payload: object, user: AuthenticatedUser) -> dict:
        return {
            "id": "pred-save",
            "user_id": user.id,
            "match_id": event_id,
            "competition_id": 42,
            "edition_id": 10,
            "sport_id": 1,
            "home_score": 3,
            "away_score": 2,
            "points": None,
            "status": "open",
            "created_at": "2026-04-03T10:00:00+00:00",
            "updated_at": "2026-04-03T10:00:00+00:00",
        }

    def update_prediction(
        self,
        event_id: int,
        home_score: int,
        away_score: int,
        user: AuthenticatedUser,
    ) -> dict:
        return {
            "id": "pred-update",
            "user_id": user.id,
            "match_id": event_id,
            "competition_id": 42,
            "edition_id": 10,
            "sport_id": 1,
            "home_score": home_score,
            "away_score": away_score,
            "points": None,
            "status": "open",
            "created_at": "2026-04-03T10:00:00+00:00",
            "updated_at": "2026-04-03T10:05:00+00:00",
        }

    def get_prediction_feed(self) -> list[dict]:
        return [
            {
                "id": "feed-1",
                "userId": "user-1",
                "username": "elian",
                "matchId": 501,
                "kickoff": "20:00 01/04/2026",
                "matchStatus": "NS",
                "homeTeam": "Barcelona",
                "awayTeam": "Real Madrid",
                "predicted": "2-1",
                "homeScore": None,
                "awayScore": None,
                "minute": None,
                "sportId": 1,
                "sportName": "Football",
                "competitionId": 42,
                "competitionName": "UEFA Champions League",
                "edition": _edition(),
                "points": None,
                "createdAt": "2026-04-03T10:00:00+00:00",
            }
        ]

    def get_structure(self, season_id: int) -> dict:
        return {
            "competitionId": 42,
            "name": "UEFA Champions League",
            "badge": "badge.png",
            "country": None,
            "formatKind": "league_phase_knockout",
            "edition": _edition(),
            "stages": [
                {
                    "id": "league_phase",
                    "name": "Clasificacion",
                    "stageType": "league_table",
                    "order": 0,
                    "roundLabels": [],
                    "groups": [{"id": "overall", "name": "Tabla general", "order": 0}],
                },
                {
                    "id": "round_of_16",
                    "name": "Octavos",
                    "stageType": "knockout_round",
                    "order": 20,
                    "roundLabels": ["Octavos"],
                    "groups": [],
                },
            ],
        }

    def get_tournament_prediction_options(self, season_id: int) -> dict:
        return {
            "season": _edition(),
            "groups": [
                {
                    "id": "group_a",
                    "name": "Grupo A",
                    "order": 0,
                    "teams": [_team(1, "Barcelona"), _team(2, "Real Madrid")],
                }
            ],
            "bracket": self.get_bracket(season_id),
            "awardCandidates": [
                {
                    "id": 101,
                    "name": "Player One",
                    "teamId": 1,
                    "teamName": "Barcelona",
                    "badge": None,
                    "country": "ES",
                }
            ],
            "rules": {
                "groupPosition": 1,
                "groupPerfectBonus": 3,
                "qualifiedThird": 2,
                "knockoutByRound": {"round_of_16": 10, "final": 25},
                "champion": 0,
                "awards": {"mvp": 0, "bestGoalkeeper": 0, "topScorer": 0},
            },
            "locks": {
                "groupsLocked": False,
                "awardsLocked": False,
                "championLocked": False,
                "lockedEventIds": [],
            },
        }

    def get_tournament_prediction(self, season_id: int, user: AuthenticatedUser) -> dict:
        return {
            "id": None,
            "user_id": user.id,
            "competition_id": 42,
            "edition_id": season_id,
            "sport_id": 1,
            "status": "open",
            "payload": {
                "groupPredictions": [],
                "qualifiedThirdParticipantIds": [],
                "knockoutPredictions": [],
                "awards": {},
                "championParticipantId": None,
            },
            "points": None,
            "pointsBreakdown": {},
            "created_at": None,
            "updated_at": None,
            "options": self.get_tournament_prediction_options(season_id),
        }

    def save_tournament_prediction(
        self, season_id: int, payload: object, user: AuthenticatedUser
    ) -> dict:
        return {
            "id": "tournament-pred-1",
            "user_id": user.id,
            "competition_id": 42,
            "edition_id": season_id,
            "sport_id": 1,
            "status": "open",
            "payload": payload.model_dump(),
            "points": None,
            "pointsBreakdown": {},
            "created_at": "2026-04-03T10:00:00+00:00",
            "updated_at": "2026-04-03T10:00:00+00:00",
            "options": self.get_tournament_prediction_options(season_id),
        }

    def score_tournament_predictions(self, season_id: int) -> list[dict]:
        return [
            self.get_tournament_prediction(
                season_id,
                AuthenticatedUser(id="user-1", email=None, username="elian"),
            )
        ]

    def get_bracket(self, season_id: int) -> list[dict]:
        return [
            {
                "id": "round_of_16",
                "name": "Octavos",
                "order": 20,
                "ties": [
                    {
                        "id": "tie-1",
                        "roundId": "round_of_16",
                        "roundName": "Octavos",
                        "order": 20,
                        "homeTeam": _team(1, "Barcelona"),
                        "awayTeam": _team(2, "Real Madrid"),
                        "aggregateHomeScore": 3,
                        "aggregateAwayScore": 2,
                        "winnerParticipantId": 1,
                        "isTwoLegged": True,
                        "legs": [
                            {
                                "eventId": 501,
                                "kickoff": "20:00 01/04/2026",
                                "status": "FT",
                                "minute": None,
                                "result": "2-1",
                                "leg": 1,
                                "homeTeam": _team(1, "Barcelona"),
                                "awayTeam": _team(2, "Real Madrid"),
                            },
                            {
                                "eventId": 502,
                                "kickoff": "20:00 08/04/2026",
                                "status": "FT",
                                "minute": None,
                                "result": "1-1",
                                "leg": 2,
                                "homeTeam": _team(2, "Real Madrid"),
                                "awayTeam": _team(1, "Barcelona"),
                            },
                        ],
                    }
                ],
            }
        ]

    def get_standings(
        self,
        competition_id: int,
        stage_id: str | None = None,
        group_id: str | None = None,
    ) -> dict:
        return {
            "competitionId": competition_id,
            "stageId": stage_id or "group_stage",
            "stageName": "Fase de grupos",
            "stageType": "group",
            "edition": _edition(),
            "groups": [
                {
                    "id": "group_a",
                    "name": "Grupo A",
                    "order": 0,
                    "teams": [
                        {
                            "id": "1",
                            "position": 1,
                            "name": "Barcelona",
                            "badge": "barca.png",
                            "played": 3,
                            "wins": 2,
                            "draws": 1,
                            "losses": 0,
                            "points": 7,
                            "goalsFor": 6,
                            "goalsAgainst": 2,
                            "goalDifference": 4,
                            "form": [],
                        }
                    ],
                },
                {
                    "id": "group_b",
                    "name": "Grupo B",
                    "order": 1,
                    "teams": [
                        {
                            "id": "2",
                            "position": 1,
                            "name": "Real Madrid",
                            "badge": "rm.png",
                            "played": 3,
                            "wins": 2,
                            "draws": 0,
                            "losses": 1,
                            "points": 6,
                            "goalsFor": 5,
                            "goalsAgainst": 3,
                            "goalDifference": 2,
                            "form": [],
                        }
                    ],
                },
            ]
            if group_id is None
            else [
                {
                    "id": group_id,
                    "name": "Grupo B",
                    "order": 1,
                    "teams": [],
                }
            ],
        }

    def get_leaderboard(self, scope: str, filter_id: int | None) -> list[dict]:
        return [
            {
                "user_id": "user-1",
                "username": "elian",
                "avatar_url": None,
                "total_points": 10,
                "predictions_count": 4,
                "exact_hits": 2,
            }
        ]

    def get_leaderboard_filters(self) -> dict:
        return {
            "sports": self.get_sports(),
            "competitions": self.get_competitions(1),
        }


class _FakeUsersRepository:
    def get_profile(self, user_id: str) -> dict:
        return {
            "id": user_id,
            "username": "elian-dev",
            "email": "elian@example.com",
            "avatar_url": "avatar.png",
        }


class _FakeUsersService:
    def __init__(self) -> None:
        self.repository = _FakeUsersRepository()

    def get_profiles(self, user_ids: list[str]) -> list[dict]:
        return [
            {
                "id": user_id,
                "username": f"user-{index}",
                "email": f"user-{index}@example.com",
                "img": None,
            }
            for index, user_id in enumerate(user_ids, start=1)
        ]


class ApiV2Tests(TestCase):
    def setUp(self) -> None:
        self.original_football_service = football.service
        self.original_catalog_service = catalog.service
        self.original_leaderboard_service = leaderboard.service
        self.original_users_service = users.users_service

        fake_service = _FakeFootballService()
        football.service = fake_service
        catalog.service = fake_service
        leaderboard.service = fake_service
        users.users_service = _FakeUsersService()

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id="user-1",
            email="elian@example.com",
            username="elian",
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        football.service = self.original_football_service
        catalog.service = self.original_catalog_service
        leaderboard.service = self.original_leaderboard_service
        users.users_service = self.original_users_service
        app.dependency_overrides.clear()
        self.client.close()

    def test_root_reports_only_v2_runtime(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active"], ["/api/v2"])
        self.assertEqual(response.json()["legacy"], [])

    def test_health_reports_service_status(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "Quinisindic Backend API",
                "active": ["/api/v2"],
            },
        )

    def test_catalog_endpoints_return_v2_options(self) -> None:
        sports_response = self.client.get("/api/v2/catalog/sports")
        competitions_response = self.client.get(
            "/api/v2/catalog/competitions", params={"sport_id": 1}
        )

        self.assertEqual(sports_response.status_code, 200)
        self.assertEqual(competitions_response.status_code, 200)
        self.assertEqual(sports_response.json()[0]["slug"], "football")
        self.assertEqual(
            competitions_response.json()[0]["current_edition"]["season_key"], "2025-2026"
        )

    def test_football_endpoints_cover_feed_structure_and_standings(self) -> None:
        live_response = self.client.get("/api/v2/football/events/live", params={"limit": 12})
        results_response = self.client.get("/api/v2/football/events/results", params={"limit": 8})
        season_response = self.client.get("/api/v2/football/competitions/42/current-season")
        overview_response = self.client.get("/api/v2/football/seasons/10/overview")
        standings_response = self.client.get(
            "/api/v2/football/standings/42", params={"group_id": "group_b"}
        )

        self.assertEqual(live_response.status_code, 200)
        self.assertEqual(results_response.status_code, 200)
        self.assertEqual(season_response.status_code, 200)
        self.assertEqual(overview_response.status_code, 200)
        self.assertEqual(standings_response.status_code, 200)

        self.assertEqual(live_response.json()[0]["matches"][0]["id"], 501)
        self.assertEqual(results_response.json()[0]["matches"][0]["id"], 900)
        self.assertEqual(season_response.json()["season_key"], "2025-2026")
        self.assertEqual(overview_response.json()["formatKind"], "league_phase_knockout")
        self.assertEqual(standings_response.json()["groups"][0]["id"], "group_b")

    def test_football_bracket_and_prediction_endpoints_work(self) -> None:
        bracket_response = self.client.get("/api/v2/football/seasons/10/bracket")
        current_bracket_response = self.client.get("/api/v2/football/events/bracket/42")
        event_response = self.client.get("/api/v2/football/events/501")
        prediction_me_response = self.client.get("/api/v2/football/events/501/predictions/me")
        prediction_save_response = self.client.post(
            "/api/v2/football/events/501/predictions",
            json={
                "competition_id": 42,
                "sport_id": 1,
                "event_id": 501,
                "home_score": 3,
                "away_score": 2,
            },
        )
        prediction_update_response = self.client.put(
            "/api/v2/football/events/501/predictions",
            json={"home_score": 1, "away_score": 1},
        )

        self.assertEqual(bracket_response.status_code, 200)
        self.assertEqual(current_bracket_response.status_code, 200)
        self.assertEqual(event_response.status_code, 200)
        self.assertEqual(prediction_me_response.status_code, 200)
        self.assertEqual(prediction_save_response.status_code, 200)
        self.assertEqual(prediction_update_response.status_code, 200)

        self.assertTrue(bracket_response.json()[0]["ties"][0]["isTwoLegged"])
        self.assertEqual(current_bracket_response.json()[0]["ties"][0]["legs"][1]["leg"], 2)
        self.assertEqual(event_response.json()["id"], 501)
        self.assertEqual(prediction_me_response.json()["user_id"], "user-1")
        self.assertEqual(prediction_save_response.json()["home_score"], 3)
        self.assertEqual(prediction_update_response.json()["away_score"], 1)

    def test_tournament_prediction_endpoints_work(self) -> None:
        options_response = self.client.get(
            "/api/v2/football/seasons/10/tournament-prediction/options"
        )
        me_response = self.client.get("/api/v2/football/seasons/10/tournament-prediction")
        save_response = self.client.put(
            "/api/v2/football/seasons/10/tournament-prediction",
            json={
                "groupPredictions": [{"groupId": "group_a", "orderedParticipantIds": [1, 2]}],
                "qualifiedThirdParticipantIds": [],
                "knockoutPredictions": [
                    {
                        "eventId": 501,
                        "homeScore": 2,
                        "awayScore": 1,
                        "winnerParticipantId": 1,
                        "wonOnPenalties": False,
                    }
                ],
                "awards": {
                    "mvpParticipantId": 101,
                    "bestGoalkeeperParticipantId": None,
                    "topScorerParticipantId": None,
                },
                "championParticipantId": 1,
            },
        )

        self.assertEqual(options_response.status_code, 200)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(options_response.json()["groups"][0]["id"], "group_a")
        self.assertEqual(save_response.json()["id"], "tournament-pred-1")

    def test_users_and_leaderboard_endpoints_use_v2_contracts(self) -> None:
        me_response = self.client.get("/api/v2/users/me")
        profiles_response = self.client.get(
            "/api/v2/users/profiles",
            params=[("ids", "user-1"), ("ids", "user-2")],
        )
        leaderboard_response = self.client.get(
            "/api/v2/leaderboard", params={"scope": "competition", "filter_id": 42}
        )
        leaderboard_filters_response = self.client.get("/api/v2/leaderboard/filters")

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(profiles_response.status_code, 200)
        self.assertEqual(leaderboard_response.status_code, 200)
        self.assertEqual(leaderboard_filters_response.status_code, 200)

        self.assertEqual(me_response.json()["username"], "elian-dev")
        self.assertEqual(len(profiles_response.json()), 2)
        self.assertEqual(leaderboard_response.json()[0]["total_points"], 10)
        self.assertEqual(leaderboard_filters_response.json()["sports"][0]["slug"], "football")
