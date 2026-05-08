"""
API 配置服务
管理各数据源的 API Key 和配置
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from .api_config_models import ApiConfig, DEFAULT_PROVIDERS

logger = logging.getLogger(__name__)


class ApiConfigService:
    """API 配置服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_configs(self) -> list[dict]:
        """获取所有 API 配置"""
        result = await self.db.execute(select(ApiConfig).order_by(ApiConfig.provider))
        configs = result.scalars().all()
        
        # 如果没有配置，初始化默认值
        if not configs:
            await self._init_default_configs()
            result = await self.db.execute(select(ApiConfig).order_by(ApiConfig.provider))
            configs = result.scalars().all()
        
        return [c.to_dict() for c in configs]

    async def get_config(self, provider: str) -> dict | None:
        """获取指定 provider 的配置"""
        result = await self.db.execute(
            select(ApiConfig).where(ApiConfig.provider == provider)
        )
        config = result.scalar_one_or_none()
        return config.to_dict() if config else None

    async def get_config_full(self, provider: str) -> ApiConfig | None:
        """获取指定 provider 的完整配置（含 API Key）"""
        result = await self.db.execute(
            select(ApiConfig).where(ApiConfig.provider == provider)
        )
        return result.scalar_one_or_none()

    async def update_config(
        self,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
        enabled: bool | None = None,
        extra: dict | None = None,
    ) -> dict:
        """
        更新 API 配置
        
        Args:
            provider: 数据源标识
            api_key: API Key（None 表示不更新）
            base_url: 自定义 API 地址
            enabled: 是否启用
            extra: 其他配置
            
        Returns:
            更新后的配置
        """
        config = await self.get_config_full(provider)
        if not config:
            # 创建新配置
            config = ApiConfig(provider=provider)
            self.db.add(config)
        
        if api_key is not None:
            config.api_key = api_key if api_key.strip() else None
        if base_url is not None:
            config.base_url = base_url if base_url.strip() else None
        if enabled is not None:
            config.enabled = enabled
        if extra is not None:
            config.extra = json.dumps(extra, ensure_ascii=False)
        
        await self.db.flush()
        await self.db.refresh(config)
        
        logger.info(f"[ApiConfig] Updated config for {provider}")
        return config.to_dict()

    async def delete_config(self, provider: str) -> bool:
        """删除 API 配置（清除 API Key）"""
        config = await self.get_config_full(provider)
        if not config:
            return False
        
        config.api_key = None
        await self.db.flush()
        
        logger.info(f"[ApiConfig] Cleared API key for {provider}")
        return True

    async def get_effective_config(self, provider: str) -> dict:
        """
        获取生效的配置（合并数据库配置和环境变量）
        
        数据库配置优先于环境变量。
        """
        db_config = await self.get_config_full(provider)
        
        # 从环境变量获取默认值
        env_defaults = {
            "tmdb": {"api_key": "TMDB_API_KEY", "base_url": None},
            "douban": {"api_key": "DOUBAN_COOKIE", "base_url": None},
            "bangumi": {"api_key": "BANGUMI_TOKEN", "base_url": None},
            "thetvdb": {"api_key": "TVDB_API_KEY", "base_url": None},
            "fanart": {"api_key": "FANART_API_KEY", "base_url": None},
            "openai": {"api_key": "OPENAI_API_KEY", "base_url": "OPENAI_BASE_URL"},
            "siliconflow": {"api_key": "SILICONFLOW_API_KEY", "base_url": None},
            "deepseek": {"api_key": "DEEPSEEK_API_KEY", "base_url": None},
            "adult": {"api_key": None, "base_url": None},  # Adult Provider 无需 API Key
        }
        
        env_key = env_defaults.get(provider, {}).get("api_key")
        env_url_key = env_defaults.get(provider, {}).get("base_url")
        
        result = {
            "provider": provider,
            "api_key": None,
            "base_url": None,
            "enabled": True,
            "source": "none",  # none / db / env
            "extra": {},  # 额外配置（如 adult_dirs, javdb_cookie 等）
        }
        
        # 优先使用数据库配置
        if db_config and db_config.api_key:
            result["api_key"] = db_config.api_key
            result["base_url"] = db_config.base_url
            result["enabled"] = db_config.enabled
            result["source"] = "db"
        # 对于 adult provider，即使没有 api_key 也使用数据库配置
        elif db_config and provider == "adult":
            result["base_url"] = db_config.base_url
            result["enabled"] = db_config.enabled
            result["source"] = "db"
        # 其次使用环境变量
        elif env_key:
            import os
            env_val = os.environ.get(env_key, "")
            if env_val:
                result["api_key"] = env_val
                result["source"] = "env"
                if env_url_key:
                    result["base_url"] = os.environ.get(env_url_key) or result.get("base_url")
        
        # 解析 extra 字段
        if db_config and db_config.extra:
            try:
                result["extra"] = json.loads(db_config.extra)
            except json.JSONDecodeError:
                result["extra"] = {}
        
        return result

    async def _init_default_configs(self) -> None:
        """初始化默认配置"""
        for provider_info in DEFAULT_PROVIDERS:
            config = ApiConfig(
                provider=provider_info["provider"],
                description=provider_info["description"],
                base_url=provider_info["base_url"],
                enabled=True,
            )
            self.db.add(config)
        
        await self.db.flush()
        logger.info("[ApiConfig] Initialized default configurations")

    async def test_connection(self, provider: str) -> dict:
        """
        测试 API 连接
        
        Returns:
            {"success": bool, "message": str, "details": dict}
        """
        config = await self.get_effective_config(provider)
        
        if not config["api_key"]:
            return {
                "success": False,
                "message": f"{provider} 未配置 API Key",
                "details": {"has_key": False},
            }
        
        # 根据不同 provider 测试连接
        if provider == "tmdb":
            return await self._test_tmdb(config)
        elif provider == "douban":
            return await self._test_douban(config)
        elif provider == "bangumi":
            return await self._test_bangumi(config)
        elif provider == "thetvdb":
            return await self._test_tvdb(config)
        elif provider == "fanart":
            return await self._test_fanart(config)
        elif provider in ("openai", "siliconflow", "deepseek"):
            return await self._test_openai(config)
        elif provider == "adult":
            return await self._test_adult(config)
        else:
            return {"success": False, "message": f"不支持的 provider: {provider}"}

    async def _test_tmdb(self, config: dict) -> dict:
        """测试 TMDb API"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config.get('base_url', 'https://api.themoviedb.org/3')}/configuration",
                    params={"api_key": config["api_key"]},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "message": "TMDb API 连接成功",
                        "details": {"images": data.get("images", {})},
                    }
                else:
                    return {
                        "success": False,
                        "message": f"TMDb API 错误: {resp.status_code}",
                        "details": {"status": resp.status_code},
                    }
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def _test_douban(self, config: dict) -> dict:
        """测试豆瓣 Cookie"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.douban.com/v2/movie/top250",
                    cookies={"cookie": config["api_key"]},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "豆瓣 Cookie 有效"}
                else:
                    return {"success": False, "message": f"豆瓣 Cookie 无效: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def _test_bangumi(self, config: dict) -> dict:
        """测试 Bangumi API"""
        try:
            import httpx
            headers = {"Authorization": f"Bearer {config['api_key']}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.bgm.tv/v0/me",
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "message": f"Bangumi API 有效 (用户: {data.get('username', 'unknown')})",
                        "details": data,
                    }
                else:
                    return {"success": False, "message": f"Bangumi API 错误: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def _test_tvdb(self, config: dict) -> dict:
        """测试 TheTVDB API"""
        try:
            import httpx
            headers = {"Authorization": f"Bearer {config['api_key']}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api4.thetvdb.com/v4/login",
                    headers=headers,
                    json={"apikey": config["api_key"]},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "message": "TheTVDB API 有效",
                        "details": {"token": data.get("token", "")[:20] + "..."},
                    }
                else:
                    return {"success": False, "message": f"TheTVDB API 错误: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def _test_fanart(self, config: dict) -> dict:
        """测试 Fanart.tv API"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://webservice.fanart.tv/v3/movies/862",
                    params={"api_key": config["api_key"]},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "Fanart.tv API 有效"}
                elif resp.status_code == 404:
                    return {"success": True, "message": "Fanart.tv API 有效 (无匹配图片)"}
                else:
                    return {"success": False, "message": f"Fanart.tv API 错误: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def _test_openai(self, config: dict) -> dict:
        """测试 OpenAI 兼容 API"""
        try:
            import httpx
            base_url = config.get("base_url", "https://api.openai.com/v1")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 5,
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    return {"success": True, "message": f"{config['provider']} API 连接成功"}
                else:
                    data = resp.json()
                    return {
                        "success": False,
                        "message": f"API 错误: {data.get('error', {}).get('message', resp.status_code)}",
                    }
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def _test_adult(self, config: dict) -> dict:
        """测试 Adult Provider 配置（测试 JavBus 连接）"""
        try:
            import httpx
            import os
            # 使用配置的 base_url 或默认值
            base_url = config.get("base_url") or "https://www.javbus.com"
            # 获取代理配置：优先使用自定义代理，否则使用系统环境变量代理
            extra = config.get("extra", {})
            proxy = extra.get("proxy") if extra else None
            # httpx 默认 trust_env=True，会自动使用环境变量 HTTP_PROXY/HTTPS_PROXY
            async with httpx.AsyncClient(proxy=proxy) as client:
                resp = await client.get(
                    f"{base_url}/",
                    timeout=10,
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    proxy_info = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "系统代理"
                    return {
                        "success": True,
                        "message": f"JavBus 连接成功 via {proxy_info}",
                        "details": {"status": resp.status_code},
                    }
                else:
                    return {
                        "success": False,
                        "message": f"JavBus 连接失败: HTTP {resp.status_code}",
                    }
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}
