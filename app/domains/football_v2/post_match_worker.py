from __future__ import annotations

import asyncio
import logging
import time

from app.domains.football_v2.post_match_sync import FootballPostMatchSyncService

logger = logging.getLogger(__name__)


def _configure_worker_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    for logger_name in ("httpx", "httpcore", "postgrest", "supabase"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


async def run_worker(interval_seconds: int = 300) -> None:
    post_match_sync = FootballPostMatchSyncService()
    cycle = 0
    while True:
        cycle += 1
        started_at = time.perf_counter()
        logger.debug("[worker-football-post-match] cycle=%s started", cycle)
        try:
            stats = await post_match_sync.run()
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
            interval_seconds,
        )
        await asyncio.sleep(interval_seconds)


def main() -> None:
    _configure_worker_logging()
    asyncio.run(run_worker())
