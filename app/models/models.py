from typing import Any, List

from pydantic import BaseModel, Field


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
    role: str = "user"


class BasicLoginRequest(BaseModel):
    username: str
    password: str


class BasicRegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None


class SessionLogoutRequest(BaseModel):
    token: str | None = None
    username: str | None = None


class AdminCreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "user"


class AdminUpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None


class AdminResetPasswordRequest(BaseModel):
    password: str


class NoteChangeRequest(BaseModel):
    action: str
    note_id: str | None = None
    payload: dict[str, Any] | None = None
    reason: str | None = None


class ChangeDecisionRequest(BaseModel):
    reason: str | None = None
