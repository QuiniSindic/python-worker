from __future__ import annotations

import asyncio
import logging
import time

from app.domains.football_v2.live_sync import FootballLiveSyncService
from app.domains.football_v2.utils import configure_logging

logger = logging.getLogger(__name__)

class LiveMatchesWorker:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.live_sync = FootballLiveSyncService()
        
    async def start(self) -> None:
        cycle = 0
        
        while True:
            cycle += 1
            started_at = time.perf_counter()
            
            logger.info("[worker-football-live] cycle=%s started", cycle)
            
            try:
                stats = await self.live_sync.run()
                duration = time.perf_counter() - started_at
                logger.info(
                    "[worker-football-live] cycle=%s completed in %.2fs "
                    "(dates=%s, matches_seen=%s, events_updated=%s, details_updated=%s, "
                    "details_with_timeline=%s, empty_timelines=%s, missing_events=%s)",
                    cycle,
                    duration,
                    stats.get("dates_synced", 0),
                    stats.get("matches_seen", 0),
                    stats.get("events_updated", 0),
                    stats.get("details_updated", 0),
                    stats.get("details_with_timeline", 0),
                    stats.get("empty_timelines", 0),
                    stats.get("missing_events", 0),
                )
            except Exception:
                duration = time.perf_counter() - started_at
                
                logger.exception(
                    "[worker-football-live] cycle=%s failed after %.2fs",
                    cycle,
                    duration,
                )
                
                logger.debug(
                    "[worker-football-live] sleeping for %ss before next cycle",
                    self.interval_seconds,
                )
                
                await asyncio.sleep(self.interval_seconds)


def main() -> None:
    configure_logging()
    asyncio.run(LiveMatchesWorker().start())
