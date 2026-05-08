"""
下载模块 Pydantic 模型
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── 下载客户端 ──
class DownloadClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    client_type: str = Field(..., pattern=r"^(qbittorrent|transmission|aria2)$")
    host: str = Field(..., min_length=1)
    port: int = Field(default=8080, ge=1, le=65535)
    username: str | None = None
    password: str | None = None  # aria2 复用为 RPC secret token
    enabled: bool = True
    category: str = "MediaStation"


class DownloadClientUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    enabled: bool | None = None
    category: str | None = None


class DownloadClientOut(BaseModel):
    id: int
    name: str
    client_type: str
    host: str
    port: int
    enabled: bool
    category: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 下载任务 ──
class DownloadTaskCreate(BaseModel):
    torrent_url: str = Field(..., min_length=1)
    client_id: int | None = None
    save_path: str | None = None
    category: str | None = None
    # 站点信息（可选，用于解析 genDlToken 等需要认证的下载链接）
    site_id: int | None = None
    site_type: str | None = None
    title: str | None = None  # 种子名称（用于解析失败时的记录）


class DownloadTaskOut(BaseModel):
    id: int
    client_id: int | None
    subscription_id: int | None
    media_id: int | None
    torrent_name: str | None
    torrent_url: str | None
    info_hash: str | None
    save_path: str | None
    status: str
    progress: float
    total_size: int
    downloaded: int
    speed: int
    seeders: int
    eta: int
    message: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class DownloadTaskBulkAction(BaseModel):
    ids: list[int]
    action: str = Field(..., pattern=r"^(pause|resume|delete)$")
    delete_files: bool = False


# ── Aria2 扩展 ──
class Aria2GlobalStats(BaseModel):
    """Aria2 全局统计"""
    numActive: int = 0
    numWaiting: int = 0
    numStopped: int = 0
    numStoppedTotal: int = 0
    downloadSpeed: int = 0     # bytes/s
    uploadSpeed: int = 0       # bytes/s
