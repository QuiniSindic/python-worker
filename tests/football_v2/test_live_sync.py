from __future__ import annotations

import asyncio
from unittest import TestCase

from app.domains.football_v2.live_sync import FootballLiveSyncService
from app.schemas.match import CompetitionData, MatchData, MatchStatus, TeamInfo


class _FakeLiveRepository:
    def __init__(self) -> None:
        self.upserted_events: list[dict] = []
        self.upserted_football_events: list[dict] = []
        self.sync_state: dict | None = None

    def list_events_by_provider_event_ids(
        self,
        provider_name: str,
        provider_event_ids: list[str],
    ) -> list[dict]:
        return [
            {
                "id": 9001,
                "sport_id": 1,
                "competition_id": 8,
                "competition_season_id": 8,
                "competition_phase_id": None,
                "phase_group_id": None,
                "parent_event_id": None,
                "event_type": "match",
                "slug": "1113",
                "title": "Paris Saint-Germain vs Toulouse",
                "provider_name": provider_name,
                "provider_event_id": "1113",
                "start_at": "2026-04-03T18:45:00+00:00",
                "end_at": None,
                "status": "scheduled",
                "sort_order": 0,
                "is_placeholder": False,
                "metadata": {"competition_slug": "ligue-1"},
            }
            for provider_event_id in provider_event_ids
            if provider_event_id == "1113"
        ]

    def list_football_event_rows(self, event_ids: list[int]) -> list[dict]:
        return [
            {
                "event_id": event_id,
                "minute": None,
                "status_detail": "NS",
                "round_key": "league",
                "round_label": "28",
                "leg": None,
                "home_score": None,
                "away_score": None,
                "penalties_home": None,
                "penalties_away": None,
                "aggregate_home_score": None,
                "aggregate_away_score": None,
                "winner_participant_id": None,
                "timeline": [],
                "metadata": {},
            }
            for event_id in event_ids
        ]

    def upsert_events(self, event_payloads: list[dict]) -> list[dict]:
        self.upserted_events = event_payloads
        return event_payloads

    def upsert_football_events(self, payloads: list[dict]) -> None:
        self.upserted_football_events = payloads

    def upsert_sync_state(
        self,
        provider_name: str,
        scope_ref: str,
        state_key: str,
        state_value: dict,
    ) -> None:
        self.sync_state = {
            "provider_name": provider_name,
            "scope_ref": scope_ref,
            "state_key": state_key,
            "state_value": state_value,
        }


class _FakeLiveScraper:
    async def get_live_matches_fotmob(
        self, target_date: str | None = None
    ) -> list[CompetitionData]:
        if target_date != "20260403":
            return []

        home = TeamInfo(
            id=244,
            name="Paris Saint-Germain",
            abbr="PAR",
            img=None,
            country="FR",
        )
        away = TeamInfo(
            id=234,
            name="Toulouse",
            abbr="TOU",
            img=None,
            country="FR",
        )
        return [
            CompetitionData(
                id="53",
                name="Ligue 1",
                fullName="Ligue 1",
                badge="",
                matches=[
                    MatchData(
                        id=1113,
                        status=MatchStatus.LIVE,
                        result="1-0",
                        kickoff="18:45 03/04/2026",
                        kickoff_iso="2026-04-03T18:45:00+00:00",
                        minute="12'",
                        round="28",
                        homeId=244,
                        awayId=234,
                        competitionid=8,
                        homeTeam=home,
                        awayTeam=away,
                        country="FR",
                    )
                ],
            )
        ]

    async def get_match_details(self, match_id: int) -> list[dict]:
        return [{"type": "Goal", "minute": 12, "player": "Dembele"}] if match_id == 1113 else []


class FootballLiveSyncServiceTests(TestCase):
    def test_run_updates_existing_live_event(self) -> None:
        repository = _FakeLiveRepository()
        scraper = _FakeLiveScraper()
        service = FootballLiveSyncService(repository=repository, scraper=scraper)  # type: ignore[arg-type]

        stats = asyncio.run(service.run(["20260403"]))

        self.assertEqual(stats["events_updated"], 1)
        self.assertEqual(stats["details_updated"], 1)
        self.assertEqual(repository.upserted_events[0]["status"], "live")
        self.assertEqual(repository.upserted_football_events[0]["minute"], "12'")
        self.assertEqual(repository.upserted_football_events[0]["home_score"], 1)
        self.assertEqual(repository.upserted_football_events[0]["away_score"], 0)
        self.assertEqual(
            repository.upserted_football_events[0]["timeline"],
            [{"type": "Goal", "minute": 12, "player": "Dembele"}],
        )
        self.assertEqual(repository.sync_state["state_key"], "worker-football-live")
