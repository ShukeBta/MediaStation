# -*- coding: utf-8 -*-
"""
Database initialization & session management
Supports SQLite (default) and PostgreSQL (optional)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def __getattr__(name: str):
    """Lazy-init: modules that do `from app.database import async_session_factory`
    will always get a valid session factory, never None.
    """
    if name == "async_session_factory":
        return get_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _is_postgresql(url: str) -> bool:
    return "postgresql" in url or "postgres" in url


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    url = settings.db_url

    if _is_postgresql(url):
        logger.info(f"Using PostgreSQL database: {_mask_db_url(url)}")
        return create_async_engine(
            url,
            echo=settings.app_debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
            pool_timeout=30,
        )
    else:
        logger.info(f"Using SQLite database: {url.rsplit('/', 1)[-1]}")

        # Pre-set WAL mode on the database file directly (persistent across all connections)
        import sqlite3
        import os
        db_path = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        if db_path and not db_path.startswith(":"):
            try:
                os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
                raw = sqlite3.connect(db_path)
                raw.execute("PRAGMA journal_mode=WAL")
                raw.execute("PRAGMA synchronous=NORMAL")
                raw.close()
                logger.info("SQLite WAL mode enabled (pre-init)")
            except Exception as e:
                logger.warning(f"Could not pre-set SQLite PRAGMAs: {e}")

        eng = create_async_engine(
            url,
            echo=settings.app_debug,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        def _set_sqlite_pragma(dbapi_connection, connection_record):
            """Ensure busy_timeout is set on every connection (WAL is already persistent)."""
            if isinstance(dbapi_connection, sqlite3.Connection):
                dbapi_connection.execute("PRAGMA busy_timeout=5000")

        event.listen(eng.sync_engine, "connect", _set_sqlite_pragma)
        return eng


def get_engine() -> AsyncEngine:
    global engine, _async_session_factory
    if engine is None:
        engine = _build_engine()
        _async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 session factory，如果未初始化则自动初始化"""
    global _async_session_factory
    
    # 如果未初始化，先初始化 engine 和 session factory
    if _async_session_factory is None:
        get_engine()
    
    # 双重检查：如果还是 None，直接创建
    if _async_session_factory is None:
        from app.config import get_settings
        settings = get_settings()
        eng = _build_engine()
        _async_session_factory = async_sessionmaker(
            eng, class_=AsyncSession, expire_on_commit=False
        )
        logger.warning("async_session_factory was None, created directly in get_session_factory()")
    
    return _async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def _mask_db_url(url: str) -> str:
    try:
        if "@" not in url:
            return url.split("/")[-1] or url
        parts = url.split("@", 1)
        scheme_user = parts[0].split("://", 1)
        user_part = scheme_user[1].split(":", 1)[0] if ":" in scheme_user[1] else ""
        return f"{scheme_user[0]}://{user_part}:****@{parts[1]}"
    except Exception:
        return "***"


async def init_db():
    from app.base_models import Base
    import app.media.models
    import app.download.models
    import app.subscribe.models
    import app.user.models          # 包含 User, UserPermission, SystemConfig
    import app.system.models
    import app.system.api_config_models
    import app.playback.models
    # import app.license.models      # 授权管理模型（可选）

    eng = get_engine()
    settings = get_settings()

    if _is_postgresql(settings.db_url):
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL tables created/verified")
        await _create_pg_indexes(eng)
    else:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite tables created/verified")


async def _create_pg_indexes(eng: AsyncEngine):
    index_sqls = [
        "CREATE INDEX IF NOT EXISTS idx_media_items_title ON media_items USING gin(to_tsvector('simple', title))",
        "CREATE INDEX IF NOT EXISTS idx_media_items_type ON media_items(media_type)",
        "CREATE INDEX IF NOT EXISTS idx_media_items_scraped ON media_items(scraped)",
        "CREATE INDEX IF NOT EXISTS idx_media_items_rating ON media_items(rating DESC NULLS LAST)",
        "CREATE INDEX IF NOT EXISTS idx_watch_history_user ON watch_history(user_id, last_watched DESC)",
        "CREATE INDEX IF NOT EXISTS idx_watch_history_media ON watch_history(media_item_id)",
        "CREATE INDEX IF NOT EXISTS idx_download_tasks_status ON download_tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_download_tasks_client ON download_tasks(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)",
        "CREATE INDEX IF NOT EXISTS idx_subtitles_item ON subtitles(media_item_id)",
    ]
    for sql in index_sqls:
        try:
            async with eng.begin() as conn:
                await conn.execute(text(sql))
        except Exception as e:
            logger.debug(f"Index creation skipped/failed: {e}")


async def close_db():
    global engine, _async_session_factory
    if engine is None:
        return
    await engine.dispose()
    engine = None
    _async_session_factory = None
    logger.info("Database connection closed")
