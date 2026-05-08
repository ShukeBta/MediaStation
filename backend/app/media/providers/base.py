"""
Provider Chain - 元数据 Provider 基类和接口
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class ProviderPriority(IntEnum):
    """Provider 优先级定义（数字越小越优先）"""
    Adult = 5        # 18+ 番号刮削（最高优先级）
    TMDb = 10
    Douban = 20
    TheTVDB = 25
    Bangumi = 30
    Fanart = 50
    AI = 100


@dataclass
class MediaMetadata:
    """统一的元数据结构 - 用于 Provider 之间传递数据"""
    # ID 字段
    tmdb_id: int | None = None
    douban_id: str | None = None
    bangumi_id: int | None = None
    thetvdb_id: int | None = None

    # 基础信息
    title: str = ""
    original_title: str | None = None
    year: int | None = None
    overview: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None

    # 评分
    rating: float = 0.0
    douban_rating: float | None = None
    bangumi_rating: float | None = None

    # 类型信息
    genres: list[str] = field(default_factory=list)
    duration: int | None = None  # 秒
    is_adult: bool = False

    # 电影合集信息
    collection_id: int | None = None
    collection_name: str | None = None
    collection_poster_url: str | None = None
    collection_backdrop_url: str | None = None

    # 扩展字段（用于 Provider 特定数据）
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "tmdb_id": self.tmdb_id,
            "douban_id": self.douban_id,
            "bangumi_id": self.bangumi_id,
            "thetvdb_id": self.thetvdb_id,
            "title": self.title,
            "original_title": self.original_title,
            "year": self.year,
            "overview": self.overview,
            "poster_url": self.poster_url,
            "backdrop_url": self.backdrop_url,
            "rating": self.rating,
            "douban_rating": self.douban_rating,
            "bangumi_rating": self.bangumi_rating,
            "genres": self.genres,
            "duration": self.duration,
            "is_adult": self.is_adult,
            "collection_id": self.collection_id,
            "collection_name": self.collection_name,
        }
        result.update(self.extra)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MediaMetadata:
        """从字典创建"""
        extra = {k: v for k, v in data.items()
                 if k not in ["tmdb_id", "douban_id", "bangumi_id", "thetvdb_id",
                             "title", "original_title", "year", "overview",
                             "poster_url", "backdrop_url", "rating", "douban_rating",
                             "bangumi_rating", "genres", "duration", "is_adult",
                             "collection_id", "collection_name"]}
        return cls(
            tmdb_id=data.get("tmdb_id"),
            douban_id=data.get("douban_id"),
            bangumi_id=data.get("bangumi_id"),
            thetvdb_id=data.get("thetvdb_id"),
            title=data.get("title", ""),
            original_title=data.get("original_title"),
            year=data.get("year"),
            overview=data.get("overview"),
            poster_url=data.get("poster_url"),
            backdrop_url=data.get("backdrop_url"),
            rating=data.get("rating", 0.0),
            douban_rating=data.get("douban_rating"),
            bangumi_rating=data.get("bangumi_rating"),
            genres=data.get("genres", []),
            duration=data.get("duration"),
            is_adult=data.get("is_adult", False),
            collection_id=data.get("collection_id"),
            collection_name=data.get("collection_name"),
            extra=extra,
        )


class MetadataProvider(ABC):
    """Provider 基类 - 所有数据源 Provider 必须实现此接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级（数字越小越优先）"""
        pass

    @property
    def is_primary(self) -> bool:
        """是否是主数据源（提供完整的元数据）"""
        return self.priority <= ProviderPriority.Douban

    @abstractmethod
    async def is_configured(self) -> bool:
        """
        检查 Provider 是否已配置

        Returns:
            True 如果 Provider 可以使用（已配置必要的 API Key 等）
        """
        pass

    @abstractmethod
    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索媒体

        Args:
            title: 搜索标题
            media_type: 媒体类型（movie, tv, anime）
            year: 年份（可选）

        Returns:
            搜索结果列表，每项包含 id, title 等基本信息
        """
        pass

    @abstractmethod
    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """
        获取媒体元数据（主数据源调用）

        Args:
            media_id: 媒体 ID（Provider 特定的格式）
            media_type: 媒体类型

        Returns:
            完整的元数据对象
        """
        pass

    async def enrich_metadata(
        self,
        metadata: MediaMetadata,
        media_type: str,
    ) -> MediaMetadata:
        """
        补充/丰富元数据（辅助数据源调用）

        默认实现不做任何处理，子类可以覆盖此方法。

        Args:
            metadata: 已有元数据
            media_type: 媒体类型

        Returns:
            补充后的元数据
        """
        return metadata

    async def get_images(
        self,
        media_id: str | int,
        media_type: str,
    ) -> dict[str, list[str]]:
        """
        获取媒体图片（用于图片增强 Provider）

        Args:
            media_id: 媒体 ID
            media_type: 媒体类型

        Returns:
            图片字典，包含 poster, backdrop, logo 等类型的 URL 列表
        """
        return {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} priority={self.priority}>"


# 导出
__all__ = [
    "ProviderPriority",
    "MediaMetadata",
    "MetadataProvider",
]
