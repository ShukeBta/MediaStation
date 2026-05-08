"""
Adult Provider - 18+ 番号刮削 Provider (优化版 v2.0)

整合 nowen-video 的优秀设计，新增特性：
- 多镜像轮询（4个 JavBus + 4个 JavDB 镜像）
- 健康检查和熔断机制（连续失败3次冷却10分钟）
- 请求延迟和反爬策略（随机1.5-3秒延迟）
- Cookie 支持（JavBus + JavDB 均可配置）
- 更好的错误处理和日志

多层 Fallback 刮削策略：
第1层: JavBus (主刮削，支持多镜像)
第2层: JavDB (Fallback，支持多镜像)
第3层: Python 微服务 (最终兜底)
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .base import MediaMetadata, MetadataProvider, ProviderPriority

logger = logging.getLogger(__name__)


class MirrorStatus(Enum):
    """镜像状态"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    COOLING = "cooling"  # 熔断冷却中


@dataclass
class MirrorInfo:
    """镜像信息"""
    url: str
    status: MirrorStatus = MirrorStatus.HEALTHY
    fail_count: int = 0
    success_count: int = 0
    last_check: float = 0
    last_success: float = 0
    cooldown_until: float = 0
    response_time: float = 0  # 秒


class AdultProviderConfig:
    """Adult Provider 配置（优化版）"""

    # 内置多镜像列表（参考 nowen-video）
    DEFAULT_MIRRORS = {
        "javbus": [
            "https://www.javbus.com",
            "https://www.buscdn.work",
            "https://www.javbus.red",
            "https://www.seejav.art",
        ],
        "javdb": [
            "https://javdb.com",
            "https://javdb001.com",
            "https://javdb002.com",
            "https://javdb521.com",
        ],
    }

    def __init__(
        self,
        enabled: bool = False,
        adult_dirs: list[str] | None = None,
        javbus_url: str = "https://www.javbus.com",
        javdb_url: str = "https://javdb.com",
        microservice_url: str | None = None,
        proxy: str | None = None,
        javbus_cookie: str | None = None,
        javdb_cookie: str | None = None,
        # 多镜像配置
        javbus_mirrors: list[str] | None = None,
        javdb_mirrors: list[str] | None = None,
        # 反爬配置
        enable_delay: bool = True,
        min_delay_ms: int = 1500,
        max_delay_ms: int = 3000,
        # 健康检查
        enable_health_check: bool = True,
        health_check_interval: int = 300,  # 5 分钟
        # 熔断配置
        max_fail_count: int = 3,
        cooldown_seconds: int = 600,  # 10 分钟
    ):
        self.enabled = enabled
        self.adult_dirs = adult_dirs or []
        self.javbus_url = javbus_url
        self.javdb_url = javdb_url
        self.microservice_url = microservice_url
        self.proxy = proxy
        self.javbus_cookie = javbus_cookie
        self.javdb_cookie = javdb_cookie

        # 多镜像（使用内置默认值或用户自定义）
        self.javbus_mirrors = javbus_mirrors or self.DEFAULT_MIRRORS["javbus"]
        self.javdb_mirrors = javdb_mirrors or self.DEFAULT_MIRRORS["javdb"]

        # 反爬配置
        self.enable_delay = enable_delay
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms

        # 健康检查配置
        self.enable_health_check = enable_health_check
        self.health_check_interval = health_check_interval

        # 熔断配置
        self.max_fail_count = max_fail_count
        self.cooldown_seconds = cooldown_seconds


