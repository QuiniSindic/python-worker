from __future__ import annotations

from json import JSONDecodeError

import httpx

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class FotmobPayloadError(ValueError):
    pass


def parse_fotmob_json_response(response: httpx.Response, url: str) -> dict | list:
    response.raise_for_status()
    text = response.text.strip()
    if not text:
        raise FotmobPayloadError(f"Empty response from {url}")

    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type and not text.startswith(("{", "[")):
        snippet = " ".join(text.split())[:120]
        raise FotmobPayloadError(f"Non-JSON response from {url}: {snippet or '<empty>'}")

    try:
        return response.json()
    except JSONDecodeError as exc:
        snippet = " ".join(text.split())[:120]
        raise FotmobPayloadError(
            f"Invalid JSON response from {url}: {snippet or '<empty>'}"
        ) from exc


class FotmobClient:
    def __init__(self, timeout: float = 20.0, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}

    async def fetch_live_matches(self, date_str: str) -> dict:
        return await self._get_json(f"https://www.fotmob.com/api/data/matches?date={date_str}")

    async def fetch_standings(self, league_id: int) -> dict | list:
        return await self._get_json(f"https://www.fotmob.com/api/data/tltable?leagueId={league_id}")

    async def fetch_match_details(self, match_id: int) -> dict:
        return await self._get_json(
            f"https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"
        )

    async def fetch_league_season(self, league_id: int) -> dict:
        return await self._get_json(f"https://www.fotmob.com/api/data/leagues?id={league_id}")

    async def _get_json(self, url: str) -> dict | list:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers)
            return parse_fotmob_json_response(response, url)
