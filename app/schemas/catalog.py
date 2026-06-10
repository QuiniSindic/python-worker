from __future__ import annotations

from pydantic import BaseModel


class CompetitionEditionLite(BaseModel):
    id: int
    season_key: str
    season_label: str
    is_current: bool


class SportOption(BaseModel):
    id: int
    name: str
    slug: str
    displayName: str


class CompetitionOption(BaseModel):
    id: int
    name: str
    country: str | None = None
    current_edition: CompetitionEditionLite | None = None
