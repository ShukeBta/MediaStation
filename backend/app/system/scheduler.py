"""
后台任务调度器 (APScheduler)
"""
from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"coalesce": True, "max_instances": 1},
        )
    return _scheduler


def setup_scheduler():
    """注册所有定时任务"""
    scheduler = get_scheduler()

    # 媒体库自动扫描（每 60 分钟）
    scheduler.add_job(
        job_scan_libraries,
        trigger=IntervalTrigger(minutes=60),
        id="media_scan",
        name="媒体库扫描",
        replace_existing=True,
    )

    # 订阅自动搜索（每 60 分钟）
    scheduler.add_job(
        job_process_subscriptions,
        trigger=IntervalTrigger(minutes=60),
        id="subscription_search",
        name="订阅搜索",
        replace_existing=True,
    )

    # 下载状态同步（每 30 秒）
    scheduler.add_job(
        job_sync_downloads,
        trigger=IntervalTrigger(seconds=30),
        id="download_sync",
        name="下载状态同步",
        replace_existing=True,
    )

    # RSS 拉取（每 30 分钟）
    scheduler.add_job(
        job_pull_rss,
        trigger=IntervalTrigger(minutes=30),
        id="rss_pull",
        name="RSS 拉取",
        replace_existing=True,
    )

    # 转码缓存清理（每天凌晨 3 点）
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(
        job_cleanup_transcode_cache,
        trigger=CronTrigger(hour=3, minute=0),
        id="cache_cleanup",
        name="转码缓存清理",
        replace_existing=True,
    )

    # 下载完成自动整理 + 入库（每 5 分钟）
    scheduler.add_job(
        job_process_completed_downloads,
        trigger=IntervalTrigger(minutes=5),
        id="download_complete",
        name="下载完成整理入库",
        replace_existing=True,
    )

    return scheduler


async def job_scan_libraries():
    """
    定时扫描所有媒体库。
    - 扫描文件系统变化（新增/删除/更新文件）
    - 增量刮削未完成元数据的条目（补全遗漏的刮削）
    """
    from app.database import async_session_factory
    from app.media.repository import MediaRepository
    from app.media.service import MediaService
    from app.system.events import get_event_bus

    logger.info("Scheduled job: scanning all libraries")
    event_bus = get_event_bus()

    async with async_session_factory() as session:
        try:
            repo = MediaRepository(session)
            libraries = await repo.get_enabled_libraries()
            service = MediaService(repo, event_bus)
            for lib in libraries:
                try:
                    # 1. 扫描文件系统（不自动刮削，因为新增条目会在创建时刮削）
                    result = await service.scan_library(lib.id, auto_scrape=False)
                    logger.info(f"Scan {lib.name}: +{result.added} ~{result.updated} -{result.removed}")

                    # 2. 增量刮削：补全未刮削的条目（最多 20 条）
                    scrape_stats = await service.scrape_unscraped(lib.id, limit=20)
                    if scrape_stats["scraped"] > 0 or scrape_stats["failed"] > 0:
                        logger.info(
                            f"Scrape {lib.name}: +{scrape_stats['scraped']} scraped, "
                            f"-{scrape_stats['failed']} failed"
                        )

                    await session.commit()
                except Exception as e:
                    logger.error(f"Scan {lib.name} failed: {e}")
                    # Issue #34 修复：在单个库扫描失败后立即回滚，清理事务失效状态。
                    # 若不回滚，SQLAlchemy 会将 Session 标记为 Invalidated，
                    # 下一次循环访问数据库时抛出 PendingRollbackError，导致后续所有库全部瘫痪。
                    await session.rollback()
        except Exception as e:
            logger.error(f"Job scan_libraries failed: {e}")


async def job_process_subscriptions():
    """定时处理所有订阅"""
    from app.database import async_session_factory
    from app.subscribe.service import SubscribeService

    logger.info("Scheduled job: processing subscriptions")
    async with async_session_factory() as session:
        try:
            service = SubscribeService(session)
            result = await service.process_all_subscriptions()
            logger.info(
                f"Subscriptions: searched={result['searched']} downloaded={result['downloaded']}"
            )
            await session.commit()
        except Exception as e:
            logger.error(f"Job process_subscriptions failed: {e}")


async def job_sync_downloads():
    """定时同步下载状态"""
    from app.database import async_session_factory
    from app.download.service import DownloadService
    from app.system.events import get_event_bus

    async with async_session_factory() as session:
        try:
            service = DownloadService(session)
            await service.sync_task_status()
            await session.commit()
        except Exception as e:
            logger.error(f"Job sync_downloads failed: {e}")


async def job_pull_rss():
    """定时拉取 RSS"""
    from app.database import async_session_factory
    from app.subscribe.service import SubscribeService

    logger.info("Scheduled job: pulling RSS")
    async with async_session_factory() as session:
        try:
            service = SubscribeService(session)
            result = await service.pull_rss()
            logger.info(f"RSS: {result['sites']} sites, {result['resources']} resources")
            await session.commit()
        except Exception as e:
            logger.error(f"Job pull_rss failed: {e}")


async def job_cleanup_transcode_cache():
    """清理转码缓存"""
    from app.playback.transcoder import Transcoder

    logger.info("Scheduled job: cleaning transcode cache")
    try:
        transcoder = Transcoder()
        cleaned = await transcoder.cleanup_cache(max_age_hours=24)
        logger.info(f"Cleaned {cleaned} transcode cache directories")
    except Exception as e:
        logger.error(f"Job cleanup_transcode_cache failed: {e}")


async def job_process_completed_downloads():
    """定时检测下载完成并自动整理入库"""
    from app.database import async_session_factory
    from app.download.service import DownloadService

    logger.info("Scheduled job: processing completed downloads")
    async with async_session_factory() as session:
        try:
            service = DownloadService(session)
            stats = await service.detect_and_process_completed()
            if stats["organized"] > 0 or stats["errors"] > 0:
                logger.info(
                    f"Completed downloads processed: organized={stats['organized']}, "
                    f"skipped={stats['skipped']}, errors={stats['errors']}"
                )
            else:
                logger.debug(
                    f"No new completed downloads to process "
                    f"(total_completed={stats['total_completed']})"
                )
            await session.commit()
        except Exception as e:
            logger.error(f"Job process_completed_downloads failed: {e}")

