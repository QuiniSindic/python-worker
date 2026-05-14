from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import HTTPException, status

from app.domains.football_v2.repository import FootballV2Repository
from app.schemas.auth import AuthenticatedUser, CurrentUserResponse
from app.schemas.catalog import CompetitionEditionLite, CompetitionOption, SportOption
from app.schemas.football import (
    BracketLegResponse,
    BracketRoundResponse,
    BracketTieResponse,
    CompetitionDataResponse,
    CompetitionStageGroupResponse,
    CompetitionStageResponse,
    CompetitionStandingsSnapshotResponse,
    CompetitionStructureResponse,
    MatchEventResponse,
    MatchResponse,
    PredictionFeedItemResponse,
    PredictionRowResponse,
    PredictionUpsertPayload,
    StandingsGroupResponse,
    TeamInfoResponse,
    TeamStandingResponse,
    TournamentAwardCandidate,
    TournamentGroupOption,
    TournamentLocks,
    TournamentPredictionOptionsResponse,
    TournamentPredictionPayload,
    TournamentPredictionResponse,
    TournamentScoringRules,
    TournamentTeamOption,
)
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardFilterOptions

DEFAULT_GLOBAL_FEED_LIMIT = 30
DEFAULT_COMPETITION_FEED_LIMIT = 50
MAX_FEED_LIMIT = 100


def _map_status(status_value: str) -> str:
    return {
        "scheduled": "NS",
        "live": "LIVE",
        "finished": "FT",
        "cancelled": "Canc.",
        "postponed": "NS",
    }.get(status_value, "NS")


