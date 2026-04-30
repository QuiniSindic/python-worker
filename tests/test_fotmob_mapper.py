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

    def test_map_standings_payload_normalizes_3rd_placed_group(self) -> None:
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
                            "name": "Best 3rd-placed teams",
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
            ["group_a", "best_third_placed"],
        )
        self.assertEqual(
            [group["name"] for group in standings["groups"]],
            ["Grupo A", "Mejores terceros"],
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
                                "type": "Card",
                                "time": 30,
                                "isHome": False,
                                "player": {"id": 7, "name": "Jose Maria Gimenez"},
                                "card": "Yellow",
                                "cancelled": True,
                            },
                            {
                                "type": "Var",
                                "time": 31,
                                "isHome": False,
                                "text": "Tarjeta roja anulada",
                                "player": {"id": 11, "name": "Gerard Martin"},
                                "reason": "Fuera de juego previo",
                                "isCancelled": True,
                            },
                            {
                                "type": "Substitution",
                                "time": 65,
                                "swap": [
                                    {"id": 9, "name": "Marc Bernal"},
                                    {"id": 10, "name": "Ronald Araujo"},
                                ],
                            },
                            {
                                "type": "AddedTime",
                                "time": 45,
                                "minutesAddedStr": "+3 añadido",
                            },
                            {
                                "type": "Half",
                                "time": 45,
                                "halfStrShort": "HT",
                            },
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1001)

        self.assertEqual(len(events), 6)
        self.assertEqual(events[0]["score"], {"home": 1, "away": 0})
        self.assertEqual(events[0]["player"], "Lamine Yamal")
        self.assertEqual(events[0]["kind"], "goal")
        self.assertEqual(events[0]["side"], "home")
        self.assertEqual(events[0]["detail"], "Asist. Pedri")
        self.assertEqual(events[1]["kind"], "card")
        self.assertTrue(events[1]["isCancelled"])
        self.assertEqual(events[1]["detail"], "Tarjeta amarilla anulada")
        self.assertEqual(events[2]["kind"], "var")
        self.assertEqual(events[2]["title"], "Tarjeta roja anulada")
        self.assertEqual(events[2]["subtitle"], "Gerard Martin")
        self.assertEqual(events[2]["detail"], "Fuera de juego previo")
        self.assertEqual(events[3]["playerIn"], "Marc Bernal")
        self.assertEqual(events[3]["playerOut"], "Ronald Araujo")
        self.assertEqual(events[3]["title"], "Marc Bernal")
        self.assertEqual(events[3]["detail"], "Sale Ronald Araujo")
        self.assertEqual(events[3]["kind"], "substitution")
        self.assertEqual(events[4]["kind"], "added_time")
        self.assertEqual(events[4]["side"], "neutral")
        self.assertEqual(events[5]["kind"], "period")
        self.assertEqual(events[5]["title"], "Descanso")

    def test_map_match_details_payload_var_fallback_uses_generic_decision(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "Var",
                                "time": 46,
                                "isHome": True,
                                "player": {"id": 19, "name": "Nicolas Gonzalez"},
                                "reason": "Posible roja",
                            }
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1002)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "var")
        self.assertEqual(events[0]["title"], "Revisión VAR")
        self.assertEqual(events[0]["subtitle"], "Nicolas Gonzalez")
        self.assertEqual(events[0]["detail"], "Posible roja")

    def test_map_match_details_payload_reads_uppercase_var_decision(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "VAR",
                                "time": 45,
                                "timeStr": "45 + 3",
                                "overloadTime": 3,
                                "isHome": True,
                                "player": {"id": 841672, "name": "Nicolás González"},
                                "VAR": {
                                    "pendingDecision": False,
                                    "decision": {
                                        "key": ["var_yellow_card_removed"],
                                        "value": ["Yellow card cancelled"],
                                    },
                                },
                            },
                            {
                                "type": "VAR",
                                "time": 46,
                                "isHome": False,
                                "player": {"id": 1598982, "name": "Gerard Martín"},
                                "VAR": {
                                    "pendingDecision": False,
                                    "decision": {
                                        "key": ["var_red_card_removed"],
                                        "value": ["Red card overturned"],
                                    },
                                },
                            },
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1003)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "Var")
        self.assertEqual(events[0]["kind"], "var")
        self.assertEqual(events[0]["title"], "Tarjeta amarilla cancelada")
        self.assertEqual(events[0]["subtitle"], "Nicolás González")
        self.assertEqual(events[0]["detail"], None)
        self.assertEqual(events[1]["title"], "Tarjeta roja anulada")
        self.assertEqual(events[1]["subtitle"], "Gerard Martín")

    def test_map_match_details_payload_supports_yellow_red_cards(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "Card",
                                "time": 39,
                                "isHome": False,
                                "player": {"id": 291635, "name": "Pedro Bigas"},
                                "card": "YellowRed",
                            }
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1004)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "card")
        self.assertEqual(events[0]["cardType"], "YellowRed")
        self.assertEqual(events[0]["detail"], "Doble amarilla")

    def test_map_match_details_payload_detects_penalty_goals_from_goal_metadata(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "Goal",
                                "time": 52,
                                "timeStr": 52,
                                "isHome": True,
                                "player": {"id": 846033, "name": "Vinicius Junior"},
                                "homeScore": 0,
                                "awayScore": 1,
                                "goalDescription": "Penalty",
                                "goalDescriptionKey": "penalty",
                                "suffix": "Pen",
                                "suffixKey": "penalties_short",
                                "isPenaltyShootoutEvent": False,
                                "newScore": [1, 1],
                                "shotmapEvent": {
                                    "situation": "Penalty",
                                },
                            }
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1005)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "PenaltyGoal")
        self.assertEqual(events[0]["kind"], "goal")
        self.assertEqual(events[0]["player"], "Vinicius Junior")
        self.assertTrue(events[0]["isPenalty"])
        self.assertEqual(events[0]["detail"], "De penalti")
        self.assertEqual(events[0]["score"], {"home": 1, "away": 1})

    def test_map_match_details_payload_supports_missed_penalties(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "MissedPenalty",
                                "time": 90,
                                "timeStr": "90 + 2",
                                "overloadTime": 2,
                                "isHome": False,
                                "player": {"id": 517052, "name": "Vedat Muriqi"},
                                "homeScore": 2,
                                "awayScore": 1,
                                "isPenaltyShootoutEvent": False,
                            }
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=1006)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "MissedPenalty")
        self.assertEqual(events[0]["kind"], "missed_penalty")
        self.assertEqual(events[0]["player"], "Vedat Muriqi")
        self.assertEqual(events[0]["detail"], "Penalti fallado")
        self.assertEqual(events[0]["side"], "away")
        self.assertEqual(events[0]["score"], {"home": 2, "away": 1})

    def test_map_match_details_payload_keeps_unknown_events_as_other(self) -> None:
        payload = {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "CoachCard",
                                "time": 90,
                                "isHome": True,
                                "text": "Diego Simeone",
                                "reason": "Protestar",
                            }
                        ]
                    }
                }
            }
        }

        events = self.mapper.map_match_details_payload(payload, match_id=2002)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "other")
        self.assertEqual(events[0]["title"], "Diego Simeone")
        self.assertEqual(events[0]["detail"], "Protestar")

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
