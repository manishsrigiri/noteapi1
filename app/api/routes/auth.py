import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse

from app.database.mongodb import get_session_collection, get_user_collection
from app.models.models import (
    AdminCreateUserRequest,
    AdminResetPasswordRequest,
    AdminUpdateUserRequest,
    BasicLoginRequest,
    BasicRegisterRequest,
    SessionLogoutRequest,
    UserPreferences,
    User,
)
from app.services.auth_service import bearer_scheme, create_session, get_current_user, hash_password
from app.utils.helpers import (
    active_session_filter,
    basic_auth_password,
    basic_auth_username,
    google_oauth_client_id,
    google_oauth_client_secret,
    google_oauth_redirect_uri,
    google_workspace_client_id,
    google_workspace_client_secret,
    google_workspace_domains,
    google_workspace_redirect_uri,
    is_admin_username,
    oauth_client_id,
    oauth_client_secret,
    oauth_redirect_uri,
    streamlit_public_url,
    now_iso,
)

router = APIRouter(tags=["auth"])
ALLOWED_ROLES = {"viewer", "editor", "admin", "user", "client"}
MAX_BG_COUNT = 8
MAX_BG_B64 = 1_500_000


def _normalize_role(role: str | None) -> str:
    normalized = (role or "client").strip().lower()
    if normalized in {"user", "viewer"}:
        normalized = "client"
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    return normalized


def _is_admin(username: str, role: str) -> bool:
    return role == "admin" or is_admin_username(username)


def _sanitize_prefs(prefs: UserPreferences) -> dict:
    data = prefs.model_dump()
    backgrounds = []
    for item in data.get("backgrounds", [])[:MAX_BG_COUNT]:
        if not isinstance(item, dict):
            continue
        data_b64 = item.get("data_b64", "")
        if not data_b64 or len(data_b64) > MAX_BG_B64:
            continue
        backgrounds.append(item)
    data["backgrounds"] = backgrounds
    bg_ids = {item.get("id") for item in backgrounds}
    if data.get("background_image_id") not in bg_ids:
        data["background_image_id"] = None
    return data


@router.get("/auth/github/login")
def github_login(next_url: str | None = Query(default=None)):
    client_id = oauth_client_id()
    if not client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth client id is missing")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(),
        "scope": "read:user user:email",
        "state": state,
    }
    if next_url:
        params["state"] = f"{state}|{next_url}"

    authorize_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=authorize_url)


@router.get("/auth/github/callback")
def github_callback(
    code: str,
    state: str | None = None,
    session_collection=Depends(get_session_collection),
):
    client_id = oauth_client_id()
    client_secret = oauth_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth credentials are missing")

    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": oauth_redirect_uri(),
        },
        timeout=10,
    )
    access_token = token_response.json().get("access_token")
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
        role="client",
        is_admin=_is_admin(profile.get("login", ""), "client"),
    )
    token = create_session(user, session_collection)

    next_url = streamlit_public_url()
    if state and "|" in state:
        next_url = state.split("|", 1)[1] or next_url
    return RedirectResponse(url=f"{next_url}?auth_token={token}")


@router.get("/auth/google/login")
def google_login(next_url: str | None = Query(default=None)):
    client_id = google_oauth_client_id()
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth client id is missing")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": google_oauth_redirect_uri(),
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


@router.get("/auth/google-workspace/login")
def google_workspace_login(next_url: str | None = Query(default=None)):
    client_id = google_workspace_client_id()
    if not client_id:
        raise HTTPException(status_code=500, detail="Google Workspace OAuth client id is missing")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "redirect_uri": google_workspace_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
        "access_type": "online",
    }
    domains = google_workspace_domains()
    if len(domains) == 1:
        params["hd"] = next(iter(domains))
    if next_url:
        params["state"] = f"{state}|{next_url}"

    authorize_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=authorize_url)

@router.get("/auth/google/callback")
def google_callback(
    code: str,
    state: str | None = None,
    session_collection=Depends(get_session_collection),
):
    client_id = google_oauth_client_id()
    client_secret = google_oauth_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth credentials are missing")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": google_oauth_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    access_token = token_response.json().get("access_token")
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
        role="client",
        is_admin=_is_admin(username, "client"),
    )
    token = create_session(user, session_collection)

    next_url = streamlit_public_url()
    if state and "|" in state:
        next_url = state.split("|", 1)[1] or next_url
    return RedirectResponse(url=f"{next_url}?auth_token={token}")


