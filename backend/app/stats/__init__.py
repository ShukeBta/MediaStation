"""
数据统计模块
"""
from app.stats.router import router as stats_router
from app.stats.service import StatsService
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

__all__ = [
    "stats_router",
    "StatsService",
    "OverviewStats",
    "PlayTrend",
    "TopContentResponse",
    "TopUsersResponse",
    "LibrariesStatsResponse",
    "SystemMonitor",
    "UserStatsResponse",
    "PlayRecordCreate",
]
