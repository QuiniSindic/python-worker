from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domains.football_v2.repository import FootballV2Repository
from app.domains.football_v2.scraper import ScraperService
from app.schemas.match import MatchData

logger = logging.getLogger(__name__)

RECOVERY_LOOKBACK_DAYS = 7
RECOVERY_GRACE_HOURS = 6
RECOVERY_MAX_EVENTS = 200


def _match_status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _map_status(status: str) -> str:
    return {
        "NS": "scheduled",
        "LIVE": "live",
        "FT": "finished",
        "AET": "finished",
        "AP": "finished",
        "Canc.": "cancelled",
    }.get(status, "scheduled")


def _parse_score(result: str) -> tuple[int | None, int | None]:
    if "-" not in result:
        return None, None
    left, right = result.split("-", maxsplit=1)
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None, None


def _default_target_dates() -> list[str]:
    today = datetime.now(UTC).date()
    return [(today + timedelta(days=offset)).strftime("%Y%m%d") for offset in (-1, 0, 1)]


def _recoverable_live_dates(
    repository: FootballV2Repository,
    *,
    now: datetime,
) -> list[str]:
    if not hasattr(repository, "list_recoverable_live_events"):
        return []
    stale_live_events = repository.list_recoverable_live_events(
        "fotmob",
        started_after=(now - timedelta(days=RECOVERY_LOOKBACK_DAYS)).isoformat(),
        started_before=(now - timedelta(hours=RECOVERY_GRACE_HOURS)).isoformat(),
        limit=RECOVERY_MAX_EVENTS,
    )
    dates: set[str] = set()
    for event in stale_live_events:
        start_at = event.get("start_at")
        if not start_at:
            continue
        try:
            kickoff = datetime.fromisoformat(start_at.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        dates.add(kickoff.strftime("%Y%m%d"))
    return sorted(dates)


def _resolve_target_dates(
    repository: FootballV2Repository,
    target_dates: list[str] | None = None,
    *,
    now: datetime | None = None,
) -> list[str]:
    resolved_now = now or datetime.now(UTC)
    dates = set(target_dates or _default_target_dates())
    dates.update(_recoverable_live_dates(repository, now=resolved_now))
    return sorted(dates)


class FootballLiveSyncService:
    def __init__(
        self,
        repository: FootballV2Repository | None = None,
        scraper: ScraperService | None = None,
    ) -> None:
        self.repository = repository or FootballV2Repository()
        self.scraper = scraper or ScraperService()

    async def run(self, target_dates: list[str] | None = None) -> dict[str, int]:
        dates = _resolve_target_dates(self.repository, target_dates)
        live_by_provider_id: dict[str, MatchData] = {}

        logger.debug("[live-sync] scanning dates=%s", ",".join(dates))
        for date_str in dates:
            competitions = await self.scraper.get_live_matches_fotmob(date_str)
            logger.debug(
                "[live-sync] date=%s competitions=%s",
                date_str,
                len(competitions),
            )
            for competition in competitions:
                for match in competition.matches:
                    live_by_provider_id[str(match.id)] = match

        if not live_by_provider_id:
            stats = {
                "dates_synced": len(dates),
                "matches_seen": 0,
                "events_updated": 0,
                "details_updated": 0,
                "missing_events": 0,
            }
            self.repository.upsert_sync_state("fotmob", "football", "worker-football-live", stats)
            logger.debug("[live-sync] no matches found for scanned dates")
            return stats

        existing_events = self.repository.list_events_by_provider_event_ids(
            "fotmob", list(live_by_provider_id)
        )
        if not existing_events:
            stats = {
                "dates_synced": len(dates),
                "matches_seen": len(live_by_provider_id),
                "events_updated": 0,
                "details_updated": 0,
                "missing_events": len(live_by_provider_id),
            }
            self.repository.upsert_sync_state("fotmob", "football", "worker-football-live", stats)
            logger.warning(
                "[live-sync] found %s provider matches but none are mapped to local events",
                len(live_by_provider_id),
            )
            return stats

        event_ids = [row["id"] for row in existing_events]
        football_rows = {
            row["event_id"]: row for row in self.repository.list_football_event_rows(event_ids)
        }
        detailed_match_ids = [
            int(provider_event_id)
            for provider_event_id, match in live_by_provider_id.items()
            if _match_status_value(match.status) != "NS"
        ]
        detail_results = await asyncio.gather(
            *(self.scraper.get_match_details(match_id) for match_id in detailed_match_ids)
        )
        details_by_match_id = {
            match_id: details
            for match_id, details in zip(detailed_match_ids, detail_results, strict=False)
        }
        details_with_timeline = sum(1 for details in details_by_match_id.values() if details)
        details_empty = len(details_by_match_id) - details_with_timeline
        if detailed_match_ids:
            logger.debug(
                "[live-sync] matched_events=%s detail_requests=%s timelines_with_events=%s empty_timelines=%s",
                len(existing_events),
                len(detailed_match_ids),
                details_with_timeline,
                details_empty,
            )

        now_iso = datetime.now(UTC).isoformat()
        event_payloads: list[dict[str, Any]] = []
        football_payloads: list[dict[str, Any]] = []

        for event in existing_events:
            provider_event_id = str(event["provider_event_id"])
            live_match = live_by_provider_id.get(provider_event_id)
            if not live_match:
                continue

            status_value = _match_status_value(live_match.status)
            home_score, away_score = _parse_score(live_match.result)
            football_event = football_rows.get(event["id"], {})

            event_payloads.append(
                {
                    "sport_id": event["sport_id"],
                    "competition_id": event["competition_id"],
                    "competition_season_id": event["competition_season_id"],
                    "competition_phase_id": event.get("competition_phase_id"),
                    "phase_group_id": event.get("phase_group_id"),
                    "parent_event_id": event.get("parent_event_id"),
                    "event_type": event["event_type"],
                    "slug": event.get("slug"),
                    "title": f"{live_match.homeTeam.name} vs {live_match.awayTeam.name}",
                    "provider_name": event["provider_name"],
                    "provider_event_id": provider_event_id,
                    "start_at": live_match.kickoff_iso or event["start_at"],
                    "end_at": event.get("end_at"),
                    "status": _map_status(status_value),
                    "sort_order": event.get("sort_order"),
                    "is_placeholder": live_match.homeId <= 0 or live_match.awayId <= 0,
                    "metadata": event.get("metadata") or {},
                    "last_synced_at": now_iso,
                    "updated_at": now_iso,
                }
            )
            football_payloads.append(
                {
                    "event_id": event["id"],
                    "minute": live_match.minute,
                    "status_detail": status_value,
                    "round_key": football_event.get("round_key"),
                    "round_label": live_match.round or football_event.get("round_label"),
                    "leg": football_event.get("leg"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "penalties_home": football_event.get("penalties_home"),
                    "penalties_away": football_event.get("penalties_away"),
                    "aggregate_home_score": football_event.get("aggregate_home_score"),
                    "aggregate_away_score": football_event.get("aggregate_away_score"),
                    "winner_participant_id": football_event.get("winner_participant_id"),
                    "timeline": details_by_match_id.get(
                        int(provider_event_id), football_event.get("timeline") or []
                    ),
                    "metadata": football_event.get("metadata") or {},
                }
            )

        self.repository.upsert_events(event_payloads)
        self.repository.upsert_football_events(football_payloads)

        stats = {
            "dates_synced": len(dates),
            "matches_seen": len(live_by_provider_id),
            "events_updated": len(event_payloads),
            "details_updated": len(details_by_match_id),
            "details_with_timeline": details_with_timeline,
            "empty_timelines": details_empty,
            "missing_events": len(live_by_provider_id) - len(event_payloads),
        }
        self.repository.upsert_sync_state("fotmob", "football", "worker-football-live", stats)
        logger.debug(
            "[live-sync] persisted events_updated=%s missing_events=%s "
            "details_updated=%s details_with_timeline=%s empty_timelines=%s",
            len(event_payloads),
            stats["missing_events"],
            len(details_by_match_id),
            details_with_timeline,
            details_empty,
        )
        return stats
