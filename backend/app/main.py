"""
MediaStation — 轻量级家庭媒体服务器
FastAPI 主入口，生命周期管理，路由注册。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_db, init_db
from app.system.scheduler import get_scheduler, setup_scheduler
from app.exceptions import AppError

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mediastation")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting MediaStation...")

    # 启动
    settings = get_settings()
    await init_db()
    logger.info("Database initialized")

    # 创建默认管理员（检查是否存在任何管理员，而非仅检查 "admin" 用户名）
    from app.database import async_session_factory
    from app.user.repository import UserRepository
    from app.user.auth import hash_password

    async with async_session_factory() as session:
        repo = UserRepository(session)
        # 检查是否存在任何 admin 角色的用户（防止用户改名后后门被反复重建）
        has_admin = await repo.check_admin_exists()
        if not has_admin:
            initial_password = os.getenv("ADMIN_INITIAL_PASSWORD", "admin123")
            await repo.create("admin", hash_password(initial_password), role="admin")
            if initial_password == "admin123":
                logger.warning("⚠️  Default admin password 'admin123' in use — please change it immediately after first login!")
            logger.info(f"Default admin user created: admin / {initial_password}")
        await session.commit()

    # 启动调度器
    setup_scheduler()
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    # 初始化 Provider Chain（元数据刮削调度）
    try:
        from app.media.providers import init_provider_chain
        init_provider_chain(settings)
        logger.info("Provider chain initialized")
    except Exception as e:
        logger.warning(f"Provider chain init failed: {e}")

    # 启动文件监控
    try:
        from app.media.watcher import get_watcher
        from app.media.repository import MediaRepository
        from app.database import async_session_factory

        async with async_session_factory() as session:
            repo = MediaRepository(session)
            libraries = await repo.get_all_libraries()
            if libraries:
                lib_data = [{"id": lib.id, "path": lib.path, "enabled": lib.enabled} for lib in libraries]
                watcher = get_watcher()
                watcher.start(lib_data)
                logger.info(f"File watcher started for {len(lib_data)} libraries")
    except Exception as e:
        logger.warning(f"File watcher start failed: {e}")

    # 确保媒体目录存在
    for d in settings.media_dirs:
        d.mkdir(parents=True, exist_ok=True)

    logger.info(f"MediaStation started on port {settings.app_port}")
    yield

    # 关闭 - 清理转码任务（防止 FFmpeg 僵尸进程）
    try:
        from app.playback.service import get_transcoder
        transcoder = get_transcoder()
        await transcoder.shutdown_all()
        logger.info("All transcode jobs killed")
    except Exception as e:
        logger.warning(f"Transcoder shutdown failed: {e}")

    # 关闭
    scheduler.shutdown()
    try:
        from app.media.watcher import stop_watcher
        stop_watcher()
        logger.info("File watcher stopped")
    except Exception as e:
        logger.warning(f"File watcher stop failed: {e}")
    await close_db()
    logger.info("MediaStation stopped")


# ── 创建 FastAPI 应用 ──
app = FastAPI(
    title="MediaStation",
    description="轻量级家庭媒体服务器 — 融合播放 + 自动化订阅下载",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── 中间件 ──
settings = get_settings()

# CORS 配置：allow_origins=["*"] 不能与 allow_credentials=True 同时使用
# 使用环境变量 CORS_ORIGINS（逗号分隔），未设置时默认允许前端开发服务器
_cors_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 全局异常处理 ──
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "Internal server error", "status": 500},
    )


# ── 注册路由（统一加 /api 前缀）──
from app.user.router import router as user_router
from app.media.router import router as media_router
from app.playback.router import router as playback_router
from app.playback.external import router as playback_external_router
from app.download.router import router as download_router
from app.subscribe.router import router as subscribe_router
from app.system.router import router as system_router
from app.emby_api import router as emby_router
from app.media.discover_router import router as discover_router
from app.system.api_config_router import router as api_config_router
from app.system.settings_router import router as settings_router
from app.admin.router import router as admin_router
from app.stats.router import router as stats_router
from app.playlist.router import router as playlist_router
from app.strm.router import router as strm_router
from app.dlna import router as dlna_router
from app.license.router import router as license_router

API_PREFIX = "/api"

app.include_router(user_router, prefix=API_PREFIX)
app.include_router(media_router, prefix=API_PREFIX)
app.include_router(playback_router, prefix=API_PREFIX)
app.include_router(playback_external_router, prefix=API_PREFIX)
app.include_router(download_router, prefix=API_PREFIX)
app.include_router(subscribe_router, prefix=API_PREFIX)
app.include_router(system_router, prefix=API_PREFIX)
app.include_router(emby_router, prefix=API_PREFIX)
app.include_router(discover_router, prefix=API_PREFIX)
app.include_router(api_config_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(stats_router, prefix=API_PREFIX)
app.include_router(playlist_router, prefix=API_PREFIX)
app.include_router(strm_router, prefix=API_PREFIX)
app.include_router(dlna_router, prefix=API_PREFIX)
app.include_router(license_router, prefix=API_PREFIX)


# ── 静态文件（前端构建产物） ──
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA 前端路由回退（排除 API 和静态资源路径）"""
        # 不拦截 API 请求和已挂载的静态路径
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            from fastapi.responses import Response
            return Response(status_code=404)
        # Path Traversal 防护：resolve 后严格校验路径在 static_dir 内
        file = (static_dir / full_path).resolve()
        static_resolved = static_dir.resolve()
        try:
            is_safe = file.is_relative_to(static_resolved)
        except AttributeError:
            # Python < 3.9 兼容
            is_safe = str(file).startswith(str(static_resolved))
        if file.exists() and file.is_file() and is_safe:
            return FileResponse(str(file))
        return FileResponse(str(static_dir / "index.html"))
