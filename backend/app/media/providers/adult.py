"""
Adult Provider - 18+ 番号刮削 Provider

多层 Fallback 刮削策略：
第1层: JavBus (主刮削)
第2层: JavDB (Fallback)
第3层: Python 微服务 (最终兜底)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from .base import MediaMetadata, MetadataProvider, ProviderPriority

logger = logging.getLogger(__name__)


class AdultProviderConfig:
    """Adult Provider 配置"""

    def __init__(
        self,
        enabled: bool = False,
        adult_dirs: list[str] | None = None,
        javbus_url: str = "https://www.javbus.com",
        javdb_url: str = "https://javdb.com",
        microservice_url: str | None = None,
        proxy: str | None = None,
        javdb_cookie: str | None = None,
    ):
        self.enabled = enabled
        self.adult_dirs = adult_dirs or []
        self.javbus_url = javbus_url
        self.javdb_url = javdb_url
        self.microservice_url = microservice_url
        self.proxy = proxy
        self.javdb_cookie = javdb_cookie


class AdultProvider(MetadataProvider):
    """
    18+ 番号刮削 Provider

    调度策略：
    1. 第1层: JavBus (https://www.javbus.com)
    2. 第2层: JavDB (https://javdb.com)
    3. 第3层: Python 微服务 (用户现有服务)

    配置说明：
    - 配置存储在数据库 ApiConfig 表中，运行时实时读取
    - 无需重启后端即可生效
    """

    def __init__(self, config: AdultProviderConfig | None = None):
        self._initial_config = config  # 保存启动时的配置（备用）
        self._db_config_loaded = False
        self._session = None  # aiohttp session (lazy init)

    async def _load_config_from_db(self) -> AdultProviderConfig:
        """从数据库加载最新配置"""
        try:
            from app.database import get_db_session
            from app.system.api_config_models import ApiConfig
            from sqlalchemy import select
            import json

            async with get_db_session() as db:
                result = await db.execute(
                    select(ApiConfig).where(ApiConfig.provider == "adult")
                )
                db_config = result.scalar_one_or_none()

            if db_config:
                extra = {}
                if db_config.extra:
                    try:
                        extra = json.loads(db_config.extra)
                    except json.JSONDecodeError:
                        extra = {}

                return AdultProviderConfig(
                    enabled=db_config.enabled,
                    adult_dirs=extra.get("adult_dirs", []),
                    javbus_url=extra.get("javbus_url", "https://www.javbus.com"),
                    javdb_url=extra.get("javdb_url", "https://javdb.com"),
                    microservice_url=extra.get("microservice_url"),
                    proxy=extra.get("proxy"),
                    javdb_cookie=extra.get("javdb_cookie"),
                )
        except Exception as e:
            logger.warning(f"[AdultProvider] Failed to load config from DB: {e}")

        # 回退到初始配置
        return self._initial_config or AdultProviderConfig()

    @property
    def name(self) -> str:
        return "Adult"

    @property
    def priority(self) -> int:
        return ProviderPriority.Adult  # 5

    @property
    def is_primary(self) -> bool:
        """Adult Provider 是主数据源（提供完整元数据）"""
        return True

    async def is_configured(self) -> bool:
        """检查 Provider 是否已配置（实时从数据库读取）"""
        config = await self._load_config_from_db()
        return config.enabled

    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索 18+ 内容

        Args:
            title: 搜索标题（可以是番号或关键词）
            media_type: 媒体类型（对于 Adult，通常为 movie）
            year: 年份（可选）

        Returns:
            搜索结果列表
        """
        # 实时从数据库加载最新配置
        config = await self._load_config_from_db()
        
        # 尝试用番号搜索
        from app.media.parse_code import parse_code
        parsed = parse_code(title)
        if parsed:
            # 用番号搜索
            return await self._search_by_code(parsed.code, config)

        # 用标题搜索
        return await self._search_by_title(title, year, config)

    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """
        获取 18+ 内容元数据（多层 Fallback）

        调度策略：
        1. 第1层: JavBus
        2. 第2层: JavDB
        3. 第3层: Python 微服务
        """
        # 实时从数据库加载最新配置
        config = await self._load_config_from_db()
        code = str(media_id)

        # 第1层: JavBus
        logger.info(f"[Adult] Trying JavBus for code: {code}")
        metadata = await self._scrape_javbus(code, config)
        if metadata:
            logger.info(f"[Adult] JavBus success for {code}")
            return metadata

        # 第2层: JavDB
        logger.info(f"[Adult] JavBus failed, trying JavDB for code: {code}")
        metadata = await self._scrape_javdb(code, config)
        if metadata:
            logger.info(f"[Adult] JavDB success for {code}")
            return metadata

        # 第3层: Python 微服务
        if config.microservice_url:
            logger.info(f"[Adult] JavDB failed, trying microservice for code: {code}")
            metadata = await self._scrape_microservice(code, config)
            if metadata:
                logger.info(f"[Adult] Microservice success for {code}")
                return metadata

        logger.warning(f"[Adult] All sources failed for code: {code}")
        return None

    async def _search_by_code(self, code: str, config: AdultProviderConfig | None = None) -> list[dict[str, Any]]:
        """用番号搜索"""
        # 优先使用 JavBus 搜索
        results = await self._search_javbus(code, config)
        if results:
            return results

        # Fallback 到 JavDB
        results = await self._search_javdb(code, config)
        if results:
            return results

        return []

    async def _search_by_title(self, title: str, year: int | None, config: AdultProviderConfig | None = None) -> list[dict[str, Any]]:
        """用标题搜索（模糊搜索）"""
        # JavBus 支持关键词搜索
        results = await self._search_javbus(title, config)
        return results

    # ── JavBus 客户端 ─────────────────────────────────────

    async def _search_javbus(self, keyword: str, config: AdultProviderConfig | None = None) -> list[dict[str, Any]]:
        """JavBus 搜索（网页爬取）"""
        cfg = config or self._initial_config or AdultProviderConfig()
        try:
            import urllib.parse
            from bs4 import BeautifulSoup

            encoded_keyword = urllib.parse.quote(keyword)
            url = f"{cfg.javbus_url}/search/{encoded_keyword}"

            session = await self._get_session()
            proxy = self._get_proxy(cfg)
            async with session.get(url, proxy=proxy, ssl=False) as resp:
                if resp.status != 200:
                    logger.warning(f"[JavBus] Search failed: {resp.status}")
                    return []

                html = await resp.text()

            # 解析搜索结果
            soup = BeautifulSoup(html, 'lxml')

            results = []
            # 搜索结果在 class="item" 的 div 中
            items = soup.find_all('div', class_='item')
            for item in items:
                link = item.find('a')
                img = item.find('img')
                title_span = item.find('span', class_='title')

                if link and title_span:
                    code = link.get('href', '').strip('/').split('/')[-1]
                    results.append({
                        'id': code,
                        'title': title_span.text.strip(),
                        'poster': img.get('src', '') if img else '',
                    })

            logger.debug(f"[JavBus] Search '{keyword}' found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"[JavBus] Search error: {e}")
            return []

    async def _scrape_javbus(self, code: str, config: AdultProviderConfig | None = None) -> MediaMetadata | None:
        """
        使用 JavBus 刮削番号（网页爬取）
        """
        cfg = config or self._initial_config or AdultProviderConfig()
        try:
            import urllib.parse
            from bs4 import BeautifulSoup

            # 番号标准化（将空格、下划线转为-）
            normalized_code = code.replace(' ', '-').replace('_', '-')
            url = f"{cfg.javbus_url}/{normalized_code}"

            session = await self._get_session()
            proxy = self._get_proxy(cfg)
            async with session.get(url, proxy=proxy, ssl=False) as resp:
                if resp.status != 200:
                    logger.debug(f"[JavBus] Detail page not found: {resp.status}")
                    return None

                html = await resp.text()

            # 解析详情页
            soup = BeautifulSoup(html, 'lxml')

            # 提取元数据
            title_tag = soup.find('h3')
            title = title_tag.text.strip() if title_tag else ''

            # 番号
            code_tag = soup.find('span', class_='header', string=lambda x: x and '番号' in x)
            if code_tag:
                code_span = code_tag.find_next_sibling('span', class_='text')
                code = code_span.text.strip() if code_span else code

            # 日期
            date_tag = soup.find('span', class_='header', string=lambda x: x and '发行日期' in x)
            release_date = ''
            if date_tag:
                date_span = date_tag.find_next_sibling('span', class_='text')
                release_date = date_span.text.strip() if date_span else ''

            # 片商
            studio_tag = soup.find('span', class_='header', string=lambda x: x and '出品商' in x)
            studio = ''
            if studio_tag:
                studio_link = studio_tag.find_next_sibling('a')
                if studio_link:
                    studio = studio_link.text.strip()
                else:
                    studio_span = studio_tag.find_next_sibling('span', class_='text')
                    studio = studio_span.text.strip() if studio_span else ''

            # 导演
            director = ''
            director_tag = soup.find('span', class_='header', string=lambda x: x and '导演' in x)
            if director_tag:
                director_link = director_tag.find_next_sibling('a')
                if director_link:
                    director = director_link.text.strip()

            # 类型
            genres = []
            genre_links = soup.find_all('a', href=lambda x: x and '/genre/' in x)
            for link in genre_links:
                genre = link.text.strip()
                if genre and genre not in genres:
                    genres.append(genre)

            # 演员
            actors = []
            star_names = soup.find_all('span', class_='star-name')
            for name_span in star_names:
                actor_link = name_span.find('a')
                if actor_link:
                    actors.append(actor_link.text.strip())

            # 封面
            poster_url = ''
            jacket = soup.find('a', class_='bigImage')
            if jacket:
                poster_url = jacket.get('href', '')

            # 简介
            overview = ''
            intro = soup.find('div', id='video_introduce')
            if intro:
                overview_span = intro.find('span', class_='text')
                if overview_span:
                    overview = overview_span.text.strip()

            # 时长（需要解析，例如 "120分钟"）
            duration = None
            time_tag = soup.find('span', class_='header', string=lambda x: x and '长度' in x)
            if time_tag:
                time_span = time_tag.find_next_sibling('span', class_='text')
                if time_span:
                    match = re.search(r'(\d+)', time_span.text)
                    if match:
                        duration = int(match.group(1)) * 60  # 转为秒

            # 评分
            rating = 0.0
            rating_tag = soup.find('span', class_='header', string=lambda x: x and '评分' in x)
            if rating_tag:
                rating_span = rating_tag.find_next_sibling('span', class_='score')
                if rating_span:
                    try:
                        rating = float(rating_span.text.strip()) * 2  # JavBus 评分通常是 5 分制
                    except ValueError:
                        pass

            # 构建 MediaMetadata
            metadata = MediaMetadata(
                title=title,
                year=int(release_date[:4]) if release_date else None,
                overview=overview,
                poster_url=poster_url,
                rating=rating,
                genres=genres,
                duration=duration,
                is_adult=True,
                extra={
                    'adult_code': code,
                    'studio': studio,
                    'director': director,
                    'actors': actors,
                    'release_date': release_date,
                },
            )

            logger.info(f"[JavBus] Successfully scraped {code}")
            return metadata

        except Exception as e:
            logger.error(f"[JavBus] Error scraping {code}: {e}")
            return None

    # ── JavDB 客户端 ─────────────────────────────────────

    async def _search_javdb(self, keyword: str, config: AdultProviderConfig | None = None) -> list[dict[str, Any]]:
        """JavDB 搜索（需要登录/cookie）"""
        cfg = config or self._initial_config or AdultProviderConfig()
        try:
            import urllib.parse
            from bs4 import BeautifulSoup

            encoded_keyword = urllib.parse.quote(keyword)
            # JavDB 搜索 URL
            url = f"{cfg.javdb_url}/search?q={encoded_keyword}&f=all"

            session = await self._get_session()
            proxy = self._get_proxy(cfg)
            headers = {}
            if cfg.javdb_cookie:
                headers['Cookie'] = cfg.javdb_cookie

            async with session.get(url, proxy=proxy, ssl=False, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"[JavDB] Search failed: {resp.status}")
                    return []

                html = await resp.text()

            soup = BeautifulSoup(html, 'lxml')

            results = []
            # JavDB 搜索结果：.item 或 .box
            items = soup.find_all('div', class_='item') or soup.find_all('div', class_='box')
            for item in items:
                link = item.find('a')
                title = item.find('div', class_='video-title') or item.find('img')

                if link:
                    href = link.get('href', '')
                    code = href.strip('/').split('/')[-1]
                    results.append({
                        'id': code,
                        'title': title.get('alt', '') if title and title.name == 'img' else (title.text.strip() if title else ''),
                        'poster': title.get('src', '') if title and title.name == 'img' else '',
                    })

            logger.debug(f"[JavDB] Search '{keyword}' found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"[JavDB] Search error: {e}")
            return []

    async def _scrape_javdb(self, code: str, config: AdultProviderConfig | None = None) -> MediaMetadata | None:
        """
        使用 JavDB 刮削番号（作为 JavBus 的 Fallback）

        注意: JavDB 通常需要登录，需要配置 cookie
        """
        cfg = config or self._initial_config or AdultProviderConfig()
        try:
            import urllib.parse
            from bs4 import BeautifulSoup

            # JavDB 可能没有直接的番号详情页，需要先搜索
            search_results = await self._search_javdb(code, cfg)
            if not search_results:
                return None

            # 获取第一个结果的详情页
            video_id = search_results[0].get('id')
            if not video_id:
                return None

            url = f"{cfg.javdb_url}/v/{video_id}"

            session = await self._get_session()
            proxy = self._get_proxy(cfg)
            headers = {}
            if cfg.javdb_cookie:
                headers['Cookie'] = cfg.javdb_cookie

            async with session.get(url, proxy=proxy, ssl=False, headers=headers) as resp:
                if resp.status != 200:
                    logger.debug(f"[JavDB] Detail page not found: {resp.status}")
                    return None

                html = await resp.text()

            soup = BeautifulSoup(html, 'lxml')

            # 解析元数据（JavDB 的 HTML 结构可能变化）
            title_tag = soup.find('strong', class_='current-title')
            title = title_tag.text.strip() if title_tag else ''

            # 封面
            poster_url = ''
            cover = soup.find('img', class_='video-cover')
            if cover:
                poster_url = cover.get('src', '')

            # 番号
            code_tag = soup.find('strong', string=lambda x: x and code.upper() in x.upper())
            if code_tag:
                code = code_tag.text.strip()

            # 日期
            release_date = ''
            date_tag = soup.find('span', string=lambda x: x and '发行日期' in x)
            if date_tag:
                date_parent = date_tag.find_parent()
                if date_parent:
                    release_date = date_parent.text.replace('发行日期', '').strip()

            # 片商
            studio = ''
            studio_tag = soup.find('span', string=lambda x: x and '片商' in x)
            if studio_tag:
                studio_link = studio_tag.find_next_sibling('a')
                if studio_link:
                    studio = studio_link.text.strip()

            # 类型
            genres = []
            genre_tags = soup.find_all('a', href=lambda x: x and '/tags/' in x)
            for tag in genre_tags:
                genre = tag.text.strip()
                if genre and genre not in genres:
                    genres.append(genre)

            # 演员
            actors = []
            actor_tags = soup.find_all('a', href=lambda x: x and '/actors/' in x)
            for tag in actor_tags:
                actor = tag.text.strip()
                if actor and actor not in actors:
                    actors.append(actor)

            # 评分
            rating = 0.0
            rating_tag = soup.find('span', class_='score')
            if rating_tag:
                try:
                    rating = float(rating_tag.text.strip()) * 2  # 5分制转10分制
                except ValueError:
                    pass

            # 构建 MediaMetadata
            metadata = MediaMetadata(
                title=title,
                year=int(release_date[:4]) if release_date else None,
                overview='',  # JavDB 可能没有简介
                poster_url=poster_url,
                rating=rating,
                genres=genres,
                is_adult=True,
                extra={
                    'adult_code': code,
                    'studio': studio,
                    'actors': actors,
                    'release_date': release_date,
                },
            )

            logger.info(f"[JavDB] Successfully scraped {code}")
            return metadata

        except Exception as e:
            logger.error(f"[JavDB] Error scraping {code}: {e}")
            return None

    # ── Python 微服务客户端 ──────────────────────────────

    async def _scrape_microservice(self, code: str, config: AdultProviderConfig | None = None) -> MediaMetadata | None:
        """
        使用 Python 微服务刮削（最终兜底）

        用户现有服务，需要提供服务地址和 API 文档
        """
        cfg = config or self._initial_config or AdultProviderConfig()
        if not cfg.microservice_url:
            return None

        try:
            # TODO: 根据用户微服务 API 实现
            # 示例:
            # import aiohttp
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(
            #         f"{cfg.microservice_url}/api/scrape",
            #         params={"code": code}
            #     ) as resp:
            #         data = await resp.json()
            #         return self._parse_microservice_data(data)
            logger.debug(f"[Microservice] Scraping {code}")
            return None
        except Exception as e:
            logger.error(f"[Microservice] Error scraping {code}: {e}")
            return None

    # ── 辅助方法 ─────────────────────────────────────

    def _map_to_metadata(self, data: dict) -> MediaMetadata:
        """
        将 JavBus/JavDB 数据映射为 MediaMetadata
        """
        return MediaMetadata(
            title=data.get("title", ""),
            original_title=data.get("original_title"),
            year=data.get("year"),
            overview=data.get("plot") or data.get("overview"),
            poster_url=data.get("cover") or data.get("poster_url"),
            backdrop_url=data.get("backdrop_url"),
            rating=data.get("rating", 0.0),
            genres=data.get("genres", []),
            duration=data.get("runtime"),  # 秒
            is_adult=True,
            extra={
                "adult_code": data.get("cid") or data.get("code"),
                "studio": data.get("studio"),
                "director": data.get("director"),
                "actors": data.get("actor") or data.get("actors", []),
                "gallery": data.get("gallery", []),
            },
        )

    async def _get_session(self):
        """获取 aiohttp session（懒加载，自动使用系统代理）"""
        if self._session is None:
            import aiohttp
            import random
            # 随机 User-Agent 减少被识别
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            timeout = aiohttp.ClientTimeout(total=30)
            # aiohttp 默认 trust_env=True，自动读取 HTTP_PROXY/HTTPS_PROXY 环境变量
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    def _get_proxy(self, config: AdultProviderConfig | None = None):
        """获取当前生效的代理（自定义代理 > 系统代理 > 无代理）"""
        cfg = config or self._initial_config or AdultProviderConfig()
        if cfg.proxy:
            return cfg.proxy
        import os
        return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    async def close(self):
        """关闭 session"""
        if self._session:
            await self._session.close()
            self._session = None


# 导出
__all__ = [
    "AdultProvider",
    "AdultProviderConfig",
]
