"""
订阅模块 Pydantic 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── 站点 ──
SITE_TYPE_VALUES = Literal["nexusphp", "gazelle", "unit3d", "discuz", "mteam", "custom_rss"]
AUTH_TYPE_VALUES = Literal["cookie", "api_key", "authorization"]
DOWNLOADER_VALUES = Literal["qbittorrent", "transmission", "aria2", None]


class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1, max_length=500)
    site_type: str = Field(default="nexusphp")
    auth_type: str = Field(default="cookie")   # cookie / api_key / authorization
    cookie: str | None = None
    api_key: str | None = None                  # API令牌 / Passkey
    auth_header: str | None = None              # Authorization 头内容
    user_agent: str | None = None
    rss_url: str | None = None
    timeout: int = Field(default=15, ge=0, le=300)
    priority: int = Field(default=50, ge=1, le=100)
    use_proxy: bool = False
    rate_limit: bool = False
    browser_emulation: bool = False
    enabled: bool = True
    downloader: str | None = None


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    base_url: str | None = None
    site_type: str | None = None
    auth_type: str | None = None
    cookie: str | None = None
    api_key: str | None = None
    auth_header: str | None = None
    user_agent: str | None = None
    rss_url: str | None = None
    timeout: int | None = Field(default=None, ge=0, le=300)
    priority: int | None = Field(default=None, ge=1, le=100)
    use_proxy: bool | None = None
    rate_limit: bool | None = None
    browser_emulation: bool | None = None
    enabled: bool | None = None
    downloader: str | None = None


class SiteOut(BaseModel):
    id: int
    name: str
    base_url: str
    site_type: str
    auth_type: str = "cookie"
    rss_url: str | None
    timeout: int = 15
    enabled: bool
    priority: int
    use_proxy: bool = False
    rate_limit: bool = False
    browser_emulation: bool = False
    downloader: str | None = None
    login_status: str
    last_check: datetime | None
    upload_bytes: int = 0
    download_bytes: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 订阅 ──
class SubscriptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    original_name: str | None = Field(default=None, max_length=500, description="TMDB 英文原名，用于站点搜索")
    tmdb_id: int | None = None
    media_type: str = Field(..., pattern=r"^(movie|tv|anime)$")
    year: int | None = None
    quality_filter: list[str] = Field(default_factory=lambda: ["1080p", "720p"])
    min_size: int = Field(default=0, ge=0)
    max_size: int = Field(default=0, ge=0)
    exclude_keywords: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    quality_filter: list[str] | None = None
    min_size: int | None = None
    max_size: int | None = None
    exclude_keywords: list[str] | None = None
    include_keywords: list[str] | None = None
    status: str | None = Field(default=None, pattern=r"^(active|paused|completed)$")


class SubscriptionLogOut(BaseModel):
    action: str
    resource_title: str | None = None
    message: str | None = None
    success: bool  # derived: download=success, search/error=not success
    created_at: datetime
    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: int
    name: str
    original_name: str | None = None
    tmdb_id: int | None
    media_type: str
    year: int | None
    quality_filter: list[str] = []
    min_size: int
    max_size: int
    exclude_keywords: list[str] = []
    include_keywords: list[str] = []
    status: str
    last_search: datetime | None
    total_downloaded: int
    created_at: datetime
    last_log: SubscriptionLogOut | None = None
    model_config = {"from_attributes": True}


# ── 通知渠道 ──
class NotifyChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    channel_type: str = Field(..., pattern=r"^(telegram|wechat|bark|webhook|email)$")
    config: dict  # 通道配置（不同类型有不同字段）
    enabled: bool = True
    events: list[str] = Field(default_factory=list)


class NotifyChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None
    events: list[str] | None = None


class NotifyChannelOut(BaseModel):
    id: int
    name: str
    channel_type: str
    config: dict = {}
    enabled: bool
    events: list[str] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 搜索结果 ──
class ResourceOut(BaseModel):
    site_name: str
    site_id: int
    title: str
    size: int
    seeders: int
    leechers: int
    upload_time: str
    category: str
    free: bool
    download_url: str
