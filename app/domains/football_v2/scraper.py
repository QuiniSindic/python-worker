from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.core.config import FOTMOB_TARGET_LEAGUE_IDS
from app.providers.fotmob_client import FotmobClient, FotmobPayloadError
from app.providers.fotmob_mapper import FotmobMapper
from app.schemas.match import CompetitionData

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(
        self, client: FotmobClient | None = None, mapper: FotmobMapper | None = None
    ) -> None:
        self.client = client or FotmobClient()
        self.mapper = mapper or FotmobMapper()

    async def get_live_matches_fotmob(
        self, target_date: str | None = None
    ) -> list[CompetitionData]:
        date_str = target_date or datetime.now().strftime("%Y%m%d")
        try:
            payload = await self.client.fetch_live_matches(date_str)
            return self.mapper.map_live_matches_payload(payload, FOTMOB_TARGET_LEAGUE_IDS)
        except FotmobPayloadError as exc:
            logger.warning("FotMob live matches payload unavailable for %s: %s", date_str, exc)
        except httpx.HTTPError as exc:
            logger.error("FotMob live matches request failed for %s: %s", date_str, exc)
        except Exception as exc:
            logger.exception(
                "Unexpected error while mapping live matches for %s: %s", date_str, exc
            )
        return []

    async def get_standings(self, league_id: int) -> dict | None:
        try:
            payload = await self.client.fetch_standings(league_id)
            return self.mapper.map_standings_payload(payload, league_id)
        except FotmobPayloadError as exc:
            logger.warning("FotMob standings unavailable for league %s: %s", league_id, exc)
        except httpx.HTTPError as exc:
            logger.error("FotMob standings request failed for league %s: %s", league_id, exc)
        except Exception as exc:
            logger.exception(
                "Unexpected error while mapping standings for league %s: %s", league_id, exc
            )
        return None

    async def get_match_details(self, match_id: int) -> list[dict]:
        try:
            payload = await self.client.fetch_match_details(match_id)
            return self.mapper.map_match_details_payload(payload, match_id)
        except FotmobPayloadError as exc:
            logger.warning("FotMob match details payload unavailable for %s: %s", match_id, exc)
        except httpx.HTTPError as exc:
            logger.error("FotMob match details request failed for match %s: %s", match_id, exc)
        except Exception as exc:
            logger.exception(
                "Unexpected error while mapping match details for %s: %s", match_id, exc
            )
        return []

    async def get_all_season_matches(self, league_id: int) -> list[CompetitionData]:
        try:
            payload = await self.client.fetch_league_season(league_id)
            return self.mapper.map_season_matches_payload(payload)
        except FotmobPayloadError as exc:
            logger.warning("FotMob season payload unavailable for league %s: %s", league_id, exc)
        except httpx.HTTPError as exc:
            logger.error("FotMob season matches request failed for league %s: %s", league_id, exc)
        except Exception as exc:
            logger.exception(
                "Unexpected error while mapping season matches for league %s: %s", league_id, exc
            )
        return []
