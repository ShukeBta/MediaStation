"""
用户模块 Pydantic 模型
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── 认证 ──
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


# ── 用户 CRUD ──
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="user", pattern=r"^(admin|user)$")
    tier: str = Field(default="free", pattern=r"^(free|plus)$")


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=100)
    role: str | None = Field(default=None, pattern=r"^(admin|user)$")
    tier: str | None = Field(default=None, pattern=r"^(free|plus)$")
    avatar: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    tier: str = "free"
    avatar: str | None = None
    nickname: str | None = None
    is_active: bool
    last_login: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 个人资料更新（普通用户自改）──
class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=100)


class UpdateProfileRequest(BaseModel):
    avatar: str | None = None
    nickname: str | None = None


# ── 用户权限 ──
class UserPermissionOut(BaseModel):
    """用户权限输出模型"""
    # 基础权限
    can_view_dashboard: bool = True
    can_play_media: bool = True
    can_cast: bool = True
    can_external_player: bool = True
    can_favorite: bool = True
    can_view_history: bool = True

    # 受限功能
    can_edit_media: bool = False
    can_rescrape: bool = False
    can_use_ai: bool = False
    can_capture_frames: bool = False
    can_manage_downloads: bool = False
    can_view_discover: bool = False
    can_manage_subscriptions: bool = False
    can_manage_sites: bool = False
    can_use_ai_assistant: bool = False
    can_manage_users: bool = False
    can_manage_files: bool = False
    can_manage_strm: bool = False
    can_access_settings: bool = False

    model_config = {"from_attributes": True}


class UserPermissionUpdate(BaseModel):
    """用户权限更新请求（管理员使用）"""
    can_view_dashboard: bool | None = None
    can_play_media: bool | None = None
    can_cast: bool | None = None
    can_external_player: bool | None = None
    can_favorite: bool | None = None
    can_view_history: bool | None = None
    can_edit_media: bool | None = None
    can_rescrape: bool | None = None
    can_use_ai: bool | None = None
    can_capture_frames: bool | None = None
    can_manage_downloads: bool | None = None
    can_view_discover: bool | None = None
    can_manage_subscriptions: bool | None = None
    can_manage_sites: bool | None = None
    can_use_ai_assistant: bool | None = None
    can_manage_users: bool | None = None
    can_manage_files: bool | None = None
    can_manage_strm: bool | None = None
    can_access_settings: bool | None = None


# ── 系统配置 ──
class SystemConfigOut(BaseModel):
    user_tier: str = "free"
    max_free_users: int = 30
    current_user_count: int = 0


class SystemConfigUpdate(BaseModel):
    user_tier: str | None = Field(default=None, pattern=r"^(free|plus)$")
    max_free_users: int | None = Field(default=None, ge=1, le=10000)


# ── 观看历史 ──
class WatchHistoryOut(BaseModel):
    id: int
    user_id: int
    media_item_id: int
    episode_id: int | None
    progress: float
    duration: float
    completed: bool
    last_watched: datetime
    # 附加信息
    media_title: str | None = None
    media_type: str | None = None
    poster_url: str | None = None
    episode_title: str | None = None

    model_config = {"from_attributes": True}
