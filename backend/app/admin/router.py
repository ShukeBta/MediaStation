"""
管理后台 API 路由
统一响应格式：
- Success: {data: ...}
- Error: {error: ..., detail: ...}  
- Batch: {message, started, errors}
"""
from __future__ import annotations

from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body

from app.admin.schemas import (
    # 任务
    TaskResponse,
    TaskCreate,
    TaskUpdate,
    # 批量操作
    BatchScanRequest,
    BatchScrapeRequest,
    BatchDeleteRequest,
    BatchMoveRequest,
    BatchFavoriteRequest,
    BatchWatchedRequest,
    BatchRenameRequest,
    # 系统设置
    SystemSettings,
    SystemSettingsUpdate,
    # 内容分级
    ContentRatingResponse,
    ContentRatingUpdate,
    # 文件操作
    FileItem,
    BrowseResponse,
    FileOperationRequest,
    FileRenamePreview,
    BatchRenamePreview,
    # 文件夹操作
    FolderCreateRequest,
    FolderRenameRequest,
    FolderDeleteRequest,
    # AI 重命名
    AIRenameRequest,
    AIRenameResponse,
    # 系统统计
    AdminStatsResponse,
)
from app.admin.service import AdminService
from app.common.schemas import (
    SuccessResponse,
    ErrorResponse,
    BatchResponse,
    MessageResponse,
    PathValidator,
)
from app.deps import AdminUser, DB
from app.config import Settings, get_settings as get_app_settings

router = APIRouter(prefix="/admin", tags=["admin"])


def get_service() -> AdminService:
    """获取服务实例"""
    return AdminService()


def get_path_validator(settings: Annotated[Settings, Depends(get_app_settings)]) -> PathValidator:
    """获取路径验证器"""
    return PathValidator(
        media_dirs=settings.media_dirs,
        data_dir=settings.data_dir,
    )


# ── 定时任务 ──

@router.get(
    "/scheduler/tasks",
    response_model=SuccessResponse[list[TaskResponse]],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    }
)
async def list_tasks(user: AdminUser):
    """列出所有定时任务"""
    service = get_service()
    tasks = await service.list_tasks()
    return SuccessResponse.ok(tasks)


@router.post(
    "/scheduler/tasks",
    response_model=SuccessResponse[TaskResponse],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    }
)
async def create_task(data: TaskCreate, user: AdminUser):
    """创建定时任务"""
    service = get_service()
    try:
        task = await service.create_task(data)
        return SuccessResponse.ok(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/scheduler/tasks/{task_id}",
    response_model=SuccessResponse[TaskResponse],
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    }
)
async def update_task(task_id: str, data: TaskUpdate, user: AdminUser):
    """更新定时任务"""
    service = get_service()
    try:
        task = await service.update_task(task_id, data)
        return SuccessResponse.ok(task)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/scheduler/tasks/{task_id}",
    response_model=MessageResponse,
    responses={
        404: {"model": ErrorResponse},
    }
)
async def delete_task(task_id: str, user: AdminUser):
    """删除定时任务"""
    service = get_service()
    try:
        await service.delete_task(task_id)
        return MessageResponse.ok(f"Task {task_id} deleted")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/scheduler/tasks/{task_id}/run",
    response_model=SuccessResponse[dict[str, Any]],
    responses={
        404: {"model": ErrorResponse},
    }
)
async def run_task_now(task_id: str, user: AdminUser):
    """立即执行任务"""
    service = get_service()
    try:
        result = await service.run_task_now(task_id)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── 批量操作 ──

