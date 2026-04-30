from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.domains.football_v2.catalog import FOOTBALL_COMPETITIONS, FootballCompetitionDefinition
from app.domains.football_v2.competition_structure_service import (
    FootballCompetitionStructureService,
)
from app.domains.football_v2.repository import FootballV2Repository
from app.domains.football_v2.scraper import ScraperService
from app.domains.football_v2.season import SeasonRule, resolve_current_season
from app.schemas.football import CompetitionStandingsSnapshotResponse, StandingsGroupResponse

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "unknown"


def _parse_score(result: str) -> tuple[int | None, int | None]:
    if "-" not in result:
        return None, None
    left, right = result.split("-", maxsplit=1)
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None, None


def _map_status(status: str) -> str:
    return {
        "NS": "scheduled",
        "LIVE": "live",
        "FT": "finished",
        "AET": "finished",
        "AP": "finished",
        "Canc.": "cancelled",
    }.get(status, "scheduled")


def _normalize_standings_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_groups: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        normalized_group = dict(group)
        normalized_group["id"] = str(group.get("id") or f"group-{index}")
        normalized_group["name"] = str(group.get("name") or normalized_group["id"])
        normalized_group["order"] = int(group.get("order", index))

        normalized_teams: list[dict[str, Any]] = []
        for team in group.get("teams", []):
            normalized_team = dict(team)
            normalized_team["id"] = str(team["id"])
            normalized_teams.append(normalized_team)
        normalized_group["teams"] = normalized_teams
        normalized_groups.append(normalized_group)

    return normalized_groups


