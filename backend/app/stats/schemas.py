"""
数据统计 Schema 定义
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 概览统计 ──
class OverviewStats(BaseModel):
    """概览统计"""
    total_media: int = 0
    total_movies: int = 0
    total_tv: int = 0
    total_size: int = 0  # bytes
    total_users: int = 0
    total_plays: int = 0
    total_watch_time: int = 0  # seconds
    today_plays: int = 0
    today_watch_time: int = 0
    active_users: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


# ── 趋势数据 ──
class TrendPoint(BaseModel):
    """趋势数据点"""
    timestamp: datetime
    value: float


class PlayTrend(BaseModel):
    """播放趋势"""
    hourly: list[TrendPoint] = []
    daily: list[TrendPoint] = []
    weekly: list[TrendPoint] = []


class GrowthTrend(BaseModel):
    """增长趋势"""
    media_count: list[TrendPoint] = []
    storage_used: list[TrendPoint] = []
    user_count: list[TrendPoint] = []


# ── TOP 排行 ──
class TopContentItem(BaseModel):
    """热门内容项"""
    id: int = Field(alias="media_id", serialization_alias="id")  # 前端期望 id
    title: str
    poster_url: str | None
    play_count: int
    watch_time: int  # seconds
    rating: float = 0

    model_config = {"populate_by_name": True}


class TopUserItem(BaseModel):
    """活跃用户项"""
    id: int = Field(alias="user_id", serialization_alias="id")  # 前端期望 id
    username: str
    avatar_url: str | None
    play_count: int
    watch_time: int
    last_active: datetime | None

    model_config = {"populate_by_name": True}


class TopContentResponse(BaseModel):
    """热门内容响应"""
    items: list[TopContentItem] = []
    period: str = "7d"  # 1d, 7d, 30d, all


class TopUsersResponse(BaseModel):
    """活跃用户响应"""
    items: list[TopUserItem] = []
    period: str = "7d"


# ── 媒体库统计 ──
class LibraryStats(BaseModel):
    """媒体库统计"""
    library_id: int
    name: str
    media_count: int
    total_size: int
    last_scan: datetime | None
    type_breakdown: dict[str, int] = {}


class LibrariesStatsResponse(BaseModel):
    """媒体库统计响应"""
    libraries: list[LibraryStats] = []
    total_media: int = 0
    total_size: int = 0


# ── 用户统计 ──
class UserStats(BaseModel):
    """用户播放统计"""
    user_id: int
    username: str
    total_plays: int
    total_watch_time: int
    avg_watch_time: int
    favorite_genres: list[str] = []
    recently_watched: list[int] = []  # media_ids


class UserStatsResponse(BaseModel):
    """用户统计响应"""
    user: UserStats
    hourly_distribution: list[TrendPoint] = []
    weekly_activity: list[TrendPoint] = []


# ── 系统监控 ──
class SystemMonitor(BaseModel):
    """系统监控"""
    cpu_percent: float
    memory_percent: float
    memory_used: int  # bytes
    memory_total: int
    disk_percent: float
    disk_used: int
    disk_total: int
    network_sent: int
    network_recv: int
    active_transcodes: int = 0
    active_streams: int = 0
    uptime: str
    timestamp: datetime = Field(default_factory=datetime.now)


# ── 播放统计记录 ──
class PlayRecordCreate(BaseModel):
    """播放记录创建"""
    media_id: int = Field(..., description="媒体 ID")
    duration_seconds: int = Field(0, ge=0, description="播放时长（秒）")
    device_type: str = Field("web", description="设备类型: web, mobile, tv, cast")
    ip_address: str | None = None


class PlayRecord(BaseModel):
    """播放记录"""
    id: int
    user_id: int
    media_id: int
    played_at: datetime
    duration_seconds: int
    device_type: str
    ip_address: str | None
    model_config = {"from_attributes": True}