@router.get("/auth/google-workspace/callback")
def google_workspace_callback(
    code: str,
    state: str | None = None,
    session_collection=Depends(get_session_collection),
    user_collection=Depends(get_user_collection),
):
    client_id = google_workspace_client_id()
    client_secret = google_workspace_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google Workspace OAuth credentials are missing")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": google_workspace_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    access_token = token_response.json().get("access_token")
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
    allowed_domains = google_workspace_domains()
    email = profile.get("email", "")
    username = (email.split("@")[0] if email else profile.get("sub", "google-user")).lower()
    email_domain = email.split("@")[1].lower() if "@" in email else ""
    hosted_domain = (profile.get("hd") or "").lower()
    if allowed_domains:
        if email_domain not in allowed_domains and hosted_domain not in allowed_domains:
            raise HTTPException(status_code=403, detail="Google Workspace domain not allowed")

    existing_user = None
    if username:
        existing_user = user_collection.find_one({"_id": username})
        if not existing_user:
            user_collection.insert_one(
                {
                    "_id": username,
                    "display_name": profile.get("name", username or "Google User"),
                    "email": email,
                    "oauth_provider": "google_workspace",
                    "oauth_sub": profile.get("sub", ""),
                    "role": "client",
                    "created_at": now_iso(),
                }
            )
            existing_user = user_collection.find_one({"_id": username})

    role = _normalize_role((existing_user or {}).get("role"))
    user = User(
        id=str(profile.get("sub", "")),
        username=username,
        display_name=profile.get("name", username or "Google User"),
        avatar_url=profile.get("picture"),
        role=role,
        is_admin=_is_admin(username, role),
    )
    token = create_session(user, session_collection)

    next_url = streamlit_public_url()
    if state and "|" in state:
        next_url = state.split("|", 1)[1] or next_url
    return RedirectResponse(url=f"{next_url}?auth_token={token}")

@router.get("/auth/me", response_model=User)
def auth_me(user: User = Depends(get_current_user)):
    return user


