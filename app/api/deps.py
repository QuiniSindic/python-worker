from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.core.supabase import get_auth_client
from app.schemas.auth import AuthenticatedUser


def _extract_username(email: str | None, user_metadata: dict | None) -> str:
    if isinstance(user_metadata, dict):
        username = user_metadata.get("username")
        if isinstance(username, str) and username.strip():
            return username.strip()
    if email and "@" in email:
        return email.split("@", maxsplit=1)[0]
    return "Usuario"


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    auth_client = get_auth_client()
    try:
        response = auth_client.auth.get_user(token)
    except Exception as exc:  # pragma: no cover - client exceptions vary by version
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        ) from exc

    user = getattr(response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )

    email = getattr(user, "email", None)
    user_metadata = getattr(user, "user_metadata", None)

    return AuthenticatedUser(
        id=user.id,
        email=email,
        username=_extract_username(email, user_metadata),
    )


def require_internal_access(x_internal_key: str | None = Header(default=None)) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoints are disabled",
        )

    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key",
        )
