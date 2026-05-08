"""
Provider Chain - Bangumi Provider 实现
Bangumi Provider - 优先级 30，动漫元数据来源
API 文档：https://bangumi.github.io/api/
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.media.providers.base import MediaMetadata, MetadataProvider, ProviderPriority

from ..bangumi_scraper import BangumiClient, get_bangumi_client

logger = logging.getLogger(__name__)


class BangumiProvider(MetadataProvider):
    """Bangumi Provider - 动漫元数据来源"""

    # Bangumi 条目类型
    TYPE_ANIME = 2  # 动画

    def __init__(self):
        self._client: BangumiClient | None = None

    @property
    def name(self) -> str:
        return "Bangumi"

    @property
    def priority(self) -> int:
        return ProviderPriority.Bangumi

    @property
    def is_primary(self) -> bool:
        """Bangumi 作为辅助数据源（主要补充动漫信息）"""
        return False

    async def is_configured(self) -> bool:
        """Bangumi 无需强制 Token，基础搜索可用"""
        return True

    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """搜索 Bangumi"""
        client = self._get_client()
        try:
            # 优先搜索动画类型
            type_filter = self.TYPE_ANIME if media_type == "anime" else None
            results = await client.search(title, type_=type_filter)

            parsed = []
            for r in results:
                # 解析图片 URL
                images = r.get("images", {})
                if isinstance(images, dict):
                    poster = images.get("large") or images.get("common") or images.get("small", "")
                else:
                    poster = ""

                # 解析年份
                year_str = r.get("date", "") or ""
                year_match = re.search(r"\d{4}", year_str)
                result_year = int(year_match.group()) if year_match else None

                parsed.append({
                    "id": r.get("id", ""),
                    "title": r.get("name_cn") or r.get("name", ""),
                    "original_title": r.get("name", ""),
                    "year": result_year,
                    "poster_path": poster,
                    "overview": r.get("summary", "")[:200] if r.get("summary") else "",
                })

            return parsed
        except Exception as e:
            logger.warning(f"[Bangumi] Search failed: {e}")
            return []

    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """获取 Bangumi 元数据（作为主数据源时）"""
        client = self._get_client()
        try:
            data = await client.get_detail(int(media_id))
            if not data:
                return None
            return self._to_metadata(data)
        except Exception as e:
            logger.error(f"[Bangumi] Get metadata failed for {media_id}: {e}")
            return None

    async def enrich_metadata(
        self,
        metadata: MediaMetadata,
        media_type: str,
    ) -> MediaMetadata:
        """
        用 Bangumi 数据补充元数据
        主要用于动漫类型，补充中文标题、评分等信息
        """
        title = metadata.title
        if not title:
            title = metadata.original_title or ""

        if not title:
            return metadata

        try:
            client = self._get_client()

            # 优先搜索动画
            type_filter = self.TYPE_ANIME if media_type == "anime" else None
            results = await client.search(title, type_=type_filter)

            if not results:
                # 尝试无类型过滤
                results = await client.search(title)

            if not results:
                return metadata

            # 取第一个匹配
            best = results[0]
            subject_id = best.get("id")
            if not subject_id:
                return metadata

            detail = await client.get_detail(subject_id)
            if not detail:
                return metadata

            # 补充元数据
            # 标题：中文名优先
            name_cn = detail.get("name_cn", "")
            name = detail.get("name", "")

            if name_cn and not metadata.title:
                metadata.title = name_cn
                metadata.original_title = name
            elif name and not metadata.title:
                metadata.title = name
                if name_cn:
                    metadata.original_title = name_cn

            # 简介
            if detail.get("summary") and not metadata.overview:
                # Bangumi summary 可能很长，截取前1000字符
                summary = detail["summary"]
                if len(summary) > 1000:
                    summary = summary[:1000] + "..."
                metadata.overview = summary

            # 海报
            images = detail.get("images", {})
            if isinstance(images, dict):
                poster = images.get("large") or images.get("common")
                if poster and not metadata.poster_url:
                    metadata.poster_url = poster

            # 评分
            rating = detail.get("rating", {})
            if isinstance(rating, dict) and rating.get("score"):
                metadata.bangumi_rating = float(rating["score"])

            # 标签
            tags = detail.get("tags", [])
            if tags and not metadata.genres:
                tag_names = []
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("name"):
                        tag_names.append(tag["name"])
                    elif isinstance(tag, str):
                        tag_names.append(tag)
                if tag_names:
                    metadata.genres = tag_names[:8]

            # 年份
            date_str = detail.get("date", "")
            if date_str:
                year_match = re.search(r"\d{4}", str(date_str))
                if year_match and not metadata.year:
                    metadata.year = int(year_match.group())

            # 保存 bangumi_id
            metadata.bangumi_id = subject_id

            logger.debug(f"[Bangumi] Enriched metadata for '{title}': bangumi_id={subject_id}")

        except Exception as e:
            logger.warning(f"[Bangumi] Enrichment failed for '{title}': {e}")

        return metadata

    def _to_metadata(self, data: dict) -> MediaMetadata:
        """将 Bangumi 数据转换为 MediaMetadata"""
        # 标题
        title = data.get("name_cn") or data.get("name", "")
        original_title = data.get("name", "") if data.get("name_cn") else None

        # 标签
        tags = data.get("tags", [])
        genres = []
        for tag in tags:
            if isinstance(tag, dict) and tag.get("name"):
                genres.append(tag["name"])
            elif isinstance(tag, str):
                genres.append(tag)

        # 评分
        rating = data.get("rating", {})
        if isinstance(rating, dict):
            rating_value = rating.get("score")
        else:
            rating_value = rating

        # 海报
        images = data.get("images", {})
        if isinstance(images, dict):
            poster_url = images.get("large") or images.get("common")
        else:
            poster_url = None

        # 年份
        date_str = data.get("date", "")
        year = None
        year_match = re.search(r"\d{4}", str(date_str))
        if year_match:
            year = int(year_match.group())

        # 简介
        summary = data.get("summary", "")
        if len(summary) > 1000:
            summary = summary[:1000] + "..."

        return MediaMetadata(
            bangumi_id=data.get("id"),
            title=title,
            original_title=original_title,
            year=year,
            overview=summary,
            poster_url=poster_url,
            bangumi_rating=float(rating_value) if rating_value else None,
            genres=genres[:8],
        )

    def _get_client(self) -> BangumiClient:
        """获取 Bangumi 客户端"""
        if self._client is None:
            self._client = get_bangumi_client()
        return self._client
