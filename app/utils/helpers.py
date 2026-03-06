import os
from datetime import UTC, datetime

from app.models.models import Note


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def normalize_note(note: dict) -> Note:
    return Note(
        id=note["_id"],
        title=note["title"],
        content=note["content"],
        pinned=note.get("pinned", False),
        is_private=note.get("is_private", False),
        category=note.get("category", "General"),
        tags=note.get("tags", []),
        created_at=note.get("created_at"),
        updated_at=note.get("updated_at"),
    )


def active_session_filter() -> dict:
    return {"expires_at": {"$gt": datetime.now(UTC).timestamp()}}


def auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED", "false").lower() == "true"


def oauth_client_id() -> str:
    return os.getenv("OAUTH_GITHUB_CLIENT_ID", "")


def oauth_client_secret() -> str:
    return os.getenv("OAUTH_GITHUB_CLIENT_SECRET", "")


def oauth_redirect_uri() -> str:
    return os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback")


def google_oauth_client_id() -> str:
    return os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")


def google_oauth_client_secret() -> str:
    return os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "")


def google_oauth_redirect_uri() -> str:
    return os.getenv(
        "OAUTH_GOOGLE_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback",
    )


def streamlit_public_url() -> str:
    return os.getenv("OAUTH_STREAMLIT_URL", "http://localhost:8501")


def basic_auth_username() -> str:
    return os.getenv("BASIC_AUTH_USERNAME", "demo")


def basic_auth_password() -> str:
    return os.getenv("BASIC_AUTH_PASSWORD", "demo123")


def admin_usernames() -> set[str]:
    raw = os.getenv("ADMIN_USERNAMES", "demo")
    return {name.strip().lower() for name in raw.split(",") if name.strip()}


def is_admin_username(username: str) -> bool:
    return username.strip().lower() in admin_usernames()
