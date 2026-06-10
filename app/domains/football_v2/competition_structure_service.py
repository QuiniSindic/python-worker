from __future__ import annotations

from dataclasses import dataclass

from app.domains.football_v2.competition_blueprints import (
    FootballCompetitionBlueprint,
    get_competition_blueprint,
)
from app.schemas.football import (
    CompetitionStageGroupResponse,
    CompetitionStageResponse,
    CompetitionStandingsSnapshotResponse,
    CompetitionStructureResponse,
)


@dataclass(frozen=True)
class KnockoutRoundMeta:
    id: str
    name: str
    order: int


KNOCKOUT_ROUND_RULES: tuple[tuple[KnockoutRoundMeta, tuple[str, ...]], ...] = (
    (
        KnockoutRoundMeta("round_of_64", "Ronda de 64", 5),
        ("1/32", "round of 64", "r64", "treintaidosavos", "32nd"),
    ),
    (
        KnockoutRoundMeta("round_of_32", "Dieciseisavos", 10),
        ("1/16", "round of 32", "r32", "dieciseisavos", "16th"),
    ),
    (KnockoutRoundMeta("playoff", "Play-offs", 15), ("playoff", "preliminar")),
    (
        KnockoutRoundMeta("round_of_16", "Octavos", 20),
        ("1/8", "round of 16", "octavos"),
    ),
    (
        KnockoutRoundMeta("quarterfinals", "Cuartos", 30),
        ("1/4", "quarter", "cuartos"),
    ),
    (KnockoutRoundMeta("semifinals", "Semis", 40), ("1/2", "semi")),
    (
        KnockoutRoundMeta("third_place", "Tercer puesto", 45),
        ("third place", "3rd place", "bronze", "tercer puesto"),
    ),
    (KnockoutRoundMeta("final", "Final", 50), ("final",)),
)


def normalize_round_label(value: str | None) -> str:
    return str(value or "").strip().lower()


def get_knockout_round_meta(round_label: str | None) -> KnockoutRoundMeta | None:
    normalized = normalize_round_label(round_label)
    if not normalized:
        return None

    for meta, tokens in KNOCKOUT_ROUND_RULES:
        if meta.id == "final":
            if normalized == "final" or ("final" in normalized and "1/" not in normalized):
                return meta
            continue
        if any(token in normalized for token in tokens):
            return meta
    return None


class FootballCompetitionStructureService:
    def get_blueprint(self, competition_id: int | None) -> FootballCompetitionBlueprint:
        return get_competition_blueprint(competition_id)

    def enrich_standings_snapshot(
        self,
        competition_id: int,
        snapshot: CompetitionStandingsSnapshotResponse,
    ) -> CompetitionStandingsSnapshotResponse:
        blueprint = self.get_blueprint(competition_id)
        if not blueprint.standings_stage_id:
            return snapshot

        return snapshot.model_copy(
            update={
                "stageId": blueprint.standings_stage_id,
                "stageName": blueprint.standings_stage_name or snapshot.stageName,
                "stageType": blueprint.standings_stage_type or snapshot.stageType,
            }
        )

    def resolve_format_kind(
        self,
        competition_id: int | None,
        match_rows: list[dict],
        standings_snapshot: CompetitionStandingsSnapshotResponse | None,
    ) -> str:
        blueprint = self.get_blueprint(competition_id)
        if blueprint.format_kind != "league":
            return blueprint.format_kind

        has_knockout = any(get_knockout_round_meta(row.get("round")) for row in match_rows)
        if standings_snapshot and standings_snapshot.stageType == "group" and has_knockout:
            return "groups_knockout"
        if has_knockout:
            return "knockout"
        return "league"

    def build_structure(
        self,
        competition_id: int,
        name: str,
        badge: str,
        country: str | None,
        match_rows: list[dict],
        standings_snapshot: CompetitionStandingsSnapshotResponse | None,
    ) -> CompetitionStructureResponse:
        stages = self.build_stages(competition_id, match_rows, standings_snapshot)
        format_kind = self.resolve_format_kind(competition_id, match_rows, standings_snapshot)
        return CompetitionStructureResponse(
            competitionId=competition_id,
            name=name,
            badge=badge,
            country=country,
            formatKind=format_kind,
            stages=stages,
        )

    def build_stages(
        self,
        competition_id: int | None,
        match_rows: list[dict],
        standings_snapshot: CompetitionStandingsSnapshotResponse | None,
    ) -> list[CompetitionStageResponse]:
        stages: list[CompetitionStageResponse] = []
        if standings_snapshot:
            stages.append(
                CompetitionStageResponse(
                    id=standings_snapshot.stageId,
                    name=standings_snapshot.stageName,
                    stageType=standings_snapshot.stageType,
                    order=0,
                    groups=[
                        CompetitionStageGroupResponse(
                            id=group.id,
                            name=group.name,
                            order=group.order,
                        )
                        for group in standings_snapshot.groups
                    ],
                )
            )

        seen_stage_ids = {stage.id for stage in stages}
        knockout_stage_map: dict[str, CompetitionStageResponse] = {}
        for row in match_rows:
            meta = self.resolve_knockout_stage_meta(competition_id, row.get("round"))
            if not meta:
                continue

            stage = knockout_stage_map.get(meta.id)
            round_label = row.get("round")
            if stage:
                if (
                    isinstance(round_label, str)
                    and round_label
                    and round_label not in stage.roundLabels
                ):
                    stage.roundLabels.append(round_label)
                continue

            knockout_stage_map[meta.id] = CompetitionStageResponse(
                id=meta.id,
                name=meta.name,
                stageType="knockout_round",
                order=meta.order,
                roundLabels=[round_label] if isinstance(round_label, str) and round_label else [],
            )

        for stage in sorted(knockout_stage_map.values(), key=lambda item: item.order):
            if stage.id not in seen_stage_ids:
                stages.append(stage)
        return stages

    def resolve_knockout_stage_meta(
        self, competition_id: int | None, round_label: str | None
    ) -> KnockoutRoundMeta | None:
        meta = get_knockout_round_meta(round_label)
        if meta:
            return meta

        blueprint = self.get_blueprint(competition_id)
        normalized = normalize_round_label(round_label)
        if blueprint.format_kind == "knockout" and not normalized:
            return KnockoutRoundMeta(id="knockout", name="Eliminatorias", order=10)
        return None
