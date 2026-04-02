from __future__ import annotations

from app.repositories.users_repository import UsersRepository
from app.schemas.auth import PublicProfile


class UsersQueryService:
    def __init__(self, repository: UsersRepository | None = None) -> None:
        self.repository = repository or UsersRepository()

    def get_profiles(self, user_ids: list[str]) -> list[PublicProfile]:
        profiles = self.repository.get_profiles_map(user_ids)
        items: list[PublicProfile] = []
        for user_id in user_ids:
            profile = profiles.get(user_id)
            if not profile:
                continue
            username = (
                profile.get("username")
                or (profile.get("email") or "Usuario").split("@", maxsplit=1)[0]
            )
            items.append(
                PublicProfile(
                    id=user_id,
                    username=username,
                    email=profile.get("email"),
                    img=profile.get("avatar_url"),
                )
            )
        return items
