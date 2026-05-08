"""
管理后台 Schema 定义
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 定时任务 ──
class TaskResponse(BaseModel):
    """定时任务响应"""
    id: str
    name: str
    type: str
    schedule: str
    next_run: datetime | None
    enabled: bool
    last_run: datetime | None = None
    status: str = "idle"


class TaskCreate(BaseModel):
    """创建定时任务"""
    name: str = Field(..., description="任务名称", min_length=1)
    type: str = Field(..., description="任务类型: scan, scrape, cleanup")
    schedule: str = Field(..., description="Cron 表达式，如 @daily, @hourly, 0 * * * *")
    target_id: int | None = Field(None, description="目标媒体库 ID")
    enabled: bool = Field(True, description="是否启用")


class TaskUpdate(BaseModel):
    """更新定时任务"""
    name: str | None = None
    schedule: str | None = None
    enabled: bool | None = None


# ── 批量操作 ──
class BatchScanRequest(BaseModel):
    """批量扫描请求"""
    library_ids: list[int] = Field(..., description="媒体库 ID 列表", min_length=1)


class BatchScrapeRequest(BaseModel):
    """批量刮削请求"""
    media_ids: list[int] = Field(..., description="媒体 ID 列表", min_length=1)
    sources: list[str] | None = Field(None, description="刮削数据源列表")


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    media_ids: list[int] = Field(..., description="媒体 ID 列表", min_length=1)
    force: bool = Field(False, description="是否强制删除（跳过回收站）")


class BatchMoveRequest(BaseModel):
    """批量移动请求"""
    media_ids: list[int] = Field(..., description="媒体 ID 列表", min_length=1)
    target_library_id: int = Field(..., description="目标媒体库 ID")


class BatchFavoriteRequest(BaseModel):
    """批量收藏请求"""
    media_ids: list[int] = Field(..., description="媒体 ID 列表", min_length=1)
    action: str = Field("add", description="操作: add, remove")


class BatchWatchedRequest(BaseModel):
    """批量标记已看请求"""
    media_ids: list[int] = Field(..., description="媒体 ID 列表", min_length=1)
    action: str = Field("mark", description="操作: mark, unmark")


class BatchOperationResult(BaseModel):
    """批量操作结果"""
    message: str
    started: list[int] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    success_count: int = 0
    error_count: int = 0


# ── 系统设置 ──
class SystemSettings(BaseModel):
    """系统设置响应"""
    app_name: str
    version: str
    enable_gpu: bool
    max_transcode: int
    transcode_enabled: bool
    cache_path: str
    data_path: str
    tmdb_configured: bool = False
    adult_enabled: bool = True
    max_upload_size: int = 1024 * 1024 * 1024  # 1GB


class SystemSettingsUpdate(BaseModel):
    """系统设置更新"""
    app_name: str | None = None
    enable_gpu: bool | None = None
    max_transcode: int | None = Field(None, ge=1, le=10)
    transcode_enabled: bool | None = None
    cache_path: str | None = None
    adult_enabled: bool | None = None


# ── 内容分级 ──
class ContentRatingResponse(BaseModel):
    """内容分级响应"""
    enabled: bool
    default_level: str
    allowed_levels: list[str]


class ContentRatingUpdate(BaseModel):
    """内容分级更新"""
    enabled: bool | None = None
    default_level: str | None = None


# ── 文件浏览 ──
class FileItem(BaseModel):
    """文件项"""
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    modified: datetime | None = None
    permissions: str | None = None


class BrowseResponse(BaseModel):
    """目录浏览响应"""
    current: str
    parent: str | None
    items: list[FileItem]


class FileOperationRequest(BaseModel):
    """文件操作请求"""
    path: str = Field(..., description="文件路径", min_length=1)
    target: str | None = Field(None, description="目标路径（移动/复制时）")
    new_name: str | None = Field(None, description="新名称（重命名时）")


class FileRenamePreview(BaseModel):
    """重命名预览"""
    original: str
    renamed: str
    exists: bool = False
    warning: str | None = None


class BatchRenamePreview(BaseModel):
    """批量重命名预览响应"""
    total: int = 0
    valid: int = 0
    conflicts: int = 0
    previews: list[FileRenamePreview] = Field(default_factory=list)


class BatchRenameOperation(BaseModel):
    """批量重命名操作"""
    path: str = Field(..., description="原文件路径", min_length=1)
    new_name: str = Field(..., description="新名称", min_length=1)


class BatchRenameRequest(BaseModel):
    """批量重命名请求"""
    operations: list[BatchRenameOperation] = Field(..., description="重命名操作列表", min_length=1)
    mode: str = Field("execute", description="模式: preview | execute")


# ── AI 重命名 ──
class AIRenameRequest(BaseModel):
    """AI 生成重命名请求"""
    paths: list[str] = Field(..., description="文件路径列表", min_length=1)
    style: str = Field("media", description="重命名风格: media(媒体规范) | clean(整洁) | original(保留原名)")
    language: str = Field("zh", description="语言偏好: zh | en")
    extra_hint: str | None = Field(None, description="补充提示，如系列名称、年份等")


class AIRenameCandidate(BaseModel):
    """AI 重命名候选结果"""
    original: str = Field(..., description="原始文件名")
    original_path: str = Field(..., description="原始完整路径")
    suggested: str = Field(..., description="AI 建议的文件名")
    suggested_path: str = Field(..., description="建议的完整路径")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度 0-1")
    reason: str = Field("", description="重命名理由")
    exists: bool = Field(False, description="目标路径是否已存在")
    error: str | None = Field(None, description="错误信息（AI 无法处理时）")


class AIRenameResponse(BaseModel):
    """AI 重命名响应"""
    total: int = Field(0, description="总数")
    success: int = Field(0, description="成功生成建议数")
    failed: int = Field(0, description="失败数")
    candidates: list[AIRenameCandidate] = Field(default_factory=list)
    model_used: str = Field("", description="使用的 AI 模型")
    tokens_used: int = Field(0, description="消耗的 token 数")


# ── 文件夹操作（alias schemas）──
class FolderCreateRequest(BaseModel):
    """创建文件夹请求"""
    path: str = Field(..., description="要创建的文件夹完整路径", min_length=1)


class FolderRenameRequest(BaseModel):
    """重命名文件夹请求"""
    path: str = Field(..., description="文件夹路径", min_length=1)
    new_name: str = Field(..., description="新名称（不含路径）", min_length=1)


class FolderDeleteRequest(BaseModel):
    """删除文件夹请求"""
    path: str = Field(..., description="文件夹路径", min_length=1)
    force: bool = Field(False, description="强制删除（递归删除非空目录）")


# ── 系统统计 ──
class MediaStats(BaseModel):
    """媒体统计"""
    total: int
    movies: int = 0
    tv_shows: int = 0
    episodes: int = 0
    total_size: int = 0  # bytes


class SystemStats(BaseModel):
    """系统统计"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    uptime: str


class AdminStatsResponse(BaseModel):
    """管理后台统计响应"""
    media: MediaStats
    system: SystemStats
    users: int = 0
    downloads: int = 0
    subscriptions: int = 0
    timestamp: datetime
