"""
Provider Chain - Douban Provider 实现
豆瓣 Provider - 优先级 20，中文媒体元数据补充
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.media.providers.base import MediaMetadata, MetadataProvider, ProviderPriority

from ..douban_scraper import DoubanClient, get_douban_client

logger = logging.getLogger(__name__)


class DoubanProvider(MetadataProvider):
    """Douban Provider - 中文媒体元数据来源"""

    def __init__(self):
        self._client: DoubanClient | None = None

    @property
    def name(self) -> str:
        return "豆瓣"

    @property
    def priority(self) -> int:
        return ProviderPriority.Douban

    @property
    def is_primary(self) -> bool:
        """豆瓣作为辅助数据源（不提供完整的元数据）"""
        return False

    async def is_configured(self) -> bool:
        """豆瓣 API 无需特殊配置（Cookie 可选但推荐）"""
        return True

    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """搜索豆瓣"""
        client = self._get_client()
        try:
            results = await client.search(title, media_type)
            return [
                {
                    "id": r.get("douban_id", ""),
                    "title": r.get("title", ""),
                    "year": r.get("year"),
                    "poster_path": r.get("cover", ""),
                    "overview": "",
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"[Douban] Search failed: {e}")
            return []

    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """获取豆瓣元数据（作为主数据源时）"""
        client = self._get_client()
        try:
            data = await client.get_detail(str(media_id))
            if not data:
                return None
            return self._to_metadata(data)
        except Exception as e:
            logger.error(f"[Douban] Get metadata failed for {media_id}: {e}")
            return None

    async def enrich_metadata(
        self,
        metadata: MediaMetadata,
        media_type: str,
    ) -> MediaMetadata:
        """
        用豆瓣数据补充元数据
        不覆盖已有数据，只补充缺失字段
        """
        # 跳过已有中文标题的情况
        title = metadata.title
        if not title:
            # 尝试用 original_title
            title = metadata.original_title or ""

        if not title:
            return metadata

        try:
            client = self._get_client()
            results = await client.search(title, media_type)
            if not results:
                return metadata

            # 取第一个匹配
            best = results[0]
            douban_id = best.get("douban_id", "")
            if not douban_id:
                return metadata

            detail = await client.get_detail(douban_id)
            if not detail:
                return metadata

            # 补充元数据
            if detail.get("title") and not metadata.title:
                metadata.title = detail["title"]

            if detail.get("overview") and not metadata.overview:
                metadata.overview = detail["overview"]

            if detail.get("cover") and not metadata.poster_url:
                metadata.poster_url = detail["cover"]

            if detail.get("rating"):
                metadata.douban_rating = detail["rating"]

            if detail.get("genres"):
                if not metadata.genres:
                    metadata.genres = detail["genres"]
                elif isinstance(metadata.genres, str):
                    import json
                    try:
                        metadata.genres = json.loads(metadata.genres)
                    except Exception:
                        pass

            # 保存 douban_id
            metadata.douban_id = str(douban_id)

            logger.debug(f"[Douban] Enriched metadata for '{title}': douban_id={douban_id}")

        except Exception as e:
            logger.warning(f"[Douban] Enrichment failed for '{title}': {e}")

        return metadata

    def _to_metadata(self, data: dict) -> MediaMetadata:
        """将豆瓣数据转换为 MediaMetadata"""
        import json

        genres = data.get("genres", [])
        if isinstance(genres, str):
            try:
                genres = json.loads(genres)
            except Exception:
                genres = []

        return MediaMetadata(
            douban_id=str(data.get("douban_id", "")),
            title=data.get("title", ""),
            year=data.get("year"),
            overview=data.get("overview"),
            poster_url=data.get("poster_url") or data.get("cover"),
            douban_rating=data.get("rating"),
            genres=genres if isinstance(genres, list) else [],
        )

    def _get_client(self) -> DoubanClient:
        """获取 Douban 客户端"""
        if self._client is None:
            self._client = get_douban_client()
        return self._client
