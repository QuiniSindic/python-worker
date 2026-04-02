from __future__ import annotations

import unittest

from app.providers.fotmob_mapper import FotmobMapper
from app.schemas.match import MatchStatus


class FotmobMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = FotmobMapper()

    def test_map_live_matches_payload_filters_target_leagues(self) -> None:
        payload = {
            "leagues": [
                {
                    "primaryId": 47,
                    "name": "Champions League",
                    "ccode": "INT",
                    "matches": [
                        {
                            "id": 1001,
                            "status": {
                                "started": True,
                                "utcTime": "2026-03-29T19:00:00.000Z",
                                "scoreStr": "2-1",
                                "liveTime": {"short": "67'"},
                            },
                            "time": "19:00",
                            "home": {"id": 10, "name": "Barcelona", "score": 2},
                            "away": {"id": 20, "name": "Arsenal", "score": 1},
                            "round": {"name": "Semi-finals"},
                        }
                    ],
                },
                {
                    "primaryId": 999,
                    "name": "Ignored League",
                    "ccode": "XX",
                    "matches": [{"id": 3001}],
                },
            ]
        }

        competitions = self.mapper.map_live_matches_payload(payload, {47})

        self.assertEqual(len(competitions), 1)
        competition = competitions[0]
        self.assertEqual(competition.id, "47")
        self.assertEqual(competition.matches[0].status, MatchStatus.LIVE)
        self.assertEqual(competition.matches[0].minute, "67'")
        self.assertEqual(competition.matches[0].round, "Semi-finals")
        self.assertEqual(competition.matches[0].homeTeam.abbr, "BAR")

    def test_map_standings_payload_supports_tables_shape(self) -> None:
        payload = [
            {
                "data": {
                    "tables": [
                        {
                            "table": {
                                "all": [
                                    {
                                        "idx": 1,
                                        "id": 12,
                                        "name": "Team A",
                                        "shortName": "A",
                                        "played": 8,
                                        "wins": 6,
                                        "draws": 1,
                                        "losses": 1,
                                        "pts": 19,
                                        "scoresStr": "18-7",
                                        "goalConDiff": 11,
                                    }
                                ]
                            }
                        }
                    ],
                    "teamForm": {"12": ["W", "W", "D"]},
                }
            }
        ]

        standings = self.mapper.map_standings_payload(payload, league_id=47)

        self.assertIsNotNone(standings)
        self.assertEqual(standings["stageType"], "league_table")
        self.assertEqual(standings["groups"][0]["teams"][0]["goalsFor"], 18)
        self.assertEqual(standings["groups"][0]["teams"][0]["goalsAgainst"], 7)
        self.assertEqual(standings["groups"][0]["teams"][0]["form"], ["W", "W", "D"])

    def test_map_standings_payload_preserves_multiple_groups(self) -> None:
        payload = [
            {
                "data": {
                    "tables": [
                        {
                            "name": "Grupo A",
                            "table": {
                                "all": [
                                    {
                                        "idx": 1,
                                        "id": 12,
                                        "name": "Team A",
                                        "shortName": "A",
                                        "played": 3,
                                        "wins": 2,
                                        "draws": 1,
                                        "losses": 0,
                                        "pts": 7,
                                        "scoresStr": "5-1",
                                        "goalConDiff": 4,
                                    }
                                ]
                            },
                        },
                        {
                            "name": "Grupo B",
                            "table": {
                                "all": [
                                    {
                                        "idx": 1,
                                        "id": 99,
                                        "name": "Team B",
                                        "shortName": "B",
                                        "played": 3,
                                        "wins": 3,
                                        "draws": 0,
                                        "losses": 0,
                                        "pts": 9,
                                        "scoresStr": "8-2",
                                        "goalConDiff": 6,
                                    }
                                ]
                            },
                        },
                    ]
                }
            }
        ]

        standings = self.mapper.map_standings_payload(payload, league_id=77)

        self.assertIsNotNone(standings)
        self.assertEqual(standings["stageType"], "group")
        self.assertEqual([group["name"] for group in standings["groups"]], ["Grupo A", "Grupo B"])
        self.assertEqual([group["id"] for group in standings["groups"]], ["group_a", "group_b"])

    def test_map_standings_payload_normalizes_numeric_groups_and_best_thirds(self) -> None:
        payload = [
            {
                "data": {
                    "tables": [
                        {
                            "name": "Group 1",
                            "table": {
                                "all": [
                                    {
                                        "idx": 1,
                                        "id": 12,
                                        "name": "Team A",
                                        "shortName": "A",
                                        "played": 3,
                                        "wins": 2,
                                        "draws": 1,
                                        "losses": 0,
                                        "pts": 7,
                                        "scoresStr": "5-1",
                                        "goalConDiff": 4,
                                    }
                                ]
                            },
                        },
                        {
                            "name": "Group 10",
                            "table": {
                                "all": [
                                    {
                                        "idx": 1,
                                        "id": 99,
                                        "name": "Team J",
                                        "shortName": "J",
                                        "played": 3,
                                        "wins": 3,
                                        "draws": 0,
                                        "losses": 0,
                                        "pts": 9,
                                        "scoresStr": "8-2",
                                        "goalConDiff": 6,
                                    }
                                ]
                            },
                        },
                        {
                            "name": "Best third-placed teams",
                            "table": {
                                "all": [
                                    {
                                        "idx": 1,
                                        "id": 77,
                                        "name": "Team Third",
                                        "shortName": "T",
                                        "played": 3,
                                        "wins": 1,
                                        "draws": 1,
                                        "losses": 1,
                                        "pts": 4,
                                        "scoresStr": "3-3",
                                        "goalConDiff": 0,
                                    }
                                ]
                            },
                        },
                    ]
                }
            }
        ]

        standings = self.mapper.map_standings_payload(payload, league_id=77)

        self.assertIsNotNone(standings)
        self.assertEqual(
            [group["id"] for group in standings["groups"]],
            ["group_a", "group_j", "best_third_placed"],
        )
        self.assertEqual(
            [group["name"] for group in standings["groups"]],
            ["Grupo A", "Grupo J", "Mejores terceros"],
        )

    def test_map_match_details_payload_normalizes_events(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "Goal",
                                "time": 12,
                                "timeStr": "12'",
                                "isHome": True,
                                "newScore": [1, 0],
                                "player": {"id": 5, "name": "Lamine Yamal"},
                                "assistInput": "Pedri",
                            },
                            {
                                "type": "Substitution",
                                "time": 65,
                                "swap": [
                                    {"id": 9, "name": "Player Out"},
                                    {"id": 10, "name": "Player In"},
                                ],
                            },
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1001)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["score"], {"home": 1, "away": 0})
        self.assertEqual(events[0]["player"], "Lamine Yamal")
        self.assertEqual(events[1]["playerIn"], "Player In")

    def test_map_season_matches_payload_builds_competition(self) -> None:
        payload = {
            "details": {"id": 55, "name": "LaLiga", "country": "ESP"},
            "fixtures": {
                "allMatches": [
                    {
                        "id": 2020,
                        "status": {"utcTime": "2026-04-01T20:00:00.000Z", "scoreStr": "vs"},
                        "home": {"id": 1, "name": "Real Madrid"},
                        "away": {"id": 2, "name": "Valencia"},
                        "roundName": 30,
                    }
                ]
            },
        }

        competitions = self.mapper.map_season_matches_payload(payload)

        self.assertEqual(len(competitions), 1)
        competition = competitions[0]
        self.assertEqual(competition.id, "55")
        self.assertEqual(competition.matches[0].round, "30")
        self.assertEqual(competition.matches[0].status, MatchStatus.NS)


if __name__ == "__main__":
    unittest.main()
