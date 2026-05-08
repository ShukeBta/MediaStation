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

    # 在线授权心跳检查（每 6 小时检查一次，到点才真正发送心跳）
    scheduler.add_job(
        job_license_heartbeat,
        trigger=IntervalTrigger(hours=6),
        id="license_heartbeat",
        name="在线授权心跳",
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
                except Exception as e:
                    logger.error(f"Scan {lib.name} failed: {e}")
                await session.commit()
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


async def job_license_heartbeat():
    """
    定时检查在线授权心跳。
    - 每 6 小时检查一次
    - 如果 verification_mode != "online" → 跳过
    - 如果 now < next_heartbeat_at → 跳过（还没到心跳时间）
    - 如果到期：发送心跳到授权服务器
      - 成功 → 更新缓存，清除宽限期
      - 失败 → 启动/延续宽限期
      - 宽限期已过 → 降级为免费版
    """
    import random
    from datetime import datetime, timedelta

    from app.database import async_session_factory
    from app.license.cache import LicenseCacheManager
    from app.license.fingerprint import get_device_fingerprint
    from app.license.remote_client import RemoteLicenseClient
    from app.user.models import SystemConfig

    # 读取配置
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                __import__("sqlalchemy").select(SystemConfig).where(
                    SystemConfig.key == "license_verification_mode"
                )
            )
            cfg = result.scalar_one_or_none()
            mode = cfg.value if cfg else "local"
            if mode != "online":
                return  # 非在线模式，跳过

            # 读取缓存
            secret_result = await session.execute(
                __import__("sqlalchemy").select(SystemConfig).where(
                    SystemConfig.key == "license_server_secret"
                )
            )
            secret_cfg = secret_result.scalar_one_or_none()
            hmac_secret = secret_cfg.value if secret_cfg else ""

            cache_mgr = LicenseCacheManager(session, hmac_secret=hmac_secret)
            cache = await cache_mgr.get_cache()

            if not cache or not cache.license_type:
                return  # 无授权缓存，跳过

            now = datetime.now()

            # 还没到心跳时间，跳过（加随机抖动 ±2 小时避免雷群效应）
            jitter_minutes = random.randint(-120, 120)
            effective_next = cache.next_heartbeat_at + timedelta(minutes=jitter_minutes) if cache.next_heartbeat_at else None
            if effective_next and now < effective_next:
                logger.debug("License heartbeat: not due yet, skipping")
                return

            # 检查宽限期是否已过
            if cache.grace_period_ends and now >= cache.grace_period_ends:
                logger.warning("License heartbeat: grace period expired, downgrading to free tier")
                await cache_mgr.clear_cache(cache.instance_id)
                await session.commit()
                return

            # 读取服务器 URL 和 instance_id
            url_result = await session.execute(
                __import__("sqlalchemy").select(SystemConfig).where(
                    SystemConfig.key == "license_server_url"
                )
            )
            url_cfg = url_result.scalar_one_or_none()
            server_url = url_cfg.value if url_cfg else ""

            inst_result = await session.execute(
                __import__("sqlalchemy").select(SystemConfig).where(
                    SystemConfig.key == "license_instance_id"
                )
            )
            inst_cfg = inst_result.scalar_one_or_none()
            instance_id = inst_cfg.value if inst_cfg else ""

            grace_result = await session.execute(
                __import__("sqlalchemy").select(SystemConfig).where(
                    SystemConfig.key == "license_grace_period_days"
                )
            )
            grace_cfg = grace_result.scalar_one_or_none()
            grace_days = int(grace_cfg.value) if grace_cfg else 14

            if not server_url or not instance_id:
                logger.warning("License heartbeat: server URL or instance ID not configured")
                return

            # 发送心跳
            fingerprint = get_device_fingerprint()
            client = RemoteLicenseClient(server_url)
            try:
                hb_result = await client.heartbeat(
                    fingerprint=fingerprint,
                    instance_id=instance_id,
                    cached_info={
                        "license_type": cache.license_type,
                        "activated_at": cache.last_verified_at.isoformat() if cache.last_verified_at else None,
                    },
                )

                if hb_result.get("valid"):
                    await cache_mgr.save_online_result(
                        instance_id=instance_id,
                        fingerprint=fingerprint,
                        server_response=hb_result,
                    )
                    logger.info("License heartbeat: success, cache updated")
                else:
                    logger.warning(f"License heartbeat: server returned invalid - {hb_result.get('error', 'unknown')}")
                    await cache_mgr.clear_cache(instance_id)

            except (ConnectionError, OSError) as e:
                # 网络失败，记录宽限期
                logger.warning(f"License heartbeat: connection failed - {e}")
                await cache_mgr.record_heartbeat_failure(instance_id, grace_period_days=grace_days)
            except Exception as e:
                logger.error(f"License heartbeat: unexpected error - {e}")
            finally:
                await client.close()

            await session.commit()

        except Exception as e:
            logger.error(f"Job license_heartbeat failed: {e}")
