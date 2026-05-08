"""
Provider Chain - AI Provider 实现
AI Provider - 优先级 100，作为最后的兜底数据源
支持 OpenAI 兼容 API（包括 Ollama、vLLM 等本地模型）
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.media.providers.base import MediaMetadata, MetadataProvider, ProviderPriority

from ..ai_scraper import AIScraper, get_ai_scraper, AI_SCRAPE_OVERVIEW, AI_SCRAPE_TAGS

logger = logging.getLogger(__name__)


class AIProvider(MetadataProvider):
    """AI Provider - 使用 LLM 作为兜底数据源"""

    def __init__(self):
        self._scraper: AIScraper | None = None

    @property
    def name(self) -> str:
        return "AI"

    @property
    def priority(self) -> int:
        return ProviderPriority.AI

    @property
    def is_primary(self) -> bool:
        """AI 作为兜底数据源（不是主数据源）"""
        return False

    async def is_configured(self) -> bool:
        """检查 AI Provider 是否已配置"""
        scraper = self._get_scraper()
        # AI Provider 只要有 scraper 实例就算配置
        return scraper is not None

    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        AI Provider 不提供搜索功能
        AI 用于补充元数据，而不是搜索
        """
        return []

    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """
        AI Provider 不提供直接获取元数据的功能
        使用 enrich_metadata 方法补充元数据
        """
        return None

    async def enrich_metadata(
        self,
        metadata: MediaMetadata,
        media_type: str,
    ) -> MediaMetadata:
        """
        使用 AI 补充/优化元数据

        主要功能：
        1. 生成/优化剧情简介
        2. 翻译/优化中文标题
        3. 生成标签/关键词
        4. 验证刮削结果是否合理

        注意：AI Provider 作为兜底，不覆盖已有数据
        """
        scraper = self._get_scraper()
        if not scraper:
            logger.debug("[AI] Scraper not available, skipping")
            return metadata

        title = metadata.title or metadata.original_title or ""
        if not title:
            return metadata

        try:
            # 准备当前元数据
            current_metadata = self._to_dict(metadata)

            # 调用 AI 刮削
            result = await scraper.scrape(
                title=title,
                media_type=media_type,
                operations=[AI_SCRAPE_OVERVIEW, AI_SCRAPE_TAGS],
                current_metadata=current_metadata,
            )

            if not result.success:
                logger.warning(f"[AI] Enrichment failed: {result.error}")
                return metadata

            # 补充元数据（不覆盖已有数据）
            # 简介
            if result.overview and not metadata.overview:
                metadata.overview = result.overview
                logger.debug(f"[AI] Added overview for '{title}'")

            # 标签
            if result.tags and not metadata.genres:
                metadata.genres = result.tags
                logger.debug(f"[AI] Added tags for '{title}': {result.tags}")

            # 置信度信息可以存储在 extra 中
            if result.confidence:
                metadata.extra["ai_confidence"] = result.confidence
                metadata.extra["ai_model"] = result.model_used

            logger.info(
                f"[AI] Enriched metadata for '{title}': "
                f"overview={bool(result.overview)}, tags={len(result.tags)}, "
                f"confidence={result.confidence:.2f}, tokens={result.tokens_used}"
            )

        except Exception as e:
            logger.error(f"[AI] Enrichment error for '{title}': {e}")

        return metadata

    async def validate_metadata(
        self,
        metadata: MediaMetadata,
        media_type: str,
    ) -> tuple[bool, float]:
        """
        使用 AI 验证刮削结果是否正确

        Args:
            metadata: 待验证的元数据
            media_type: 媒体类型

        Returns:
            (is_valid, confidence): 是否有效及置信度
        """
        scraper = self._get_scraper()
        if not scraper:
            return True, 1.0

        title = metadata.title or metadata.original_title or ""
        if not title:
            return True, 1.0

        try:
            current_metadata = self._to_dict(metadata)
            result = await scraper.scrape(
                title=title,
                media_type=media_type,
                operations=["validate"],
                current_metadata=current_metadata,
            )

            if result.success and result.is_valid is not None:
                confidence = result.confidence or 0.8
                logger.info(
                    f"[AI] Validation for '{title}': "
                    f"valid={result.is_valid}, confidence={confidence:.2f}"
                )
                return result.is_valid, confidence

        except Exception as e:
            logger.error(f"[AI] Validation error for '{title}': {e}")

        return True, 1.0  # 默认返回有效

    def _to_dict(self, metadata: MediaMetadata) -> dict[str, Any]:
        """将 MediaMetadata 转换为字典"""
        return {
            "title": metadata.title,
            "original_title": metadata.original_title,
            "year": metadata.year,
            "overview": metadata.overview,
            "rating": metadata.rating,
            "genres": metadata.genres if isinstance(metadata.genres, list) else [],
            "poster_url": metadata.poster_url,
            "tmdb_id": metadata.tmdb_id,
            "douban_id": metadata.douban_id,
            "bangumi_id": metadata.bangumi_id,
        }

    def _get_scraper(self) -> AIScraper | None:
        """获取 AI Scraper 实例"""
        if self._scraper is None:
            try:
                self._scraper = get_ai_scraper()
            except Exception as e:
                logger.warning(f"[AI] Failed to get scraper: {e}")
                return None
        return self._scraper
