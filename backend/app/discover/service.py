"""
Discover 服务层 - 发现/推荐功能
支持 TMDB、豆瓣等外部数据源，以及本地数据库
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.media.models import MediaItem


class SectionOption(BaseModel):
    """发现区块配置"""
    key: str
    label: str
    icon: str
    source: str
    enabled: bool


class DiscoverService:
    """发现服务"""

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self.settings = get_settings()

    # ── 区块配置 ──

    def get_sections(self) -> list[dict]:
        """返回所有可用的发现区块"""
        options = [
            # TMDB 数据源
            SectionOption(
                key="tmdb_trending",
                label="TMDB 热门",
                icon="🔥",
                source="tmdb",
                enabled=bool(self.settings.tmdb_api_key),
            ),
            SectionOption(
                key="tmdb_popular_movies",
                label="TMDB 热门电影",
                icon="🎬",
                source="tmdb",
                enabled=bool(self.settings.tmdb_api_key),
            ),
            SectionOption(
                key="tmdb_now_playing",
                label="TMDB 院线热映",
                icon="🎫",
                source="tmdb",
                enabled=bool(self.settings.tmdb_api_key),
            ),
            # 豆瓣数据源
            SectionOption(
                key="douban_hot_movies",
                label="豆瓣热门电影",
                icon="🎬",
                source="douban",
                enabled=bool(self.settings.douban_cookie),
            ),
            SectionOption(
                key="douban_top250",
                label="豆瓣 Top250",
                icon="🏆",
                source="douban",
                enabled=bool(self.settings.douban_cookie),
            ),
            # 本地数据源
            SectionOption(
                key="recent_movies",
                label="最近添加电影",
                icon="🆕",
                source="local",
                enabled=True,
            ),
            SectionOption(
                key="recent_tv",
                label="最近添加剧集",
                icon="📺",
                source="local",
                enabled=True,
            ),
            SectionOption(
                key="top_rated",
                label="评分最高",
                icon="⭐",
                source="local",
                enabled=True,
            ),
            SectionOption(
                key="anime",
                label="动漫推荐",
                icon="🌸",
                source="local",
                enabled=True,
            ),
        ]

        return [o.model_dump() for o in options]

    # ── 获取推荐数据 ──

    async def get_feed(self, section_keys: list[str]) -> dict[str, Any]:
        """获取多个区块的推荐数据"""
        result = {}

        for key in section_keys:
            try:
                if key.startswith("tmdb_"):
                    result[key] = await self._fetch_tmdb(key)
                elif key.startswith("douban_"):
                    result[key] = await self._fetch_douban(key)
                elif key.startswith("recent_"):
                    result[key] = await self._fetch_local_recent(key)
                elif key == "top_rated":
                    result[key] = await self._fetch_local_top_rated()
                elif key == "anime":
                    result[key] = await self._fetch_local_anime()
                else:
                    result[key] = {"items": []}
            except Exception as e:
                # 外部 API 失败，降级到本地数据
                print(f"[Discover] {key} failed: {e}, falling back to local data")
                result[key] = await self._fallback_local(key)

        return result

    # ── TMDB 数据源 ──

    async def _fetch_tmdb(self, key: str) -> dict:
        """从 TMDB API 获取数据"""
        if not self.settings.tmdb_api_key:
            return await self._fallback_local(key)

        # 确定 API 路径
        if key == "tmdb_trending":
            api_path = "/trending/all/week"
        elif key == "tmdb_popular_movies":
            api_path = "/movie/popular"
        elif key == "tmdb_now_playing":
            api_path = "/movie/now_playing"
        else:
            return {"items": []}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.settings.tmdb_base_url}{api_path}",
                    params={"api_key": self.settings.tmdb_api_key, "language": self.settings.tmdb_language},
                )
                resp.raise_for_status()
                data = resp.json()

            items = data.get("results", [])
            return {
                "items": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title") or item.get("name", ""),
                        "poster_path": item.get("poster_path"),
                        "backdrop_path": item.get("backdrop_path"),
                        "rating": item.get("vote_average", 0),
                        "year": (item.get("release_date") or item.get("first_air_date") or "")[:4] or None,
                        "media_type": item.get("media_type") or ("movie" if "movie" in key else "tv"),
                        "overview": item.get("overview", ""),
                        "external": True,
                        "source": "tmdb",
                    }
                    for item in items[:20]
                ]
            }
        except Exception as e:
            print(f"[Discover] TMDB API failed: {e}")
            return await self._fallback_local(key)

    # ── 豆瓣数据源 ──

    async def _fetch_douban(self, key: str) -> dict:
        """从豆瓣获取数据（简单爬取）"""
        if not self.settings.douban_cookie:
            return await self._fallback_local(key)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Cookie": self.settings.douban_cookie,
                }

                if key == "douban_hot_movies":
                    url = "https://movie.douban.com/j/new_search_subjects?sort=U&range=0,10&tags=电影&start=0"
                elif key == "douban_top250":
                    url = "https://movie.douban.com/j/new_search_subjects?sort=R&range=0,10&tags=电影&start=0"
                else:
                    return {"items": []}

                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            items = data.get("data", [])
            return {
                "items": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title", ""),
                        "poster_url": item.get("cover", ""),
                        "rating": float(item.get("rate", 0)) if item.get("rate") else 0,
                        "year": item.get("year"),
                        "media_type": "movie",
                        "external": True,
                        "source": "douban",
                    }
                    for item in items[:20]
                ]
            }
        except Exception as e:
            print(f"[Discover] 豆瓣 API failed: {e}")
            return await self._fallback_local(key)

    # ── 本地数据源 ──

    async def _fetch_local_recent(self, key: str) -> dict:
        """从本地数据库获取最近添加的内容"""
        if not self.db:
            return {"items": []}

        media_type = "movie" if "movie" in key else "tv"

        stmt = (
            select(MediaItem)
            .where(MediaItem.media_type == media_type)
            .order_by(MediaItem.date_added.desc())
            .limit(20)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "external": False,
                    "source": "local",
                }
                for item in items
            ]
        }

    async def _fetch_local_top_rated(self) -> dict:
        """从本地数据库获取评分最高的内容"""
        if not self.db:
            return {"items": []}

        stmt = (
            select(MediaItem)
            .where(MediaItem.rating > 0)
            .order_by(MediaItem.rating.desc())
            .limit(20)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "external": False,
                    "source": "local",
                }
                for item in items
            ]
        }

    async def _fetch_local_anime(self) -> dict:
        """从本地数据库获取动漫内容"""
        if not self.db:
            return {"items": []}

        stmt = (
            select(MediaItem)
            .where(MediaItem.media_type == "anime")
            .order_by(MediaItem.date_added.desc())
            .limit(20)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        # 如果没有 anime 类型，返回评分最高的
        if not items:
            stmt = (
                select(MediaItem)
                .where(MediaItem.rating > 8.0)
                .order_by(MediaItem.rating.desc())
                .limit(20)
            )
            result = await self.db.execute(stmt)
            items = result.scalars().all()

        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "external": False,
                    "source": "local",
                }
                for item in items
            ]
        }

    # ── 降级方案 ──

    async def _fallback_local(self, key: str) -> dict:
        """外部 API 失败时的降级方案：返回本地数据"""
        if "movie" in key:
            return await self._fetch_local_recent("recent_movies")
        elif "tv" in key:
            return await self._fetch_local_recent("recent_tv")
        else:
            return await self._fetch_local_top_rated()

    # ── 图片代理 ──

    async def proxy_image(self, url: str) -> bytes:
        """代理外部图片，绕过防盗链"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://movie.douban.com/",
            }
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
