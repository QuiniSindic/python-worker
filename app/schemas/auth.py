from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None
    username: str


class PublicProfile(BaseModel):
    id: str
    username: str
    email: str | None = None
    img: str | None = None


class CurrentUserResponse(PublicProfile):
    pass