@router.post(
    "/library/batch-scan",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def batch_scan_library(data: BatchScanRequest, user: AdminUser):
    """
    批量扫描媒体库
    
    请求:
        library_ids: 媒体库 ID 列表
    
    响应:
        - message: 操作消息
        - started: 成功启动的媒体库 ID 列表
        - errors: 失败项详情 [{id, error}]
        - total: 总数
        - success_count: 成功数
        - error_count: 失败数
    """
    service = get_service()
    result = await service.batch_scan(data)
    return result


@router.post(
    "/media/batch-scrape",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def batch_scrape_media(data: BatchScrapeRequest, user: AdminUser):
    """
    批量刮削媒体元数据
    
    请求:
        media_ids: 媒体 ID 列表
        sources: 刮削数据源列表（可选）
    """
    service = get_service()
    result = await service.batch_scrape(data)
    return result


@router.post(
    "/media/batch-delete",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def batch_delete_media(data: BatchDeleteRequest, user: AdminUser):
    """
    批量删除媒体
    
    请求:
        media_ids: 媒体 ID 列表
        force: 是否强制删除（跳过回收站）
    """
    service = get_service()
    result = await service.batch_delete(data)
    return result


@router.post(
    "/media/batch-move",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def batch_move_media(data: BatchMoveRequest, user: AdminUser):
    """
    批量移动媒体
    
    请求:
        media_ids: 媒体 ID 列表
        target_library_id: 目标媒体库 ID
    """
    service = get_service()
    result = await service.batch_move(data)
    return result


@router.post(
    "/media/batch-favorite",
    response_model=BatchResponse,
)
async def batch_favorite_media(data: BatchFavoriteRequest, user: AdminUser):
    """
    批量收藏/取消收藏
    
    请求:
        media_ids: 媒体 ID 列表
        action: add | remove
    """
    service = get_service()
    result = await service.batch_favorite(data)
    return result


@router.post(
    "/media/batch-watched",
    response_model=BatchResponse,
)
async def batch_watched_media(data: BatchWatchedRequest, user: AdminUser):
    """
    批量标记已看/未看
    
    请求:
        media_ids: 媒体 ID 列表
        action: mark | unmark
    """
    service = get_service()
    result = await service.batch_watched(data)
    return result


# ── 系统设置 ──

@router.get(
    "/settings",
    response_model=SuccessResponse[SystemSettings],
)
async def get_settings(user: AdminUser):
    """获取系统设置"""
    service = get_service()
    settings = await service.get_settings()
    return SuccessResponse.ok(settings)


@router.put(
    "/settings",
    response_model=SuccessResponse[SystemSettings],
)
async def update_settings(data: SystemSettingsUpdate, user: AdminUser):
    """更新系统设置"""
    service = get_service()
    settings = await service.update_settings(data)
    return SuccessResponse.ok(settings)


# ── 系统统计 ──

@router.get(
    "/stats",
    response_model=SuccessResponse[AdminStatsResponse],
)
async def get_stats(user: AdminUser):
    """获取系统统计"""
    service = get_service()
    stats = await service.get_stats()
    return SuccessResponse.ok(stats)


# ── 内容分级 ──

@router.get(
    "/content-rating",
    response_model=SuccessResponse[ContentRatingResponse],
)
async def get_content_rating(user: AdminUser):
    """获取内容分级配置"""
    service = get_service()
    return SuccessResponse.ok(await service.get_content_rating())


@router.put(
    "/content-rating",
    response_model=SuccessResponse[ContentRatingResponse],
)
async def update_content_rating(data: ContentRatingUpdate, user: AdminUser):
    """更新内容分级配置"""
    service = get_service()
    return SuccessResponse.ok(await service.update_content_rating(data))


# ── 文件浏览（带路径白名单验证） ──

@router.get(
    "/files/browse",
    response_model=SuccessResponse[BrowseResponse],
    responses={
        400: {"model": ErrorResponse},
    }
)
async def browse_files(
    path: Annotated[str, Query(description="目录路径", min_length=1)] = ".",
    user: AdminUser = None,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    浏览目录
    
    安全限制：只允许访问媒体库配置目录
    
    响应:
        - current: 当前目录
        - parent: 父目录（无则 null）
        - items: 文件/目录列表
    """
    # 路径安全验证
    validator.validate_or_raise(path)

    service = get_service()
    try:
        result = await service.browse_files(path)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/mkdir",
    response_model=SuccessResponse[FileItem],
    responses={
        400: {"model": ErrorResponse},
    }
)
async def create_directory(
    data: Annotated[FileOperationRequest, Body(description="路径信息")],
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """创建目录"""
    # 路径安全验证
    validator.validate_or_raise(data.path)
    
    service = get_service()
    try:
        result = await service.create_directory(data.path)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/rename",
    response_model=SuccessResponse[FileItem],
    responses={
        400: {"model": ErrorResponse},
    }
)
async def rename_file(
    data: Annotated[FileOperationRequest, Body(description="重命名信息")],
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """重命名文件"""
    if not data.new_name:
        raise HTTPException(status_code=400, detail="new_name is required")
    
    # 路径安全验证
    validator.validate_or_raise(data.path)
    
    service = get_service()
    try:
        result = await service.rename_file(data.path, data.new_name)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/rename/preview",
    response_model=SuccessResponse[FileRenamePreview],
    responses={
        400: {"model": ErrorResponse},
    }
)
async def preview_rename(
    data: Annotated[FileOperationRequest, Body(description="重命名信息")],
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """预览重命名结果"""
    if not data.new_name:
        raise HTTPException(status_code=400, detail="new_name is required")
    
    # 路径安全验证
    validator.validate_or_raise(data.path)
    
    service = get_service()
    try:
        result = await service.preview_rename(data.path, data.new_name)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/batch-rename",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def batch_rename_files(
    data: BatchRenameRequest,
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    批量重命名文件
    
    请求:
        operations: 重命名操作列表 [{path, new_name}]
        mode: preview | execute
    """
    # 验证所有路径
    for op in data.operations:
        validator.validate_or_raise(op.path)
    
    service = get_service()
    if data.mode == "preview":
        result = await service.batch_rename_preview(data.operations)
    else:
        result = await service.batch_rename_execute(data.operations)
    return result


@router.delete(
    "/files",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def delete_file(
    path: Annotated[str, Query(description="文件路径")],
    force: Annotated[bool, Query(description="强制删除（目录）")] = False,
    user: AdminUser = None,
    validator: PathValidator = Depends(get_path_validator),
):
    """删除文件"""
    # 路径安全验证
    validator.validate_or_raise(path)
    
    service = get_service()
    try:
        await service.delete_file(path, force)
        return MessageResponse.ok(f"Deleted: {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/move",
    response_model=SuccessResponse[FileItem],
    responses={
        400: {"model": ErrorResponse},
    }
)
async def move_file(
    data: Annotated[FileOperationRequest, Body(description="移动信息")],
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """移动文件"""
    if not data.target:
        raise HTTPException(status_code=400, detail="target is required")
    
    # 路径安全验证
    validator.validate_or_raise(data.path)
    validator.validate_or_raise(data.target)
    
    service = get_service()
    try:
        result = await service.move_file(data.path, data.target)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── 文件批量刮削 ──

@router.post(
    "/files/batch-scrape",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
    }
)
async def batch_scrape_files(
    paths: Annotated[list[str], Body(description="文件路径列表")],
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    批量刮削文件
    
    请求:
        paths: 文件路径列表
    """
    # 验证所有路径
    for path in paths:
        validator.validate_or_raise(path)
    
    service = get_service()
    result = await service.batch_scrape_files(paths)
    return result


@router.get(
    "/files/folders",
    response_model=SuccessResponse[list[str]],
)
async def get_media_folders(user: AdminUser):
    """获取媒体库配置的所有文件夹"""
    service = get_service()
    folders = await service.get_media_folders()
    return SuccessResponse.ok(folders)


# ── 文件夹操作（符合路线图路径规范的别名端点） ──

@router.post(
    "/files/folders/create",
    response_model=SuccessResponse[FileItem],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="创建文件夹",
)
async def create_folder(
    data: FolderCreateRequest,
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    创建文件夹

    安全限制：只允许在媒体库配置目录下创建

    请求:
        path: 要创建的文件夹完整路径
    """
    validator.validate_or_raise(data.path)
    service = get_service()
    try:
        result = await service.create_directory(data.path)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/folders/rename",
    response_model=SuccessResponse[FileItem],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="重命名文件夹",
)
async def rename_folder(
    data: FolderRenameRequest,
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    重命名文件夹

    请求:
        path: 文件夹路径
        new_name: 新名称（不含路径）
    """
    validator.validate_or_raise(data.path)
    service = get_service()
    try:
        result = await service.rename_file(data.path, data.new_name)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/files/folders/delete",
    response_model=SuccessResponse[dict],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="删除文件夹",
)
async def delete_folder(
    data: FolderDeleteRequest,
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    删除文件夹

    请求:
        path: 文件夹路径
        force: 是否强制递归删除非空目录（默认 false）

    警告：force=true 时将递归删除所有子文件，操作不可逆！
    """
    validator.validate_or_raise(data.path)
    service = get_service()
    try:
        result = await service.delete_file(data.path, force=data.force)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── AI 重命名 ──

@router.post(
    "/files/rename/ai",
    response_model=SuccessResponse[AIRenameResponse],
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="AI 生成重命名建议",
)
async def ai_rename_files(
    data: AIRenameRequest,
    user: AdminUser,
    validator: PathValidator = Depends(get_path_validator),
):
    """
    AI 生成重命名建议

    调用 LLM（OpenAI 兼容格式）分析文件名，生成规范化的媒体文件名建议。

    请求:
        paths: 文件路径列表
        style: 重命名风格 — media（媒体规范，如 Movie.Name.2023.1080p）| clean（整洁格式）| original（尽量保留原名）
        language: 语言偏好 zh | en
        extra_hint: 补充提示（如系列名称、年份等）

    响应:
        candidates: 每个文件的重命名建议列表，含置信度和理由

    说明：该接口只生成建议，不会执行重命名。
    执行重命名请使用 POST /api/admin/files/batch-rename。
    """
    # 验证所有路径
    for path in data.paths:
        validator.validate_or_raise(path)

    service = get_service()
    try:
        result = await service.ai_rename_files(data)
        return SuccessResponse.ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# 内容分级过滤  /api/admin/content-rating
# ═══════════════════════════════════════════════════════════════════════

from pydantic import BaseModel as _BaseModel

class ContentRatingConfig(_BaseModel):
    """内容分级配置"""
    enabled: bool = True
    max_rating: str = "PG-13"      # G / PG / PG-13 / R / NC-17 / X
    block_adult: bool = True
    require_auth_for_adult: bool = True
    allowed_tags: list[str] = []    # 允许的内容标签
    blocked_tags: list[str] = []    # 屏蔽的内容标签
    age_verification: bool = False  # 是否启用年龄验证

# 内存存储（生产环境应持久化到数据库或配置文件）
_content_rating_config: dict = {
    "enabled": True,
    "max_rating": "PG-13",
    "block_adult": True,
    "require_auth_for_adult": True,
    "allowed_tags": [],
    "blocked_tags": [],
    "age_verification": False,
}

RATING_ORDER = ["G", "PG", "PG-13", "R", "NC-17", "X"]


@router.get("/content-rating", summary="获取内容分级配置")
async def get_content_rating(user: AdminUser):
    """获取全局内容分级过滤配置"""
    return SuccessResponse.ok({
        **_content_rating_config,
        "rating_levels": RATING_ORDER,
        "description": {
            "G": "适合所有年龄（无限制内容）",
            "PG": "建议家长陪同（轻微暴力/语言）",
            "PG-13": "13岁以下家长指导（激烈动作/语言）",
            "R": "17岁以下需家长陪同（暴力/粗俗语言）",
            "NC-17": "仅限成人（强烈内容）",
            "X": "成人内容",
        }
    })


@router.put("/content-rating", summary="更新内容分级配置")
async def update_content_rating(data: ContentRatingConfig, user: AdminUser):
    """更新全局内容分级过滤规则"""
    global _content_rating_config
    if data.max_rating not in RATING_ORDER:
        raise HTTPException(400, f"无效的分级: {data.max_rating}，有效值: {RATING_ORDER}")

    _content_rating_config.update(data.model_dump())

    return SuccessResponse.ok({
        "message": "内容分级配置已更新",
        **_content_rating_config,
    })


# ═══════════════════════════════════════════════════════════════════════
# 外部存储支持  /api/admin/storage/*
# ═══════════════════════════════════════════════════════════════════════

import json as _json

# ── 内存配置存储（生产环境应持久化到数据库） ──
_storage_configs: dict = {
    "webdav": None,
    "alist": None,
    "s3": None,
}


class WebDAVConfig(_BaseModel):
    url: str
    username: str
    password: str
    root_path: str = "/"
    enabled: bool = True
    verify_ssl: bool = True


class AlistConfig(_BaseModel):
    url: str
    token: str
    root_path: str = "/"
    enabled: bool = True


class S3Config(_BaseModel):
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"
    path_prefix: str = ""
    enabled: bool = True
    use_ssl: bool = True


# ── WebDAV ──

@router.get("/storage/webdav", summary="获取 WebDAV 配置")
async def get_webdav_config(user: AdminUser):
    """获取 WebDAV 存储配置（密码字段脱敏）"""
    cfg = _storage_configs.get("webdav")
    if cfg:
        safe_cfg = {**cfg, "password": "***" if cfg.get("password") else None}
        return SuccessResponse.ok({"configured": True, "config": safe_cfg})
    return SuccessResponse.ok({"configured": False, "config": None})


@router.put("/storage/webdav", summary="更新 WebDAV 配置")
async def update_webdav_config(data: WebDAVConfig, user: AdminUser):
    """保存 WebDAV 存储配置"""
    _storage_configs["webdav"] = data.model_dump()
    return SuccessResponse.ok({"message": "WebDAV 配置已保存", "url": data.url})


@router.post("/storage/webdav/test", summary="测试 WebDAV 连接")
async def test_webdav(user: AdminUser):
    """测试 WebDAV 连接（需已配置）"""
    cfg = _storage_configs.get("webdav")
    if not cfg:
        raise HTTPException(400, "WebDAV 尚未配置")

    try:
        import httpx
        async with httpx.AsyncClient(verify=cfg.get("verify_ssl", True), timeout=10) as client:
            resp = await client.request(
                "PROPFIND",
                cfg["url"].rstrip("/") + cfg.get("root_path", "/"),
                auth=(cfg["username"], cfg["password"]),
                headers={"Depth": "0"},
            )
            ok = resp.status_code in (207, 200)
            return SuccessResponse.ok({
                "success": ok,
                "status_code": resp.status_code,
                "message": "连接成功" if ok else f"连接失败 (HTTP {resp.status_code})",
            })
    except Exception as e:
        return SuccessResponse.ok({
            "success": False,
            "message": f"连接失败: {str(e)}",
        })


@router.get("/storage/webdav/status", summary="WebDAV 存储状态")
async def webdav_status(user: AdminUser):
    """获取 WebDAV 存储实时状态（已挂载路径、可用空间）"""
    cfg = _storage_configs.get("webdav")
    if not cfg or not cfg.get("enabled"):
        return SuccessResponse.ok({"status": "disabled", "message": "WebDAV 未启用"})

    return SuccessResponse.ok({
        "status": "configured",
        "url": cfg.get("url"),
        "root_path": cfg.get("root_path"),
        "enabled": cfg.get("enabled"),
    })


# ── Alist ──

@router.get("/storage/alist", summary="获取 Alist 配置")
async def get_alist_config(user: AdminUser):
    """获取 Alist 配置（token 脱敏）"""
    cfg = _storage_configs.get("alist")
    if cfg:
        safe_cfg = {**cfg, "token": "***" if cfg.get("token") else None}
        return SuccessResponse.ok({"configured": True, "config": safe_cfg})
    return SuccessResponse.ok({"configured": False, "config": None})


@router.put("/storage/alist", summary="更新 Alist 配置")
async def update_alist_config(data: AlistConfig, user: AdminUser):
    """保存 Alist 配置"""
    _storage_configs["alist"] = data.model_dump()
    return SuccessResponse.ok({"message": "Alist 配置已保存", "url": data.url})


@router.post("/storage/alist/test", summary="测试 Alist 连接")
async def test_alist(user: AdminUser):
    """测试 Alist 连接（调用 /api/me 验证 Token）"""
    cfg = _storage_configs.get("alist")
    if not cfg:
        raise HTTPException(400, "Alist 尚未配置")

    try:
        import httpx
        base_url = cfg["url"].rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{base_url}/api/me",
                headers={"Authorization": cfg["token"]},
            )
            ok = resp.status_code == 200
            return SuccessResponse.ok({
                "success": ok,
                "status_code": resp.status_code,
                "message": "Alist 连接成功" if ok else f"连接失败: HTTP {resp.status_code}",
                "user_info": resp.json().get("data") if ok else None,
            })
    except Exception as e:
        return SuccessResponse.ok({
            "success": False,
            "message": f"连接失败: {str(e)}",
        })


# ── S3 ──

@router.get("/storage/s3", summary="获取 S3 配置")
async def get_s3_config(user: AdminUser):
    """获取 S3/兼容存储配置（secret_key 脱敏）"""
    cfg = _storage_configs.get("s3")
    if cfg:
        safe_cfg = {**cfg, "secret_key": "***" if cfg.get("secret_key") else None}
        return SuccessResponse.ok({"configured": True, "config": safe_cfg})
    return SuccessResponse.ok({"configured": False, "config": None})


@router.put("/storage/s3", summary="更新 S3 配置")
async def update_s3_config(data: S3Config, user: AdminUser):
    """保存 S3 存储配置（支持 AWS S3/MinIO/阿里云 OSS/腾讯云 COS）"""
    _storage_configs["s3"] = data.model_dump()
    return SuccessResponse.ok({"message": "S3 配置已保存", "endpoint": data.endpoint, "bucket": data.bucket})


@router.post("/storage/s3/test", summary="测试 S3 连接")
async def test_s3(user: AdminUser):
    """测试 S3 存储连接（尝试 ListBuckets 或 HeadBucket）"""
    cfg = _storage_configs.get("s3")
    if not cfg:
        raise HTTPException(400, "S3 尚未配置")

    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
        client = boto3.client(
            "s3",
            endpoint_url=cfg["endpoint"] if not cfg["endpoint"].startswith("https://s3.amazonaws.com") else None,
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            region_name=cfg["region"],
            config=Config(signature_version="s3v4"),
        )
        client.head_bucket(Bucket=cfg["bucket"])
        return SuccessResponse.ok({
            "success": True,
            "message": f"S3 Bucket '{cfg['bucket']}' 连接成功",
            "bucket": cfg["bucket"],
            "region": cfg["region"],
        })
    except ImportError:
        return SuccessResponse.ok({
            "success": False,
            "message": "boto3 未安装，请运行: pip install boto3",
        })
    except Exception as e:
        return SuccessResponse.ok({
            "success": False,
            "message": f"S3 连接失败: {str(e)}",
        })


# ── 通用存储状态 ──

@router.get("/storage/status", summary="所有存储状态总览")
async def storage_status_overview(user: AdminUser):
    """获取所有外部存储（WebDAV/Alist/S3）的配置和启用状态总览"""
    def _safe_status(key: str) -> dict:
        cfg = _storage_configs.get(key)
        if not cfg:
            return {"configured": False, "enabled": False}
        return {
            "configured": True,
            "enabled": cfg.get("enabled", True),
            "url": cfg.get("url") or cfg.get("endpoint"),
        }

    return SuccessResponse.ok({
        "webdav": _safe_status("webdav"),
        "alist": _safe_status("alist"),
        "s3": _safe_status("s3"),
        "summary": {
            "total": 3,
            "configured": sum(1 for k in ["webdav", "alist", "s3"] if _storage_configs.get(k)),
            "enabled": sum(1 for k in ["webdav", "alist", "s3"]
                          if _storage_configs.get(k) and _storage_configs[k].get("enabled")),
        }
    })
