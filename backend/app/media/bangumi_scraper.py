"""
Bangumi 元数据刮削
使用 Bangumi API 搜索和获取动漫元数据，补充中文信息。
Bangumi 是专注于 ACG 领域的数据库，特别适合动漫刮削。
API 文档：https://bangumi.github.io/api/
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class BangumiClient:
    """Bangumi API 客户端"""

    # Bangumi 条目类型
    TYPE_ANIME = 2      # 动画
    TYPE_MANGA = 1      # 漫画
    TYPE_MUSIC = 3      # 音乐
    TYPE_GAME = 4       # 游戏

    def __init__(self):
        self.settings = get_settings()
        self.token = self.settings.bangumi_token
        self.base_url = "https://api.bgm.tv"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": "MediaStation/1.0 (https://github.com/mediastation)",
                "Accept": "application/json",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=15.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def is_configured(self) -> bool:
        """Bangumi 是否已配置 Token"""
        return bool(self.token)

    # ── 搜索 ──
    async def search(self, query: str, type_: int | None = None) -> list[dict]:
        """搜索 Bangumi 条目"""
        params: dict[str, Any] = {"keyword": query}
        if type_ is not None:
            params["type"] = type_

        try:
            resp = await self.client.get("/v0/search/subjects", params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"Bangumi search failed: {e}")

        # 回退旧 API
        return await self._search_legacy(query, type_)

    async def _search_legacy(self, query: str, type_: int | None = None) -> list[dict]:
        """使用旧版搜索 API"""
        try:
            params = {
                "keywords": query,
                "responseGroup": "small",
            }
            if type_ is not None:
                params["type"] = type_

            resp = await self.client.get("/search/subject", params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("list", [])
        except Exception as e:
            logger.warning(f"Bangumi legacy search failed: {e}")
        return []

    # ── 详情 ──
    async def get_detail(self, subject_id: int) -> dict | None:
        """获取条目详情"""
        try:
            resp = await self.client.get(f"/v0/subjects/{subject_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"Bangumi detail failed for {subject_id}: {e}")

        # 回退旧 API
        return await self._get_detail_legacy(subject_id)

    async def _get_detail_legacy(self, subject_id: int) -> dict | None:
        """旧版详情 API"""
        try:
            resp = await self.client.get(f"/subject/{subject_id}", params={"responseGroup": "large"})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"Bangumi legacy detail failed for {subject_id}: {e}")
        return None

    # ── 转换为标准格式 ──
    def to_media_metadata(self, data: dict) -> dict:
        """将 Bangumi 数据转换为标准元数据格式"""
        result: dict[str, Any] = {}

        if data.get("id"):
            result["bangumi_id"] = data["id"]
        if data.get("name"):
            result["title"] = data["name"]
        if data.get("name_cn"):
            result["title_cn"] = data["name_cn"]

        # 取中文名优先
        if data.get("name_cn"):
            result["title"] = data["name_cn"]
            result["original_title"] = data.get("name", "")
        elif data.get("name"):
            result["title"] = data["name"]

        # 简介
        if data.get("summary"):
            result["overview"] = data["summary"]

        # 评分
        rating = data.get("rating", {})
        if isinstance(rating, dict) and rating.get("score"):
            result["rating"] = rating["score"]

        # 海报
        images = data.get("images", {})
        if isinstance(images, dict):
            if images.get("large"):
                result["poster_url"] = images["large"]
            elif images.get("common"):
                result["poster_url"] = images["common"]

        # 标签
        tags = data.get("tags", [])
        if isinstance(tags, list) and tags:
            tag_names = []
            for tag in tags:
                if isinstance(tag, dict) and tag.get("name"):
                    tag_names.append(tag["name"])
                elif isinstance(tag, str):
                    tag_names.append(tag)
            if tag_names:
                result["genres"] = json.dumps(tag_names[:8], ensure_ascii=False)

        # 日期/年份
        date_str = data.get("date", "")
        if date_str:
            year_match = re.search(r"\d{4}", str(date_str))
            if year_match:
                result["year"] = int(year_match.group())

        # 集数
        eps = data.get("eps")
        if eps:
            try:
                result["total_episodes"] = int(eps)
            except (ValueError, TypeError):
                pass
        eps_count = data.get("total_episodes")
        if eps_count and "total_episodes" not in result:
            try:
                result["total_episodes"] = int(eps_count)
            except (ValueError, TypeError):
                pass

        return result

    async def enrich_metadata(self, metadata: dict, media_type: str) -> dict:
        """用 Bangumi 数据补充元数据（主要用于动漫类型）"""
        title = metadata.get("title") or metadata.get("original_title", "")
        if not title:
            return metadata

        try:
            # 搜索动漫类型
            results = await self.search(title, type_=self.TYPE_ANIME)
            if not results:
                # 尝试搜索所有类型
                results = await self.search(title)
            if not results:
                return metadata

            # 取第一个匹配
            best = results[0]
            subject_id = best.get("id")
            if not subject_id:
                return metadata

            detail = await self.get_detail(subject_id)
            if not detail:
                return metadata

            bgm_data = self.to_media_metadata(detail)

            # 补充缺失的字段
            for key, value in bgm_data.items():
                if key == "rating":
                    # Bangumi 评分存到 bangumi_rating
                    if value:
                        metadata["bangumi_rating"] = value
                    continue
                if key == "title" and metadata.get("title"):
                    # Bangumi 中文名优先，但如果是中文环境且 TMDb 标题是英文，则用中文
                    if bgm_data.get("title_cn") and not metadata.get("title", "").isascii():
                        # 原标题已经是中文，不覆盖
                        pass
                    elif bgm_data.get("title_cn"):
                        metadata["title_cn"] = bgm_data["title_cn"]
                    continue
                if key not in metadata or not metadata[key]:
                    metadata[key] = value

            # 保存 bangumi_id
            if bgm_data.get("bangumi_id"):
                metadata["bangumi_id"] = bgm_data["bangumi_id"]

        except Exception as e:
            logger.warning(f"Bangumi enrichment failed for '{title}': {e}")

        return metadata


# 全局客户端实例
_bangumi_client: BangumiClient | None = None


def get_bangumi_client() -> BangumiClient:
    global _bangumi_client
    if _bangumi_client is None:
        _bangumi_client = BangumiClient()
    return _bangumi_client