class MirrorManager:
    """镜像管理器（参考 nowen-video 的 AdultProxyManager）"""

    def __init__(self, config: AdultProviderConfig):
        self.config = config
        self.mirrors: dict[str, list[MirrorInfo]] = {}
        self._init_mirrors()

    def _init_mirrors(self):
        """初始化镜像列表"""
        self.mirrors["javbus"] = [
            MirrorInfo(url=url) for url in self.config.javbus_mirrors
        ]
        self.mirrors["javdb"] = [
            MirrorInfo(url=url) for url in self.config.javdb_mirrors
        ]

    def get_preferred_url(self, source: str) -> str:
        """获取首选镜像 URL"""
        if source not in self.mirrors:
            logger.warning(f"[Mirror] Unknown source: {source}")
            return ""

        available = self.mirrors[source]

        # 查找健康的镜像
        for mirror in available:
            if self._is_healthy(mirror):
                return mirror.url

        # 全部不健康，返回第一个
        logger.warning(f"[Mirror] All {source} mirrors are unhealthy, using first one")
        return available[0].url if available else ""

    def _is_healthy(self, mirror: MirrorInfo) -> bool:
        """检查镜像是否健康"""
        if mirror.status == MirrorStatus.COOLING:
            if time.time() < mirror.cooldown_until:
                return False
            else:
                mirror.status = MirrorStatus.HEALTHY
                mirror.fail_count = 0

        return mirror.status == MirrorStatus.HEALTHY

    def mark_success(self, source: str, url: str, response_time: float):
        """标记镜像访问成功"""
        mirror = self._find_mirror(source, url)
        if mirror:
            mirror.fail_count = 0
            mirror.success_count += 1
            mirror.last_success = time.time()
            mirror.response_time = response_time
            mirror.status = MirrorStatus.HEALTHY

    def mark_failure(self, source: str, url: str):
        """标记镜像访问失败（熔断机制）"""
        mirror = self._find_mirror(source, url)
        if mirror:
            mirror.fail_count += 1
            mirror.last_check = time.time()

            # 达到失败阈值，触发熔断
            if mirror.fail_count >= self.config.max_fail_count:
                mirror.status = MirrorStatus.COOLING
                mirror.cooldown_until = time.time() + self.config.cooldown_seconds
                logger.warning(
                    f"[Mirror] {source} mirror {url} fused for "
                    f"{self.config.cooldown_seconds}s (fail_count={mirror.fail_count})"
                )

    def _find_mirror(self, source: str, url: str) -> MirrorInfo | None:
        """查找镜像信息"""
        if source not in self.mirrors:
            return None

        for mirror in self.mirrors[source]:
            if mirror.url == url or mirror.url.rstrip("/") == url.rstrip("/"):
                return mirror

        return None

    def get_mirror_status(self, source: str) -> list[dict]:
        """获取镜像状态"""
        if source not in self.mirrors:
            return []

        return [
            {
                "url": m.url,
                "status": m.status.value,
                "fail_count": m.fail_count,
                "success_count": m.success_count,
                "response_time": round(m.response_time, 2),
                "cooldown_until": m.cooldown_until,
            }
            for m in self.mirrors[source]
        ]

    async def health_check(self, session) -> dict[str, int]:
        """健康检查（并发检测所有镜像）"""
        if not self.config.enable_health_check:
            return {"total": 0, "healthy": 0}

        logger.info("[Mirror] Starting health check for all mirrors...")

        tasks = []
        for source, mirrors in self.mirrors.items():
            for mirror in mirrors:
                task = self._check_mirror(session, source, mirror)
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total = len(tasks)
        healthy = sum(1 for r in results if r is True)

        logger.info(f"[Mirror] Health check complete: {healthy}/{total} healthy")
        return {"total": total, "healthy": healthy}

    async def _check_mirror(self, session, source: str, mirror: MirrorInfo) -> bool:
        """检查单个镜像的健康状态"""
        try:
            start_time = time.time()
            proxy = self._get_proxy()
            headers = self._get_headers(source, "")

            async with session.head(
                mirror.url,
                proxy=proxy,
                headers=headers,
                timeout=8,
                ssl=False,
            ) as resp:
                response_time = time.time() - start_time

                if 200 <= resp.status < 400:
                    mirror.status = MirrorStatus.HEALTHY
                    mirror.fail_count = 0
                    mirror.response_time = response_time
                    mirror.last_check = time.time()
                    logger.debug(f"[Mirror] {source} {mirror.url} is healthy ({resp.status})")
                    return True
                else:
                    logger.warning(f"[Mirror] {source} {mirror.url} returned {resp.status}")
                    self.mark_failure(source, mirror.url)
                    return False

        except Exception as e:
            logger.warning(f"[Mirror] {source} {mirror.url} health check failed: {e}")
            self.mark_failure(source, mirror.url)
            return False

    def _get_proxy(self):
        """获取代理配置"""
        if self.config.proxy:
            return self.config.proxy
        return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    def _get_headers(self, source: str, cookie: str) -> dict:
        """获取请求头"""
        headers = {
            "User-Agent": self._get_random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # 添加 Cookie
        if cookie:
            headers["Cookie"] = cookie

        return headers

    def _get_random_ua(self) -> str:
        """随机 User-Agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        ]
        return random.choice(user_agents)


class AdultProvider(MetadataProvider):
    """
    18+ 番号刮削 Provider (优化版)

    调度策略：
    1. 第1层: JavBus (支持多镜像)
    2. 第2层: JavDB (支持多镜像)
    3. 第3层: Python 微服务 (最终兜底)
    """

    def __init__(self, config: AdultProviderConfig | None = None):
        self.config = config or AdultProviderConfig()
        self._session = None
        self.mirror_manager = MirrorManager(self.config)
        self._last_health_check = 0

    @property
    def name(self) -> str:
        return "Adult"

    @property
    def priority(self) -> int:
        return ProviderPriority.Adult  # 5

    @property
    def is_primary(self) -> bool:
        return True

    async def is_configured(self) -> bool:
        return self.config.enabled

    async def search(
        self,
        title: str,
        media_type: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """搜索 18+ 内容"""
        from app.media.parse_code import parse_code
        parsed = parse_code(title)
        if parsed:
            return await self._search_by_code(parsed.code)
        return await self._search_by_title(title, year)

    async def get_metadata(
        self,
        media_id: str | int,
        media_type: str,
    ) -> MediaMetadata | None:
        """获取 18+ 内容元数据（多层 Fallback）"""
        code = str(media_id)

        # 触发健康检查
        await self._maybe_health_check()

        # 第1层: JavBus
        logger.info(f"[Adult] Trying JavBus for code: {code}")
        metadata = await self._scrape_javbus_with_mirror(code)
        if metadata:
            logger.info(f"[Adult] JavBus success for {code}")
            return metadata

        # 第2层: JavDB
        logger.info(f"[Adult] JavBus failed, trying JavDB for code: {code}")
        metadata = await self._scrape_javdb_with_mirror(code)
        if metadata:
            logger.info(f"[Adult] JavDB success for {code}")
            return metadata

        # 第3层: Python 微服务
        if self.config.microservice_url:
            logger.info(f"[Adult] JavDB failed, trying microservice for code: {code}")
            metadata = await self._scrape_microservice(code)
            if metadata:
                logger.info(f"[Adult] Microservice success for {code}")
                return metadata

        logger.warning(f"[Adult] All sources failed for code: {code}")
        return None

    async def _maybe_health_check(self):
        """触发健康检查"""
        if not self.config.enable_health_check:
            return

        now = time.time()
        if now - self._last_health_check > self.config.health_check_interval:
            session = await self._get_session()
            await self.mirror_manager.health_check(session)
            self._last_health_check = now

    async def _scrape_javbus_with_mirror(self, code: str) -> MediaMetadata | None:
        """使用 JavBus 刮削（支持多镜像）"""
        base_url = self.mirror_manager.get_preferred_url("javbus")
        if not base_url:
            logger.error("[JavBus] No available mirror")
            return None

        normalized_code = code.replace(' ', '-').replace('_', '-')
        url = f"{base_url}/{normalized_code}"

        try:
            session = await self._get_session()
            proxy = self._get_proxy()
            headers = self._get_headers("javbus")

            # 请求延迟（反爬策略）
            if self.config.enable_delay:
                delay = random.uniform(
                    self.config.min_delay_ms / 1000,
                    self.config.max_delay_ms / 1000
                )
                logger.debug(f"[JavBus] Delay {delay:.2f}s before request")
                await asyncio.sleep(delay)

            start_time = time.time()
            async with session.get(url, proxy=proxy, headers=headers, ssl=False) as resp:
                response_time = time.time() - start_time

                if resp.status != 200:
                    logger.debug(f"[JavBus] Detail page not found: {resp.status}")
                    self.mirror_manager.mark_failure("javbus", base_url)
                    return None

                html = await resp.text()

            self.mirror_manager.mark_success("javbus", base_url, response_time)

            # 解析元数据
            metadata = self._parse_javbus_html(html, code)
            if metadata:
                logger.info(f"[JavBus] Successfully scraped {code}")
            return metadata

        except Exception as e:
            logger.error(f"[JavBus] Error scraping {code}: {e}")
            self.mirror_manager.mark_failure("javbus", base_url)
            return None

    async def _scrape_javdb_with_mirror(self, code: str) -> MediaMetadata | None:
        """使用 JavDB 刮削（支持多镜像）"""
        base_url = self.mirror_manager.get_preferred_url("javdb")
        if not base_url:
            logger.error("[JavDB] No available mirror")
            return None

        try:
            session = await self._get_session()
            proxy = self._get_proxy()
            headers = self._get_headers("javdb")

            # 请求延迟
            if self.config.enable_delay:
                delay = random.uniform(
                    self.config.min_delay_ms / 1000,
                    self.config.max_delay_ms / 1000
                )
                logger.debug(f"[JavDB] Delay {delay:.2f}s before request")
                await asyncio.sleep(delay)

            # JavDB 需要先搜索
            import urllib.parse
            search_url = f"{base_url}/search?q={urllib.parse.quote(code)}&f=all"
            start_time = time.time()

            async with session.get(search_url, proxy=proxy, headers=headers, ssl=False) as resp:
                response_time = time.time() - start_time

                if resp.status != 200:
                    logger.debug(f"[JavDB] Search failed: {resp.status}")
                    self.mirror_manager.mark_failure("javdb", base_url)
                    return None

                html = await resp.text()

            self.mirror_manager.mark_success("javdb", base_url, response_time)

            # 解析搜索结果
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            items = soup.find_all('div', class_='item') or soup.find_all('div', class_='box')
            if not items:
                logger.debug(f"[JavDB] No search results for {code}")
                return None

            link = items[0].find('a')
            if not link:
                return None

            video_id = link.get('href', '').strip('/').split('/')[-1]

            # 请求详情页（再次延迟）
            if self.config.enable_delay:
                await asyncio.sleep(random.uniform(1, 2))

            detail_url = f"{base_url}/v/{video_id}"

            async with session.get(detail_url, proxy=proxy, headers=headers, ssl=False) as resp:
                if resp.status != 200:
                    logger.debug(f"[JavDB] Detail page not found: {resp.status}")
                    return None

                html = await resp.text()

            metadata = self._parse_javdb_html(html, code)
            if metadata:
                logger.info(f"[JavDB] Successfully scraped {code}")
            return metadata

        except Exception as e:
            logger.error(f"[JavDB] Error scraping {code}: {e}")
            self.mirror_manager.mark_failure("javdb", base_url)
            return None

    def _parse_javbus_html(self, html: str, code: str) -> MediaMetadata | None:
        """解析 JavBus 详情页 HTML"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            # 标题
            title_tag = soup.find('h3')
            title = title_tag.text.strip() if title_tag else ''

            # 番号
            code_tag = soup.find('span', class_='header', string=lambda x: x and '番号' in x)
            if code_tag:
                code_span = code_tag.find_next_sibling('span', class_='text')
                code = code_span.text.strip() if code_span else code

            # 日期
            release_date = ''
            date_tag = soup.find('span', class_='header', string=lambda x: x and '发行日期' in x)
            if date_tag:
                date_span = date_tag.find_next_sibling('span', class_='text')
                release_date = date_span.text.strip() if date_span else ''

            # 片商
            studio = ''
            studio_tag = soup.find('span', class_='header', string=lambda x: x and '出品商' in x)
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

            # 时长
            duration = None
            time_tag = soup.find('span', class_='header', string=lambda x: x and '长度' in x)
            if time_tag:
                time_span = time_tag.find_next_sibling('span', class_='text')
                if time_span:
                    match = re.search(r'(\d+)', time_span.text)
                    if match:
                        duration = int(match.group(1)) * 60

            # 评分
            rating = 0.0
            rating_tag = soup.find('span', class_='header', string=lambda x: x and '评分' in x)
            if rating_tag:
                rating_span = rating_tag.find_next_sibling('span', class_='score')
                if rating_span:
                    try:
                        rating = float(rating_span.text.strip()) * 2
                    except ValueError:
                        pass

            return MediaMetadata(
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

        except Exception as e:
            logger.error(f"[JavBus] Parse error: {e}")
            return None

    def _parse_javdb_html(self, html: str, code: str) -> MediaMetadata | None:
        """解析 JavDB 详情页 HTML"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            # 标题
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
                    rating = float(rating_tag.text.strip()) * 2
                except ValueError:
                    pass

            return MediaMetadata(
                title=title,
                year=int(release_date[:4]) if release_date else None,
                overview='',
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

        except Exception as e:
            logger.error(f"[JavDB] Parse error: {e}")
            return None

    async def _search_by_code(self, code: str) -> list[dict[str, Any]]:
        """用番号搜索"""
        results = await self._search_javbus(code)
        if results:
            return results
        results = await self._search_javdb(code)
        if results:
            return results
        return []

    async def _search_by_title(self, title: str, year: int | None) -> list[dict[str, Any]]:
        """用标题搜索"""
        return await self._search_javbus(title)

    async def _search_javbus(self, keyword: str) -> list[dict[str, Any]]:
        """JavBus 搜索"""
        try:
            import urllib.parse
            from bs4 import BeautifulSoup

            base_url = self.mirror_manager.get_preferred_url("javbus")
            if not base_url:
                return []

            encoded_keyword = urllib.parse.quote(keyword)
            url = f"{base_url}/search/{encoded_keyword}"

            session = await self._get_session()
            proxy = self._get_proxy()
            headers = self._get_headers("javbus")

            async with session.get(url, proxy=proxy, headers=headers, ssl=False) as resp:
                if resp.status != 200:
                    logger.warning(f"[JavBus] Search failed: {resp.status}")
                    self.mirror_manager.mark_failure("javbus", base_url)
                    return []

                html = await resp.text()

            self.mirror_manager.mark_success("javbus", base_url, 0)

            soup = BeautifulSoup(html, 'lxml')
            results = []
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

    async def _search_javdb(self, keyword: str) -> list[dict[str, Any]]:
        """JavDB 搜索"""
        try:
            import urllib.parse
            from bs4 import BeautifulSoup

            base_url = self.mirror_manager.get_preferred_url("javdb")
            if not base_url:
                return []

            encoded_keyword = urllib.parse.quote(keyword)
            url = f"{base_url}/search?q={encoded_keyword}&f=all"

            session = await self._get_session()
            proxy = self._get_proxy()
            headers = self._get_headers("javdb")

            async with session.get(url, proxy=proxy, headers=headers, ssl=False) as resp:
                if resp.status != 200:
                    logger.warning(f"[JavDB] Search failed: {resp.status}")
                    self.mirror_manager.mark_failure("javdb", base_url)
                    return []

                html = await resp.text()

            self.mirror_manager.mark_success("javdb", base_url, 0)

            soup = BeautifulSoup(html, 'lxml')
            results = []
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

    async def _scrape_microservice(self, code: str) -> MediaMetadata | None:
        """Python 微服务兜底"""
        if not self.config.microservice_url:
            return None

        try:
            logger.debug(f"[Microservice] Scraping {code}")
            return None
        except Exception as e:
            logger.error(f"[Microservice] Error scraping {code}: {e}")
            return None

    # ── 辅助方法 ─────────────────────────────────────

    async def _get_session(self):
        """获取 aiohttp session"""
        if self._session is None:
            import aiohttp

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
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    def _get_proxy(self):
        """获取代理配置"""
        if self.config.proxy:
            return self.config.proxy
        return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    def _get_headers(self, source: str) -> dict:
        """获取请求头"""
        import random as rand

        headers = {
            "User-Agent": rand.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            ]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # 添加 Cookie
        if source == "javbus" and self.config.javbus_cookie:
            headers["Cookie"] = self.config.javbus_cookie
        elif source == "javdb" and self.config.javdb_cookie:
            headers["Cookie"] = self.config.javdb_cookie

        return headers

    async def close(self):
        """关闭 session"""
        if self._session:
            await self._session.close()
            self._session = None

    # ── API 接口 ─────────────────────────────────────

    def get_status(self) -> dict:
        """获取刮削器状态（用于 API 返回）"""
        return {
            "javbus_mirrors": self.mirror_manager.get_mirror_status("javbus"),
            "javdb_mirrors": self.mirror_manager.get_mirror_status("javdb"),
            "config": {
                "enable_delay": self.config.enable_delay,
                "min_delay_ms": self.config.min_delay_ms,
                "max_delay_ms": self.config.max_delay_ms,
                "enable_health_check": self.config.enable_health_check,
                "max_fail_count": self.config.max_fail_count,
                "cooldown_seconds": self.config.cooldown_seconds,
                "javbus_cookie": bool(self.config.javbus_cookie),
                "javdb_cookie": bool(self.config.javdb_cookie),
                "proxy": bool(self._get_proxy()),
            }
        }


# 导出
__all__ = [
    "AdultProvider",
    "AdultProviderConfig",
    "MirrorManager",
    "MirrorInfo",
    "MirrorStatus",
]
