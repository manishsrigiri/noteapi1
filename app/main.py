# app/main.py
import os
import secrets
import hashlib
from datetime import datetime, UTC
from typing import List
from urllib.parse import urlencode

import requests
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pymongo import MongoClient

app = FastAPI()
bearer_scheme = HTTPBearer(auto_error=False)

# -------------------------
# Models
# -------------------------
class Note(BaseModel):
    id: str
    title: str
    content: str
    pinned: bool = False
    is_private: bool = False
    category: str = "General"
    tags: List[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class PinRequest(BaseModel):
    pinned: bool = True


class User(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    is_admin: bool = False


class BasicLoginRequest(BaseModel):
    username: str
    password: str


class BasicRegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None

# -------------------------
# MongoDB Dependency
# -------------------------
def get_client():
    """Return a MongoClient instance."""
    return MongoClient("mongodb://mongo:27017")  # Change host if needed

def get_collection(client: MongoClient = Depends(get_client)):
    """Return the MongoDB collection object."""
    db = client["notesdb"]
    return db["notes"]


def get_session_collection(client: MongoClient = Depends(get_client)):
    db = client["notesdb"]
    return db["sessions"]


def get_user_collection(client: MongoClient = Depends(get_client)):
    db = client["notesdb"]
    return db["users"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_note(note: dict) -> Note:
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


def _auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED", "false").lower() == "true"


def _oauth_client_id() -> str:
    return os.getenv("OAUTH_GITHUB_CLIENT_ID", "")


def _oauth_client_secret() -> str:
    return os.getenv("OAUTH_GITHUB_CLIENT_SECRET", "")


def _oauth_redirect_uri() -> str:
    return os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback")


def _google_oauth_client_id() -> str:
    return os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")


def _google_oauth_client_secret() -> str:
    return os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "")


def _google_oauth_redirect_uri() -> str:
    return os.getenv(
        "OAUTH_GOOGLE_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback",
    )


def _streamlit_public_url() -> str:
    return os.getenv("OAUTH_STREAMLIT_URL", "http://localhost:8501")


def _basic_auth_username() -> str:
    return os.getenv("BASIC_AUTH_USERNAME", "demo")


def _basic_auth_password() -> str:
    return os.getenv("BASIC_AUTH_PASSWORD", "demo123")


def _admin_usernames() -> set[str]:
    raw = os.getenv("ADMIN_USERNAMES", "demo")
    return {name.strip().lower() for name in raw.split(",") if name.strip()}


def _is_admin_username(username: str) -> bool:
    return username.strip().lower() in _admin_usernames()


def _create_session(user: User, session_collection) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC).timestamp() + 60 * 60 * 24
    session_collection.insert_one(
        {
            "_id": token,
            "user": user.model_dump(),
            "created_at": _now_iso(),
            "expires_at": expires_at,
        }
    )
    return token


def _hash_password(password: str, salt: bytes) -> str:
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return derived.hex()


def _read_session(token: str, session_collection) -> User | None:
    session = session_collection.find_one({"_id": token})
    if not session:
        return None
    if session.get("expires_at", 0) < datetime.now(UTC).timestamp():
        session_collection.delete_one({"_id": token})
        return None
    return User(**session["user"])


def _active_session_filter() -> dict:
    return {"expires_at": {"$gt": datetime.now(UTC).timestamp()}}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session_collection=Depends(get_session_collection),
) -> User:
    if _auth_disabled():
        return User(
            id="dev-user",
            username="dev-user",
            display_name="Dev User",
            is_admin=True,
        )

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = _read_session(credentials.credentials, session_collection)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user


@app.get("/auth/github/login")
def github_login(next_url: str | None = Query(default=None)):
    client_id = _oauth_client_id()
    if not client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth client id is missing")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": _oauth_redirect_uri(),
        "scope": "read:user user:email",
        "state": state,
    }
    if next_url:
        params["state"] = f"{state}|{next_url}"

    authorize_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=authorize_url)


@app.get("/auth/github/callback")
def github_callback(
    code: str,
    state: str | None = None,
    session_collection=Depends(get_session_collection),
):
    client_id = _oauth_client_id()
    client_secret = _oauth_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth credentials are missing")

    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": _oauth_redirect_uri(),
        },
        timeout=10,
    )
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=10,
    )
    if user_response.status_code >= 400:
        raise HTTPException(status_code=400, detail="Could not fetch GitHub user")

    profile = user_response.json()
    user = User(
        id=str(profile["id"]),
        username=profile.get("login", "github-user"),
        display_name=profile.get("name") or profile.get("login", "GitHub User"),
        avatar_url=profile.get("avatar_url"),
        is_admin=_is_admin_username(profile.get("login", "")),
    )
    token = _create_session(user, session_collection)

    next_url = _streamlit_public_url()
    if state and "|" in state:
        next_url = state.split("|", 1)[1] or next_url
    redirect_url = f"{next_url}?auth_token={token}"
    return RedirectResponse(url=redirect_url)


@app.get("/auth/google/login")
def google_login(next_url: str | None = Query(default=None)):
    client_id = _google_oauth_client_id()
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth client id is missing")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": _google_oauth_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
        "access_type": "online",
    }
    if next_url:
        params["state"] = f"{state}|{next_url}"

    authorize_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=authorize_url)


