"""
Provider Chain - TMDb Provider 实现
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings, get_settings
from app.media.providers.base import MediaMetadata, MetadataProvider, ProviderPriority
from app.common.utils import safe_json

logger = logging.getLogger(__name__)


class TMDbProvider(MetadataProvider):
    """TMDb Provider - 主数据源"""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._client: TMDbClient | None = None

    @property
    def name(self) -> str:
        return "TMDb"

    @property
    def priority(self) -> int:
        return ProviderPriority.TMDb

    async def is_configured(self) -> bool:
        """检查 TMDb API Key 是否配置"""
        return bool(self._settings.tmdb_api_key)

    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """搜索 TMDb"""
        client = self._get_client()
        try:
            results = await client.search(title, media_type, year)
            # 转换为统一格式
            return [
                {
                    "id": r.get("id"),
                    "title": r.get("title") or r.get("name", ""),
                    "year": self._extract_year(r),
                    "poster_path": r.get("poster_path"),
                    "overview": r.get("overview", ""),
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"[TMDb] Search failed: {e}")
            return []

    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """获取 TMDb 元数据"""
        client = self._get_client()
        try:
            data = await client.get_detail(int(media_id), media_type)
            return self._to_metadata(data, media_type)
        except Exception as e:
            logger.error(f"[TMDb] Get metadata failed for {media_id}: {e}")
            return None

    async def enrich_metadata(
        self,
        metadata: MediaMetadata,
        media_type: str,
    ) -> MediaMetadata:
        """
        TMDb 作为主数据源，enrich_metadata 只在主刮削失败时使用
        如果 metadata 已有内容，直接返回
        """
        # 如果 metadata 已有标题，说明主数据源已经有内容了
        if metadata.title:
            return metadata

        # 否则尝试补充
        if metadata.tmdb_id:
            data = await self.get_metadata(metadata.tmdb_id, media_type)
            if data:
                return data

        return metadata

    def _to_metadata(self, data: dict, media_type: str) -> MediaMetadata:
        """将 TMDb 数据转换为 MediaMetadata"""
        genres = [g["name"] for g in data.get("genres", [])]

        # 提取年份
        year = None
        if media_type == "movie":
            date_str = data.get("release_date", "")
        else:
            date_str = data.get("first_air_date", "")
        if date_str:
            try:
                year = int(date_str[:4])
            except (ValueError, TypeError):
                pass

        # 提取时长（仅电影）
        duration = None
        if media_type == "movie" and data.get("runtime"):
            duration = data["runtime"] * 60  # 转为秒

        # 提取电影合集信息
        collection_id = None
        collection_name = None
        collection_poster_url = None
        collection_backdrop_url = None
        belongs_to_collection = data.get("belongs_to_collection")
        if belongs_to_collection and media_type == "movie":
            collection_id = belongs_to_collection.get("id")
            collection_name = belongs_to_collection.get("name")
            poster_path = belongs_to_collection.get("poster_path")
            backdrop_path = belongs_to_collection.get("backdrop_path")
            if poster_path:
                collection_poster_url = self._poster_url(poster_path, "w500")
            if backdrop_path:
                collection_backdrop_url = self._poster_url(backdrop_path, "original")

        return MediaMetadata(
            tmdb_id=data.get("id"),
            title=data.get("title") or data.get("name", ""),
            original_title=data.get("original_title") or data.get("original_name", ""),
            year=year,
            overview=data.get("overview", ""),
            poster_url=self._poster_url(data.get("poster_path"), "w500"),
            backdrop_url=self._poster_url(data.get("backdrop_path"), "original"),
            rating=data.get("vote_average", 0.0),
            genres=genres,
            duration=duration,
            collection_id=collection_id,
            collection_name=collection_name,
            collection_poster_url=collection_poster_url,
            collection_backdrop_url=collection_backdrop_url,
            extra={
                "genres_json": json.dumps(genres, ensure_ascii=False),
                "vote_count": data.get("vote_count", 0),
                "adult": data.get("adult", False),
            },
        )

    def _poster_url(self, path: str | None, size: str = "w500") -> str | None:
        """生成海报 URL"""
        if not path:
            return None
        return f"{self._settings.tmdb_image_base}/{size}{path}"

    def _extract_year(self, result: dict) -> int | None:
        """从搜索结果提取年份"""
        if self._settings.tmdb_language == "zh-CN":
            date_str = result.get("release_date") or result.get("first_air_date", "")
        else:
            date_str = result.get("release_date") or result.get("first_air_date", "")
        if date_str:
            try:
                return int(date_str[:4])
            except (ValueError, TypeError):
                pass
        return None

    async def get_collection(self, collection_id: int) -> dict | None:
        """
        获取电影合集详情

        Returns:
            合集信息，包含:
            - id: 合集 ID
            - name: 合集名称
            - overview: 合集简介
            - poster_path: 海报路径
            - backdrop_path: 背景图路径
            - parts: 合集中的电影列表
        """
        client = self._get_client()
        try:
            data = await client.get_collection(collection_id)
            # 转换海报 URL
            if data.get("poster_path"):
                data["poster_url"] = self._poster_url(data["poster_path"], "w500")
            if data.get("backdrop_path"):
                data["backdrop_url"] = self._poster_url(data["backdrop_path"], "original")

            # 处理合集中的电影列表
            for part in data.get("parts", []):
                if part.get("poster_path"):
                    part["poster_url"] = self._poster_url(part["poster_path"], "w342")
                if part.get("release_date"):
                    try:
                        part["year"] = int(part["release_date"][:4])
                    except (ValueError, TypeError):
                        pass

            return data
        except Exception as e:
            logger.error(f"[TMDb] Get collection failed for {collection_id}: {e}")
            return None

    def _get_client(self) -> TMDbClient:
        """获取 TMDb 客户端"""
        if self._client is None:
            self._client = TMDbClient()
        return self._client


# 内部导入（避免循环依赖）
class TMDbClient:
    """TMDb API 客户端 - 简化版"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.tmdb_base_url
        self.api_key = self.settings.tmdb_api_key
        self.language = self.settings.tmdb_language
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

    async def search(
        self, query: str, media_type: str, year: int | None = None
    ) -> list[dict]:
        import httpx

        params: dict[str, Any] = {"query": query}
        if year:
            params["year"] = year

        endpoint = "/search/movie" if media_type == "movie" else "/search/tv"
        resp = await self.client.get(endpoint, params=params)
        resp.raise_for_status()
        data = safe_json(resp, url_hint=f"tmdb_search:{media_type}")
        return data.get("results", []) if data else []

    async def get_detail(self, tmdb_id: int, media_type: str) -> dict:
        endpoint = f"/movie/{tmdb_id}" if media_type == "movie" else f"/tv/{tmdb_id}"
        resp = await self.client.get(endpoint)
        resp.raise_for_status()
        return safe_json(resp, url_hint=f"tmdb_detail:{tmdb_id}") or {}

    async def get_collection(self, collection_id: int) -> dict:
        """获取电影合集详情（包含所有电影列表）"""
        resp = await self.client.get(f"/collection/{collection_id}")
        resp.raise_for_status()
        return safe_json(resp, url_hint=f"tmdb_collection:{collection_id}") or {}


# 需要 httpx
import httpx
