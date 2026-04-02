from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.auth import AuthenticatedUser, CurrentUserResponse, PublicProfile
from app.services.users_query_service import UsersQueryService

router = APIRouter()
users_service = UsersQueryService()


@router.get("/me", response_model=CurrentUserResponse)
def get_me(user: AuthenticatedUser = Depends(get_current_user)) -> CurrentUserResponse:
    profile = users_service.repository.get_profile(user.id) or {}
    username = profile.get("username") or user.username
    return CurrentUserResponse(
        id=user.id,
        username=username,
        email=profile.get("email") or user.email,
        img=profile.get("avatar_url"),
    )


@router.get("/profiles", response_model=list[PublicProfile])
def get_profiles(ids: list[str] = Query(default_factory=list)) -> list[PublicProfile]:
    return users_service.get_profiles(ids)
