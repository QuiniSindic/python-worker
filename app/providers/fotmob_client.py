from __future__ import annotations

import json
import logging
import re
from html import unescape
from json import JSONDecodeError

import httpx

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

logger = logging.getLogger(__name__)


class FotmobPayloadError(ValueError):
    pass


_NEXT_DATA_PATTERN = re.compile(
    r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(?P<payload>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


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


def parse_fotmob_match_page_payload(html_text: str, url: str) -> dict:
    match = _NEXT_DATA_PATTERN.search(html_text)
    if not match:
        raise FotmobPayloadError(f"Embedded match payload not found in {url}")

    raw_payload = unescape(match.group("payload")).strip()
    if not raw_payload:
        raise FotmobPayloadError(f"Embedded match payload is empty in {url}")

    try:
        payload = json.loads(raw_payload)
    except JSONDecodeError as exc:
        raise FotmobPayloadError(f"Invalid embedded match payload in {url}") from exc

    if not isinstance(payload, dict):
        raise FotmobPayloadError(f"Unexpected embedded match payload in {url}")

    page_props = payload.get("props", {}).get("pageProps")
    if isinstance(page_props, dict):
        return page_props

    return payload


class FotmobClient:
    def __init__(self, timeout: float = 20.0, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}

    async def fetch_live_matches(self, date_str: str) -> dict:
        return await self._get_json(
            f"https://www.fotmob.com/api/data/matches?date={date_str}&timezone=Europe%2FMadrid&ccode3=ESP"
        )

    async def fetch_standings(self, league_id: int) -> dict | list:
        return await self._get_json(f"https://www.fotmob.com/api/data/tltable?leagueId={league_id}")

    async def fetch_match_details(self, match_id: int) -> dict:
        url = f"https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"
        try:
            return await self._get_json(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {401, 403}:
                raise
            logger.debug(
                "[fotmob] matchDetails blocked for match_id=%s status=%s, using HTML fallback",
                match_id,
                exc.response.status_code,
            )
            return await self._get_match_page_payload(match_id)
        except FotmobPayloadError:
            logger.debug(
                "[fotmob] matchDetails payload invalid for match_id=%s, using HTML fallback",
                match_id,
            )
            return await self._get_match_page_payload(match_id)

    async def fetch_league_season(self, league_id: int) -> dict:
        return await self._get_json(f"https://www.fotmob.com/api/data/leagues?id={league_id}")

    async def fetch_team(self, team_id: int) -> dict:
        return await self._get_json(
            f"https://www.fotmob.com/api/data/teams?id={team_id}&ccode3=ESP"
        )

    async def _get_json(self, url: str) -> dict | list:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers)
            return parse_fotmob_json_response(response, url)

    async def _get_match_page_payload(self, match_id: int) -> dict:
        entry_url = f"https://www.fotmob.com/match/{match_id}"

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.get(entry_url, headers=self.headers)

            page_url = self._resolve_match_page_url(response, entry_url)
            if page_url != entry_url:
                response = await client.get(page_url, headers=self.headers)
            response.raise_for_status()

        logger.debug("[fotmob] HTML fallback succeeded for match_id=%s page=%s", match_id, page_url)
        return parse_fotmob_match_page_payload(response.text, page_url)

    def _resolve_match_page_url(self, response: httpx.Response, fallback_url: str) -> str:
        if response.status_code not in {301, 302, 307, 308}:
            return str(response.request.url)

        location = response.headers.get("location") or response.text.strip()
        if not location:
            return fallback_url

        return str(httpx.URL(fallback_url).join(location))
