"""
系统路由（健康检查、SSE、设置）
"""
from __future__ import annotations

import platform
import shutil
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.deps import AdminUser, CurrentUser, DB
from app.config import get_settings
from app.system.events import event_generator, get_event_bus

router = APIRouter(tags=["system"])

# 记录启动时间
_start_time = time.time()


@router.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/system/info")
async def system_info(user: CurrentUser):
    settings = get_settings()

    # 检测 ffmpeg/ffprobe
    ffmpeg_ok = shutil.which(settings.ffmpeg_path) is not None
    ffprobe_ok = shutil.which(settings.ffprobe_path) is not None

    # 运行时间
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    else:
        uptime_str = f"{minutes}m {seconds}s"

    return {
        "app_name": settings.app_name,
        "version": "0.1.0",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "data_dir": settings.data_dir,
        "hw_accel": settings.hw_accel,
        "tmdb_configured": bool(settings.tmdb_api_key),
        "tmdb_language": settings.tmdb_language,
        "ffmpeg_path": settings.ffmpeg_path,
        "ffprobe_path": settings.ffprobe_path,
        "ffmpeg_ok": ffmpeg_ok,
        "ffprobe_ok": ffprobe_ok,
        "max_transcode_jobs": settings.max_transcode_jobs,
        "transcode_enabled": settings.transcode_enabled,
        "db_type": "PostgreSQL" if settings.database_url else "SQLite",
        "uptime": uptime_str,
        "start_time": datetime.fromtimestamp(_start_time, tz=timezone.utc).isoformat(),
    }


@router.get("/system/status")
async def system_status(user: CurrentUser):
    import psutil

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory": {
            "total": psutil.virtual_memory().total,
            "used": psutil.virtual_memory().used,
            "percent": psutil.virtual_memory().percent,
        },
        "disk": {
            "total": psutil.disk_usage("/").total if platform.system() != "Windows"
            else psutil.disk_usage("C:\\").total,
            "used": psutil.disk_usage("/").used if platform.system() != "Windows"
            else psutil.disk_usage("C:\\").used,
            "percent": psutil.disk_usage("/").percent if platform.system() != "Windows"
            else psutil.disk_usage("C:\\").percent,
        },
        "uptime": datetime.now().isoformat(),
    }


@router.get("/system/events")
async def system_events(request: Request, token: str = None):
    """SSE 实时事件流（支持从 query 参数传递 token）"""
    from fastapi import status
    from jose import JWTError, jwt
    from app.config import get_settings
    from app.database import async_session_factory
    from app.user.models import User
    from sqlalchemy import select
    
    # 如果没有 token query 参数，尝试从 header 获取
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer "
    
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    # 验证 token
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 获取用户并验证
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return EventSourceResponse(event_generator())


@router.get("/system/scheduler")
async def scheduler_info(user: AdminUser):
    from app.system.scheduler import get_scheduler
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        # 解析触发器描述
        trigger_str = ""
        try:
            trigger_str = str(job.trigger)
        except Exception:
            pass

        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": trigger_str,
            "status": "idle",
        })
    return {"running": scheduler.running, "jobs": jobs}


@router.post("/system/scheduler/{job_id}/trigger")
async def trigger_job(job_id: str, user: AdminUser):
    """手动立即触发一个定时任务"""
    from app.system.scheduler import get_scheduler
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    # 立即修改 next_run_time 为现在，让调度器尽快执行
    scheduler.modify_job(job_id, next_run_time=datetime.now(timezone.utc))
    return {"success": True, "message": f"Job '{job_id}' triggered"}


# ── 全局配置读取/更新 ──

class ConfigUpdate(BaseModel):
    tmdb_api_key: str | None = None
    tmdb_language: str | None = None
    hw_accel: str | None = None
    max_transcode_jobs: int | None = None
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    transcode_enabled: bool | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None


@router.get("/system/config")
async def get_config(user: AdminUser):
    """获取可编辑的系统配置（不返回密钥明文，仅返回是否已配置）"""
    settings = get_settings()
    return {
        "tmdb_api_key": "***" if settings.tmdb_api_key else "",
        "tmdb_api_key_set": bool(settings.tmdb_api_key),
        "tmdb_language": settings.tmdb_language,
        "hw_accel": settings.hw_accel,
        "max_transcode_jobs": settings.max_transcode_jobs,
        "ffmpeg_path": settings.ffmpeg_path,
        "ffprobe_path": settings.ffprobe_path,
        "transcode_enabled": settings.transcode_enabled,
        "openai_api_key_set": bool(settings.openai_api_key),
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
    }


@router.patch("/system/config")
async def update_config(body: ConfigUpdate, user: AdminUser):
    """更新系统配置（写入 .env 文件）"""
    import os
    from pathlib import Path

    env_path = Path(".env")
    # 读取现有 .env
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip().upper()] = v.strip()

    # 字段映射
    field_map = {
        "tmdb_api_key": "TMDB_API_KEY",
        "tmdb_language": "TMDB_LANGUAGE",
        "hw_accel": "HW_ACCEL",
        "max_transcode_jobs": "MAX_TRANSCODE_JOBS",
        "ffmpeg_path": "FFMPEG_PATH",
        "ffprobe_path": "FFPROBE_PATH",
        "transcode_enabled": "TRANSCODE_ENABLED",
        "openai_api_key": "OPENAI_API_KEY",
        "openai_base_url": "OPENAI_BASE_URL",
        "openai_model": "OPENAI_MODEL",
    }

    updates = body.model_dump(exclude_none=True)
    for field, env_key in field_map.items():
        if field in updates:
            val = updates[field]
            if val is not None and val != "":
                existing[env_key] = str(val)
            elif field == "transcode_enabled" and val is not None:
                existing[env_key] = str(val).lower()

    # 写回 .env
    lines = [f"{k}={v}" for k, v in existing.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"success": True, "message": "配置已保存，部分配置需重启服务生效"}
