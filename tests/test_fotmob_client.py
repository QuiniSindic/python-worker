from __future__ import annotations

import asyncio
import unittest

import httpx

from app.domains.football_v2.scraper import ScraperService
from app.providers.fotmob_client import (
    FotmobClient,
    FotmobPayloadError,
    parse_fotmob_json_response,
    parse_fotmob_match_page_payload,
)


class _PayloadErrorClient:
    async def fetch_standings(self, league_id: int) -> dict:
        raise FotmobPayloadError(f"Empty response from standings:{league_id}")


class _UnusedMapper:
    def map_standings_payload(self, payload: dict, league_id: int) -> dict:
        return {"league_id": league_id, "payload": payload}


class _FallbackFotmobClient(FotmobClient):
    async def _get_json(self, url: str) -> dict | list:
        request = httpx.Request("GET", url)
        response = httpx.Response(
            403, request=request, content=b'{"error":"Verification required"}'
        )
        raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

    async def _get_match_page_payload(self, match_id: int) -> dict:
        return {
            "content": {
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "Goal",
                                "time": 74,
                                "player": {"id": 915264, "name": "Randy Nteka"},
                            }
                        ]
                    }
                }
            }
        }


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

    def test_parse_match_page_payload_extracts_next_data(self) -> None:
        html = """
        <html>
          <body>
            <script id="__NEXT_DATA__" type="application/json">
              {"props":{"pageProps":{"content":{"matchFacts":{"events":{"events":[{"type":"Goal","time":74}]}}}}}}
            </script>
          </body>
        </html>
        """

        payload = parse_fotmob_match_page_payload(html, "https://example.test/match/4837408")

        events = payload["content"]["matchFacts"]["events"]["events"]
        self.assertEqual(events[0]["type"], "Goal")
        self.assertEqual(events[0]["time"], 74)

    def test_fetch_match_details_falls_back_to_match_page_on_403(self) -> None:
        client = _FallbackFotmobClient()

        payload = asyncio.run(client.fetch_match_details(4837408))

        events = payload["content"]["matchFacts"]["events"]["events"]
        self.assertEqual(events[0]["player"]["name"], "Randy Nteka")

    def test_scraper_returns_none_for_payload_errors(self) -> None:
        scraper = ScraperService(client=_PayloadErrorClient(), mapper=_UnusedMapper())

        standings = asyncio.run(scraper.get_standings(132))

        self.assertIsNone(standings)
