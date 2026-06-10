def extract_username(email: str | None, user_metadata: dict | None) -> str:
    """Builds a display username from Supabase metadata or email."""
    if isinstance(user_metadata, dict):
        username = user_metadata.get("username")
        if isinstance(username, str) and username.strip():
            return username.strip()
    if email and "@" in email:
        return email.split("@", maxsplit=1)[0]
    return "Usuario"