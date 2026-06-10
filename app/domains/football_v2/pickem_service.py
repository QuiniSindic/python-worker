from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.domains.football_v2.competition_structure_service import get_knockout_round_meta
from app.domains.football_v2.pickem_repository import PickemRepository
from app.domains.football_v2.pickem_scoring import (
    DEFAULT_PICKEM_SCORING_CONFIG,
    score_award_pick,
    score_group_order_pick,
    score_match_pick,
)
from app.domains.football_v2.scraper import ScraperService
from app.schemas.auth import AuthenticatedUser
from app.schemas.pickem import (
    PickemAwardCandidateResponse,
    PickemAwardPickResponse,
    PickemAwardPicksPayload,
    PickemAwardResultsPayload,
    PickemContestResponse,
    PickemEntryResponse,
    PickemGroupOrderPicksPayload,
    PickemGroupPickResponse,
    PickemGroupResponse,
    PickemGroupTeamResponse,
    PickemLeaderboardEntry,
    PickemMatchPickPayload,
    PickemMatchPickResponse,
    PickemSquadImportStats,
    PickemTeamResponse,
)

AWARD_KEYS = {"mvp", "top_scorer", "best_goalkeeper"}
WORLD_CUP_GROUP_KEYS = {f"group_{letter}" for letter in "abcdefghijkl"}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _player_position(player: dict) -> str:
    if player.get("position_id") == 0 or player.get("group") == "keepers":
        return "GK"
    group = str(player.get("group") or "").lower()
    if "def" in group:
        return "DF"
    if "mid" in group:
        return "MF"
    return "FW"


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str) or not any(marker in value for marker in ("Ã", "Â")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


class PickemService:
    def __init__(
        self,
        repository: PickemRepository | None = None,
        scraper: ScraperService | None = None,
    ) -> None:
        self.repository = repository or PickemRepository()
        self.scraper = scraper or ScraperService()

    def get_current_contest(
        self, competition_slug: str = "fifa-world-cup"
    ) -> PickemContestResponse:
        contest = self.repository.get_current_contest(competition_slug)
        if contest is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickem not found")
        return self._map_contest(contest)

    def get_entry(self, contest_id: int, user: AuthenticatedUser) -> PickemEntryResponse:
        contest = self._require_contest(contest_id)
        entry = self.repository.get_or_create_entry(contest_id, user.id)
        return self._map_entry(contest, entry)

    def save_group_picks(
        self,
        contest_id: int,
        payload: PickemGroupOrderPicksPayload,
        user: AuthenticatedUser,
    ) -> PickemEntryResponse:
        contest = self._require_contest(contest_id)
        if _now() >= _parse_dt(contest["group_deadline"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Group picks locked"
            )

        groups = self._groups_for_contest(contest)
        groups_by_id = {group["id"]: group for group in groups}
        standings_by_group = self._standings_by_group(contest["competition_season_id"])
        expected_group_ids = set(groups_by_id)
        payload_group_ids = {group.group_id for group in payload.groups}
        if payload_group_ids != expected_group_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid groups")

        picks: list[dict[str, Any]] = []
        for group_pick in payload.groups:
            actual_rows = standings_by_group.get(group_pick.group_id, [])
            expected_participant_ids = {row["participant_id"] for row in actual_rows}
            predicted_participant_ids = set(group_pick.participant_ids)
            if predicted_participant_ids != expected_participant_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid group participants",
                )
            for position, participant_id in enumerate(group_pick.participant_ids, start=1):
                picks.append(
                    {
                        "phase_group_id": group_pick.group_id,
                        "participant_id": participant_id,
                        "predicted_position": position,
                    }
                )

        entry = self.repository.get_or_create_entry(contest_id, user.id)
        self.repository.replace_group_picks(entry["id"], picks)
        self.score_contest(contest_id)
        refreshed = self.repository.get_or_create_entry(contest_id, user.id)
        return self._map_entry(contest, refreshed)

    def save_award_picks(
        self,
        contest_id: int,
        payload: PickemAwardPicksPayload,
        user: AuthenticatedUser,
    ) -> PickemEntryResponse:
        contest = self._require_contest(contest_id)
        if _now() >= _parse_dt(contest["awards_deadline"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Award picks locked"
            )

        candidates = self.repository.list_award_candidates(contest_id)
        participant_ids = self._contest_group_participant_ids(contest)
        picks = [
            {"award_key": "mvp", "candidate_id": payload.mvp_candidate_id, "participant_id": None},
            {
                "award_key": "top_scorer",
                "candidate_id": payload.top_scorer_candidate_id,
                "participant_id": None,
            },
            {
                "award_key": "best_goalkeeper",
                "candidate_id": payload.best_goalkeeper_candidate_id,
                "participant_id": None,
            },
            {
                "award_key": "champion",
                "candidate_id": None,
                "participant_id": payload.champion_participant_id,
            },
        ]
        for pick in picks:
            if pick["award_key"] == "champion":
                if pick["participant_id"] not in participant_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid champion participant",
                    )
                continue
            candidate = next(
                (
                    row
                    for row in candidates
                    if row["id"] == pick["candidate_id"] and row["award_key"] == pick["award_key"]
                ),
                None,
            )
            if candidate is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid award candidate",
                )

        entry = self.repository.get_or_create_entry(contest_id, user.id)
        self.repository.replace_award_picks(entry["id"], picks)
        self.score_contest(contest_id)
        refreshed = self.repository.get_or_create_entry(contest_id, user.id)
        return self._map_entry(contest, refreshed)

    def save_match_pick(
        self,
        contest_id: int,
        event_id: int,
        payload: PickemMatchPickPayload,
        user: AuthenticatedUser,
    ) -> PickemMatchPickResponse:
        contest = self._require_contest(contest_id)
        event = self.repository.get_match(event_id)
        if event is None or event["competition_season_id"] != contest["competition_season_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if _now() >= _parse_dt(event["start_at"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Match pick locked")

        participant_ids = {
            row["participant_id"]
            for row in self.repository.list_match_competitors(event_id)
            if row.get("participant_id") is not None
        }
        if len(participant_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Match participants are not resolved",
            )
        if payload.winner_participant_id not in participant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid winner")

        entry = self.repository.get_or_create_entry(contest_id, user.id)
        row = self.repository.upsert_match_pick(
            entry["id"],
            event_id,
            {
                "winner_participant_id": payload.winner_participant_id,
                "home_score": payload.home_score,
                "away_score": payload.away_score,
            },
        )
        self.score_contest(contest_id)
        return self._map_match_pick(row)

    async def sync_squads_from_fotmob(self, contest_id: int) -> PickemSquadImportStats:
        contest = self._require_contest(contest_id)
        participant_ids = self._contest_group_participant_ids(contest)
        competitors = {
            row["id"]: row for row in self.repository.list_competitors(list(participant_ids))
        }
        player_payloads: dict[str, dict[str, Any]] = {}
        synced_competitor_ids: set[int] = set()
        teams_processed = 0

        for competitor in competitors.values():
            metadata = competitor.get("metadata") or {}
            provider_team_id = metadata.get("provider_team_id")
            if provider_team_id is None:
                continue
            teams_processed += 1
            squad = await self.scraper.get_team_squad(int(provider_team_id))
            if not squad:
                continue
            synced_competitor_ids.add(competitor["id"])
            for player in squad:
                provider_player_id = str(player["player_id"])
                player_payloads[provider_player_id] = {
                    "provider_name": "fotmob",
                    "provider_id": provider_player_id,
                    "competitor_id": competitor["id"],
                    "name": _clean_text(player["name"]),
                    "position": _player_position(player),
                    "shirt_number": player.get("shirt_number"),
                    "club_name": _clean_text(player.get("club_name")),
                    "is_active": True,
                }

        self.repository.deactivate_missing_pickem_players(
            contest_id,
            set(player_payloads),
            synced_competitor_ids,
        )
        players = self.repository.upsert_pickem_players(contest_id, list(player_payloads.values()))
        candidate_rows = self.repository.list_award_candidates(contest_id)
        return PickemSquadImportStats(
            teams_processed=teams_processed,
            players_upserted=len(players),
            squad_players_upserted=len(players),
            candidates_upserted=len(candidate_rows),
        )

    def save_award_results(self, contest_id: int, payload: PickemAwardResultsPayload) -> None:
        self._require_contest(contest_id)
        rows = []
        for result in payload.results:
            if result.award_key == "champion":
                if result.participant_id is None or result.candidate_id is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Champion result requires participant_id",
                    )
            elif result.award_key not in AWARD_KEYS or result.candidate_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Award result requires candidate_id",
                )
            rows.append(result.model_dump())
        self.repository.upsert_award_results(contest_id, rows)

    def get_leaderboard(self, contest_id: int) -> list[PickemLeaderboardEntry]:
        self._require_contest(contest_id)
        entries = self.repository.list_entries(contest_id)
        profiles = {
            row["id"]: row
            for row in self.repository.get_profiles([entry["user_id"] for entry in entries])
        }
        return [
            PickemLeaderboardEntry(
                user_id=row["user_id"],
                username=profiles.get(row["user_id"], {}).get("username", "Usuario"),
                avatar_url=profiles.get(row["user_id"], {}).get("img"),
                total_points=row["total_points"],
                group_points=row["group_points"],
                knockout_points=row["knockout_points"],
                award_points=row["award_points"],
                perfect_groups=row["perfect_groups"],
                exact_scores=row["exact_scores"],
            )
            for row in sorted(
                entries,
                key=lambda item: (
                    -int(item["total_points"]),
                    -int(item["perfect_groups"]),
                    -int(item["exact_scores"]),
                ),
            )
        ]

    def score_contest(self, contest_id: int) -> None:
        contest = self._require_contest(contest_id)
        config = self._scoring_config(contest)
        entries = self.repository.list_entries(contest_id)
        standings_by_group = self._standings_by_group(contest["competition_season_id"])
        award_results = {
            row["award_key"]: row for row in self.repository.list_award_results(contest_id)
        }
        for entry in entries:
            group_points, perfect_groups = self._score_entry_groups(
                entry["id"], contest["competition_season_id"], standings_by_group, config
            )
            knockout_points, exact_scores = self._score_entry_matches(entry["id"], config)
            award_points = self._score_entry_awards(entry["id"], award_results, config)
            self.repository.update_entry_scores(
                entry["id"],
                {
                    "total_points": group_points + knockout_points + award_points,
                    "group_points": group_points,
                    "knockout_points": knockout_points,
                    "award_points": award_points,
                    "perfect_groups": perfect_groups,
                    "exact_scores": exact_scores,
                },
            )

    def _score_entry_groups(
        self,
        entry_id: str,
        season_id: int,
        standings_by_group: dict[int, list[dict]],
        config: dict,
    ) -> tuple[int, int]:
        picks_by_group: dict[int, list[dict]] = defaultdict(list)
        for pick in self.repository.list_group_picks(entry_id):
            picks_by_group[pick["phase_group_id"]].append(pick)

        updates: list[dict] = []
        total_points = 0
        perfect_groups = 0
        for group_id, picks in picks_by_group.items():
            actual_rows = standings_by_group.get(group_id, [])
            if not self._is_group_finished(season_id, group_id, actual_rows):
                updates.extend(
                    {"id": pick["id"], "points": 0, "is_exact": False} for pick in picks
                )
                continue
            score = score_group_order_pick(
                [
                    pick["participant_id"]
                    for pick in sorted(picks, key=lambda item: item["predicted_position"])
                ],
                {row["participant_id"]: row["position"] for row in actual_rows},
                position_points=int(config["group_position_points"]),
                perfect_group_bonus=int(config["perfect_group_bonus"]),
            )
            total_points += score.total_points
            if score.is_perfect_group:
                perfect_groups += 1
            for pick in picks:
                updates.append(
                    {
                        "id": pick["id"],
                        "points": score.points_by_participant_id.get(pick["participant_id"], 0),
                        "is_exact": pick["participant_id"] in score.exact_participant_ids,
                    }
                )
        self.repository.update_group_pick_scores(updates)
        return total_points, perfect_groups

    def _is_group_finished(self, season_id: int, group_id: int, standings_rows: list[dict]) -> bool:
        participant_count = len(
            {row["participant_id"] for row in standings_rows if row.get("participant_id")}
        )
        if participant_count < 2:
            return False

        expected_match_count = participant_count * (participant_count - 1) // 2
        matches = self.repository.list_group_matches(season_id, group_id)
        if len(matches) < expected_match_count:
            return False

        return all(match.get("status") == "finished" for match in matches)

    def _score_entry_matches(self, entry_id: str, config: dict) -> tuple[int, int]:
        updates: list[dict] = []
        total_points = 0
        exact_scores = 0
        for pick in self.repository.list_match_picks(entry_id):
            event = self.repository.get_match(pick["event_id"])
            match_details = self.repository.get_football_match_details(pick["event_id"])
            if event is None or match_details is None or event["status"] != "finished":
                continue
            phase = self.repository.get_phase(event.get("competition_phase_id"))
            round_key = (phase or {}).get("key")
            if not round_key:
                meta = get_knockout_round_meta(match_details.get("round_label"))
                round_key = meta.id if meta else ""
            score = score_match_pick(
                predicted_winner_id=pick["winner_participant_id"],
                actual_winner_id=match_details.get("winner_participant_id"),
                round_key=round_key,
                predicted_home_score=pick.get("home_score"),
                predicted_away_score=pick.get("away_score"),
                actual_home_score=match_details.get("home_score"),
                actual_away_score=match_details.get("away_score"),
                winner_points_by_round=config["knockout_winner_points"],
                exact_score_bonus=int(config["exact_score_bonus"]),
            )
            total_points += score.points
            if score.is_exact_score:
                exact_scores += 1
            updates.append({"id": pick["id"], **score.__dict__})
        self.repository.update_match_pick_scores(updates)
        return total_points, exact_scores

    def _score_entry_awards(
        self, entry_id: str, award_results: dict[str, dict], config: dict
    ) -> int:
        updates: list[dict] = []
        total_points = 0
        for pick in self.repository.list_award_picks(entry_id):
            result = award_results.get(pick["award_key"])
            if result is None:
                continue
            points, is_hit = score_award_pick(
                award_key=pick["award_key"],
                candidate_id=pick.get("candidate_id"),
                participant_id=pick.get("participant_id"),
                result_candidate_id=result.get("candidate_id"),
                result_participant_id=result.get("participant_id"),
                award_points=config["award_points"],
            )
            total_points += points
            updates.append({"id": pick["id"], "points": points, "is_hit": is_hit})
        self.repository.update_award_pick_scores(updates)
        return total_points

    def _require_contest(self, contest_id: int) -> dict:
        contest = self.repository.get_contest(contest_id)
        if contest is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickem not found")
        return contest

    def _scoring_config(self, contest: dict) -> dict:
        return {**DEFAULT_PICKEM_SCORING_CONFIG, **(contest.get("scoring_config") or {})}

    def _groups_for_contest(self, contest: dict) -> list[dict]:
        phases = self.repository.list_group_phase_rows(contest["competition_season_id"])
        groups = self.repository.list_groups_for_phase_ids([row["id"] for row in phases])
        standings_by_group = self._standings_by_group(contest["competition_season_id"])
        if contest.get("slug") == "fifa-world-cup-2026":
            return [
                group
                for group in groups
                if group.get("key") in WORLD_CUP_GROUP_KEYS
                and len(standings_by_group.get(group["id"], [])) == 4
            ]
        return groups

    def _standings_by_group(self, season_id: int) -> dict[int, list[dict]]:
        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in self.repository.list_standings_rows(season_id):
            grouped[row["phase_group_id"]].append(row)
        return grouped

    def _map_contest(self, contest: dict) -> PickemContestResponse:
        season_id = contest["competition_season_id"]
        groups = self._groups_for_contest(contest)
        standings_by_group = self._standings_by_group(season_id)
        group_ids = {group["id"] for group in groups}
        participant_ids = [
            row["participant_id"]
            for group_id, rows in standings_by_group.items()
            if group_id in group_ids
            for row in rows
        ]
        competitors = {row["id"]: row for row in self.repository.list_competitors(participant_ids)}
        return PickemContestResponse(
            id=contest["id"],
            slug=contest["slug"],
            name=contest["name"],
            competition_id=contest["season"]["competition_id"],
            competition_season_id=season_id,
            group_deadline=contest["group_deadline"],
            awards_deadline=contest["awards_deadline"],
            scoring_config=self._scoring_config(contest),
            groups=[
                PickemGroupResponse(
                    id=group["id"],
                    key=group["key"],
                    name=group["name"],
                    order=group["order_index"],
                    teams=[
                        self._map_group_team(row, competitors.get(row["participant_id"]))
                        for row in standings_by_group.get(group["id"], [])
                    ],
                )
                for group in groups
            ],
            award_candidates=[
                self._map_award_candidate(row)
                for row in self.repository.list_award_candidates(contest["id"])
            ],
            champion_candidates=[
                self._map_team(row)
                for row in sorted(
                    competitors.values(),
                    key=lambda item: (str(item.get("name") or ""), int(item["id"])),
                )
            ],
        )

    def _contest_group_participant_ids(self, contest: dict) -> set[int]:
        standings_by_group = self._standings_by_group(contest["competition_season_id"])
        group_ids = {group["id"] for group in self._groups_for_contest(contest)}
        return {
            row["participant_id"]
            for group_id, standings_rows in standings_by_group.items()
            if group_id in group_ids
            for row in standings_rows
        }

    def _map_entry(self, contest: dict, entry: dict) -> PickemEntryResponse:
        return PickemEntryResponse(
            id=entry["id"],
            contest_id=entry["contest_id"],
            user_id=entry["user_id"],
            total_points=entry["total_points"],
            group_points=entry["group_points"],
            knockout_points=entry["knockout_points"],
            award_points=entry["award_points"],
            perfect_groups=entry["perfect_groups"],
            exact_scores=entry["exact_scores"],
            group_picks=[
                PickemGroupPickResponse(
                    group_id=row["phase_group_id"],
                    participant_id=row["participant_id"],
                    predicted_position=row["predicted_position"],
                    points=row.get("points"),
                    is_exact=row.get("is_exact"),
                )
                for row in self.repository.list_group_picks(entry["id"])
            ],
            award_picks=[
                PickemAwardPickResponse(
                    award_key=row["award_key"],
                    candidate_id=row.get("candidate_id"),
                    participant_id=row.get("participant_id"),
                    points=row.get("points"),
                    is_hit=row.get("is_hit"),
                )
                for row in self.repository.list_award_picks(entry["id"])
            ],
            match_picks=[
                self._map_match_pick(row) for row in self.repository.list_match_picks(entry["id"])
            ],
        )

    def _map_team(self, row: dict) -> PickemTeamResponse:
        name = row.get("name") or "Equipo"
        return PickemTeamResponse(
            id=row["id"],
            name=name,
            abbr=row.get("code") or name[:3].upper(),
            badge=row.get("badge_url"),
            country=row.get("country_code"),
        )

    def _map_group_team(self, row: dict, participant: dict | None) -> PickemGroupTeamResponse:
        team = self._map_team(participant or {"id": row["participant_id"], "name": "Equipo"})
        return PickemGroupTeamResponse(**team.model_dump(), position=row["position"])

    def _map_award_candidate(self, row: dict) -> PickemAwardCandidateResponse:
        metadata = row.get("metadata") or {}
        return PickemAwardCandidateResponse(
            id=row["id"],
            award_key=row["award_key"],
            display_name=row["display_name"],
            participant_id=row.get("participant_id"),
            player_id=metadata.get("player_id"),
            squad_player_id=row.get("squad_player_id") or metadata.get("squad_player_id"),
            team_id=row.get("participant_id") or metadata.get("participant_id"),
            team_name=metadata.get("team_name") or metadata.get("participant_name"),
            position_desc=metadata.get("position_desc"),
            is_goalkeeper=metadata.get("is_goalkeeper"),
            is_active=bool(row.get("is_active", True)),
        )

    def _map_match_pick(self, row: dict) -> PickemMatchPickResponse:
        return PickemMatchPickResponse(
            event_id=row["event_id"],
            winner_participant_id=row["winner_participant_id"],
            home_score=row.get("home_score"),
            away_score=row.get("away_score"),
            points=row.get("points"),
            winner_points=row.get("winner_points"),
            exact_score_points=row.get("exact_score_points"),
            is_winner_hit=row.get("is_winner_hit"),
            is_exact_score=row.get("is_exact_score"),
        )
