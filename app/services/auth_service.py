import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database.mongodb import get_session_collection
from app.models.models import User
from app.utils.helpers import auth_disabled

bearer_scheme = HTTPBearer(auto_error=False)


def create_session(user: User, session_collection) -> str:
    token = secrets.token_urlsafe(32)
    created_at = datetime.now(UTC).isoformat()
    expires_at = datetime.now(UTC).timestamp() + 60 * 60 * 24
    session_collection.insert_one(
        {
            "_id": token,
            "user": user.model_dump(),
            "created_at": created_at,
            "last_seen": created_at,
            "logged_out_at": None,
            "expires_at": expires_at,
        }
    )
    return token


def read_session(token: str, session_collection) -> User | None:
    session = session_collection.find_one({"_id": token})
    if not session:
        return None
    if session.get("logged_out_at"):
        return None
    if session.get("expires_at", 0) < datetime.now(UTC).timestamp():
        session_collection.delete_one({"_id": token})
        return None
    session_collection.update_one({"_id": token}, {"$set": {"last_seen": datetime.now(UTC).isoformat()}})
    return User(**session["user"])


def hash_password(password: str, salt: bytes) -> str:
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return derived.hex()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session_collection=Depends(get_session_collection),
) -> User:
    if auth_disabled():
        return User(
            id="dev-user",
            username="dev-user",
            display_name="Dev User",
            is_admin=True,
            role="admin",
        )

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = read_session(credentials.credentials, session_collection)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user
