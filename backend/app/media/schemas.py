"""
媒体库 Pydantic 模型
"""
from __future__ import annotations

import json
from annotated_types import Gt, Lt
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator

# 自定义 validator 函数
def parse_optional_int(v: Any) -> int | None:
    """将空字符串或 None 转换为 None，其他情况尝试转换为 int"""
    if v is None or v == "":
        return None
    return int(v)


# 类型别名
OptionalInt = Annotated[int | None, BeforeValidator(parse_optional_int)]


# ── 媒体库 ──
class LibraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1, max_length=500)
    media_type: str = Field(default="movie", pattern=r"^(movie|tv|anime)$")
    scan_interval: int = Field(default=60, ge=5)
    enabled: bool = True
    # 高级设置
    min_file_size: int = Field(default=0, ge=0)                   # 最小文件大小（字节），0表示不限
    metadata_language: str = Field(default="zh-CN")                 # 元数据语言
    adult_content: bool = Field(default=False)                      # 允许成人内容
    prefer_nfo: bool = Field(default=True)                         # 优先使用NFO元数据
    enable_watch: bool = Field(default=True)                       # 启用实时监控

class LibraryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    path: str | None = Field(default=None, max_length=500)
    media_type: str | None = Field(default=None, pattern=r"^(movie|tv|anime)$")
    scan_interval: int | None = Field(default=None, ge=5)
    enabled: bool | None = None
    # 高级设置
    min_file_size: int | None = Field(default=None, ge=0)
    metadata_language: str | None = None
    adult_content: bool | None = None
    prefer_nfo: bool | None = None
    enable_watch: bool | None = None

class LibraryOut(BaseModel):
    id: int
    name: str
    path: str
    media_type: str
    scan_interval: int
    enabled: bool
    last_scan: datetime | None
    item_count: int = 0
    created_at: datetime
    # 高级设置
    min_file_size: int = 0
    metadata_language: str = "zh-CN"
    adult_content: bool = False
    prefer_nfo: bool = True
    enable_watch: bool = True
    model_config = {"from_attributes": True}


# ── 媒体条目 ──
class MediaItemOut(BaseModel):
    id: int
    library_id: int
    tmdb_id: int | None
    title: str
    original_title: str | None
    year: int | None
    overview: str | None
    poster_url: str | None
    backdrop_url: str | None
    media_type: str
    rating: float
    douban_rating: float | None = None
    bangumi_rating: float | None = None
    genres: list[str] = []
    file_path: str
    file_size: int
    duration: int
    video_codec: str | None
    audio_codec: str | None
    resolution: str | None
    container: str | None
    scraped: bool
    created_at: datetime
    # 视频增强元数据
    hdr_format: str | None = None
    audio_channels: str | None = None
    frame_rate: float | None = None
    color_space: str | None = None
    bit_depth: int | None = None
    # 重复检测
    is_duplicate: bool = False
    duplicate_of: int | None = None
    model_config = {"from_attributes": True}

    @field_validator("genres", mode="before")
    @classmethod
    def parse_genres(cls, v: any) -> list[str]:
        """数据库存 JSON 字符串，反序列化为 list"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return v if isinstance(v, list) else []


class MediaItemDetail(MediaItemOut):
    seasons: list[SeasonOut] = []
    subtitles: list[SubtitleOut] = []


class SeasonOut(BaseModel):
    id: int
    season_number: int
    name: str | None
    poster_url: str | None
    episode_count: int = 0
    episodes: list[EpisodeOut] = []
    model_config = {"from_attributes": True}


class EpisodeOut(BaseModel):
    id: int
    episode_number: int
    title: str | None
    file_path: str | None
    file_size: int
    duration: int
    air_date: date | None
    video_codec: str | None = None
    audio_codec: str | None = None
    model_config = {"from_attributes": True}


class SubtitleOut(BaseModel):
    id: int
    language: str
    language_name: str
    path: str | None
    source: str
    model_config = {"from_attributes": True}


# ── 刮削 ──
class ScrapeRequest(BaseModel):
    tmdb_id: int | None = None
    title: str | None = None
    year: int | None = None


# ── 手动编辑元数据 ──
class MediaItemUpdate(BaseModel):
    """手动更新媒体条目元数据（管理员用）"""
    title: str | None = Field(default=None, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None, ge=1900, le=2030)
    overview: str | None = None
    poster_url: str | None = Field(default=None, max_length=1000)
    backdrop_url: str | None = Field(default=None, max_length=1000)
    tmdb_id: OptionalInt = None
    douban_id: str | None = Field(default=None, max_length=50)
    bangumi_id: OptionalInt = None
    rating: float | None = Field(default=None, ge=0, le=10)
    douban_rating: float | None = Field(default=None, ge=0, le=10)
    bangumi_rating: float | None = Field(default=None, ge=0, le=10)
    genres: list[str] | None = None
    duration: int | None = Field(default=None, ge=0)
    media_type: str | None = Field(default=None, pattern=r"^(movie|tv|anime)$")


# ── 分页 ──
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: list, total: int, page: int, page_size: int):
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0,
        )


# ── 扫描结果 ──
class ScanResult(BaseModel):
    added: int = 0
    updated: int = 0
    removed: int = 0
    scraped: int = 0  # 自动刮削成功的数量
    errors: list[str] = []
