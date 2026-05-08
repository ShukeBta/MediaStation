"""
Provider Chain - Provider 调度链实现
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import MediaMetadata, MetadataProvider, ProviderPriority

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class ProviderChain:
    """
    Provider 调度链

    调度策略：
    1. 按优先级排序所有 Provider
    2. 第一个可用且配置好的 Provider 提供主元数据
    3. 其他 Provider 依次补充元数据
    """

    def __init__(self, providers: list[MetadataProvider] | None = None):
        """
        初始化 Provider Chain

        Args:
            providers: Provider 列表，如果为 None 则使用所有注册的 Provider
        """
        self._providers: list[MetadataProvider] = []
        if providers:
            self._providers = sorted(providers, key=lambda p: p.priority)

    def add_provider(self, provider: MetadataProvider) -> None:
        """添加 Provider"""
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)

    def remove_provider(self, provider_name: str) -> bool:
        """移除 Provider"""
        for i, p in enumerate(self._providers):
            if p.name == provider_name:
                del self._providers[i]
                return True
        return False

    @property
    def providers(self) -> list[MetadataProvider]:
        """获取所有 Provider（按优先级排序）"""
        return self._providers.copy()

    async def scrape(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
        media_id: int | None = None,
        prefer_provider: str | None = None,
    ) -> MediaMetadata | None:
        """
        执行 Provider Chain 刮削

        调度策略：
        1. 如果指定了 media_id，优先使用该 Provider 获取元数据
        2. 否则按优先级尝试每个 Provider 的 search + get_metadata
        3. 其他 Provider 依次 enrich_metadata

        Args:
            title: 媒体标题
            media_type: 媒体类型（movie, tv, anime）
            year: 年份
            media_id: 指定的媒体 ID（如果有）
            prefer_provider: 优先使用的 Provider 名称

        Returns:
            合并后的元数据对象
        """
        result = MediaMetadata()

        # 获取已配置且可用的 Provider
        available = [p for p in self._providers if await p.is_configured()]
        if not available:
            logger.warning("No provider is configured")
            return None

        # 如果指定了优先 Provider，尝试使用它
        primary_provider = None
        if prefer_provider:
            primary_provider = next(
                (p for p in available if p.name == prefer_provider),
                None
            )

        # 如果没有指定或找不到，尝试使用最高优先级的 Provider
        if not primary_provider:
            for provider in available:
                if provider.is_primary:
                    primary_provider = provider
                    break

        # 如果仍然没有，使用第一个可用的
        if not primary_provider:
            primary_provider = available[0]

        # 主刮削
        try:
            if media_id:
                # 直接使用 media_id 获取详情
                logger.info(f"[Chain] Using {primary_provider.name} with ID {media_id}")
                metadata = await primary_provider.get_metadata(media_id, media_type)
            else:
                # 搜索 + 获取详情
                logger.info(f"[Chain] Searching with {primary_provider.name}: {title}")
                results = await primary_provider.search(title, media_type, year)

                if results:
                    # 选择最佳匹配
                    best = await self._find_best_match(
                        results, title, year, primary_provider
                    )
                    if best:
                        metadata = await primary_provider.get_metadata(
                            best["id"], media_type
                        )
                    else:
                        logger.warning(
                            f"[Chain] No matching result found for {title}"
                        )
                        metadata = None
                else:
                    logger.warning(
                        f"[Chain] No search results from {primary_provider.name}"
                    )
                    metadata = None

            if metadata:
                result = metadata
            else:
                # 主 Provider 失败，尝试其他 Provider
                logger.info("[Chain] Primary provider failed, trying fallbacks")
                for provider in available:
                    if provider == primary_provider:
                        continue
                    results = await provider.search(title, media_type, year)
                    if results:
                        best = await self._find_best_match(
                            results, title, year, provider
                        )
                        if best:
                            metadata = await provider.get_metadata(
                                best["id"], media_type
                            )
                            if metadata:
                                result = metadata
                                break

        except Exception as e:
            logger.error(f"[Chain] Primary scrape error: {e}")
            # 继续使用其他 Provider

        # 补充刮削：使用剩余 Provider 丰富元数据
        for provider in available:
            if provider == primary_provider:
                continue
            if result and not self._needs_enrichment(result, provider):
                continue

            try:
                logger.debug(f"[Chain] Enriching with {provider.name}")
                result = await provider.enrich_metadata(result, media_type)
            except Exception as e:
                logger.warning(f"[Chain] {provider.name} enrichment failed: {e}")

        return result

    async def _find_best_match(
        self,
        results: list[dict],
        title: str,
        year: int | None,
        provider: MetadataProvider,
    ) -> dict | None:
        """
        选择最佳匹配结果

        策略：
        1. 优先匹配年份
        2. 计算标题相似度
        3. 返回最佳匹配
        """
        if not results:
            return None

        if len(results) == 1:
            return results[0]

        best_match = None
        best_score = 0.0

        for result in results:
            score = 0.0
            result_title = result.get("title", result.get("name", ""))
            result_year = result.get("year") or result.get("release_date", "")

            # 年份匹配（很重要）
            if year and result_year:
                if str(year) in str(result_year):
                    score += 50

            # 标题相似度
            similarity = self._title_similarity(title.lower(), result_title.lower())
            score += similarity * 50

            if score > best_score:
                best_score = score
                best_match = result

        # 如果最佳匹配分数太低，返回 None
        if best_score < 30:
            logger.warning(
                f"[Chain] Best match score {best_score:.1f} too low for {title}"
            )
            return None

        return best_match

    def _title_similarity(self, title1: str, title2: str) -> float:
        """
        计算两个标题的相似度

        使用简单的公共字符比例
        """
        # 移除特殊字符
        import re
        t1 = re.sub(r'[^\w\u4e00-\u9fa5]', '', title1)
        t2 = re.sub(r'[^\w\u4e00-\u9fa5]', '', title2)

        if not t1 or not t2:
            return 0.0

        # 计算公共字符
        set1 = set(t1.lower())
        set2 = set(t2.lower())
        common = set1 & set2

        # Jaccard 相似度
        union = set1 | set2
        return len(common) / len(union) if union else 0.0

    def _needs_enrichment(
        self,
        metadata: MediaMetadata,
        provider: MetadataProvider,
    ) -> bool:
        """
        判断是否需要使用某个 Provider 补充元数据
        """
        # 如果海报为空，Fanart 可能有用
        if not metadata.poster_url and provider.name == "Fanart":
            return True

        # 如果评分低，Bangumi 可能有用（对于动画）
        if metadata.bangumi_rating is None and provider.name == "Bangumi":
            return True

        return False

    def get_provider(self, name: str) -> MetadataProvider | None:
        """获取指定名称的 Provider"""
        for p in self._providers:
            if p.name == name:
                return p
        return None

    async def list_providers(self) -> list[dict]:
        """获取所有 Provider 的状态"""
        result = []
        for p in self._providers:
            configured = await p.is_configured()
            result.append({
                "name": p.name,
                "priority": p.priority,
                "configured": configured,
                "is_primary": p.is_primary,
            })
        return result

    def __repr__(self) -> str:
        providers = [f"{p.name}({p.priority})" for p in self._providers]
        return f"<ProviderChain [{', '.join(providers)}]>"


# 全局 Provider Chain 实例（延迟初始化）
_chain_instance: ProviderChain | None = None


def get_provider_chain() -> ProviderChain:
    """获取全局 Provider Chain 实例"""
    global _chain_instance
    if _chain_instance is None:
        _chain_instance = ProviderChain()
    return _chain_instance


def init_provider_chain(settings: Settings) -> ProviderChain:
    """初始化 Provider Chain（从 settings 加载配置）"""
    from .tmdb import TMDbProvider
    from .douban import DoubanProvider
    from .bangumi import BangumiProvider
    from .adult import AdultProvider, AdultProviderConfig

    global _chain_instance

    chain = ProviderChain()

    # 创建 Adult Provider 配置（从 settings 读取）
    adult_config = AdultProviderConfig(
        enabled=getattr(settings, 'adult_provider_enabled', False),
        adult_dirs=getattr(settings, 'adult_dirs', []),
        javbus_url=getattr(settings, 'javbus_url', 'https://www.javbus.com'),
        javdb_url=getattr(settings, 'javdb_url', 'https://javdb.com'),
        microservice_url=getattr(settings, 'adult_microservice_url', None),
        proxy=getattr(settings, 'adult_proxy', None),
        javdb_cookie=getattr(settings, 'javdb_cookie', None),
    )

    # 注册 Provider（按优先级顺序）
    chain.add_provider(AdultProvider(adult_config))  # 优先级 5
    chain.add_provider(TMDbProvider(settings))        # 优先级 10
    chain.add_provider(DoubanProvider())            # 优先级 20
    chain.add_provider(BangumiProvider())            # 优先级 30
    # AI Provider 已移除（开源版不再包含 AI 功能）

    _chain_instance = chain
    return chain


# 导出
__all__ = [
    "ProviderChain",
    "get_provider_chain",
    "init_provider_chain",
]
