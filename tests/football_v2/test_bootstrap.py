from __future__ import annotations

from unittest import TestCase

from app.domains.football_v2.jobs.bootstrap import _normalize_standings_groups


class FootballBootstrapHelpersTests(TestCase):
    def test_normalize_standings_groups_coerces_team_ids_to_strings(self) -> None:
        groups = [
            {
                "id": "overall",
                "name": "Tabla general",
                "order": 0,
                "teams": [
                    {
                        "id": 9823,
                        "position": 1,
                        "name": "Bayern",
                        "badge": "https://example.com/bayern.png",
                        "played": 27,
                        "wins": 20,
                        "draws": 5,
                        "losses": 2,
                        "points": 65,
                        "goalsFor": 78,
                        "goalsAgainst": 26,
                        "goalDifference": 52,
                        "form": [],
                    }
                ],
            }
        ]

        normalized = _normalize_standings_groups(groups)

        self.assertEqual(normalized[0]["id"], "overall")
        self.assertEqual(normalized[0]["teams"][0]["id"], "9823")
