"""
豆瓣元数据刮削
通过豆瓣 API 搜索和获取影视元数据，补充中文信息。
使用非官方 API（无需 API Key，但需要 Cookie 防反爬）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class DoubanClient:
    """豆瓣元数据客户端"""

    def __init__(self):
        self.settings = get_settings()
        self.cookie = self.settings.douban_cookie
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://movie.douban.com/",
                "Accept": "application/json",
            }
            if self.cookie:
                headers["Cookie"] = self.cookie
            self._client = httpx.AsyncClient(
                base_url="https://movie.douban.com",
                headers=headers,
                timeout=15.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def is_configured(self) -> bool:
        """豆瓣是否可用（有 Cookie 则更稳定，没有也能用但易触发反爬）"""
        return True  # 基础搜索无需 Cookie，但推荐配置

    # ── 搜索 ──
    async def search(self, query: str, media_type: str = "movie") -> list[dict]:
        """搜索豆瓣影视条目，返回简要列表"""
        # 使用豆瓣 suggest API
        try:
            resp = await self.client.get(
                "/j/subject_suggest",
                params={"q": query},
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data:
                    # 只取电影和电视剧
                    cat = item.get("type", "")
                    if media_type == "movie" and cat not in ("movie",):
                        continue
                    if media_type in ("tv", "anime") and cat not in ("tv",):
                        # 动漫也可能是 movie 类型，不过滤
                        pass
                    results.append({
                        "douban_id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "year": item.get("year", ""),
                        "type": cat,
                        "cover": item.get("cover", ""),
                        "url": item.get("url", ""),
                    })
                return results
        except Exception as e:
            logger.warning(f"Douban search failed: {e}")

        # 回退：解析搜索页面
        return await self._search_by_page(query)

    async def _search_by_page(self, query: str) -> list[dict]:
        """通过 HTML 页面搜索（回退方案）"""
        try:
            from bs4 import BeautifulSoup
            resp = await self.client.get(
                "/subject_search",
                params={"search_text": query, "cat": "1002"},  # 1002=电影
            )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for item in soup.select(".item-root"):
                link = item.select_one("a")
                title_el = item.select_one(".title-text")
                if not link or not title_el:
                    continue
                url = link.get("href", "")
                douban_id_match = re.search(r"/subject/(\d+)", url)
                if not douban_id_match:
                    continue
                results.append({
                    "douban_id": douban_id_match.group(1),
                    "title": title_el.get_text(strip=True),
                    "url": url,
                })
            return results
        except Exception as e:
            logger.warning(f"Douban page search failed: {e}")
            return []

    # ── 详情 ──
    async def get_detail(self, douban_id: str) -> dict | None:
        """获取豆瓣条目详情"""
        try:
            # 尝试 JSON API
            resp = await self.client.get(f"/j/subject_abstract/{douban_id}")
            if resp.status_code == 200:
                return self._parse_abstract(resp.json(), douban_id)
        except Exception:
            pass

        # 回退：解析 HTML 页面
        return await self._get_detail_by_page(douban_id)

    async def _get_detail_by_page(self, douban_id: str) -> dict | None:
        """通过 HTML 页面获取详情"""
        try:
            from bs4 import BeautifulSoup

            resp = await self.client.get(f"/subject/{douban_id}")
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            result: dict[str, Any] = {"douban_id": douban_id}

            # 标题
            title_el = soup.select_one("span[property='v:itemreviewed']")
            if title_el:
                result["title"] = title_el.get_text(strip=True)

            # 年份
            year_el = soup.select_one(".year")
            if year_el:
                year_text = re.search(r"\d{4}", year_el.get_text())
                if year_text:
                    result["year"] = int(year_text.group())

            # 评分
            rating_el = soup.select_one("strong.ll.rating_num")
            if rating_el:
                try:
                    result["rating"] = float(rating_el.get_text(strip=True))
                except ValueError:
                    pass

            # 简介
            summary_el = soup.select_one("span[property='v:summary']")
            if summary_el:
                result["overview"] = summary_el.get_text(strip=True)

            # 海报
            img_el = soup.select_one("#mainpic img")
            if img_el:
                result["poster_url"] = img_el.get("src", "")

            # 类型标签
            genres = [g.get_text(strip=True) for g in soup.select("span[property='v:genre']")]
            if genres:
                result["genres"] = genres

            # 导演
            directors = [d.get_text(strip=True) for d in soup.select("a[rel='v:directedBy']")]
            if directors:
                result["directors"] = directors

            # 演员
            actors = []
            for a in soup.select("a[rel='v:starring']"):
                actors.append(a.get_text(strip=True))
            if actors:
                result["actors"] = actors[:5]  # 最多取5个

            # 集数（电视剧）
            episodes_el = soup.select_one("span[property='v:episodes']")
            if episodes_el:
                try:
                    result["total_episodes"] = int(episodes_el.get_text(strip=True))
                except ValueError:
                    pass

            return result
        except Exception as e:
            logger.warning(f"Douban detail parse failed for {douban_id}: {e}")
            return None

    def _parse_abstract(self, data: dict, douban_id: str) -> dict:
        """解析豆瓣 abstract API 响应"""
        result: dict[str, Any] = {"douban_id": douban_id}
        if "title" in data:
            result["title"] = data["title"]
        if "rate" in data:
            try:
                result["rating"] = float(data["rate"])
            except (ValueError, TypeError):
                pass
        if "cover_url" in data:
            result["poster_url"] = data["cover_url"]
        return result

    # ── 转换为标准格式 ──
    def to_media_metadata(self, data: dict) -> dict:
        """将豆瓣数据转换为标准元数据格式（用于补充 TMDb 数据）"""
        result: dict[str, Any] = {}

        if data.get("douban_id"):
            result["douban_id"] = str(data["douban_id"])
        if data.get("title"):
            result["title"] = data["title"]
        if data.get("year"):
            try:
                result["year"] = int(data["year"])
            except (ValueError, TypeError):
                pass
        if data.get("overview"):
            result["overview"] = data["overview"]
        if data.get("poster_url"):
            result["poster_url"] = data["poster_url"]
        if data.get("rating"):
            result["rating"] = data["rating"]
        if data.get("genres"):
            result["genres"] = json.dumps(data["genres"], ensure_ascii=False)
        if data.get("directors"):
            result["directors"] = data["directors"]
        if data.get("actors"):
            result["actors"] = data["actors"]

        return result

    async def enrich_metadata(self, metadata: dict, media_type: str) -> dict:
        """用豆瓣数据补充 TMDb 元数据（不覆盖已有字段）"""
        title = metadata.get("title") or metadata.get("original_title", "")
        if not title:
            return metadata

        try:
            results = await self.search(title, media_type)
            if not results:
                return metadata

            # 取第一个匹配结果
            best = results[0]
            douban_id = best.get("douban_id", "")
            if not douban_id:
                return metadata

            detail = await self.get_detail(douban_id)
            if not detail:
                return metadata

            douban_data = self.to_media_metadata(detail)

            # 补充缺失的字段（不覆盖 TMDb 已有数据）
            for key, value in douban_data.items():
                if key == "rating":
                    # 豆瓣评分存到 douban_rating，不覆盖 tmdb rating
                    if value:
                        metadata["douban_rating"] = value
                    continue
                if key not in metadata or not metadata[key]:
                    metadata[key] = value

            # 确保 douban_id 被保存
            if douban_data.get("douban_id"):
                metadata["douban_id"] = douban_data["douban_id"]

        except Exception as e:
            logger.warning(f"Douban enrichment failed for '{title}': {e}")

        return metadata


# 全局客户端实例
_douban_client: DoubanClient | None = None


def get_douban_client() -> DoubanClient:
    global _douban_client
    if _douban_client is None:
        _douban_client = DoubanClient()
    return _douban_client
