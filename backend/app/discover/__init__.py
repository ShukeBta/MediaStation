"""
Discover 模块 - 发现/推荐功能
提供 TMDB、豆瓣等外部数据源的推荐内容
"""
from app.config import get_settings

settings = get_settings()

__all__ = ["settings"]
