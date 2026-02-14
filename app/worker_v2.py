import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Any

from app.core.config import FOTMOB_TARGET_LEAGUE_IDS
from app.services.database import DatabaseService
from app.services.points import PointsService
from app.services.scraper import ScraperService

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("WorkerV2")


class SoccerWorkerV2:
    def __init__(self) -> None:
        self.scraper = ScraperService()
        self.db = DatabaseService()
        self.points_calculator = PointsService()

        self.live_interval_active_seconds = 30
        self.live_interval_idle_seconds = 300

        self.settlement_retry_delays_seconds = [120, 600]

        self.backfill_hour = 5
        self.backfill_days = 3

        self.future_seed_hour = 3

        self._match_state: dict[int, dict[str, Any]] = {}
        self._pending_settlements: dict[int, dict[str, Any]] = {}

    def _get_val(self, obj: Any, attr_name: str, default: Any = None) -> Any:
        if hasattr(obj, attr_name):
            value = getattr(obj, attr_name)
            return value if value is not None else default
        if isinstance(obj, dict):
            return obj.get(attr_name, default)
        return default

    def _normalize_status(self, status_raw: Any) -> str:
        if hasattr(status_raw, "value"):
            return str(status_raw.value)
        if hasattr(status_raw, "short"):
            return str(status_raw.short)
        if isinstance(status_raw, dict):
            return str(status_raw.get("short", "NS"))
        return str(status_raw)

    def _parse_score(self, result_str: str | None) -> tuple[int, int] | None:
        if not result_str:
            return None
        cleaned = result_str.replace(" ", "")
        if "-" not in cleaned:
            return None
        left, right = cleaned.split("-", maxsplit=1)
        if not left.isdigit() or not right.isdigit():
            return None
        return int(left), int(right)

    async def _run_db(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def _update_events_for_matches(self, match_ids: list[int], concurrency: int = 6) -> None:
        if not match_ids:
            return

        sem = asyncio.Semaphore(concurrency)

        async def _one(match_id: int) -> None:
            async with sem:
                events = await self.scraper.get_match_details(match_id)
                if events:
                    await self._run_db(self.db.save_match_events, match_id, events)

        await asyncio.gather(*(_one(mid) for mid in match_ids), return_exceptions=True)

    async def _update_standings_for_leagues(self, league_ids: set[int]) -> None:
        if not league_ids:
            return

        for league_id in league_ids:
            try:
                standings = await self.scraper.get_standings(league_id)
                if standings:
                    await self._run_db(self.db.save_standings, league_id, standings)
            except Exception as exc:
                logger.error("Failed standings update for league %s: %s", league_id, exc)

    def _schedule_settlement(self, match_id: int, result_str: str | None) -> None:
        parsed_score = self._parse_score(result_str)
        if not parsed_score:
            return

        existing = self._pending_settlements.get(match_id)
        if existing:
            existing["score"] = parsed_score
            return

        self._pending_settlements[match_id] = {
            "score": parsed_score,
            "attempt": 0,
            "next_run_ts": time.time(),
        }

    async def live_monitor_job(self) -> None:
        logger.info("Starting live monitor job")

        while True:
            cycle_start = time.time()
            try:
                matches_data = await self.scraper.get_live_matches_fotmob()

                if not matches_data:
                    logger.info("No competitions returned for today")
                    await asyncio.sleep(self.live_interval_idle_seconds)
                    continue

                await self._run_db(self.db.save_matches, matches_data)

                active_match_ids: list[int] = []
                finished_leagues: set[int] = set()

                for league in matches_data:
                    league_id = int(self._get_val(league, "id", 0) or 0)
                    matches = self._get_val(league, "matches", [])

                    for match in matches:
                        match_id = int(self._get_val(match, "id", 0) or 0)
                        if not match_id:
                            continue

                        status = self._normalize_status(self._get_val(match, "status", "NS"))
                        result = self._get_val(match, "result")

                        previous = self._match_state.get(match_id)

                        if status == "LIVE":
                            active_match_ids.append(match_id)

                        if status in {"FT", "AET", "AP"}:
                            prev_status = previous.get("status") if previous else None
                            prev_result = previous.get("result") if previous else None
                            if prev_status not in {"FT", "AET", "AP"} or prev_result != result:
                                self._schedule_settlement(match_id, result)
                                if league_id:
                                    finished_leagues.add(league_id)

                        self._match_state[match_id] = {
                            "status": status,
                            "result": result,
                            "league_id": league_id,
                        }

                if active_match_ids:
                    logger.info("Updating events for %s live matches", len(active_match_ids))
                    await self._update_events_for_matches(active_match_ids)

                if finished_leagues:
                    logger.info("Updating standings for %s leagues with newly finished matches", len(finished_leagues))
                    await self._update_standings_for_leagues(finished_leagues)

                elapsed = time.time() - cycle_start
                sleep_seconds = self.live_interval_active_seconds if active_match_ids else self.live_interval_idle_seconds
                logger.info("Live cycle completed in %.2fs, sleeping %.2fs", elapsed, sleep_seconds)
                await asyncio.sleep(sleep_seconds)

            except Exception as exc:
                logger.error("Critical error in live monitor job: %s", exc)
                traceback.print_exc()
                await asyncio.sleep(20)

    async def settlement_job(self) -> None:
        logger.info("Starting settlement job")

        while True:
            try:
                now = time.time()
                due_match_ids = [
                    match_id
                    for match_id, state in self._pending_settlements.items()
                    if state["next_run_ts"] <= now
                ]

                for match_id in due_match_ids:
                    state = self._pending_settlements.get(match_id)
                    if not state:
                        continue

                    home_score, away_score = state["score"]
                    await self.points_calculator.calculate_match_points(match_id, home_score, away_score)

                    attempt = state["attempt"]
                    if attempt < len(self.settlement_retry_delays_seconds):
                        state["attempt"] += 1
                        delay = self.settlement_retry_delays_seconds[attempt]
                        state["next_run_ts"] = time.time() + delay
                    else:
                        del self._pending_settlements[match_id]

                await asyncio.sleep(10)

            except Exception as exc:
                logger.error("Error in settlement job: %s", exc)
                traceback.print_exc()
                await asyncio.sleep(20)

    async def _sleep_until_hour(self, hour_24: int) -> None:
        now = datetime.now()
        target = now.replace(hour=hour_24, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

    async def daily_backfill_job(self) -> None:
        logger.info("Starting daily backfill job")

        while True:
            try:
                await self._sleep_until_hour(self.backfill_hour)
                logger.info("Running backfill for last %s day(s)", self.backfill_days)

                today = datetime.now().date()
                for offset in range(1, self.backfill_days + 1):
                    day = today - timedelta(days=offset)
                    day_str = day.strftime("%Y%m%d")

                    competitions = await self.scraper.get_live_matches_fotmob(target_date=day_str)
                    if not competitions:
                        continue

                    await self._run_db(self.db.save_matches, competitions)

                    finished_match_ids: list[int] = []
                    leagues_for_standings: set[int] = set()

                    for league in competitions:
                        league_id = int(self._get_val(league, "id", 0) or 0)
                        for match in self._get_val(league, "matches", []):
                            status = self._normalize_status(self._get_val(match, "status", "NS"))
                            if status in {"FT", "AET", "AP"}:
                                match_id = int(self._get_val(match, "id", 0) or 0)
                                if match_id:
                                    finished_match_ids.append(match_id)
                                    self._schedule_settlement(match_id, self._get_val(match, "result"))
                                    if league_id:
                                        leagues_for_standings.add(league_id)

                    await self._update_events_for_matches(finished_match_ids)
                    await self._update_standings_for_leagues(leagues_for_standings)

            except Exception as exc:
                logger.error("Error in daily backfill job: %s", exc)
                traceback.print_exc()
                await asyncio.sleep(60)

    async def daily_future_seed_job(self) -> None:
        logger.info("Starting daily future seed job")

        while True:
            try:
                await self._sleep_until_hour(self.future_seed_hour)
                logger.info("Running future fixtures seed for %s leagues", len(FOTMOB_TARGET_LEAGUE_IDS))

                for league_id in FOTMOB_TARGET_LEAGUE_IDS:
                    competitions = await self.scraper.get_all_season_matches(league_id)
                    if competitions:
                        await self._run_db(self.db.save_matches, competitions)

            except Exception as exc:
                logger.error("Error in daily future seed job: %s", exc)
                traceback.print_exc()
                await asyncio.sleep(60)

    async def run(self) -> None:
        logger.info("Starting SoccerWorkerV2")

        tasks = [
            asyncio.create_task(self.live_monitor_job(), name="live_monitor"),
            asyncio.create_task(self.settlement_job(), name="settlement"),
            asyncio.create_task(self.daily_backfill_job(), name="daily_backfill"),
            asyncio.create_task(self.daily_future_seed_job(), name="daily_future_seed"),
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    worker = SoccerWorkerV2()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker stopped manually")


if __name__ == "__main__":
    main()

