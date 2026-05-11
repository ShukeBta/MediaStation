"""
下载模块路由
"""
from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, Depends, Query

from app.common import safe_create_task
from app.deps import AdminUser, CurrentUser, DB
from app.download.service import DownloadService
from app.download.schemas import (
    Aria2GlobalStats,
    DownloadClientCreate,
    DownloadClientOut,
    DownloadClientUpdate,
    DownloadTaskCreate,
    DownloadTaskOut,
)

router = APIRouter(prefix="", tags=["download"])


# ── 下载客户端 ──
@router.get("/download/clients", response_model=list[DownloadClientOut])
async def list_clients(user: CurrentUser, db: DB):
    service = DownloadService(db)
    return await service.list_clients()


@router.post("/download/clients", response_model=DownloadClientOut)
async def create_client(data: DownloadClientCreate, user: AdminUser, db: DB):
    service = DownloadService(db)
    return await service.create_client(data)


@router.put("/download/clients/{client_id}", response_model=DownloadClientOut)
async def update_client(client_id: int, data: DownloadClientUpdate, user: AdminUser, db: DB):
    service = DownloadService(db)
    return await service.update_client(client_id, data)


@router.delete("/download/clients/{client_id}", status_code=204)
async def delete_client(client_id: int, user: AdminUser, db: DB):
    service = DownloadService(db)
    await service.delete_client(client_id)


@router.post("/download/clients/{client_id}/test")
async def test_client(client_id: int, user: AdminUser, db: DB):
    service = DownloadService(db)
    return await service.test_client(client_id)


# ── 下载任务 ──
@router.get("/download/tasks")
async def list_tasks(
    user: CurrentUser,
    db: DB,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = DownloadService(db)
    return await service.list_tasks(status, page, page_size)


@router.post("/download/add", response_model=DownloadTaskOut)
async def add_task(data: DownloadTaskCreate, user: CurrentUser, db: DB):
    service = DownloadService(db)
    return await service.add_task(data)


@router.post("/download/{task_id}/pause")
async def pause_task(task_id: int, user: CurrentUser, db: DB):
    service = DownloadService(db)
    await service.pause_task(task_id)
    return {"ok": True}


@router.post("/download/{task_id}/resume")
async def resume_task(task_id: int, user: CurrentUser, db: DB):
    service = DownloadService(db)
    await service.resume_task(task_id)
    return {"ok": True}


@router.delete("/download/{task_id}")
async def delete_task(
    task_id: int, user: CurrentUser, db: DB,
    delete_files: bool = Query(False),
):
    service = DownloadService(db)
    await service.delete_task(task_id, delete_files)
    return {"ok": True}


@router.post("/download/sync")
async def sync_tasks(user: AdminUser, db: DB):
    service = DownloadService(db)
    await service.sync_task_status()
    return {"ok": True}


@router.post("/download/start-auto-sync")
async def start_auto_sync(user: CurrentUser):
    """启动后台自动同步（每 5 秒同步一次下载进度）"""
    import asyncio
    from app.database import async_session_factory
    from app.system.events import get_event_bus

    # 防止重复启动：检查是否已有自动同步任务在运行
    global _auto_sync_task
    if _auto_sync_task is not None and not _auto_sync_task.done():
        return {"ok": True, "message": "自动同步已在运行中"}

    async def _auto_sync_loop():
        while True:
            try:
                # 每次循环使用独立的数据库会话
                async with async_session_factory() as db:
                    service = DownloadService(db)
                    await service.sync_task_status()
            except asyncio.CancelledError:
                # 任务被取消，正常退出
                break
            except Exception as e:
                # 记录错误但继续运行
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Auto sync error: {e}")
            await asyncio.sleep(5)

    # 在后台启动自动同步任务（使用安全包装器，防止异常静默崩溃）
    _auto_sync_task = safe_create_task(_auto_sync_loop(), name="auto_sync_loop")
    return {"ok": True, "message": "已启动自动进度同步（每5秒）"}


# 全局变量用于跟踪自动同步任务
_auto_sync_task = None


# ── Aria2 扩展端点 ──

@router.get("/download/aria2/stats", response_model=Aria2GlobalStats)
async def aria2_stats(client_id: int, user: CurrentUser, db: DB):
    """获取 Aria2 客户端全局统计（活跃/等待/停止任务数、上下行速度）"""
    from app.download.clients import Aria2Adapter
    service = DownloadService(db)
    stats = await service.get_aria2_stats(client_id)
    return Aria2GlobalStats(**stats)


# ── 整理入库 ──

@router.post("/download/organize")
async def organize_downloads(user: AdminUser, db: DB):
    """手动触发所有已完成任务的整理入库"""
    service = DownloadService(db)
    stats = await service.detect_and_process_completed()
    return {"ok": True, **stats}


@router.post("/download/{task_id}/organize")
async def organize_single_task(task_id: int, user: AdminUser, db: DB):
    """手动整理单个下载任务"""
    service = DownloadService(db)
    result = await service.manual_organize(task_id)
    return {"ok": True, **result}
