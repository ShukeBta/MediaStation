"""
Provider Chain - 元数据 Provider 模块
"""
from .base import MediaMetadata, MetadataProvider, ProviderPriority
from .chain import ProviderChain, get_provider_chain, init_provider_chain

__all__ = [
    # 基础类
    "MediaMetadata",
    "MetadataProvider",
    "ProviderPriority",
    # Chain
    "ProviderChain",
    "get_provider_chain",
    "init_provider_chain",
    # 导出具体 Provider（方便直接导入）
    "TMDbProvider",
    "DoubanProvider",
    "BangumiProvider",
    "AIProvider",
    "AdultProvider",
]


# 延迟导入避免循环依赖
def __getattr__(name: str):
    if name == "TMDbProvider":
        from . import tmdb
        return tmdb.TMDbProvider
    if name == "DoubanProvider":
        from . import douban
        return douban.DoubanProvider
    if name == "BangumiProvider":
        from . import bangumi
        return bangumi.BangumiProvider
    if name == "AIProvider":
        from . import ai_provider
        return ai_provider.AIProvider
    if name == "AdultProvider":
        from . import adult
        return adult.AdultProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
