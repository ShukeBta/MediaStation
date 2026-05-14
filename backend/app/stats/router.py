"""
数据统计 API 路由
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Query

from app.stats.schemas import (
    OverviewStats,
    PlayTrend,
    TopContentResponse,
    TopUsersResponse,
    LibrariesStatsResponse,
    SystemMonitor,
    UserStatsResponse,
    PlayRecordCreate,
)
from app.stats.service import StatsService
from app.common.schemas import SuccessResponse
from app.deps import AdminUser, CurrentUser

router = APIRouter(prefix="/stats", tags=["stats"])


def get_service() -> StatsService:
    return StatsService()


# ── 概览统计 ──

@router.get(
    "/overview",
    response_model=SuccessResponse[OverviewStats],
)
async def get_overview():
    """
    获取概览统计
    
    返回:
        - total_media: 媒体总数
        - total_movies: 电影数
        - total_tv: 剧集数
        - total_size: 总大小
        - total_users: 用户数
        - total_plays: 总播放次数
        - today_plays: 今日播放次数
        - active_users: 活跃用户数
    """
    service = get_service()
    stats = await service.get_overview()
    return SuccessResponse.ok(stats)


# ── 播放趋势 ──

@router.get(
    "/trend",
    response_model=SuccessResponse[PlayTrend],
)
async def get_play_trend(
    period: Annotated[str, Query(description="时间范围: 1d, 7d, 30d", pattern=r"^(1d|7d|30d)$")] = "7d",
):
    """
    获取播放趋势
    
    返回:
        - hourly: 每小时播放次数（最近24小时）
        - daily: 每天播放次数
        - weekly: 每周播放次数
    """
    service = get_service()
    trend = await service.get_play_trend(period)
    return SuccessResponse.ok(trend)


# ── 热门内容 ──

@router.get(
    "/top-content",
    response_model=SuccessResponse[TopContentResponse],
)
async def get_top_content(
    period: Annotated[str, Query(description="时间范围: 1d, 7d, 30d, all")] = "7d",
    limit: Annotated[int, Query(description="返回数量", ge=1, le=50)] = 10,
):
    """
    获取热门内容排行
    
    返回播放次数最多的媒体
    """
    service = get_service()
    top = await service.get_top_content(period, limit)
    return SuccessResponse.ok(top)


# ── 活跃用户 ──

@router.get(
    "/top-users",
    response_model=SuccessResponse[TopUsersResponse],
)
async def get_top_users(
    period: Annotated[str, Query(description="时间范围: 1d, 7d, 30d, all")] = "7d",
    limit: Annotated[int, Query(description="返回数量", ge=1, le=50)] = 10,
):
    """
    获取活跃用户排行
    
    返回播放次数最多的用户
    """
    service = get_service()
    top = await service.get_top_users(period, limit)
    return SuccessResponse.ok(top)


# ── 媒体库统计 ──

@router.get(
    "/libraries",
    response_model=SuccessResponse[LibrariesStatsResponse],
)
async def get_libraries_stats(user: AdminUser):
    """
    获取媒体库统计
    
    返回每个媒体库的媒体数量和大小
    """
    service = get_service()
    stats = await service.get_libraries_stats()
    return SuccessResponse.ok(stats)


# ── 系统监控 ──

@router.get(
    "/monitor",
    response_model=SuccessResponse[SystemMonitor],
)
async def get_system_monitor(user: AdminUser):
    """
    获取系统监控数据
    
    返回 CPU、内存、磁盘、网络等系统指标
    """
    service = get_service()
    monitor = await service.get_system_monitor()
    return SuccessResponse.ok(monitor)


# ── 用户统计 ──

@router.get(
    "/user/{user_id}",
    response_model=SuccessResponse[UserStatsResponse],
)
async def get_user_stats(user_id: int, user: AdminUser):
    """
    获取指定用户的统计信息
    
    包括播放次数、观看时长、偏好类型等
    """
    service = get_service()
    stats = await service.get_user_stats(user_id)
    return SuccessResponse.ok(stats)


# ── 播放记录 ──

@router.post(
    "/play",
    response_model=SuccessResponse[dict],
)
async def record_play(
    data: PlayRecordCreate,
    user: CurrentUser,
):
    """
    记录播放
    
    用户播放媒体时调用，用于统计
    """
    service = get_service()
    result = await service.record_play(user.id, data)
    return SuccessResponse.ok(result)