@router.get("/auth/session-stats")
def auth_session_stats(
    user: User = Depends(get_current_user),
    session_collection=Depends(get_session_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    active_sessions = list(session_collection.find(active_session_filter(), {"user.username": 1}))
    usernames = {s.get("user", {}).get("username", "") for s in active_sessions}
    usernames.discard("")
    return {"active_sessions": len(active_sessions), "logged_in_users": len(usernames)}


@router.get("/auth/preferences")
def auth_preferences(
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    doc = user_collection.find_one({"_id": user.username}, {"ui_prefs": 1})
    return (doc or {}).get("ui_prefs", {})


@router.put("/auth/preferences")
def update_preferences(
    prefs: UserPreferences,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    data = _sanitize_prefs(prefs)
    user_collection.update_one({"_id": user.username}, {"$set": {"ui_prefs": data}}, upsert=True)
    return {"message": "Preferences saved", "prefs": data}


@router.get("/auth/admin/users/{username}/preferences")
def admin_get_preferences(
    username: str,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    doc = user_collection.find_one({"_id": username.lower()}, {"ui_prefs": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return (doc or {}).get("ui_prefs", {})


@router.put("/auth/admin/users/{username}/preferences")
def admin_update_preferences(
    username: str,
    prefs: UserPreferences,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    data = _sanitize_prefs(prefs)
    result = user_collection.update_one({"_id": username.lower()}, {"$set": {"ui_prefs": data}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Preferences saved", "prefs": data}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("/auth/sessions")
def auth_sessions(
    include_inactive: bool = True,
    user: User = Depends(get_current_user),
    session_collection=Depends(get_session_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    query = {} if include_inactive else active_session_filter()
    sessions = list(
        session_collection.find(
            query,
            {"user": 1, "created_at": 1, "last_seen": 1, "logged_out_at": 1, "expires_at": 1},
        )
    )
    now = datetime.now(UTC)
    now_ts = now.timestamp()
    response = []
    for session in sessions:
        created_at = session.get("created_at")
        last_seen = session.get("last_seen")
        logged_out_at = session.get("logged_out_at")
        created_dt = _parse_iso(created_at)
        end_dt = _parse_iso(logged_out_at) or now
        duration_seconds = None
        if created_dt:
            duration_seconds = max(0, int((end_dt - created_dt).total_seconds()))
        expires_at = session.get("expires_at", 0)
        is_active = (
            (logged_out_at is None)
            and isinstance(expires_at, (int, float))
            and expires_at > now_ts
        )
        response.append(
            {
                "token": session.get("_id"),
                "username": session.get("user", {}).get("username", ""),
                "created_at": created_at,
                "last_seen": last_seen,
                "logged_out_at": logged_out_at,
                "expires_at": expires_at,
                "is_active": is_active,
                "duration_seconds": duration_seconds,
            }
        )
    return {"sessions": response}


@router.post("/auth/sessions/logout")
def auth_sessions_logout(
    payload: SessionLogoutRequest,
    user: User = Depends(get_current_user),
    session_collection=Depends(get_session_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if not payload.token and not payload.username:
        raise HTTPException(status_code=400, detail="token or username is required")

    now_iso = datetime.now(UTC).isoformat()
    now_ts = datetime.now(UTC).timestamp()
    if payload.token:
        result = session_collection.update_one(
            {"_id": payload.token},
            {"$set": {"logged_out_at": now_iso, "expires_at": now_ts}},
        )
        return {"updated": result.modified_count}

    result = session_collection.update_many(
        {"user.username": payload.username},
        {"$set": {"logged_out_at": now_iso, "expires_at": now_ts}},
    )
    return {"updated": result.modified_count}


@router.post("/auth/basic/register")
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
    user_collection.insert_one(
        {
            "_id": username,
            "display_name": display_name,
            "password_hash": hash_password(password, salt),
            "salt": salt.hex(),
            "role": "client",
            "created_at": now_iso(),
        }
    )
    return {"message": "Account created successfully"}


@router.post("/auth/basic/login")
def basic_login(
    login_request: BasicLoginRequest,
    session_collection=Depends(get_session_collection),
    user_collection=Depends(get_user_collection),
):
    username = login_request.username.strip().lower()
    password = login_request.password

    valid_username = basic_auth_username().strip().lower()
    valid_password = basic_auth_password()
    if secrets.compare_digest(username, valid_username) and secrets.compare_digest(password, valid_password):
        role = "admin" if is_admin_username(username) else "client"
        user = User(
            id=f"basic-{username}",
            username=username,
            display_name=username,
            role=role,
            is_admin=_is_admin(username, role),
        )
        token = create_session(user, session_collection)
        return {"auth_token": token, "user": user.model_dump()}

    user_doc = user_collection.find_one({"_id": username})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    salt = bytes.fromhex(user_doc["salt"])
    provided_hash = hash_password(password, salt)
    if not secrets.compare_digest(provided_hash, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    role = _normalize_role(user_doc.get("role"))
    user = User(
        id=f"basic-{username}",
        username=username,
        display_name=user_doc.get("display_name", username),
        role=role,
        is_admin=_is_admin(username, role),
    )
    token = create_session(user, session_collection)
    return {"auth_token": token, "user": user.model_dump()}


@router.post("/auth/admin/users")
def admin_create_user(
    request: AdminCreateUserRequest,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    username = request.username.strip().lower()
    password = request.password
    display_name = (request.display_name or username).strip()
    role = _normalize_role(request.role)

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if user_collection.find_one({"_id": username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    salt = secrets.token_bytes(16)
    user_collection.insert_one(
        {
            "_id": username,
            "display_name": display_name,
            "password_hash": hash_password(password, salt),
            "salt": salt.hex(),
            "role": role,
            "created_at": now_iso(),
        }
    )
    return {"message": "User created successfully"}


@router.get("/auth/admin/users")
def admin_list_users(
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    users = list(
        user_collection.find(
            {},
            {
                "_id": 1,
                "display_name": 1,
                "role": 1,
                "email": 1,
                "oauth_provider": 1,
                "created_at": 1,
            },
        )
    )
    response = []
    for u in users:
        response.append(
            {
                "username": u.get("_id", ""),
                "display_name": u.get("display_name", ""),
                "role": _normalize_role(u.get("role")),
                "email": u.get("email", ""),
                "oauth_provider": u.get("oauth_provider", ""),
                "created_at": u.get("created_at", ""),
            }
        )
    return {"users": response}


@router.patch("/auth/admin/users/{username}")
def admin_update_user(
    username: str,
    request: AdminUpdateUserRequest,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    username = username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not user_collection.find_one({"_id": username}):
        raise HTTPException(status_code=404, detail="User not found")

    updates: dict = {}
    if request.display_name is not None:
        updates["display_name"] = request.display_name.strip()
    if request.role is not None:
        updates["role"] = _normalize_role(request.role)
    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")

    user_collection.update_one({"_id": username}, {"$set": updates})
    return {"message": "User updated successfully"}


@router.delete("/auth/admin/users/{username}")
def admin_delete_user(
    username: str,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    username = username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    result = user_collection.delete_one({"_id": username})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}


@router.post("/auth/admin/users/{username}/reset-password")
def admin_reset_password(
    username: str,
    request: AdminResetPasswordRequest,
    user: User = Depends(get_current_user),
    user_collection=Depends(get_user_collection),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    username = username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not user_collection.find_one({"_id": username}):
        raise HTTPException(status_code=404, detail="User not found")

    salt = secrets.token_bytes(16)
    user_collection.update_one(
        {"_id": username},
        {"$set": {"password_hash": hash_password(request.password, salt), "salt": salt.hex()}},
    )
    return {"message": "Password reset successfully"}


@router.post("/auth/logout")
def auth_logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session_collection=Depends(get_session_collection),
):
    if credentials:
        now_iso = datetime.now(UTC).isoformat()
        now_ts = datetime.now(UTC).timestamp()
        session_collection.update_one(
            {"_id": credentials.credentials},
            {"$set": {"logged_out_at": now_iso, "expires_at": now_ts}},
        )
    return {"message": "Logged out"}
