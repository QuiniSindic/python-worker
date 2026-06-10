from __future__ import annotations

import asyncio
from unittest import TestCase

from app.domains.football_v2.pickem_service import PickemService


class _FakePickemRepository:
    def __init__(self) -> None:
        self.players: list[dict] = []
        self.squad_players: list[dict] = []
        self.candidates: list[dict] = []

    def get_contest(self, contest_id: int) -> dict:
        return {
            "id": contest_id,
            "slug": "fifa-world-cup-2026",
            "competition_season_id": 30,
            "group_deadline": "2026-06-11T19:00:00+00:00",
            "awards_deadline": "2026-06-11T19:00:00+00:00",
            "scoring_config": {},
            "season": {"competition_id": 30},
            "competition": {"id": 30},
        }

    def list_group_phase_rows(self, season_id: int) -> list[dict]:
        return [{"id": 1}]

    def list_groups_for_phase_ids(self, phase_ids: list[int]) -> list[dict]:
        return [{"id": 10, "key": "group_a", "order_index": 0}]

    def list_standings_rows(self, season_id: int) -> list[dict]:
        return [
            {"phase_group_id": 10, "participant_id": 100, "position": 1},
            {"phase_group_id": 10, "participant_id": 101, "position": 2},
            {"phase_group_id": 10, "participant_id": 102, "position": 3},
            {"phase_group_id": 10, "participant_id": 103, "position": 4},
        ]

    def list_competitors(self, competitor_ids: list[int]) -> list[dict]:
        return [
            {
                "id": competitor_id,
                "name": f"Team {competitor_id}",
                "metadata": {"provider_team_id": competitor_id + 1000},
            }
            for competitor_id in competitor_ids
        ]

    def upsert_players(self, players: list[dict]) -> list[dict]:
        existing_by_provider_id = {row["provider_player_id"]: row for row in self.players}
        for player in players:
            row = existing_by_provider_id.get(player["provider_player_id"])
            if row is None:
                row = {"id": len(self.players) + 1, **player}
                self.players.append(row)
                existing_by_provider_id[player["provider_player_id"]] = row
            else:
                row.update(player)
        return self.players

    def list_players_by_provider_ids(
        self, provider_name: str, provider_player_ids: list[str]
    ) -> list[dict]:
        return [
            row
            for row in self.players
            if row["provider_name"] == provider_name
            and row["provider_player_id"] in provider_player_ids
        ]

    def upsert_squad_players(self, squad_players: list[dict]) -> list[dict]:
        self.squad_players = [
            {"id": index, **squad_player}
            for index, squad_player in enumerate(squad_players, start=1)
        ]
        return self.squad_players

    def upsert_pickem_players(self, pickem_id: int, players: list[dict]) -> list[dict]:
        existing_by_provider_id = {
            row["provider_id"]: row
            for row in self.players
            if row["pickem_id"] == pickem_id and row["provider_name"] == "fotmob"
        }
        upserted = []
        for player in players:
            row = existing_by_provider_id.get(player["provider_id"])
            if row is None:
                row = {"id": len(self.players) + 1, "pickem_id": pickem_id, **player}
                self.players.append(row)
            else:
                row.update(player)
            upserted.append(row)
        return upserted

    def deactivate_missing_pickem_players(
        self,
        pickem_id: int,
        active_provider_ids: set[str],
        synced_competitor_ids: set[int],
    ) -> int:
        deactivated = 0
        for player in self.players:
            if (
                player["pickem_id"] == pickem_id
                and player["provider_name"] == "fotmob"
                and player["competitor_id"] in synced_competitor_ids
                and player["is_active"]
                and player["provider_id"] not in active_provider_ids
            ):
                player["is_active"] = False
                deactivated += 1
        return deactivated

    def list_award_candidates(self, contest_id: int) -> list[dict]:
        competitors = {row["id"]: row for row in self.list_competitors([100, 101, 102, 103])}
        self.candidates = []
        for player in self.players:
            if not player["is_active"]:
                continue
            team_name = competitors[player["competitor_id"]]["name"]
            base = {
                "id": player["id"],
                "display_name": f"{player['name']} ({team_name})",
                "participant_id": player["competitor_id"],
                "metadata": {"provider": "fotmob"},
                "is_active": True,
            }
            self.candidates.append({**base, "award_key": "mvp"})
            self.candidates.append(
                {
                    **base,
                    "award_key": "best_goalkeeper" if player["position"] == "GK" else "top_scorer",
                }
            )
        return self.candidates


class _FakeScraper:
    async def get_team_squad(self, team_id: int) -> list[dict]:
        return [
            {
                "player_id": team_id * 10 + 1,
                "name": "Goalkeeper",
                "position_id": 0,
                "group": "keepers",
            },
            {
                "player_id": team_id * 10 + 2,
                "name": "Striker",
                "position_id": 3,
                "group": "attackers",
            },
        ]


class PickemFotmobImportTests(TestCase):
    def test_import_award_candidates_splits_goalkeepers_and_field_players(self) -> None:
        repository = _FakePickemRepository()
        repository.players.append(
            {
                "id": 1,
                "pickem_id": 1,
                "provider_name": "fotmob",
                "provider_id": "stale-goalkeeper",
                "competitor_id": 100,
                "name": "Old Goalkeeper",
                "position": "GK",
                "is_active": True,
            }
        )
        service = PickemService(repository=repository, scraper=_FakeScraper())

        stats = asyncio.run(service.sync_squads_from_fotmob(1))

        self.assertEqual(stats.teams_processed, 4)
        self.assertEqual(stats.players_upserted, 8)
        self.assertEqual(stats.squad_players_upserted, 8)
        self.assertEqual(stats.candidates_upserted, 16)
        award_keys = [candidate["award_key"] for candidate in repository.candidates]
        self.assertEqual(award_keys.count("best_goalkeeper"), 4)
        self.assertEqual(award_keys.count("top_scorer"), 4)
        self.assertEqual(award_keys.count("mvp"), 8)
        self.assertTrue(
            any("(Team 100)" in candidate["display_name"] for candidate in repository.candidates)
        )
        self.assertFalse(repository.players[0]["is_active"])
        self.assertEqual(repository.candidates[0]["metadata"]["provider"], "fotmob")