def _format_kickoff(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return dt.astimezone(UTC).strftime("%H:%M %d/%m/%Y")


def _short_name(value: str) -> str:
    compact = (value or "").strip()
    return compact[:3].upper() if compact else "---"


def _parse_result(result: str | None) -> tuple[int | None, int | None]:
    if not result or "-" not in result:
        return None, None
    left, right = result.split("-", maxsplit=1)
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None, None


def _sortable_kickoff(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


class FootballV2Service:
    def __init__(self, repository: FootballV2Repository | None = None) -> None:
        self.repository = repository or FootballV2Repository()

    def get_sports(self) -> list[SportOption]:
        return [
            SportOption(id=row["id"], slug=row["slug"], name=row["name"], displayName=row["name"])
            for row in self.repository.list_sports()
        ]

    def get_competitions(self, sport_id: int) -> list[CompetitionOption]:
        return [
            CompetitionOption(
                id=row["id"],
                name=row["name"],
                country=row.get("country_code"),
                current_edition=self._map_edition(row.get("current_season")),
            )
            for row in self.repository.list_competitions_by_sport(sport_id)
        ]

    def get_current_season(self, competition_id: int) -> CompetitionEditionLite:
        season = self.repository.get_current_season_by_competition(competition_id)
        edition = self._map_edition(season)
        if edition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        return edition

    def get_event_feed(
        self,
        *,
        bucket: Literal["live", "results"],
        competition_id: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int | None = None,
    ) -> list[CompetitionDataResponse]:
        season_ids = self._resolve_feed_season_ids(competition_id)
        resolved_limit = self._resolve_feed_limit(competition_id, limit)
        return self._group_matches_by_competition(
            self.repository.list_events_for_seasons(
                season_ids,
                bucket,
                from_date,
                to_date,
                resolved_limit,
            ),
            bucket,
        )

    def get_event(self, event_id: int) -> MatchResponse:
        row = self.repository.get_event(event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        return self._map_match_payloads([row])[0]

    def get_bracket(self, season_id: int) -> list[BracketRoundResponse]:
        season = self.repository.get_season(season_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        phases = self.repository.list_phases_for_season(season_id)
        phase_by_id = {row["id"]: row for row in phases}
        bracket_rows = self._get_bracket_event_rows(season_id, phases)
        if not bracket_rows:
            return []

        event_ids = [row["id"] for row in bracket_rows]
        football_rows = {
            row["event_id"]: row for row in self.repository.list_football_event_rows(event_ids)
        }
        participants_rows = self.repository.list_event_participants(event_ids)
        participants = {
            row["id"]: row
            for row in self.repository.list_participants(
                [
                    row["participant_id"]
                    for row in participants_rows
                    if row.get("participant_id") is not None
                ]
            )
        }
        slots_by_event: dict[int, dict[str, dict]] = defaultdict(dict)
        for row in participants_rows:
            slots_by_event[row["event_id"]][row["slot_key"]] = {
                "participant": participants.get(row.get("participant_id")),
                "placeholder": row.get("placeholder_label"),
            }

        rounds: dict[tuple[int, str], dict[str, Any]] = {}
        for row in bracket_rows:
            football = football_rows.get(row["id"], {})
            phase = phase_by_id.get(row.get("competition_phase_id"))
            round_id = str(
                (phase or {}).get("key")
                or football.get("round_key")
                or football.get("round_label")
                or f"round-{row['id']}"
            )
            round_name = str(
                (phase or {}).get("name")
                or football.get("round_label")
                or football.get("round_key")
                or "Eliminatoria"
            )
            round_order = int((phase or {}).get("order_index") or 999)
            rounds.setdefault(
                (round_order, round_id),
                {
                    "id": round_id,
                    "name": round_name,
                    "order": round_order,
                    "matches": [],
                },
            )["matches"].append(
                {
                    "event": row,
                    "football": football,
                    "home": self._map_side(slots_by_event.get(row["id"], {}).get("home")),
                    "away": self._map_side(slots_by_event.get(row["id"], {}).get("away")),
                }
            )

        return [
            BracketRoundResponse(
                id=round_payload["id"],
                name=round_payload["name"],
                order=round_payload["order"],
                ties=self._build_round_ties(
                    round_payload["matches"],
                    round_payload["id"],
                    round_payload["name"],
                    round_payload["order"],
                ),
            )
            for _, round_payload in sorted(rounds.items(), key=lambda item: item[0][0])
        ]

    def get_standings(
        self,
        competition_id: int,
        stage_key: str | None = None,
        group_key: str | None = None,
    ) -> CompetitionStandingsSnapshotResponse:
        season = self.repository.get_current_season_by_competition(competition_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        phases = self.repository.list_phases_for_season(season["id"])
        phase = next(
            (
                item
                for item in phases
                if item.get("is_standings_phase")
                and (stage_key is None or item["key"] == stage_key)
            ),
            None,
        )
        if phase is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standings not found")
        groups = self.repository.list_groups_for_phase_ids([phase["id"]])
        selected_group = next((item for item in groups if item["key"] == group_key), None)
        rows = self.repository.list_standings_rows(
            season["id"], phase["id"], selected_group["id"] if selected_group else None
        )
        participants = {
            row["id"]: row
            for row in self.repository.list_participants([row["participant_id"] for row in rows])
        }
        rows_by_group: dict[int, list[dict]] = defaultdict(list)
        for row in rows:
            rows_by_group[row["phase_group_id"]].append(row)
        response_groups: list[StandingsGroupResponse] = []
        for group in groups:
            if selected_group and selected_group["id"] != group["id"]:
                continue
            response_groups.append(
                StandingsGroupResponse(
                    id=group["key"],
                    name=group["name"],
                    order=group["order_index"],
                    teams=[
                        self._map_standing_row(item, participants.get(item["participant_id"]))
                        for item in rows_by_group.get(group["id"], [])
                    ],
                )
            )
        return CompetitionStandingsSnapshotResponse(
            competitionId=competition_id,
            stageId=phase["key"],
            stageName=phase["name"],
            stageType="group" if phase["phase_type"] == "group_stage" else "league_table",
            edition=self._map_edition(season),
            groups=response_groups,
        )

    def get_structure(self, season_id: int) -> CompetitionStructureResponse:
        season = self.repository.get_season(season_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        competition = self.repository.get_competition(season["competition_id"])
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competition not found"
            )
        phases = self.repository.list_phases_for_season(season_id)
        groups = self.repository.list_groups_for_phase_ids([row["id"] for row in phases])
        groups_by_phase: dict[int, list[dict]] = defaultdict(list)
        for row in groups:
            groups_by_phase[row["competition_phase_id"]].append(row)
        return CompetitionStructureResponse(
            competitionId=competition["id"],
            name=competition["name"],
            badge=self._competition_badge(competition),
            country=competition.get("country_code"),
            formatKind=season["format_kind"],
            edition=self._map_edition(season),
            stages=[
                CompetitionStageResponse(
                    id=row["key"],
                    name=row["name"],
                    stageType=self._map_stage_type(row["phase_type"]),
                    order=row["order_index"],
                    groups=[
                        CompetitionStageGroupResponse(
                            id=group["key"],
                            name=group["name"],
                            order=group["order_index"],
                        )
                        for group in groups_by_phase.get(row["id"], [])
                    ],
                )
                for row in phases
            ],
        )

    def get_tournament_prediction_options(
        self, season_id: int
    ) -> TournamentPredictionOptionsResponse:
        season = self.repository.get_season(season_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        return self._build_tournament_options(season)

    def get_tournament_prediction(
        self, season_id: int, user: AuthenticatedUser
    ) -> TournamentPredictionResponse:
        season = self.repository.get_season(season_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        row = self.repository.get_tournament_prediction(season_id, user.id)
        options = self._build_tournament_options(season)
        if row is None:
            return TournamentPredictionResponse(
                user_id=user.id,
                competition_id=season["competition_id"],
                edition_id=season_id,
                sport_id=self._season_sport_id(season),
                status="open",
                payload=TournamentPredictionPayload(),
                options=options,
            )
        return self._map_tournament_prediction_row(row, options)

    def save_tournament_prediction(
        self,
        season_id: int,
        payload: TournamentPredictionPayload,
        user: AuthenticatedUser,
    ) -> TournamentPredictionResponse:
        season = self.repository.get_season(season_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        existing = self.repository.get_tournament_prediction(season_id, user.id)
        options = self._build_tournament_options(season)
        self._validate_tournament_locks(payload, existing, options.locks)
        self._validate_tournament_payload(payload, options)
        row = self.repository.upsert_tournament_prediction(
            user_id=user.id,
            sport_id=self._season_sport_id(season),
            competition_id=season["competition_id"],
            season_id=season_id,
            payload=payload.model_dump(),
            prediction_id=existing["id"] if existing else None,
        )
        return self._map_tournament_prediction_row(row, options)

    def score_tournament_predictions(self, season_id: int) -> list[TournamentPredictionResponse]:
        season = self.repository.get_season(season_id)
        if not season:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        options = self._build_tournament_options(season)
        rows = self.repository.list_tournament_predictions([season_id])
        scored: list[TournamentPredictionResponse] = []
        for row in rows:
            payload = TournamentPredictionPayload(**(row.get("payload") or {}))
            points, breakdown = self._score_tournament_payload(payload, options, season_id)
            updated = self.repository.update_tournament_prediction_score(
                row["id"], points=points, points_breakdown=breakdown
            )
            scored.append(self._map_tournament_prediction_row(updated or row, options))
        return scored

    def get_event_predictions(self, event_id: int) -> list[PredictionRowResponse]:
        return [
            self._map_prediction_row(row)
            for row in self.repository.list_predictions_for_event(event_id)
        ]

    def get_user_prediction(
        self, event_id: int, user: AuthenticatedUser
    ) -> PredictionRowResponse | None:
        row = self.repository.get_user_prediction_for_event(event_id, user.id)
        return self._map_prediction_row(row) if row else None

    def save_prediction(
        self, event_id: int, payload: PredictionUpsertPayload, user: AuthenticatedUser
    ) -> PredictionRowResponse:
        event = self.repository.get_event(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if event["status"] != "scheduled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event is locked")
        row = self.repository.upsert_prediction(
            user_id=user.id,
            sport_id=payload.sport_id,
            competition_id=payload.competition_id,
            season_id=event["competition_season_id"],
            event_id=event_id,
            home_score=payload.home_score,
            away_score=payload.away_score,
        )
        return self._map_prediction_row(row)

    def update_prediction(
        self, event_id: int, home_score: int, away_score: int, user: AuthenticatedUser
    ) -> PredictionRowResponse:
        existing = self.repository.get_user_prediction_for_event(event_id, user.id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found"
            )
        event = self.repository.get_event(event_id)
        if not event or event["status"] != "scheduled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event is locked")
        row = self.repository.upsert_prediction(
            user_id=user.id,
            sport_id=existing["sport_id"],
            competition_id=existing["competition_id"],
            season_id=existing["competition_season_id"],
            event_id=event_id,
            home_score=home_score,
            away_score=away_score,
            prediction_id=existing["id"],
        )
        return self._map_prediction_row(row)

    def get_prediction_feed(self) -> list[PredictionFeedItemResponse]:
        prediction_rows = (
            self.repository.supabase.table("predictions")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        if not prediction_rows:
            return []
        event_ids = [row["event_id"] for row in prediction_rows]
        details = {
            row["prediction_id"]: row
            for row in (
                self.repository.supabase.table("football_predictions")
                .select("*")
                .in_("prediction_id", [row["id"] for row in prediction_rows])
                .execute()
                .data
                or []
            )
        }
        profiles = {
            row["id"]: row
            for row in self.repository.get_profiles(
                sorted({row["user_id"] for row in prediction_rows})
            )
        }
        football_event_rows = {
            row["event_id"]: row for row in self.repository.list_football_event_rows(event_ids)
        }
        matches = {
            row.id: row
            for row in self._map_match_payloads(self.repository.list_events_by_ids(event_ids))
        }
        sports = {row["id"]: row for row in self.repository.list_sports()}
        competitions = {
            row["id"]: row
            for row in self.repository.list_competitions(
                [row["competition_id"] for row in prediction_rows]
            )
        }
        return [
            PredictionFeedItemResponse(
                id=row["id"],
                userId=row["user_id"],
                username=profiles.get(row["user_id"], {}).get("username", "Usuario"),
                matchId=row["event_id"],
                kickoff=matches[row["event_id"]].kickoff,
                kickoffIso=matches[row["event_id"]].kickoffIso,
                matchStatus=matches[row["event_id"]].status,
                homeTeam=matches[row["event_id"]].homeTeam.name,
                awayTeam=matches[row["event_id"]].awayTeam.name,
                predicted=f"{details.get(row['id'], {}).get('home_score', '-')}-{details.get(row['id'], {}).get('away_score', '-')}",
                homeScore=football_event_rows.get(row["event_id"], {}).get("home_score"),
                awayScore=football_event_rows.get(row["event_id"], {}).get("away_score"),
                minute=football_event_rows.get(row["event_id"], {}).get("minute"),
                sportId=row["sport_id"],
                sportName=sports.get(row["sport_id"], {}).get("name", "Football"),
                competitionId=row["competition_id"],
                competitionName=competitions.get(row["competition_id"], {}).get("name", ""),
                points=row.get("points"),
                createdAt=row["created_at"],
            )
            for row in prediction_rows
            if row["event_id"] in matches
        ]

    def get_current_user(self, user: AuthenticatedUser) -> CurrentUserResponse:
        profile_rows = self.repository.get_profiles([user.id])
        profile = profile_rows[0] if profile_rows else {}
        return CurrentUserResponse(
            id=user.id,
            username=profile.get("username", user.username),
            email=user.email,
            img=profile.get("img"),
        )

    def get_leaderboard(self, scope: str, filter_id: int | None) -> list[LeaderboardEntry]:
        prediction_rows = (
            self.repository.supabase.table("predictions").select("*").execute().data or []
        )
        tournament_rows = self.repository.list_tournament_predictions()
        if scope == "sport" and filter_id is not None:
            prediction_rows = [row for row in prediction_rows if row["sport_id"] == filter_id]
            tournament_rows = [row for row in tournament_rows if row["sport_id"] == filter_id]
        elif scope == "competition" and filter_id is not None:
            season = self.repository.get_current_season_by_competition(filter_id)
            prediction_rows = (
                [row for row in prediction_rows if row["competition_season_id"] == season["id"]]
                if season
                else []
            )
            tournament_rows = (
                [row for row in tournament_rows if row["competition_season_id"] == season["id"]]
                if season
                else []
            )
        user_ids = sorted(
            {row["user_id"] for row in prediction_rows}
            | {row["user_id"] for row in tournament_rows}
        )
        profiles = {row["id"]: row for row in self.repository.get_profiles(user_ids)}
        grouped: dict[str, dict[str, Any]] = {}
        for row in [*prediction_rows, *tournament_rows]:
            entry = grouped.setdefault(
                row["user_id"],
                {
                    "user_id": row["user_id"],
                    "username": profiles.get(row["user_id"], {}).get("username", "Usuario"),
                    "avatar_url": profiles.get(row["user_id"], {}).get("img"),
                    "total_points": 0,
                    "predictions_count": 0,
                    "exact_hits": 0,
                },
            )
            entry["predictions_count"] += 1
            if row.get("points") is not None:
                entry["total_points"] += int(row["points"])
            if row.get("points") == 3:
                entry["exact_hits"] += 1
        ranked = sorted(
            grouped.values(),
            key=lambda item: (-item["total_points"], -item["exact_hits"], item["username"]),
        )
        return [LeaderboardEntry(**row) for row in ranked]

    def get_leaderboard_filters(self) -> LeaderboardFilterOptions:
        sports = self.get_sports()
        competitions = self.get_competitions(sports[0].id) if sports else []
        return LeaderboardFilterOptions(sports=sports, competitions=competitions)

    def _build_tournament_options(self, season: dict) -> TournamentPredictionOptionsResponse:
        groups = self._get_tournament_group_options(season)
        bracket = self.get_bracket(season["id"])
        return TournamentPredictionOptionsResponse(
            season=self._map_edition(season),
            groups=groups,
            bracket=bracket,
            awardCandidates=self._get_award_candidates(season["id"]),
            rules=self._get_tournament_rules(season["id"]),
            locks=self._get_tournament_locks(season["id"]),
        )

    def _get_tournament_group_options(self, season: dict) -> list[TournamentGroupOption]:
        phases = self.repository.list_phases_for_season(season["id"])
        standings_phase = next((row for row in phases if row.get("is_standings_phase")), None)
        if standings_phase is None:
            return []
        groups = self.repository.list_groups_for_phase_ids([standings_phase["id"]])
        rows = self.repository.list_standings_rows(season["id"], standings_phase["id"])
        participants = {
            row["id"]: row
            for row in self.repository.list_participants([row["participant_id"] for row in rows])
        }
        rows_by_group: dict[int, list[dict]] = defaultdict(list)
        for row in rows:
            rows_by_group[row["phase_group_id"]].append(row)
        options: list[TournamentGroupOption] = []
        for group in groups:
            if group["key"] == "best_third_placed":
                continue
            group_rows = sorted(
                rows_by_group.get(group["id"], []), key=lambda item: item["position"]
            )
            options.append(
                TournamentGroupOption(
                    id=group["key"],
                    name=group["name"],
                    order=group["order_index"],
                    teams=[
                        TournamentTeamOption(
                            id=item["participant_id"],
                            name=participants.get(item["participant_id"], {}).get("name", "Equipo"),
                            badge=participants.get(item["participant_id"], {}).get("badge_url"),
                            country=participants.get(item["participant_id"], {}).get(
                                "country_code"
                            ),
                        )
                        for item in group_rows
                    ],
                )
            )
        return options

    def _get_award_candidates(self, season_id: int) -> list[TournamentAwardCandidate]:
        season_participants = self.repository.list_season_participants(season_id)
        team_ids = [row["participant_id"] for row in season_participants]
        teams = {row["id"]: row for row in self.repository.list_participants(team_ids)}
        memberships = self.repository.list_participant_members(team_ids)
        player_ids = [
            row["member_participant_id"]
            for row in memberships
            if row.get("member_participant_id") is not None
        ]
        players = {
            row["id"]: row
            for row in self.repository.list_participants(player_ids)
            if row.get("kind") == "player"
        }
        candidates: list[TournamentAwardCandidate] = []
        for row in memberships:
            player = players.get(row.get("member_participant_id"))
            if not player:
                continue
            team = teams.get(row.get("parent_participant_id"), {})
            candidates.append(
                TournamentAwardCandidate(
                    id=player["id"],
                    name=player["name"],
                    teamId=team.get("id"),
                    teamName=team.get("name"),
                    badge=player.get("badge_url"),
                    country=player.get("country_code") or team.get("country_code"),
                )
            )
        return sorted(candidates, key=lambda item: (item.teamName or "", item.name))

    def _get_tournament_rules(self, season_id: int) -> TournamentScoringRules:
        row = self.repository.get_tournament_prediction_rules(season_id)
        return TournamentScoringRules(**(row.get("rules") if row else {}))

    def _get_tournament_locks(self, season_id: int) -> TournamentLocks:
        events = self.repository.list_events_for_seasons([season_id], "live")
        events.extend(self.repository.list_events_for_seasons([season_id], "results"))
        now = datetime.now(UTC)
        starts = [_sortable_kickoff(row.get("start_at")) for row in events]
        tournament_started = bool(starts) and min(starts) <= now
        locked_event_ids = [
            row["id"]
            for row in events
            if row.get("status") != "scheduled" or _sortable_kickoff(row.get("start_at")) <= now
        ]
        return TournamentLocks(
            groupsLocked=tournament_started,
            awardsLocked=tournament_started,
            championLocked=tournament_started,
            lockedEventIds=locked_event_ids,
        )

    def _validate_tournament_locks(
        self,
        payload: TournamentPredictionPayload,
        existing: dict | None,
        locks: TournamentLocks,
    ) -> None:
        old = TournamentPredictionPayload(**(existing.get("payload") or {})) if existing else None
        if locks.groupsLocked and (
            old is None
            or payload.groupPredictions != old.groupPredictions
            or payload.qualifiedThirdParticipantIds != old.qualifiedThirdParticipantIds
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Groups are locked")
        if locks.awardsLocked and (old is None or payload.awards != old.awards):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Awards are locked")
        if locks.championLocked and (
            old is None or payload.championParticipantId != old.championParticipantId
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Champion is locked"
            )
        old_knockouts = {item.eventId: item for item in old.knockoutPredictions} if old else {}
        for item in payload.knockoutPredictions:
            if item.eventId in locks.lockedEventIds and old_knockouts.get(item.eventId) != item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Event {item.eventId} is locked",
                )

    def _validate_tournament_payload(
        self, payload: TournamentPredictionPayload, options: TournamentPredictionOptionsResponse
    ) -> None:
        groups = {group.id: group for group in options.groups}
        for prediction in payload.groupPredictions:
            group = groups.get(prediction.groupId)
            if not group:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group")
            expected_ids = {team.id for team in group.teams}
            provided_ids = prediction.orderedParticipantIds
            if set(provided_ids) != expected_ids or len(provided_ids) != len(expected_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid teams for {prediction.groupId}",
                )
        third_candidates = {
            prediction.orderedParticipantIds[2]
            for prediction in payload.groupPredictions
            if len(prediction.orderedParticipantIds) >= 3
        }
        if not set(payload.qualifiedThirdParticipantIds).issubset(third_candidates):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Qualified thirds must be predicted third-place teams",
            )
        event_sides = self._tournament_event_sides(options.bracket)
        for prediction in payload.knockoutPredictions:
            sides = event_sides.get(prediction.eventId)
            if not sides:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid knockout event"
                )
            if prediction.homeScore < 0 or prediction.awayScore < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Scores must be positive"
                )
            if prediction.winnerParticipantId not in sides:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid knockout winner"
                )
        season_team_ids = {team.id for group in options.groups for team in group.teams}
        if payload.championParticipantId and payload.championParticipantId not in season_team_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid champion")
        candidate_ids = {candidate.id for candidate in options.awardCandidates}
        award_ids = [
            payload.awards.mvpParticipantId,
            payload.awards.bestGoalkeeperParticipantId,
            payload.awards.topScorerParticipantId,
        ]
        if candidate_ids and any(
            item is not None and item not in candidate_ids for item in award_ids
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid award candidate"
            )

    def _score_tournament_payload(
        self,
        payload: TournamentPredictionPayload,
        options: TournamentPredictionOptionsResponse,
        season_id: int,
    ) -> tuple[int, dict[str, int]]:
        rules = options.rules
        breakdown = {"groups": 0, "qualifiedThirds": 0, "knockout": 0, "champion": 0, "awards": 0}
        actual_groups = {
            group.id: [team.id for team in group.teams]
            for group in self._get_tournament_group_options({"id": season_id})
        }
        for prediction in payload.groupPredictions:
            actual_order = actual_groups.get(prediction.groupId, [])
            if not actual_order:
                continue
            hits = sum(
                1
                for index, participant_id in enumerate(prediction.orderedParticipantIds)
                if index < len(actual_order) and actual_order[index] == participant_id
            )
            breakdown["groups"] += hits * rules.groupPosition
            if prediction.orderedParticipantIds == actual_order:
                breakdown["groups"] += rules.groupPerfectBonus
        actual_thirds = self._actual_qualified_thirds(season_id)
        breakdown["qualifiedThirds"] = (
            len(set(payload.qualifiedThirdParticipantIds) & actual_thirds) * rules.qualifiedThird
        )
        winners = self._tournament_event_winners(options.bracket)
        round_by_event = self._tournament_event_rounds(options.bracket)
        for prediction in payload.knockoutPredictions:
            if winners.get(prediction.eventId) == prediction.winnerParticipantId:
                breakdown["knockout"] += rules.knockoutByRound.get(
                    round_by_event.get(prediction.eventId, ""), 0
                )
        results = self.repository.get_tournament_results(season_id) or {}
        champion_id = results.get("champion_participant_id") or self._final_winner(options.bracket)
        if champion_id and payload.championParticipantId == champion_id:
            breakdown["champion"] += rules.champion
        award_rules = rules.awards
        if payload.awards.mvpParticipantId == results.get("mvp_participant_id"):
            breakdown["awards"] += award_rules.get("mvp", 0)
        if payload.awards.bestGoalkeeperParticipantId == results.get(
            "best_goalkeeper_participant_id"
        ):
            breakdown["awards"] += award_rules.get("bestGoalkeeper", 0)
        if payload.awards.topScorerParticipantId == results.get("top_scorer_participant_id"):
            breakdown["awards"] += award_rules.get("topScorer", 0)
        return sum(breakdown.values()), breakdown

    def _actual_qualified_thirds(self, season_id: int) -> set[int]:
        phases = self.repository.list_phases_for_season(season_id)
        standings_phase = next((row for row in phases if row.get("is_standings_phase")), None)
        if standings_phase is None:
            return set()
        groups = self.repository.list_groups_for_phase_ids([standings_phase["id"]])
        third_group = next((row for row in groups if row["key"] == "best_third_placed"), None)
        if third_group is None:
            return set()
        return {
            row["participant_id"]
            for row in self.repository.list_standings_rows(
                season_id, standings_phase["id"], third_group["id"]
            )
        }

    def _tournament_event_sides(self, bracket: list[BracketRoundResponse]) -> dict[int, set[int]]:
        sides: dict[int, set[int]] = {}
        for round_item in bracket:
            for tie in round_item.ties:
                for leg in tie.legs:
                    ids = {leg.homeTeam.id, leg.awayTeam.id} - {0}
                    if ids:
                        sides[leg.eventId] = ids
        return sides

    def _tournament_event_winners(self, bracket: list[BracketRoundResponse]) -> dict[int, int]:
        winners: dict[int, int] = {}
        for round_item in bracket:
            for tie in round_item.ties:
                if tie.winnerParticipantId:
                    for leg in tie.legs:
                        winners[leg.eventId] = tie.winnerParticipantId
        return winners

    def _tournament_event_rounds(self, bracket: list[BracketRoundResponse]) -> dict[int, str]:
        rounds: dict[int, str] = {}
        for round_item in bracket:
            for tie in round_item.ties:
                for leg in tie.legs:
                    rounds[leg.eventId] = round_item.id
        return rounds

    def _final_winner(self, bracket: list[BracketRoundResponse]) -> int | None:
        final_round = next((round_item for round_item in bracket if round_item.id == "final"), None)
        if not final_round:
            return None
        for tie in final_round.ties:
            if tie.winnerParticipantId:
                return tie.winnerParticipantId
        return None

    def _season_sport_id(self, season: dict) -> int:
        competition = self.repository.get_competition(season["competition_id"])
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competition not found"
            )
        return competition["sport_id"]

    def _map_tournament_prediction_row(
        self, row: dict, options: TournamentPredictionOptionsResponse
    ) -> TournamentPredictionResponse:
        return TournamentPredictionResponse(
            id=row.get("id"),
            user_id=row["user_id"],
            competition_id=row["competition_id"],
            edition_id=row["competition_season_id"],
            sport_id=row["sport_id"],
            status=row["status"],
            payload=TournamentPredictionPayload(**(row.get("payload") or {})),
            points=row.get("points"),
            pointsBreakdown=row.get("points_breakdown") or {},
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            options=options,
        )

    def _resolve_feed_season_ids(self, competition_id: int | None) -> list[int]:
        if competition_id is not None:
            season = self.repository.get_current_season_by_competition(competition_id)
            return [season["id"]] if season else []
        return [row["id"] for row in self.repository.list_current_seasons()]

    def _resolve_feed_limit(self, competition_id: int | None, limit: int | None) -> int:
        if limit is None:
            return (
                DEFAULT_COMPETITION_FEED_LIMIT
                if competition_id is not None
                else DEFAULT_GLOBAL_FEED_LIMIT
            )

        return max(1, min(limit, MAX_FEED_LIMIT))

    def _group_matches_by_competition(
        self, event_rows: list[dict], bucket: Literal["live", "results"]
    ) -> list[CompetitionDataResponse]:
        sorted_rows = sorted(
            event_rows,
            key=lambda row: (
                _sortable_kickoff(row.get("start_at")),
                row["competition_id"],
                row["id"],
            ),
            reverse=bucket == "results",
        )
        matches = self._map_match_payloads(sorted_rows)
        grouped: dict[int, list[MatchResponse]] = defaultdict(list)
        for row in matches:
            grouped[row.competitionid].append(row)
        competitions = {row["id"]: row for row in self.repository.list_competitions(list(grouped))}
        seasons = {
            row["competition_id"]: row
            for row in self.repository.list_current_seasons(list(grouped))
        }
        return [
            CompetitionDataResponse(
                id=str(competition_id),
                name=competitions[competition_id]["name"],
                fullName=competitions[competition_id]["name"],
                badge=self._competition_badge(competitions[competition_id]),
                country=competitions[competition_id].get("country_code"),
                formatKind=seasons.get(competition_id, {}).get("format_kind"),
                edition=self._map_edition(seasons.get(competition_id)),
                matches=competition_matches,
            )
            for competition_id, competition_matches in grouped.items()
            if competition_id in competitions
        ]

    def _get_bracket_event_rows(self, season_id: int, phases: list[dict]) -> list[dict]:
        bracket_phase_ids = {
            row["id"]
            for row in phases
            if row.get("is_bracket_phase") or row["phase_type"] in {"knockout_round", "final_stage"}
        }
        events = self.repository.list_events_for_seasons([season_id], "live")
        events.extend(self.repository.list_events_for_seasons([season_id], "results"))
        bracket_rows = [
            row for row in events if row.get("competition_phase_id") in bracket_phase_ids
        ]
        if bracket_rows:
            return bracket_rows

        event_ids = [row["id"] for row in events]
        football_rows_by_event = {
            row["event_id"]: row for row in self.repository.list_football_event_rows(event_ids)
        }
        return [
            row
            for row in events
            if football_rows_by_event.get(row["id"], {}).get("round_key")
            or football_rows_by_event.get(row["id"], {}).get("round_label")
        ]

    def _build_round_ties(
        self,
        round_matches: list[dict[str, Any]],
        round_id: str,
        round_name: str,
        round_order: int,
    ) -> list[BracketTieResponse]:
        tie_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for match in round_matches:
            tie_groups[self._tie_group_key(match["home"], match["away"])].append(match)

        ties: list[BracketTieResponse] = []
        for tie_index, tie_matches in enumerate(
            sorted(
                tie_groups.values(),
                key=lambda items: _sortable_kickoff(items[0]["event"].get("start_at")),
            ),
            start=1,
        ):
            ordered_matches = sorted(
                tie_matches,
                key=lambda item: (
                    item["football"].get("leg") or 0,
                    _sortable_kickoff(item["event"].get("start_at")),
                    item["event"]["id"],
                ),
            )
            canonical_match = ordered_matches[0]
            canonical_home = canonical_match["home"]
            canonical_away = canonical_match["away"]

            aggregate_home: int | None = 0
            aggregate_away: int | None = 0
            parsed_leg_count = 0
            legs: list[BracketLegResponse] = []
            for leg_index, match in enumerate(ordered_matches, start=1):
                home_score, away_score = _parse_result(self._format_result(match["football"]))
                mapped_home, mapped_away = self._canonical_scores(
                    canonical_home,
                    canonical_away,
                    match["home"],
                    match["away"],
                    home_score,
                    away_score,
                )
                if mapped_home is not None and mapped_away is not None:
                    aggregate_home += mapped_home
                    aggregate_away += mapped_away
                    parsed_leg_count += 1

                legs.append(
                    BracketLegResponse(
                        eventId=match["event"]["id"],
                        kickoff=_format_kickoff(match["event"].get("start_at")),
                        kickoffIso=match["event"].get("start_at"),
                        status=_map_status(match["event"]["status"]),
                        minute=match["football"].get("minute"),
                        result=self._format_result(match["football"]),
                        leg=int(match["football"].get("leg") or leg_index),
                        homeTeam=match["home"],
                        awayTeam=match["away"],
                    )
                )

            if parsed_leg_count == 0:
                aggregate_home = None
                aggregate_away = None

            winner_participant_id: int | None = None
            if (
                aggregate_home is not None
                and aggregate_away is not None
                and aggregate_home != aggregate_away
            ):
                winner_participant_id = (
                    canonical_home.id if aggregate_home > aggregate_away else canonical_away.id
                )
                if winner_participant_id == 0:
                    winner_participant_id = None

            ties.append(
                BracketTieResponse(
                    id=f"{round_id}:tie:{tie_index}",
                    roundId=round_id,
                    roundName=round_name,
                    order=round_order,
                    homeTeam=canonical_home,
                    awayTeam=canonical_away,
                    aggregateHomeScore=aggregate_home,
                    aggregateAwayScore=aggregate_away,
                    winnerParticipantId=winner_participant_id,
                    isTwoLegged=len(legs) > 1,
                    legs=legs,
                )
            )

        return ties

    def _map_match_payloads(self, event_rows: list[dict]) -> list[MatchResponse]:
        if not event_rows:
            return []
        event_ids = [row["id"] for row in event_rows]
        football_rows = {
            row["event_id"]: row for row in self.repository.list_football_event_rows(event_ids)
        }
        participants_rows = self.repository.list_event_participants(event_ids)
        participants = {
            row["id"]: row
            for row in self.repository.list_participants(
                [
                    row["participant_id"]
                    for row in participants_rows
                    if row.get("participant_id") is not None
                ]
            )
        }
        competitions = {
            row["id"]: row
            for row in self.repository.list_competitions(
                [row["competition_id"] for row in event_rows]
            )
        }
        seasons = {
            row["id"]: row
            for row in self.repository.list_seasons(
                [row["competition_season_id"] for row in event_rows]
            )
        }
        slots_by_event: dict[int, dict[str, dict]] = defaultdict(dict)
        for row in participants_rows:
            slots_by_event[row["event_id"]][row["slot_key"]] = {
                "participant": participants.get(row.get("participant_id")),
                "placeholder": row.get("placeholder_label"),
            }
        mapped: list[MatchResponse] = []
        for row in event_rows:
            football = football_rows.get(row["id"], {})
            competition = competitions.get(row["competition_id"], {})
            home = self._map_side(slots_by_event.get(row["id"], {}).get("home"))
            away = self._map_side(slots_by_event.get(row["id"], {}).get("away"))
            mapped.append(
                MatchResponse(
                    id=row["id"],
                    status=_map_status(row["status"]),
                    result=self._format_result(football),
                    kickoff=_format_kickoff(row["start_at"]),
                    kickoffIso=row.get("start_at"),
                    minute=football.get("minute"),
                    homeId=home.id,
                    awayId=away.id,
                    competitionid=row["competition_id"],
                    sportId=row["sport_id"],
                    round=football.get("round_label") or football.get("round_key"),
                    homeTeam=home,
                    awayTeam=away,
                    country=competition.get("country_code") or "",
                    edition=self._map_edition(seasons.get(row["competition_season_id"])),
                    events=[
                        MatchEventResponse(**item)
                        for item in football.get("timeline", [])
                        if isinstance(item, dict)
                    ],
                )
            )
        return mapped

    def _map_side(self, payload: dict | None) -> TeamInfoResponse:
        payload = payload or {}
        participant = payload.get("participant")
        if participant:
            name = participant.get("name") or "TBD"
            return TeamInfoResponse(
                id=participant["id"],
                name=name,
                abbr=participant.get("code") or _short_name(name),
                img=participant.get("badge_url"),
                country=participant.get("country_code") or "",
            )
        placeholder = payload.get("placeholder") or "Por decidir"
        return TeamInfoResponse(
            id=0, name=placeholder, abbr=_short_name(placeholder), img=None, country=""
        )

    def _side_identity(self, side: TeamInfoResponse) -> str:
        if side.id > 0:
            return f"id:{side.id}"
        return f"name:{side.name.strip().lower()}"

    def _tie_group_key(self, home: TeamInfoResponse, away: TeamInfoResponse) -> str:
        return "|".join(sorted([self._side_identity(home), self._side_identity(away)]))

    def _canonical_scores(
        self,
        canonical_home: TeamInfoResponse,
        canonical_away: TeamInfoResponse,
        match_home: TeamInfoResponse,
        match_away: TeamInfoResponse,
        home_score: int | None,
        away_score: int | None,
    ) -> tuple[int | None, int | None]:
        if home_score is None or away_score is None:
            return None, None

        if self._side_identity(match_home) == self._side_identity(
            canonical_home
        ) and self._side_identity(match_away) == self._side_identity(canonical_away):
            return home_score, away_score

        if self._side_identity(match_home) == self._side_identity(
            canonical_away
        ) and self._side_identity(match_away) == self._side_identity(canonical_home):
            return away_score, home_score

        return None, None

    def _map_standing_row(self, row: dict, participant: dict | None) -> TeamStandingResponse:
        participant = participant or {}
        return TeamStandingResponse(
            id=str(participant.get("id", row["participant_id"])),
            position=row["position"],
            name=participant.get("name", "Equipo"),
            badge=participant.get("badge_url") or "",
            played=row["played"],
            wins=row["wins"],
            draws=row["draws"],
            losses=row["losses"],
            points=row["points"],
            goalsFor=row["goals_for"],
            goalsAgainst=row["goals_against"],
            goalDifference=row["goal_difference"],
            form=row.get("form") or [],
        )

    def _map_edition(self, season: dict | None) -> CompetitionEditionLite | None:
        if not season:
            return None
        return CompetitionEditionLite(
            id=season["id"],
            season_key=season["season_key"],
            season_label=season["season_label"],
            is_current=bool(season.get("is_current")),
        )

    def _map_stage_type(self, phase_type: str) -> str:
        if phase_type == "group_stage":
            return "group"
        if phase_type in {"knockout_round", "final_stage"}:
            return "knockout_round"
        return "league_table"

    def _competition_badge(self, competition: dict[str, Any]) -> str:
        provider_id = competition.get("provider_competition_id")
        return (
            f"https://images.fotmob.com/image_resources/logo/leaguelogo/{provider_id}.png"
            if provider_id
            else ""
        )

    def _format_result(self, football: dict[str, Any]) -> str:
        home = football.get("home_score")
        away = football.get("away_score")
        return "vs" if home is None or away is None else f"{home}-{away}"

    def _map_prediction_row(self, row: dict) -> PredictionRowResponse:
        return PredictionRowResponse(
            id=row["id"],
            user_id=row["user_id"],
            match_id=row.get("match_id", row.get("event_id")),
            competition_id=row.get("competition_id"),
            edition_id=row.get("competition_season_id"),
            sport_id=row.get("sport_id"),
            home_score=row["home_score"],
            away_score=row["away_score"],
            points=row.get("points"),
            status=row.get("status"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
