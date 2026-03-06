import secrets
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse

from app.database.mongodb import get_session_collection, get_user_collection
from app.models.models import BasicLoginRequest, BasicRegisterRequest, User
from app.services.auth_service import bearer_scheme, create_session, get_current_user, hash_password
from app.utils.helpers import (
    active_session_filter,
    basic_auth_password,
    basic_auth_username,
    google_oauth_client_id,
    google_oauth_client_secret,
    google_oauth_redirect_uri,
    is_admin_username,
    oauth_client_id,
    oauth_client_secret,
    oauth_redirect_uri,
    streamlit_public_url,
    now_iso,
)

router = APIRouter(tags=["auth"])


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
        is_admin=is_admin_username(profile.get("login", "")),
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
        is_admin=is_admin_username(username),
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
        user = User(
            id=f"basic-{username}",
            username=username,
            display_name=username,
            is_admin=is_admin_username(username),
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

    user = User(
        id=f"basic-{username}",
        username=username,
        display_name=user_doc.get("display_name", username),
        is_admin=is_admin_username(username),
    )
    token = create_session(user, session_collection)
    return {"auth_token": token, "user": user.model_dump()}


@router.post("/auth/logout")
def auth_logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session_collection=Depends(get_session_collection),
):
    if credentials:
        session_collection.delete_one({"_id": credentials.credentials})
    return {"message": "Logged out"}
