"""
API 配置数据模型
存储各数据源的 API Key 和配置
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.base_models import Base, TimestampMixin


class ApiConfig(TimestampMixin, Base):
    """
    API 配置表 - 存储各数据源的 API Key
    
    支持的数据源:
    - tmdb: TMDb API (themoviedb.org)
    - douban: 豆瓣 Cookie
    - bangumi: Bangumi API Token
    - thetvdb: TheTVDB API Key
    - fanart: Fanart.tv API Key
    - openai: OpenAI 兼容 API Key
    """
    __tablename__ = "api_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 数据源标识
    provider: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # API 配置
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)          # API Key / Token
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)   # 自定义 API 地址
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)              # 其他配置 (JSON)
    
    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 备注
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def get_masked_key(self) -> str:
        """返回掩码后的 API Key"""
        if not self.api_key or len(self.api_key) < 8:
            return "****"
        return self.api_key[:4] + "****" + self.api_key[-4:]

    def to_dict(self, include_key: bool = False) -> dict:
        """转换为字典"""
        result = {
            "id": self.id,
            "provider": self.provider,
            "enabled": self.enabled,
            "description": self.description,
            "has_key": bool(self.api_key),
            "masked_key": self.get_masked_key() if self.api_key else None,
            "base_url": self.base_url,
        }
        # 解析 extra JSON
        if self.extra:
            try:
                import json
                result["extra"] = json.loads(self.extra)
            except (json.JSONDecodeError, TypeError):
                result["extra"] = None
        else:
            result["extra"] = None
        if include_key:
            result["api_key"] = self.api_key
        return result


# 预定义的数据源配置
DEFAULT_PROVIDERS = [
    {
        "provider": "tmdb",
        "description": "TMDb API - 电影/剧集主数据源",
        "base_url": "https://api.themoviedb.org/3",
    },
    {
        "provider": "douban",
        "description": "豆瓣 - 中文元数据补充源",
        "base_url": None,
    },
    {
        "provider": "bangumi",
        "description": "Bangumi - 番剧/动画元数据源",
        "base_url": "https://api.bgm.tv/v0",
    },
    {
        "provider": "thetvdb",
        "description": "TheTVDB - 剧集增强数据源",
        "base_url": "https://api4.thetvdb.com/v4",
    },
    {
        "provider": "fanart",
        "description": "Fanart.tv - 高质量图片增强源",
        "base_url": "https://webservice.fanart.tv/v3",
    },
    {
        "provider": "openai",
        "description": "OpenAI 兼容 API - AI 刮削和智能增强",
        "base_url": "https://api.openai.com/v1",
    },
    {
        "provider": "siliconflow",
        "description": "硅基流动 - 国产 AI API 平替",
        "base_url": "https://api.siliconflow.cn/v1",
    },
    {
        "provider": "deepseek",
        "description": "DeepSeek - 国产大模型 API",
        "base_url": "https://api.deepseek.com/v1",
    },
    {
        "provider": "adult",
        "description": "Adult Provider - 18+ 番号刮削（ JavBus/JavDB/Python 微服务）",
        "base_url": None,  # 使用默认配置
    },
]
