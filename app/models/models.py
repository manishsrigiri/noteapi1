from typing import Any, List

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    filename: str
    content_type: str
    data_b64: str


class Note(BaseModel):
    id: str
    title: str
    content: str
    pinned: bool = False
    is_private: bool = False
    category: str = "General"
    tags: List[str] = Field(default_factory=list)
    attachments: List[Attachment] = Field(default_factory=list)
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
    role: str = "client"


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
    role: str = "client"


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


class BackgroundItem(BaseModel):
    id: str
    name: str
    data_b64: str
    content_type: str = "image/png"


class UserPreferences(BaseModel):
    theme: str | None = None
    background_mode: str | None = None
    background_solid: str | None = None
    background_gradient_start: str | None = None
    background_gradient_end: str | None = None
    background_gradient_dir: str | None = None
    background_image_id: str | None = None
    backgrounds: List[BackgroundItem] = Field(default_factory=list)
    hide_sidebar: bool | None = None
    background_image_fit: str | None = None
    background_image_scale: int | None = None
    background_image_pos_x: int | None = None
    background_image_pos_y: int | None = None
