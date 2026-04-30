from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.domains.football_v2.bootstrap import FootballBootstrapService
from app.domains.football_v2.catalog import COMPETITIONS_BY_FOTMOB_ID
from app.domains.football_v2.live_sync import (
    FootballLiveSyncService,
    _match_status_value,
    _resolve_target_dates,
)
from app.domains.football_v2.repository import FootballV2Repository
from app.domains.football_v2.scraper import ScraperService

logger = logging.getLogger(__name__)

FINISHED_STATUSES = {"FT", "AET", "AP", "Canc."}


def _default_target_dates() -> list[str]:
    today = datetime.now(UTC).date()
    return [(today + timedelta(days=offset)).strftime("%Y%m%d") for offset in (-1, 0)]


class FootballPostMatchSyncService:
    def __init__(
        self,
        repository: FootballV2Repository | None = None,
        scraper: ScraperService | None = None,
        bootstrap: FootballBootstrapService | None = None,
        live_sync: FootballLiveSyncService | None = None,
    ) -> None:
        self.repository = repository or FootballV2Repository()
        self.scraper = scraper or ScraperService()
        self.bootstrap = bootstrap or FootballBootstrapService(
            repository=self.repository, scraper=self.scraper
        )
        self.live_sync = live_sync or FootballLiveSyncService(
            repository=self.repository, scraper=self.scraper
        )

    async def run(self, target_dates: list[str] | None = None) -> dict[str, int]:
        dates = _resolve_target_dates(self.repository, target_dates)
        finished_by_provider_id: dict[str, tuple[int, str]] = {}

        logger.debug("[post-match-sync] scanning dates=%s", ",".join(dates))
        for date_str in dates:
            competitions = await self.scraper.get_live_matches_fotmob(date_str)
            logger.debug(
                "[post-match-sync] date=%s competitions=%s",
                date_str,
                len(competitions),
            )
            for competition in competitions:
                fotmob_competition_id = int(competition.id)
                for match in competition.matches:
                    status_value = _match_status_value(match.status)
                    if status_value in FINISHED_STATUSES:
                        finished_by_provider_id[str(match.id)] = (
                            fotmob_competition_id,
                            status_value,
                        )

        if not finished_by_provider_id:
            stats = {
                "dates_scanned": len(dates),
                "finished_matches_seen": 0,
                "competitions_refreshed": 0,
                "refreshed_slugs": [],
                "live_events_updated": 0,
                "live_details_with_timeline": 0,
            }
            self.repository.upsert_sync_state(
                "fotmob", "football", "worker-football-post-match", stats
            )
            logger.debug("[post-match-sync] no finished matches detected in scanned dates")
            return stats

        existing_events = self.repository.list_events_by_provider_event_ids(
            "fotmob", list(finished_by_provider_id)
        )
        competitions_to_refresh: list[int] = []

        for event in existing_events:
            provider_event_id = str(event["provider_event_id"])
            finished_match = finished_by_provider_id.get(provider_event_id)
            if not finished_match:
                continue

            fotmob_competition_id, _status_value = finished_match
            if (
                event["status"] != "finished"
                and fotmob_competition_id not in competitions_to_refresh
            ):
                competitions_to_refresh.append(fotmob_competition_id)

        if not competitions_to_refresh:
            stats = {
                "dates_scanned": len(dates),
                "finished_matches_seen": len(finished_by_provider_id),
                "competitions_refreshed": 0,
                "refreshed_slugs": [],
                "live_events_updated": 0,
                "live_details_with_timeline": 0,
            }
            self.repository.upsert_sync_state(
                "fotmob", "football", "worker-football-post-match", stats
            )
            logger.debug(
                "[post-match-sync] finished_matches_seen=%s but no structural refresh is needed",
                len(finished_by_provider_id),
            )
            return stats

        competition_labels = [
            f"{competition_id}:{COMPETITIONS_BY_FOTMOB_ID[competition_id].slug}"
            if competition_id in COMPETITIONS_BY_FOTMOB_ID
            else str(competition_id)
            for competition_id in competitions_to_refresh
        ]
        logger.debug(
            "[post-match-sync] competitions_to_refresh=%s",
            ", ".join(competition_labels),
        )

        live_stats = await self.live_sync.run(dates)
        logger.debug(
            "[post-match-sync] pre-refresh live sync completed "
            "(events_updated=%s, details_with_timeline=%s, missing_events=%s)",
            live_stats.get("events_updated", 0),
            live_stats.get("details_with_timeline", 0),
            live_stats.get("missing_events", 0),
        )

        definitions = [
            COMPETITIONS_BY_FOTMOB_ID[competition_id]
            for competition_id in competitions_to_refresh
            if competition_id in COMPETITIONS_BY_FOTMOB_ID
        ]
        if definitions:
            await self.bootstrap.run_for_definitions(definitions, state_key=None)
            logger.debug(
                "[post-match-sync] structural refresh completed for %s",
                ", ".join(definition.slug for definition in definitions),
            )

        stats = {
            "dates_scanned": len(dates),
            "finished_matches_seen": len(finished_by_provider_id),
            "competitions_refreshed": len(definitions),
            "refreshed_slugs": [definition.slug for definition in definitions],
            "live_events_updated": live_stats.get("events_updated", 0),
            "live_details_with_timeline": live_stats.get("details_with_timeline", 0),
        }
        self.repository.upsert_sync_state("fotmob", "football", "worker-football-post-match", stats)
        logger.debug(
            "[post-match-sync] persisted finished_matches_seen=%s competitions_refreshed=%s",
            len(finished_by_provider_id),
            len(definitions),
        )
        return stats
