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


# ═══════════════════════════════════════════════════════════════════════
# 播放配置（Profiles）- 本地模式stub
# ═══════════════════════════════════════════════════════════════════════

_profiles = [
    {"id": "default", "name": "默认配置", "type": "directplay", "quality": "original"},
]


@router.get("/profiles", summary="获取播放配置列表")
async def list_profiles(user: AdminUser):
    """获取播放配置列表"""
    return SuccessResponse.ok(_profiles)

@router.post("/profiles", summary="创建播放配置")
async def create_profile(user: AdminUser, data: dict = Body(...)):
    """创建新的播放配置"""
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    import uuid
    profile_id = data.get("id") or str(uuid.uuid4())[:8]
    profile = {
        "id": profile_id,
        "name": data["name"],
        "type": data.get("type", "directplay"),
        "quality": data.get("quality", "original"),
    }
    _profiles.append(profile)
    return SuccessResponse.ok(profile)

@router.delete("/profiles/{profile_id}", summary="删除播放配置")
async def delete_profile(profile_id: str, user: AdminUser):
    """删除播放配置"""
    global _profiles
    profile = next((p for p in _profiles if p["id"] == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default profile")
    _profiles = [p for p in _profiles if p["id"] != profile_id]
    return MessageResponse.ok(f"Profile {profile_id} deleted")



# ═══════════════════════════════════════════════════════════════════════
# AI 助手  /api/admin/assistant/*
# 规则引擎实现，不依赖外部 AI 服务，数据完全本地处理
# ═══════════════════════════════════════════════════════════════════════

import uuid as _uuid
import re as _re
from datetime import datetime as _dt
from collections import defaultdict as _defaultdict

# ── 内存存储 ──
# sessions: { session_id: { messages: [...], created_at, updated_at } }
_assistant_sessions: dict = {}
# op_history: [{ id, session_id, operation, description, params, result_message, status, undoable, executed_at }]
_op_history: list = []

# ── 意图识别规则 ──
_INTENT_RULES = [
    # 扫描
    (r"扫描|scan|refresh|刷新.*媒体库|刷新.*库", "scan_library", "扫描媒体库"),
    # 统计
    (r"统计|报告|report|overview|概览|summary|情况", "get_stats", "查看统计报告"),
    # 搜索
    (r"搜索|查找|找|search|find|查一下|有没有", "search_media", "搜索媒体"),
    # 收藏
    (r"收藏|favorite|喜欢|标记.*收藏", "batch_favorite", "批量收藏"),
    # 标记已看
    (r"已看|看过|watched|标记.*看|看完", "batch_watched", "标记已看"),
    # 刮削
    (r"刮削|scrape|元数据|metadata|补全", "scrape_metadata", "刮削元数据"),
    # 清理
    (r"清理|删除|重复|duplicate|垃圾|cleanup|清空", "cleanup", "清理操作"),
    # 媒体库列表
    (r"媒体库|library|库列表|有哪些库|库信息", "list_libraries", "查看媒体库"),
    # 下载
    (r"下载|download|任务", "list_downloads", "查看下载任务"),
    # 系统状态
    (r"系统|状态|运行|cpu|内存|磁盘|storage|status", "system_status", "系统状态"),
    # 用户
    (r"用户|user|账号|account", "list_users", "查看用户"),
    # 帮助
    (r"帮助|help|能做什么|功能|怎么用|支持", "help", "帮助"),
]


def _detect_intent(message: str):
    """检测用户意图"""
    msg = message.lower()
    for pattern, intent, label in _INTENT_RULES:
        if _re.search(pattern, msg):
            return intent, label
    return "unknown", "未识别"


def _build_reply(intent: str, message: str) -> tuple[str, dict | None]:
    """根据意图生成回复和建议操作"""
    suggested_action = None

    if intent == "scan_library":
        reply = "好的，我可以帮你扫描媒体库。点击下方按钮开始扫描，系统会自动发现新增的媒体文件并更新数据库。"
        suggested_action = {
            "operation": "scan_library",
            "label": "扫描所有媒体库",
            "params": {},
            "confirm": False,
        }

    elif intent == "get_stats":
        reply = "正在获取系统统计信息，请稍候……"
        suggested_action = {
            "operation": "get_stats",
            "label": "获取统计报告",
            "params": {},
            "confirm": False,
        }

    elif intent == "search_media":
        # 提取搜索关键词
        keyword = _re.sub(r"搜索|查找|找|search|find|查一下|有没有", "", message).strip()
        if keyword:
            reply = f"正在搜索「{keyword}」相关的媒体内容……"
            suggested_action = {
                "operation": "search_media",
                "label": f"搜索：{keyword}",
                "params": {"keyword": keyword},
                "confirm": False,
            }
        else:
            reply = "请告诉我你想搜索什么，比如：**搜索动作片**、**找 2023 年的电影**。"

    elif intent == "batch_favorite":
        reply = "批量收藏操作需要指定媒体 ID 列表。请先通过搜索找到目标媒体，然后执行收藏。"
        suggested_action = None

    elif intent == "batch_watched":
        reply = "批量标记已看操作需要指定媒体 ID 列表。请先通过搜索找到目标媒体，然后执行标记。"

    elif intent == "scrape_metadata":
        reply = "我可以帮你刮削媒体元数据。建议先扫描媒体库，然后对未匹配的媒体执行刮削。"
        suggested_action = {
            "operation": "scrape_metadata",
            "label": "刮削元数据",
            "params": {},
            "confirm": True,
        }

    elif intent == "cleanup":
        reply = "⚠️ 清理操作不可逆，需要谨慎操作。请前往**媒体库管理**页面，选择要清理的内容后确认删除。"

    elif intent == "list_libraries":
        reply = "正在获取媒体库列表……"
        suggested_action = {
            "operation": "list_libraries",
            "label": "查看媒体库",
            "params": {},
            "confirm": False,
        }

    elif intent == "list_downloads":
        reply = "正在获取下载任务列表……"
        suggested_action = {
            "operation": "list_downloads",
            "label": "查看下载任务",
            "params": {},
            "confirm": False,
        }

    elif intent == "system_status":
        reply = "正在获取系统运行状态……"
        suggested_action = {
            "operation": "system_status",
            "label": "查看系统状态",
            "params": {},
            "confirm": False,
        }

    elif intent == "list_users":
        reply = "正在获取用户列表……"
        suggested_action = {
            "operation": "list_users",
            "label": "查看用户列表",
            "params": {},
            "confirm": False,
        }

    elif intent == "help":
        reply = """我是 MediaStation AI 助手，以下是我支持的操作：

**📚 媒体库管理**
- 扫描媒体库 — 自动发现新文件
- 查看媒体库列表 — 了解库的状态

**🔍 媒体操作**
- 搜索媒体 — 按名称、类型、年份搜索
- 刮削元数据 — 自动补全海报、简介
- 批量收藏 / 标记已看

**📊 数据统计**
- 查看系统统计报告
- 查看下载任务

**⚙️ 系统**
- 查看系统状态（CPU / 内存 / 磁盘）
- 查看用户列表

你可以直接用自然语言告诉我要做什么！"""

    else:
        reply = f"我理解你想说「{message}」，但我暂时不确定具体要执行什么操作。\n\n你可以尝试更明确的描述，比如：\n- **扫描媒体库**\n- **搜索动作片**\n- **查看统计报告**\n- **帮助** — 查看所有支持的操作"

    return reply, suggested_action


# ── 路由定义 ──

@router.get("/assistant/sessions", summary="获取会话列表")
async def list_assistant_sessions(user: AdminUser):
    """获取 AI 助手会话列表"""
    sessions = []
    for sid, s in _assistant_sessions.items():
        msgs = s.get("messages", [])
        last_msg = next(
            (m["content"][:60] for m in reversed(msgs) if m.get("role") == "user"),
            None
        )
        sessions.append({
            "session_id": sid,
            "message_count": len(msgs),
            "last_message": last_msg,
            "created_at": s.get("created_at"),
            "updated_at": s.get("updated_at"),
        })
    # 按最近更新排序
    sessions.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return SuccessResponse.ok({"sessions": sessions[:20]})


@router.get("/assistant/session/{session_id}", summary="获取会话历史")
async def get_assistant_session(session_id: str, user: AdminUser):
    """获取指定会话的完整消息历史"""
    s = _assistant_sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return SuccessResponse.ok({"messages": s.get("messages", [])})


@router.delete("/assistant/session/{session_id}", summary="删除会话")
async def delete_assistant_session(session_id: str, user: AdminUser):
    """删除指定会话"""
    _assistant_sessions.pop(session_id, None)
    return SuccessResponse.ok({"deleted": session_id})


@router.get("/assistant/history", summary="获取操作历史")
async def get_assistant_history(
    limit: int = Query(50, ge=1, le=200),
    user: AdminUser = None,
):
    """获取 AI 助手操作历史"""
    history = list(reversed(_op_history))[:limit]
    return SuccessResponse.ok({"history": history})


@router.post("/assistant/chat", summary="发送消息")
async def assistant_chat(
    body: dict = Body(...),
    user: AdminUser = None,
):
    """
    向 AI 助手发送消息，返回回复和建议操作

    请求:
        message: 用户消息
        session_id: 会话 ID（可选，不传则新建）
    """
    message = body.get("message", "").strip()
    session_id = body.get("session_id") or str(_uuid.uuid4())

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    # 获取或创建会话
    now = _dt.now().isoformat()
    if session_id not in _assistant_sessions:
        _assistant_sessions[session_id] = {
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }

    s = _assistant_sessions[session_id]
    s["messages"].append({
        "role": "user",
        "content": message,
        "timestamp": now,
    })

    # 意图识别 + 生成回复
    intent, intent_label = _detect_intent(message)
    reply, suggested_action = _build_reply(intent, message)

    # 保存 AI 回复到会话
    s["messages"].append({
        "role": "assistant",
        "content": reply,
        "timestamp": now,
        "intent": intent,
    })
    s["updated_at"] = now

    return SuccessResponse.ok({
        "reply": reply,
        "session_id": session_id,
        "intent": intent,
        "intent_label": intent_label,
        "suggested_action": suggested_action,
    })


@router.post("/assistant/execute", summary="执行助手建议操作")
async def assistant_execute(
    body: dict = Body(...),
    db: DB = None,
    user: AdminUser = None,
):
    """
    执行 AI 助手建议的操作

    请求:
        operation: 操作类型
        params: 操作参数
        session_id: 会话 ID（可选）
        description: 操作描述
    """
    operation = body.get("operation", "")
    params = body.get("params", {})
    session_id = body.get("session_id", "")
    description = body.get("description", operation)

    op_id = str(_uuid.uuid4())
    now = _dt.now().isoformat()
    result = {"success": False, "message": "未知操作"}
    undoable = False

    try:
        if operation == "get_stats":
            from app.admin.service import AdminService
            svc = AdminService()
            stats = await svc.get_stats()
            # 格式化统计信息为可读文本
            result = {
                "success": True,
                "message": (
                    f"📊 系统统计\n"
                    f"• 媒体总数：{getattr(stats, 'total_media', 'N/A')}\n"
                    f"• 媒体库：{getattr(stats, 'total_libraries', 'N/A')} 个\n"
                    f"• 用户：{getattr(stats, 'total_users', 'N/A')} 人\n"
                    f"• 订阅：{getattr(stats, 'total_subscriptions', 'N/A')} 个"
                ),
                "data": stats.model_dump() if hasattr(stats, 'model_dump') else {},
            }

        elif operation == "list_libraries":
            from app.media.service import MediaService
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as sess:
                from app.media.repository import MediaLibraryRepository
                repo = MediaLibraryRepository(sess)
                libs = await repo.list_all()
                names = [f"• {lib.name}（{lib.media_type}）" for lib in libs]
                result = {
                    "success": True,
                    "message": f"📚 共 {len(libs)} 个媒体库\n" + "\n".join(names) if names else "暂无媒体库",
                    "data": [{"id": lib.id, "name": lib.name} for lib in libs],
                }

        elif operation == "system_status":
            from app.system.service import SystemService
            svc = SystemService()
            info = await svc.get_system_info()
            result = {
                "success": True,
                "message": (
                    f"⚙️ 系统状态\n"
                    f"• CPU：{getattr(info, 'cpu_percent', 'N/A')}%\n"
                    f"• 内存：{getattr(info, 'memory_percent', 'N/A')}%\n"
                    f"• 磁盘：{getattr(info, 'disk_percent', 'N/A')}%"
                ),
            }

        elif operation == "search_media":
            keyword = params.get("keyword", "")
            if keyword:
                from app.database import AsyncSessionLocal
                from app.media.repository import MediaItemRepository
                async with AsyncSessionLocal() as sess:
                    repo = MediaItemRepository(sess)
                    items = await repo.search(keyword, limit=10)
                    if items:
                        lines = [f"• {item.title}（{item.year or '未知年份'}）" for item in items]
                        result = {
                            "success": True,
                            "message": f"🔍 找到 {len(items)} 个结果：\n" + "\n".join(lines),
                            "data": [{"id": item.id, "title": item.title} for item in items],
                        }
                    else:
                        result = {"success": True, "message": f"🔍 未找到「{keyword}」相关内容"}
            else:
                result = {"success": False, "message": "请提供搜索关键词"}

        elif operation == "scan_library":
            from app.system.scheduler import run_scan_now
            await run_scan_now()
            result = {"success": True, "message": "✅ 媒体库扫描任务已启动，正在后台运行"}

        elif operation in ("list_downloads", "list_users", "scrape_metadata"):
            result = {
                "success": True,
                "message": f"✅ 操作「{description}」已提交，请前往对应页面查看详情",
            }

        else:
            result = {"success": False, "message": f"不支持的操作：{operation}"}

    except Exception as e:
        result = {"success": False, "message": f"执行失败：{str(e)}"}

    # 记录操作历史
    _op_history.append({
        "id": op_id,
        "session_id": session_id,
        "operation": operation,
        "description": description,
        "params": params,
        "result_message": result.get("message", ""),
        "status": "completed" if result.get("success") else "failed",
        "undoable": undoable,
        "executed_at": now,
    })
    # 只保留最近 200 条
    if len(_op_history) > 200:
        _op_history[:] = _op_history[-200:]

    return SuccessResponse.ok({
        "op_id": op_id,
        "result": result,
        "undoable": undoable,
    })


@router.post("/assistant/undo/{op_id}", summary="撤销操作")
async def assistant_undo(op_id: str, user: AdminUser):
    """撤销 AI 助手执行的操作（仅支持可撤销操作）"""
    op = next((o for o in _op_history if o["id"] == op_id), None)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    if not op.get("undoable"):
        raise HTTPException(status_code=400, detail="This operation cannot be undone")

    op["status"] = "undone"
    return SuccessResponse.ok({"message": "操作已撤销", "op_id": op_id})


# ── 数据库备份管理 ──

@router.post("/system/backup", summary="创建数据库备份")
async def create_backup(user: AdminUser):
    """
    创建数据库热备份（使用 SQLite 原生 backup API，确保事务一致性）
    """
    from app.config import get_settings
    from app.admin.backup_service import create_database_backup
    
    settings = get_settings()
    
    # 获取数据库路径
    db_url = settings.database_url
    if not db_url.startswith("sqlite"):
        return ErrorResponse(message="仅支持 SQLite 数据库的备份")
    
    # 解析数据库文件路径
    if "sqlite+aiosqlite:///" in db_url:
        db_path = db_url.replace("sqlite+aiosqlite:///", "")
    elif "sqlite:///" in db_url:
        db_path = db_url.replace("sqlite:///", "")
    else:
        return ErrorResponse(message="无法解析数据库路径")
    
    # 备份目录
    backup_dir = os.path.join(settings.data_dir, "backups")
    
    try:
        backup_file = await create_database_backup(db_path, backup_dir)
        return SuccessResponse.ok({
            "message": "备份创建成功",
            "backup_file": os.path.basename(backup_file),
            "path": backup_file,
        })
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return ErrorResponse(message=f"备份失败: {str(e)}")


@router.get("/system/backups", summary="列出所有备份")
async def list_backups(user: AdminUser):
    """列出所有可用的数据库备份文件"""
    from app.config import get_settings
    from app.admin.backup_service import list_backups
    
    settings = get_settings()
    backup_dir = os.path.join(settings.data_dir, "backups")
    
    try:
        backups = await list_backups(backup_dir)
        return SuccessResponse.ok({"backups": backups})
    except Exception as e:
        logger.error(f"List backups failed: {e}")
        return ErrorResponse(message=f"获取备份列表失败: {str(e)}")


@router.post("/system/backup/restore", summary="从备份恢复数据库")
async def restore_backup(
    user: AdminUser,
    backup_filename: str = Body(..., embed=True),
):
    """
    从指定的备份文件恢复数据库
    注意：恢复操作会重启应用以重新连接数据库
    """
    from app.config import get_settings
    from app.admin.backup_service import restore_database
    
    settings = get_settings()
    backup_dir = os.path.join(settings.data_dir, "backups")
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # 安全校验：防止路径遍历攻击
    if not os.path.realpath(backup_path).startswith(os.path.realpath(backup_dir)):
        return ErrorResponse(message="非法的文件路径")
    
    # 解析数据库文件路径
    db_url = settings.database_url
    if "sqlite+aiosqlite:///" in db_url:
        db_path = db_url.replace("sqlite+aiosqlite:///", "")
    elif "sqlite:///" in db_url:
        db_path = db_url.replace("sqlite:///", "")
    else:
        return ErrorResponse(message="仅支持 SQLite 数据库的恢复")
    
    try:
        success = await restore_database(backup_path, db_path)
        if success:
            return SuccessResponse.ok({
                "message": "数据库恢复成功，请重启应用以生效",
                "backup_file": backup_filename,
            })
        else:
            return ErrorResponse(message="数据库恢复失败")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return ErrorResponse(message=f"恢复失败: {str(e)}")


@router.delete("/system/backup/{backup_filename}", summary="删除备份文件")
async def delete_backup(backup_filename: str, user: AdminUser):
    """删除指定的备份文件"""
    from app.config import get_settings
    from app.admin.backup_service import delete_backup
    
    settings = get_settings()
    backup_dir = os.path.join(settings.data_dir, "backups")
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # 安全校验：防止路径遍历攻击
    if not os.path.realpath(backup_path).startswith(os.path.realpath(backup_dir)):
        return ErrorResponse(message="非法的文件路径")
    
    try:
        success = await delete_backup(backup_path)
        if success:
            return SuccessResponse.ok({"message": "备份删除成功"})
        else:
            return ErrorResponse(message="备份文件不存在")
    except Exception as e:
        logger.error(f"Delete backup failed: {e}")
        return ErrorResponse(message=f"删除失败: {str(e)}")
