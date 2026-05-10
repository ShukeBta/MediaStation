"""
TMDb 元数据刮削
使用 TMDb v3 API 搜索和获取影视元数据。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class TMDbClient:
    """TMDb API 客户端"""

    def __init__(
        self,
        custom_api_key: str | None = None,
        custom_base_url: str | None = None,
        custom_image_base: str | None = None,
        custom_language: str | None = None,
    ):
        """
        初始化 TMDb 客户端

        Args:
            custom_api_key: 自定义 API Key（优先级高于环境变量）
            custom_base_url: 自定义 Base URL
            custom_image_base: 自定义图片基础 URL
            custom_language: 自定义语言
        """
        self.settings = get_settings()

        # 优先使用传入的自定义值，否则使用配置
        self.api_key = custom_api_key or self.settings.tmdb_api_key
        self.base_url = custom_base_url or self.settings.tmdb_base_url
        self.image_base = custom_image_base or self.settings.tmdb_image_base
        self.language = custom_language or self.settings.tmdb_language
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                params={"api_key": self.api_key, "language": self.language},
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _poster_url(self, path: str | None, size: str = "w500") -> str | None:
        if not path:
            return None
        return f"{self.image_base}/{size}{path}"

    # ── 搜索 ──
    async def search_movie(self, query: str, year: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"query": query}
        if year:
            params["year"] = year
        try:
            resp = await self.client.get("/search/movie", params=params)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                logger.error(f"[TMDb] Server error (500) when searching movies: {e}")
                raise httpx.HTTPStatusError(
                    "TMDb 服务器错误，请稍后重试",
                    request=e.request,
                    response=e.response,
                )
            raise

    async def search_tv(self, query: str, year: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"query": query}
        if year:
            params["first_air_date_year"] = year
        try:
            resp = await self.client.get("/search/tv", params=params)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                logger.error(f"[TMDb] Server error (500) when searching TV shows: {e}")
                raise httpx.HTTPStatusError(
                    "TMDb 服务器错误，请稍后重试",
                    request=e.request,
                    response=e.response,
                )
            raise

    async def search(self, query: str, media_type: str, year: int | None = None) -> list[dict]:
        if media_type == "movie":
            return await self.search_movie(query, year)
        else:
            return await self.search_tv(query, year)

    # ── 获取英文标题（用于站点搜索） ──
    async def get_english_title(self, tmdb_id: int, media_type: str) -> str | None:
        """
        获取 TMDB 影视的英文标题，用于站点搜索。
        Issue #31 修复：复用现有 self.client 连接池，通过覆盖单次请求的 params
        传入 language=en，避免每次调用都创建新 httpx.AsyncClient 导致的
        100 次 TCP+TLS 握手开销。
        """
        try:
            endpoint = f"/movie/{tmdb_id}" if media_type == "movie" else f"/tv/{tmdb_id}"
            # 合并 params：覆盖 language 为 en，其余参数（api_key 等）由 self.client 默认提供
            params = {"api_key": self.api_key, "language": "en"}
            resp = await self.client.get(endpoint, params=params)
            resp.raise_for_status()
            data = resp.json()
            # 对于电影，使用 original_title；对于剧集，使用 original_name
            english_title = data.get("original_title") or data.get("original_name")
            logger.debug(f"[TMDb] 获取英文标题 TMDB {tmdb_id}: {english_title}")
            return english_title
        except Exception as e:
            logger.warning(f"[TMDb] 获取英文标题失败 {tmdb_id}: {e}")
            return None

    # ── 详情 ──
    async def get_movie_detail(self, tmdb_id: int) -> dict:
        try:
            resp = await self.client.get(f"/movie/{tmdb_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                logger.error(f"[TMDb] Server error (500) when getting movie {tmdb_id}: {e}")
                raise httpx.HTTPStatusError(
                    "TMDb 服务器错误，请稍后重试",
                    request=e.request,
                    response=e.response,
                )
            raise

    async def get_tv_detail(self, tmdb_id: int) -> dict:
        try:
            resp = await self.client.get(f"/tv/{tmdb_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                logger.error(f"[TMDb] Server error (500) when getting TV show {tmdb_id}: {e}")
                raise httpx.HTTPStatusError(
                    "TMDb 服务器错误，请稍后重试",
                    request=e.request,
                    response=e.response,
                )
            raise

    async def get_tv_season_detail(self, tmdb_id: int, season_number: int) -> dict:
        try:
            resp = await self.client.get(f"/tv/{tmdb_id}/season/{season_number}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                logger.error(f"[TMDb] Server error (500) when getting season {season_number} of TV {tmdb_id}: {e}")
                raise httpx.HTTPStatusError(
                    "TMDb 服务器错误，请稍后重试",
                    request=e.request,
                    response=e.response,
                )
            raise

    async def get_detail(self, tmdb_id: int, media_type: str) -> dict:
        if media_type == "movie":
            return await self.get_movie_detail(tmdb_id)
        else:
            return await self.get_tv_detail(tmdb_id)

    # ── 转换为标准格式 ──
    def to_media_metadata(self, data: dict, media_type: str) -> dict:
        """将 TMDb 数据转换为标准元数据格式"""
        genres = [g["name"] for g in data.get("genres", [])]

        result = {
            "tmdb_id": data.get("id"),
            "title": data.get("title") or data.get("name", ""),
            "original_title": data.get("original_title") or data.get("original_name", ""),
            "year": None,
            "overview": data.get("overview", ""),
            "poster_url": self._poster_url(data.get("poster_path"), "w500"),
            "backdrop_url": self._poster_url(data.get("backdrop_path"), "original"),
            "media_type": media_type,
            "rating": data.get("vote_average", 0),
            "genres": json.dumps(genres, ensure_ascii=False),
        }

        # 年份
        if media_type == "movie":
            date_str = data.get("release_date", "")
        else:
            date_str = data.get("first_air_date", "")
        if date_str:
            result["year"] = int(date_str[:4])

        # 时长（仅电影）
        if media_type == "movie" and data.get("runtime"):
            result["duration"] = data["runtime"] * 60  # 转为秒

        return result


# 全局客户端实例
_tmdb_client: TMDbClient | None = None


def get_tmdb_client() -> TMDbClient:
    global _tmdb_client
    if _tmdb_client is None:
        _tmdb_client = TMDbClient()
    return _tmdb_client
