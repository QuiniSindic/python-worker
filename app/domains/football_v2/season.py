from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

SeasonType = Literal["split_year", "calendar_year"]


@dataclass(frozen=True)
class SeasonRule:
    season_type: SeasonType
    season_start_month: int = 7


@dataclass(frozen=True)
class ResolvedSeason:
    season_key: str
    season_label: str
    season_type: SeasonType
    start_at: date
    end_at: date


def _as_date(value: date | datetime | None) -> date:
    if value is None:
        return datetime.now(UTC).date()
    if isinstance(value, datetime):
        return value.date()
    return value


def resolve_current_season(
    rule: SeasonRule,
    reference_at: date | datetime | None = None,
) -> ResolvedSeason:
    current = _as_date(reference_at)
    if rule.season_type == "calendar_year":
        year = current.year
        return ResolvedSeason(
            season_key=str(year),
            season_label=str(year),
            season_type=rule.season_type,
            start_at=date(year, 1, 1),
            end_at=date(year, 12, 31),
        )

    start_year = current.year if current.month >= rule.season_start_month else current.year - 1
    end_year = start_year + 1
    return ResolvedSeason(
        season_key=f"{start_year}-{end_year}",
        season_label=f"{start_year}/{str(end_year)[-2:]}",
        season_type=rule.season_type,
        start_at=date(start_year, rule.season_start_month, 1),
        end_at=date(end_year, rule.season_start_month, 1),
    )