@app.get("/auth/google/callback")
def google_callback(
    code: str,
    state: str | None = None,
    session_collection=Depends(get_session_collection),
):
    client_id = _google_oauth_client_id()
    client_secret = _google_oauth_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth credentials are missing")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": _google_oauth_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    user_response = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if user_response.status_code >= 400:
        raise HTTPException(status_code=400, detail="Could not fetch Google user")

    profile = user_response.json()
    email = profile.get("email", "")
    username = email.split("@")[0] if email else profile.get("sub", "google-user")
    user = User(
        id=str(profile.get("sub", "")),
        username=username,
        display_name=profile.get("name", username or "Google User"),
        avatar_url=profile.get("picture"),
        is_admin=_is_admin_username(username),
    )
    token = _create_session(user, session_collection)

    next_url = _streamlit_public_url()
    if state and "|" in state:
        next_url = state.split("|", 1)[1] or next_url
    redirect_url = f"{next_url}?auth_token={token}"
    return RedirectResponse(url=redirect_url)


@app.get("/auth/me", response_model=User)
def auth_me(user: User = Depends(get_current_user)):
    return user


@app.get("/auth/session-stats")
def auth_session_stats(
    user: User = Depends(get_current_user),
    session_collection=Depends(get_session_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    active_sessions = list(session_collection.find(_active_session_filter(), {"user.username": 1}))
    usernames = {s.get("user", {}).get("username", "") for s in active_sessions}
    usernames.discard("")
    return {
        "active_sessions": len(active_sessions),
        "logged_in_users": len(usernames),
    }


@app.post("/auth/basic/register")
def basic_register(
    register_request: BasicRegisterRequest,
    user_collection=Depends(get_user_collection),
):
    username = register_request.username.strip().lower()
    password = register_request.password
    display_name = (register_request.display_name or username).strip()

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if user_collection.find_one({"_id": username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    user_collection.insert_one(
        {
            "_id": username,
            "display_name": display_name,
            "password_hash": password_hash,
            "salt": salt.hex(),
            "created_at": _now_iso(),
        }
    )
    return {"message": "Account created successfully"}


@app.post("/auth/basic/login")
def basic_login(
    login_request: BasicLoginRequest,
    session_collection=Depends(get_session_collection),
    user_collection=Depends(get_user_collection),
):
    username = login_request.username.strip().lower()
    password = login_request.password

    valid_username = _basic_auth_username().strip().lower()
    valid_password = _basic_auth_password()
    if secrets.compare_digest(username, valid_username) and secrets.compare_digest(password, valid_password):
        user = User(
            id=f"basic-{username}",
            username=username,
            display_name=username,
            is_admin=_is_admin_username(username),
        )
        token = _create_session(user, session_collection)
        return {"auth_token": token, "user": user.model_dump()}

    user_doc = user_collection.find_one({"_id": username})
    if user_doc:
        salt = bytes.fromhex(user_doc["salt"])
        expected_hash = user_doc["password_hash"]
        provided_hash = _hash_password(password, salt)
        if not secrets.compare_digest(provided_hash, expected_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        user = User(
            id=f"basic-{username}",
            username=username,
            display_name=user_doc.get("display_name", username),
            is_admin=_is_admin_username(username),
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _create_session(user, session_collection)
    return {"auth_token": token, "user": user.model_dump()}


@app.post("/auth/logout")
def auth_logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session_collection=Depends(get_session_collection),
):
    if credentials:
        session_collection.delete_one({"_id": credentials.credentials})
    return {"message": "Logged out"}

# -------------------------
# CRUD Endpoints
# -------------------------
@app.post("/notes")
def create_note(
    note: Note,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    if collection.find_one({"_id": note.id}):
        raise HTTPException(status_code=400, detail="Note already exists")
    payload = note.model_dump()
    now = _now_iso()
    payload["created_at"] = now
    payload["updated_at"] = now
    collection.insert_one(payload | {"_id": note.id})
    return {"message": "Note created successfully"}

@app.get("/notes", response_model=List[Note])
def get_notes(collection=Depends(get_collection), user: User = Depends(get_current_user)):
    notes = []
    for note in collection.find():
        notes.append(_normalize_note(note))
    return notes


@app.get("/notes/stats")
def get_note_stats(collection=Depends(get_collection), user: User = Depends(get_current_user)):
    total_ids = collection.count_documents({})
    pinned_count = collection.count_documents({"pinned": True})
    private_count = collection.count_documents({"is_private": True})
    category_pipeline = [
        {
            "$group": {
                "_id": {"$ifNull": ["$category", "General"]},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1, "_id": 1}},
    ]
    categories = {
        doc["_id"]: doc["count"] for doc in collection.aggregate(category_pipeline)
    }
    return {
        "total_ids": total_ids,
        "pinned_ids": pinned_count,
        "private_ids": private_count,
        "public_ids": total_ids - private_count,
        "categories": categories,
    }


@app.get("/notes/{id}", response_model=Note)
def get_note(id: str, collection=Depends(get_collection), user: User = Depends(get_current_user)):
    note = collection.find_one({"_id": id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _normalize_note(note)

@app.put("/notes/{id}")
def update_note(
    id: str,
    note: Note,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    existing = collection.find_one({"_id": id})
    if not existing:
        raise HTTPException(status_code=404, detail="Note not found")

    payload = note.model_dump()
    payload["id"] = id
    payload["created_at"] = existing.get("created_at", _now_iso())
    payload["updated_at"] = _now_iso()
    result = collection.update_one({"_id": id}, {"$set": payload})
    return {"message": "Note updated successfully"}


@app.put("/notes/{id}/pin")
def pin_note(
    id: str,
    pin_request: PinRequest,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    result = collection.update_one(
        {"_id": id},
        {"$set": {"pinned": pin_request.pinned, "updated_at": _now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    action = "pinned" if pin_request.pinned else "unpinned"
    return {"message": f"Note {action} successfully"}


@app.delete("/notes/{id}")
def delete_note(
    id: str,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    result = collection.delete_one({"_id": id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}