class FootballBootstrapService:
    def __init__(
        self,
        repository: FootballV2Repository | None = None,
        scraper: ScraperService | None = None,
    ) -> None:
        self.repository = repository or FootballV2Repository()
        self.scraper = scraper or ScraperService()
        self.structure_service = FootballCompetitionStructureService()

    async def run(self) -> dict[str, int]:
        sport = self.repository.get_sport_by_slug("football")
        if not sport:
            raise RuntimeError("Sport 'football' not found. Run core seed migration first.")

        return await self.run_for_definitions(
            FOOTBALL_COMPETITIONS,
            sport_id=sport["id"],
            state_key="bootstrap-football",
        )

    async def run_for_definitions(
        self,
        definitions: list[FootballCompetitionDefinition]
        | tuple[FootballCompetitionDefinition, ...],
        *,
        sport_id: int | None = None,
        state_key: str | None = None,
    ) -> dict[str, int]:
        resolved_sport_id = sport_id
        if resolved_sport_id is None:
            sport = self.repository.get_sport_by_slug("football")
            if not sport:
                raise RuntimeError("Sport 'football' not found. Run core seed migration first.")
            resolved_sport_id = sport["id"]

        totals = defaultdict(int)
        for definition in definitions:
            logger.info("Bootstrapping football competition %s", definition.slug)
            stats = await self._sync_competition(resolved_sport_id, definition)
            for key, value in stats.items():
                totals[key] += value
        if state_key:
            self.repository.upsert_sync_state("fotmob", "football", state_key, dict(totals))
        return dict(totals)

    async def _sync_competition(
        self, sport_id: int, definition: FootballCompetitionDefinition
    ) -> dict[str, int]:
        competition_row = self.repository.upsert_competition(
            {
                "sport_id": sport_id,
                "slug": definition.slug,
                "name": definition.name,
                "short_name": definition.short_name,
                "country_code": definition.country_code,
                "competition_kind": definition.competition_kind,
                "participant_scope": definition.participant_scope,
                "gender": "men",
                "variant_key": "regular",
                "provider_name": "fotmob",
                "provider_competition_id": str(definition.fotmob_id),
                "is_active": True,
                "metadata": {"format_kind": definition.format_kind},
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

        resolved_season = resolve_current_season(
            SeasonRule(
                season_type=definition.season_type,
                season_start_month=definition.season_start_month,
            )
        )
        season_row = self.repository.upsert_season(
            {
                "competition_id": competition_row["id"],
                "season_key": resolved_season.season_key,
                "season_label": resolved_season.season_label,
                "season_type": resolved_season.season_type,
                "format_kind": definition.format_kind,
                "start_at": resolved_season.start_at.isoformat(),
                "end_at": resolved_season.end_at.isoformat(),
                "is_current": True,
                "metadata": {"source": "fotmob"},
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

        competitions = await self.scraper.get_all_season_matches(definition.fotmob_id)
        standings_data = await self.scraper.get_standings(definition.fotmob_id)
        match_rows = competitions[0].matches if competitions else []
        standings_snapshot = (
            CompetitionStandingsSnapshotResponse(
                competitionId=competition_row["id"],
                stageId=standings_data["stageId"],
                stageName=standings_data["stageName"],
                stageType=standings_data["stageType"],
                groups=[
                    StandingsGroupResponse(**group)
                    for group in _normalize_standings_groups(standings_data["groups"])
                ],
            )
            if standings_data
            else None
        )

        stage_responses = self.structure_service.build_stages(
            definition.fotmob_id,
            [match.model_dump() for match in match_rows],
            standings_snapshot,
        )
        phase_rows = self.repository.upsert_phases(
            [
                {
                    "competition_season_id": season_row["id"],
                    "key": stage.id,
                    "name": stage.name,
                    "phase_type": self._phase_type(stage.stageType),
                    "order_index": stage.order,
                    "is_standings_phase": stage.stageType in {"league_table", "group"},
                    "is_bracket_phase": stage.stageType == "knockout_round",
                    "metadata": {"round_labels": stage.roundLabels},
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                for stage in stage_responses
            ]
        )
        phases_by_key = {row["key"]: row for row in phase_rows}

        group_payloads: list[dict[str, Any]] = []
        if standings_snapshot:
            phase_row = phases_by_key.get(standings_snapshot.stageId)
            if phase_row:
                for group in standings_snapshot.groups:
                    group_payloads.append(
                        {
                            "competition_phase_id": phase_row["id"],
                            "key": group.id,
                            "name": group.name,
                            "order_index": group.order,
                            "metadata": {},
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )
        group_rows = self.repository.upsert_groups(group_payloads)
        group_lookup = {
            (
                next(
                    (
                        phase["key"]
                        for phase in phase_rows
                        if phase["id"] == row["competition_phase_id"]
                    ),
                    "",
                ),
                row["key"],
            ): row
            for row in group_rows
        }

        participant_payloads: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()
        for match in match_rows:
            for team in (match.homeTeam, match.awayTeam):
                if team.id <= 0:
                    continue
                slug = f"team-{team.id}-{_slugify(team.name)}"
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                participant_payloads.append(
                    {
                        "sport_id": sport_id,
                        "kind": "team",
                        "slug": slug,
                        "code": team.abbr,
                        "name": team.name,
                        "short_name": team.abbr,
                        "country_code": team.country or definition.country_code,
                        "badge_url": team.img,
                        "metadata": {"provider_team_id": team.id},
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                )
        if standings_snapshot:
            for group in standings_snapshot.groups:
                for team in group.teams:
                    slug = f"team-{team.id}-{_slugify(team.name)}"
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    participant_payloads.append(
                        {
                            "sport_id": sport_id,
                            "kind": "team",
                            "slug": slug,
                            "code": None,
                            "name": team.name,
                            "short_name": team.name,
                            "country_code": definition.country_code,
                            "badge_url": team.badge,
                            "metadata": {"provider_team_id": int(team.id)},
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )
        participants = self.repository.upsert_participants(participant_payloads)
        participants_by_provider_id = {
            int(row["metadata"]["provider_team_id"]): row
            for row in participants
            if isinstance(row.get("metadata"), dict)
            and row["metadata"].get("provider_team_id") is not None
        }
        self.repository.upsert_season_participants(
            [
                {
                    "competition_season_id": season_row["id"],
                    "participant_id": row["id"],
                    "role": "entrant",
                    "metadata": {},
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                for row in participants
            ]
        )

        event_payloads: list[dict[str, Any]] = []
        football_rows_by_provider: dict[str, dict[str, Any]] = {}
        slots_by_provider: dict[str, list[dict[str, Any]]] = {}
        for match in match_rows:
            provider_event_id = str(match.id)
            stage_key = self._match_stage_key(definition.fotmob_id, match.round, standings_snapshot)
            phase = phases_by_key.get(stage_key) if stage_key else None
            home_score, away_score = _parse_score(match.result)
            event_payloads.append(
                {
                    "sport_id": sport_id,
                    "competition_id": competition_row["id"],
                    "competition_season_id": season_row["id"],
                    "competition_phase_id": phase["id"] if phase else None,
                    "phase_group_id": None,
                    "parent_event_id": None,
                    "event_type": "match",
                    "slug": provider_event_id,
                    "title": f"{match.homeTeam.name} vs {match.awayTeam.name}",
                    "provider_name": "fotmob",
                    "provider_event_id": provider_event_id,
                    "start_at": match.kickoff_iso or datetime.now(UTC).isoformat(),
                    "status": _map_status(match.status.value),
                    "sort_order": phase["order_index"] if phase else 0,
                    "is_placeholder": match.homeId <= 0 or match.awayId <= 0,
                    "metadata": {"competition_slug": definition.slug},
                    "last_synced_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
            football_rows_by_provider[provider_event_id] = {
                "minute": match.minute,
                "status_detail": match.status.value,
                "round_key": stage_key,
                "round_label": match.round,
                "leg": None,
                "home_score": home_score,
                "away_score": away_score,
                "penalties_home": None,
                "penalties_away": None,
                "aggregate_home_score": None,
                "aggregate_away_score": None,
                "winner_participant_id": None,
                "timeline": [],
                "metadata": {},
            }
            slots_by_provider[provider_event_id] = [
                {
                    "slot_key": "home",
                    "slot_order": 0,
                    "participant_id": participants_by_provider_id.get(match.homeId, {}).get("id"),
                    "placeholder_label": None if match.homeId > 0 else match.homeTeam.name,
                    "is_placeholder": match.homeId <= 0,
                    "metadata": {},
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                {
                    "slot_key": "away",
                    "slot_order": 1,
                    "participant_id": participants_by_provider_id.get(match.awayId, {}).get("id"),
                    "placeholder_label": None if match.awayId > 0 else match.awayTeam.name,
                    "is_placeholder": match.awayId <= 0,
                    "metadata": {},
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            ]
        events = self.repository.upsert_events(event_payloads)
        self.repository.upsert_event_participants(
            [
                {"event_id": event["id"], **slot}
                for event in events
                for slot in slots_by_provider[event["provider_event_id"]]
            ]
        )
        self.repository.upsert_football_events(
            [
                {"event_id": event["id"], **football_rows_by_provider[event["provider_event_id"]]}
                for event in events
            ]
        )
        self.repository.upsert_provider_refs(
            [
                {
                    "provider_name": "fotmob",
                    "resource_type": "event",
                    "external_id": event["provider_event_id"],
                    "internal_table": "events",
                    "internal_id": event["id"],
                    "metadata": {"competition_slug": definition.slug},
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                for event in events
            ]
            + [
                {
                    "provider_name": "fotmob",
                    "resource_type": "competition",
                    "external_id": str(definition.fotmob_id),
                    "internal_table": "competitions",
                    "internal_id": competition_row["id"],
                    "metadata": {"slug": definition.slug},
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]
        )

        standings_payloads: list[dict[str, Any]] = []
        if standings_snapshot:
            phase = phases_by_key.get(standings_snapshot.stageId)
            if phase:
                for group in standings_snapshot.groups:
                    group_row = group_lookup.get((standings_snapshot.stageId, group.id))
                    if not group_row:
                        continue
                    for team in group.teams:
                        participant = participants_by_provider_id.get(int(team.id))
                        if not participant:
                            continue
                        standings_payloads.append(
                            {
                                "competition_season_id": season_row["id"],
                                "competition_phase_id": phase["id"],
                                "phase_group_id": group_row["id"],
                                "participant_id": participant["id"],
                                "position": team.position,
                                "played": team.played,
                                "wins": team.wins,
                                "draws": team.draws,
                                "losses": team.losses,
                                "points": team.points,
                                "goals_for": team.goalsFor,
                                "goals_against": team.goalsAgainst,
                                "goal_difference": team.goalDifference,
                                "form": [item.model_dump() for item in team.form],
                                "metadata": {},
                                "updated_at": datetime.now(UTC).isoformat(),
                            }
                        )
        self.repository.replace_standings(season_row["id"], standings_payloads)

        return {
            "competitions": 1,
            "seasons": 1,
            "participants": len(participants),
            "events": len(events),
            "standings_rows": len(standings_payloads),
        }

    def _phase_type(self, stage_type: str) -> str:
        if stage_type == "group":
            return "group_stage"
        if stage_type == "knockout_round":
            return "knockout_round"
        return "league_table"

    def _match_stage_key(
        self,
        competition_id: int,
        round_label: str | None,
        standings_snapshot: CompetitionStandingsSnapshotResponse | None,
    ) -> str | None:
        meta = self.structure_service.resolve_knockout_stage_meta(competition_id, round_label)
        if meta:
            return meta.id
        if standings_snapshot:
            return standings_snapshot.stageId
        return None
