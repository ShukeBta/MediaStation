"""
播放列表 Schema 定义
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 播放列表 ──
class PlaylistCreate(BaseModel):
    """创建播放列表"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_public: bool = False


class PlaylistUpdate(BaseModel):
    """更新播放列表"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    cover_url: str | None = None
    is_public: bool | None = None


class PlaylistOut(BaseModel):
    """播放列表响应"""
    id: int
    user_id: int
    name: str
    description: str | None
    cover_url: str | None
    is_public: bool
    item_count: int = 0
    total_duration: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PlaylistDetailOut(PlaylistOut):
    """播放列表详情响应"""
    items: list["PlaylistItemOut"] = []


# ── 播放列表项 ──
class PlaylistItemAdd(BaseModel):
    """添加播放列表项"""
    media_id: int = Field(..., description="媒体 ID")
    position: int | None = Field(None, description="插入位置")


class PlaylistItemOut(BaseModel):
    """播放列表项响应"""
    id: int
    playlist_id: int
    media_item_id: int
    position: int
    added_at: datetime
    # 媒体详情
    media_title: str | None = None
    media_poster: str | None = None
    media_type: str | None = None
    media_duration: int | None = None
    model_config = {"from_attributes": True}


# ── 批量操作 ──
class PlaylistReorder(BaseModel):
    """播放列表重排序"""
    item_ids: list[int] = Field(..., description="按新顺序排列的项 ID 列表")


# 前向引用
PlaylistDetailOut.model_rebuild()
