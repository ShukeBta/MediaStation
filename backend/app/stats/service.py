"""
数据统计服务
"""
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.stats.schemas import (
    OverviewStats,
    PlayTrend,
    TrendPoint,
    TopContentResponse,
    TopContentItem,
    TopUsersResponse,
    TopUserItem,
    LibrariesStatsResponse,
    LibraryStats,
    SystemMonitor,
    UserStats,
    UserStatsResponse,
    PlayRecordCreate,
)
from app.database import async_session_factory
from app.media.repository import MediaRepository
from app.user.models import User
from app.playback.models import PlayHistory
from app.media.models import MediaItem

logger = logging.getLogger(__name__)


class StatsService:
    """数据统计服务"""

    async def get_overview(self) -> OverviewStats:
        """获取概览统计"""
        async with async_session_factory() as db:
            # 媒体统计
            repo = MediaRepository(db)
            media_stats = await repo.get_stats()
            
            # 用户统计
            user_count = await db.scalar(select(func.count(User.id)))
            
            # 播放统计（今日）
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_plays = await db.scalar(
                select(func.count(PlayHistory.id))
                .where(PlayHistory.played_at >= today_start)
            ) or 0
            
            today_watch_time = await db.scalar(
                select(func.sum(PlayHistory.duration))
                .where(PlayHistory.played_at >= today_start)
            ) or 0
            
            # 总播放统计
            total_plays = await db.scalar(select(func.count(PlayHistory.id))) or 0
            total_watch_time = await db.scalar(
                select(func.sum(PlayHistory.duration))
            ) or 0
            
            # 活跃用户（过去7天）
            week_ago = datetime.now() - timedelta(days=7)
            active_users = await db.scalar(
                select(func.count(func.distinct(PlayHistory.user_id)))
                .where(PlayHistory.played_at >= week_ago)
            ) or 0
            
            return OverviewStats(
                total_media=media_stats.get("total_items", 0),
                total_movies=media_stats.get("total_movies", 0),
                total_tv=media_stats.get("total_tv", 0),
                total_size=media_stats.get("total_size", 0),
                total_users=user_count or 0,
                total_plays=total_plays,
                total_watch_time=total_watch_time or 0,
                today_plays=today_plays,
                today_watch_time=today_watch_time or 0,
                active_users=active_users,
            )

    async def get_play_trend(self, period: str = "7d") -> PlayTrend:
        """获取播放趋势"""
        async with async_session_factory() as db:
            now = datetime.now()
            
            # 按小时统计（最近24小时）
            hourly = []
            for i in range(24):
                hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23-i)
                hour_end = hour_start + timedelta(hours=1)
                
                count = await db.scalar(
                    select(func.count(PlayHistory.id))
                    .where(
                        and_(
                            PlayHistory.played_at >= hour_start,
                            PlayHistory.played_at < hour_end
                        )
                    )
                ) or 0
                
                hourly.append(TrendPoint(timestamp=hour_start, value=float(count)))
            
            # 按天统计（最近7天或30天）
            daily = []
            days = 7 if period == "7d" else 30
            for i in range(days):
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1-i)
                day_end = day_start + timedelta(days=1)
                
                count = await db.scalar(
                    select(func.count(PlayHistory.id))
                    .where(
                        and_(
                            PlayHistory.played_at >= day_start,
                            PlayHistory.played_at < day_end
                        )
                    )
                ) or 0
                
                daily.append(TrendPoint(timestamp=day_start, value=float(count)))
            
            return PlayTrend(hourly=hourly, daily=daily, weekly=[])

    async def get_top_content(self, period: str = "7d", limit: int = 10) -> TopContentResponse:
        """获取热门内容"""
        async with async_session_factory() as db:
            # 计算时间范围
            now = datetime.now()
            if period == "1d":
                start_time = now - timedelta(days=1)
            elif period == "7d":
                start_time = now - timedelta(days=7)
            elif period == "30d":
                start_time = now - timedelta(days=30)
            else:
                start_time = now - timedelta(days=365)  # all
            
            # 查询播放次数最多的媒体
            query = (
                select(
                    PlayHistory.media_item_id,
                    func.count(PlayHistory.id).label("play_count"),
                    func.sum(PlayHistory.duration).label("watch_time")
                )
                .where(PlayHistory.played_at >= start_time)
                .group_by(PlayHistory.media_item_id)
                .order_by(desc("play_count"))
                .limit(limit)
            )
            
            result = await db.execute(query)
            rows = result.all()
            
            # 获取媒体详情
            items = []
            from app.media.models import MediaItem
            for row in rows:
                media = await db.get(MediaItem, row.media_item_id)
                if media:
                    items.append(TopContentItem(
                        media_id=media.id,
                        title=media.title,
                        poster_url=media.poster_url,
                        play_count=row.play_count,
                        watch_time=row.watch_time or 0,
                        rating=media.rating or 0,
                    ))
            
            return TopContentResponse(items=items, period=period)

    async def get_top_users(self, period: str = "7d", limit: int = 10) -> TopUsersResponse:
        """获取活跃用户"""
        async with async_session_factory() as db:
            now = datetime.now()
            if period == "1d":
                start_time = now - timedelta(days=1)
            elif period == "7d":
                start_time = now - timedelta(days=7)
            elif period == "30d":
                start_time = now - timedelta(days=30)
            else:
                start_time = now - timedelta(days=365)
            
            # 查询活跃用户
            query = (
                select(
                    PlayHistory.user_id,
                    func.count(PlayHistory.id).label("play_count"),
                    func.sum(PlayHistory.duration).label("watch_time"),
                    func.max(PlayHistory.played_at).label("last_active")
                )
                .where(PlayHistory.played_at >= start_time)
                .group_by(PlayHistory.user_id)
                .order_by(desc("play_count"))
                .limit(limit)
            )
            
            result = await db.execute(query)
            rows = result.all()
            
            items = []
            for row in rows:
                user = await db.get(User, row.user_id)
                if user:
                    items.append(TopUserItem(
                        user_id=user.id,
                        username=user.username,
                        avatar_url=None,
                        play_count=row.play_count,
                        watch_time=row.watch_time or 0,
                        last_active=row.last_active,
                    ))
            
            return TopUsersResponse(items=items, period=period)

    async def get_libraries_stats(self) -> LibrariesStatsResponse:
        """获取媒体库统计"""
        from app.media.models import MediaLibrary
        
        async with async_session_factory() as db:
            # 获取所有媒体库
            result = await db.execute(select(MediaLibrary))
            libraries = result.scalars().all()
            
            stats = []
            total_media = 0
            total_size = 0
            
            for lib in libraries:
                # 统计该库下的媒体
                count_result = await db.execute(
                    select(func.count(MediaItem.id))
                    .where(MediaItem.library_id == lib.id)
                )
                media_count = count_result.scalar() or 0
                
                size_result = await db.execute(
                    select(func.sum(MediaItem.file_size))
                    .where(MediaItem.library_id == lib.id)
                )
                total_size_lib = size_result.scalar() or 0
                
                stats.append(LibraryStats(
                    library_id=lib.id,
                    name=lib.name,
                    media_count=media_count,
                    total_size=total_size_lib,
                    last_scan=lib.last_scan,
                    type_breakdown={},  # TODO: 实现类型统计
                ))
                
                total_media += media_count
                total_size += total_size_lib
            
            return LibrariesStatsResponse(
                libraries=stats,
                total_media=total_media,
                total_size=total_size,
            )

    async def get_system_monitor(self) -> SystemMonitor:
        """获取系统监控"""
        import psutil
        import time
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()
            
            # 获取运行时间
            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime = f"{hours}h {minutes}m"
            
            # TODO: 获取活跃转码和流媒体数量
            active_transcodes = 0
            active_streams = 0
            
            return SystemMonitor(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_total=memory.total,
                disk_percent=disk.percent,
                disk_used=disk.used,
                disk_total=disk.total,
                network_sent=net.bytes_sent,
                network_recv=net.bytes_recv,
                active_transcodes=active_transcodes,
                active_streams=active_streams,
                uptime=uptime,
            )
        except Exception as e:
            logger.error(f"Failed to get system monitor: {e}")
            return SystemMonitor(
                cpu_percent=0,
                memory_percent=0,
                memory_used=0,
                memory_total=0,
                disk_percent=0,
                disk_used=0,
                disk_total=0,
                network_sent=0,
                network_recv=0,
            )

    async def get_user_stats(self, user_id: int) -> UserStatsResponse:
        """获取用户统计"""
        from app.media.models import MediaItem
        
        async with async_session_factory() as db:
            user = await db.get(User, user_id)
            if not user:
                raise ValueError("User not found")
            
            # 总播放次数
            total_plays = await db.scalar(
                select(func.count(PlayHistory.id))
                .where(PlayHistory.user_id == user_id)
            ) or 0
            
            # 总观看时长
            total_watch_time = await db.scalar(
                select(func.sum(PlayHistory.duration))
                .where(PlayHistory.user_id == user_id)
            ) or 0
            
            avg_watch_time = int(total_watch_time / total_plays) if total_plays > 0 else 0
            
            # 最近观看的媒体
            recent_result = await db.execute(
                select(PlayHistory.media_item_id)
                .where(PlayHistory.user_id == user_id)
                .order_by(desc(PlayHistory.played_at))
                .limit(10)
            )
            recently_watched = [row[0] for row in recent_result.all()]
            
            return UserStatsResponse(
                user=UserStats(
                    user_id=user_id,
                    username=user.username,
                    total_plays=total_plays,
                    total_watch_time=total_watch_time or 0,
                    avg_watch_time=avg_watch_time,
                    recently_watched=recently_watched,
                ),
                hourly_distribution=[],
                weekly_activity=[],
            )

    async def record_play(self, user_id: int, data: PlayRecordCreate) -> dict:
        """记录播放"""
        async with async_session_factory() as db:
            record = PlayHistory(
                user_id=user_id,
                media_item_id=data.media_id,
                duration=data.duration_seconds,
                device_type=data.device_type,
                ip_address=data.ip_address,
            )
            db.add(record)
            await db.commit()
            
            return {
                "message": "Play recorded",
                "media_id": data.media_id,
                "duration": data.duration_seconds,
            }
