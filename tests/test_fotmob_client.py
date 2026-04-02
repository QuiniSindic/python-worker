from __future__ import annotations

import asyncio
import unittest

import httpx

from app.domains.football_v2.scraper import ScraperService
from app.providers.fotmob_client import FotmobPayloadError, parse_fotmob_json_response


class _PayloadErrorClient:
    async def fetch_standings(self, league_id: int) -> dict:
        raise FotmobPayloadError(f"Empty response from standings:{league_id}")


class _UnusedMapper:
    def map_standings_payload(self, payload: dict, league_id: int) -> dict:
        return {"league_id": league_id, "payload": payload}


class FotmobClientParsingTests(unittest.TestCase):
    def test_parse_json_response_accepts_json_without_content_type(self) -> None:
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.test/json"),
            content=b'{"ok": true}',
        )

        payload = parse_fotmob_json_response(response, "https://example.test/json")

        self.assertEqual(payload, {"ok": True})

    def test_parse_json_response_rejects_empty_body(self) -> None:
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.test/empty"),
            content=b"",
        )

        with self.assertRaises(FotmobPayloadError):
            parse_fotmob_json_response(response, "https://example.test/empty")

    def test_parse_json_response_rejects_non_json_body(self) -> None:
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "https://example.test/html"),
            headers={"content-type": "text/html"},
            content=b"<html>not json</html>",
        )

        with self.assertRaises(FotmobPayloadError):
            parse_fotmob_json_response(response, "https://example.test/html")

    def test_scraper_returns_none_for_payload_errors(self) -> None:
        scraper = ScraperService(client=_PayloadErrorClient(), mapper=_UnusedMapper())

        standings = asyncio.run(scraper.get_standings(132))

        self.assertIsNone(standings)
