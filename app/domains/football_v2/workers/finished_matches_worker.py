from __future__ import annotations

import asyncio
import logging
import time

from app.domains.football_v2.jobs.sync_finished_matches_job import FootballPostMatchSyncService
from app.domains.football_v2.utils import configure_logging

logger = logging.getLogger(__name__)

class FinishedMatchesWorker:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.post_match_sync = FootballPostMatchSyncService()
        
    async def start(self) -> None:
        cycle = 0
        
        while True:
            cycle += 1
            started_at = time.perf_counter()
            
            logger.debug("[worker-football-post-match] cycle=%s started", cycle)            
            
            try:
                stats = await self.post_match_sync.run()
                duration = time.perf_counter() - started_at
                
                refreshed_slugs = stats.get("refreshed_slugs", [])
                refreshed_suffix = f", refreshed={','.join(refreshed_slugs)}" if refreshed_slugs else ""
            
                
                logger.info(
                    "[worker-football-post-match] cycle=%s completed in %.2fs "
                    "(dates=%s, finished_matches_seen=%s, competitions_refreshed=%s, "
                    "live_events_updated=%s, live_details_with_timeline=%s%s)",
                    cycle,
                    duration,
                    stats.get("dates_scanned", 0),
                    stats.get("finished_matches_seen", 0),
                    stats.get("competitions_refreshed", 0),
                    stats.get("live_events_updated", 0),
                    stats.get("live_details_with_timeline", 0),
                    refreshed_suffix,
                )
            except Exception:
                duration = time.perf_counter() - started_at
                
                logger.exception(
                    "[worker-football-post-match] cycle=%s failed after %.2fs",
                    cycle,
                    duration,
                )
                
                logger.debug(
                    "[worker-football-post-match] sleeping for %ss before next cycle",
                     self.interval_seconds,
                )
                
                await asyncio.sleep(self.interval_seconds)



def main() -> None:
    configure_logging()
    asyncio.run(FinishedMatchesWorker().start())