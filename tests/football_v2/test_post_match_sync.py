from __future__ import annotations

import asyncio
from unittest import TestCase

from app.domains.football_v2.jobs.sync_finished_matches_job import FootballPostMatchSyncService
from app.schemas.match import CompetitionData, MatchData, MatchStatus, TeamInfo


class _FakePostMatchRepository:
    def __init__(self, *, event_status: str) -> None:
        self.event_status = event_status
        self.sync_state: dict | None = None

    def list_matches_by_provider_ids(
        self,
        provider_name: str,
        provider_event_ids: list[str],
    ) -> list[dict]:
        return [
            {
                "id": 9001,
                "provider_name": provider_name,
                "provider_event_id": "1113",
                "status": self.event_status,
            }
            for provider_event_id in provider_event_ids
            if provider_event_id == "1113"
        ]

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


class _FakePostMatchScraper:
    async def get_live_matches_fotmob(
        self, target_date: str | None = None
    ) -> list[CompetitionData]:
        if target_date != "20260403":
            return []

        home = TeamInfo(id=244, name="Paris Saint-Germain", abbr="PAR", img=None, country="FR")
        away = TeamInfo(id=234, name="Toulouse", abbr="TOU", img=None, country="FR")
        return [
            CompetitionData(
                id="53",
                name="Ligue 1",
                fullName="Ligue 1",
                badge="",
                matches=[
                    MatchData(
                        id=1113,
                        status=MatchStatus.FT,
                        result="2-0",
                        kickoff="18:45 03/04/2026",
                        kickoff_iso="2026-04-03T18:45:00+00:00",
                        minute=None,
                        round="28",
                        homeId=244,
                        awayId=234,
                        competitionid=53,
                        homeTeam=home,
                        awayTeam=away,
                        country="FR",
                    )
                ],
            )
        ]


class _FakeBootstrapService:
    def __init__(self) -> None:
        self.received_definitions: list = []

    async def run_for_definitions(self, definitions, *, sport_id=None, state_key=None):
        self.received_definitions = list(definitions)
        return {"competitions": len(self.received_definitions)}


class _FakeLiveSyncService:
    def __init__(self) -> None:
        self.received_dates: list[str] | None = None

    async def run(self, target_dates: list[str] | None = None):
        self.received_dates = target_dates
        return {"events_updated": 1}


class FootballPostMatchSyncServiceTests(TestCase):
    def test_run_refreshes_competition_when_match_just_finished(self) -> None:
        repository = _FakePostMatchRepository(event_status="live")
        bootstrap = _FakeBootstrapService()
        live_sync = _FakeLiveSyncService()
        service = FootballPostMatchSyncService(
            repository=repository,  # type: ignore[arg-type]
            scraper=_FakePostMatchScraper(),  # type: ignore[arg-type]
            bootstrap=bootstrap,  # type: ignore[arg-type]
            live_sync=live_sync,  # type: ignore[arg-type]
        )

        stats = asyncio.run(service.run(["20260403"]))

        self.assertEqual(stats["competitions_refreshed"], 1)
        self.assertEqual(len(bootstrap.received_definitions), 1)
        self.assertEqual(bootstrap.received_definitions[0].fotmob_id, 53)
        self.assertEqual(live_sync.received_dates, ["20260403"])
        self.assertEqual(repository.sync_state["state_key"], "worker-football-post-match")

    def test_run_skips_refresh_when_match_already_finished(self) -> None:
        repository = _FakePostMatchRepository(event_status="finished")
        bootstrap = _FakeBootstrapService()
        live_sync = _FakeLiveSyncService()
        service = FootballPostMatchSyncService(
            repository=repository,  # type: ignore[arg-type]
            scraper=_FakePostMatchScraper(),  # type: ignore[arg-type]
            bootstrap=bootstrap,  # type: ignore[arg-type]
            live_sync=live_sync,  # type: ignore[arg-type]
        )

        stats = asyncio.run(service.run(["20260403"]))

        self.assertEqual(stats["competitions_refreshed"], 0)
        self.assertEqual(bootstrap.received_definitions, [])
        self.assertIsNone(live_sync.received_dates)
