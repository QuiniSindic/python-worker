from __future__ import annotations

import asyncio
import logging

from app.domains.football_v2.bootstrap import FootballBootstrapService

logger = logging.getLogger(__name__)


async def run_worker(interval_seconds: int = 300) -> None:
    bootstrap = FootballBootstrapService()
    while True:
        logger.info("Starting football v2 sync cycle")
        await bootstrap.run()
        logger.info("Football v2 sync cycle completed, sleeping %ss", interval_seconds)
        await asyncio.sleep(interval_seconds)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_worker())
