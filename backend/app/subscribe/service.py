"""
订阅模块业务逻辑
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.subscribe.models import (
    NotifyChannel,
    Site,
    Subscription,
    SubscriptionLog,
)
from app.subscribe.notifier import NotifierService, create_channel_from_config
from app.subscribe.schemas import (
    NotifyChannelCreate,
    NotifyChannelOut,
    NotifyChannelUpdate,
    ResourceOut,
    SiteCreate,
    SiteOut,
    SiteUpdate,
    SubscriptionCreate,
    SubscriptionLogOut,
    SubscriptionOut,
    SubscriptionUpdate,
)
from app.subscribe.site_adapter import SiteResourceBrowser, create_site_adapter

logger = logging.getLogger(__name__)


# ── 画质优先级定义 ──
_RESOLUTION_PRIORITY = {
    # 4K/HDR
    "2160p": 100, "4k": 100, "uhd": 100,
    "1080p": 80, "fhd": 80,
    "720p": 60, "hd": 60,
    "480p": 40, "sd": 40,
    "other": 10,
}

# HDR 优先级加成
_HDR_BONUS = 5


def _is_title_relevant(keyword: str, title: str) -> bool:
    """检查搜索结果标题是否与关键词真正相关
    
    避免 "hoppers" 误匹配 "grasshoppers" 这类子串误判。
    中文关键词：标题包含关键词即认为相关（允许部分匹配）
    """
    if not keyword or not title:
        return False
    keyword_lower = keyword.lower().strip()
    title_lower = title.lower()
    
    # 中文关键词（包含中文字符）
    if re.search(r"[\u4e00-\u9fff]", keyword_lower):
        is_match = keyword_lower in title_lower
        logger.debug(f"[_is_title_relevant] 中文关键词 '{keyword}' vs '{title[:50]}': {is_match}")
        return is_match
    
    # 英文关键词：使用负向前瞻/回顾断言防止子串误匹配
    # 例如 "test" 不应匹配 "Testing"、"atest"、"grasshoppers"
    # (?<!\w) 确保前面不是字母/数字/下划线
    # (?!\w)  确保后面不是字母/数字/下划线
    try:
        escaped_kw = re.escape(keyword_lower)
        # ⚠️ 必须用 r"..." raw string
        pattern = r"(?<!\w)" + escaped_kw + r"(?!\w)"
        if re.search(pattern, title_lower):
            return True
    except re.error:
        pass
    
    # 降级：如果词边界匹配失败，使用简单的包含判断
    if keyword_lower in title_lower:
        logger.debug(f"[_is_title_relevant] 英文关键词降级匹配: '{keyword}' in '{title[:50]}'")
        return True
    
    return False


def _parse_resolution(title: str) -> int:
    """从标题中解析画质优先级分数"""
    title_lower = title.lower()
    
    # HDR/DoVi 加成
    hdr_bonus = 0
    if any(x in title_lower for x in ["hdr", "dolby", "dovi", "dv"]):
        hdr_bonus = _HDR_BONUS
    
    # 解析分辨率
    resolution = "other"
    if "2160" in title_lower or "4k" in title_lower or "uhd" in title_lower:
        resolution = "2160p"
    elif "1080" in title_lower:
        resolution = "1080p"
    elif "720" in title_lower:
        resolution = "720p"
    elif "480" in title_lower or "576" in title_lower:
        resolution = "480p"
    
    return _RESOLUTION_PRIORITY.get(resolution, 0) + hdr_bonus


def _extract_base_title(title: str) -> str:
    """从完整标题中提取电影/剧集基础名称（去除分辨率、编码等信息）"""
    # 常见后缀模式
    patterns_to_remove = [
        r'\s*\(.*?\)\s*$',  # (2024) 等年份括号
        r'\s*【.*?】\s*$',   # 【中文字幕】等
        r'\s*\[.*?\]\s*$',   # [中字] 等
        r'\s+2160[pP]?\s*.*$',
        r'\s+4k\s*.*$',
        r'\s+1080[pP]?\s*.*$',
        r'\s+720[pP]?\s*.*$',
        r'\s+480[pP]?\s*.*$',
        r'\s+HDR.*$',
        r'\s+Dolby.*$',
        r'\s+Bluray.*$',
        r'\s+WEB.*$',
        r'\s+WEB-DL.*$',
        r'\s+DVD.*$',
        r'\s+BDRip.*$',
        r'\s+DVDRip.*$',
        r'\s+HC\s*.*$',
        r'\s+TC.*$',
        r'\s+TS.*$',
        r'\s+Cam.*$',
    ]
    
    result = title
    for pattern in patterns_to_remove:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    
    # 去除首尾空白和特殊字符
    result = result.strip().rstrip("-_")
    
    # 如果去得太狠，至少返回原始标题
    if not result:
        return title[:50]  # 取前50字符作为基础名
    
    return result[:80]  # 限制长度


def _is_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _extract_english_title_from_results(resources: list) -> str | None:
    """从搜索结果中提取英文标题
    
    当使用中文关键词搜索到资源但标题全是英文时，
    尝试提取一个合适的英文标题用于再搜索。
    """
    if not resources:
        return None
    
    for resource in resources:
        title = getattr(resource, 'title', '') or ''
        if not title:
            continue
        
        # 跳过纯中文标题
        if re.search(r"[\u4e00-\u9fff]", title):
            continue
        
        # 提取可能的英文名称
        # 常见格式: "Chang An 2023 BluRay 1080p" -> "Chang An"
        #         "The Grandmaster 2013" -> "The Grandmaster"
        
        # 去除常见后缀
        cleaned = re.sub(
            r'\s*(19|20)\d{2}\s*.*$',  # 年份及之后
            '', title, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r'\s*(bluray|webrip|web-dl|dvdrip|bdrip|hdtv|cam|ts|tc).*$',
            '', cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r'\s*(2160p|1080p|720p|480p|4k|uhd|fhd|hd|sd).*$',
            '', cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r'\s*(x264|x265|xvid|hevc|avc|aac|ac3|dts|mp3).*$',
            '', cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r'\s*\[.*?\]|\s*【.*?】', '', cleaned  # 去除括号内容
        )
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 取第一部分作为英文名
        parts = cleaned.split()
        if parts:
            # 取前几个有意义的词
            english_name = ' '.join(parts[:4])  # 最多4个词
            if english_name and len(english_name) >= 3:
                logger.info(f"[_extract_english_title] 从 '{title[:40]}' 提取英文名: '{english_name}'")
                return english_name
    
    return None


class SubscribeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 站点管理 ──
    async def list_sites(self) -> list[SiteOut]:
        result = await self.db.execute(select(Site).order_by(Site.priority, Site.id))
        return [SiteOut.model_validate(s) for s in result.scalars().all()]

    async def create_site(self, data: SiteCreate) -> SiteOut:
        site = Site(**data.model_dump())
        self.db.add(site)
        await self.db.flush()
        await self.db.refresh(site)
        await self.db.commit()  # 提交事务
        return SiteOut.model_validate(site)

    async def update_site(self, site_id: int, data: SiteUpdate) -> SiteOut:
        site = await self._get_site(site_id)
        updates = data.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(site, k, v)
        await self.db.flush()
        await self.db.refresh(site)
        await self.db.commit()  # 提交事务
        return SiteOut.model_validate(site)

    async def delete_site(self, site_id: int):
        site = await self._get_site(site_id)
        await self.db.delete(site)
        await self.db.flush()
        await self.db.commit()  # 提交事务

    async def test_site(self, site_id: int) -> dict:
        site = await self._get_site(site_id)
        adapter = create_site_adapter(site)
        connected, message = await adapter.test_connection()
        site.login_status = "ok" if connected else "failed"
        site.last_check = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.commit()  # 提交事务
        return {"connected": connected, "message": message}

    async def browse_site_resource(
        self,
        site_id: int,
        keyword: str | None = None,
        category: str | None = None,
        page: int = 0,
    ) -> dict:
        """浏览站点资源（MoviePilot API 参考）

        支持按关键字/分类分页浏览站点资源。
        """
        site = await self._get_site(site_id)
        browser = SiteResourceBrowser(site)
        resources, total = await browser.browse(keyword, category, page)

        return {
            "site_id": site_id,
            "site_name": site.name,
            "keyword": keyword,
            "category": category,
            "page": page,
            "total": total,
            "resources": [
                ResourceOut(
                    site_name=r.site_name,
                    site_id=r.site_id,
                    title=r.title,
                    size=r.size,
                    seeders=r.seeders,
                    leechers=r.leechers,
                    upload_time=r.upload_time,
                    category=r.category,
                    free=r.free,
                    download_url=r.download_url,
                )
                for r in resources
            ],
        }

    async def refresh_site_userdata(self, site_id: int) -> dict:
        """刷新站点用户数据（MoviePilot API 参考）

        获取用户在站点的上传/下载量、做种数等信息。
        注意：不同站点实现方式不同，此为通用实现。
        """
        site = await self._get_site(site_id)
        try:
            adapter = create_site_adapter(site)

            # 尝试调用站点适配器的用户数据获取方法
            if hasattr(adapter, "get_userdata"):
                userdata = await adapter.get_userdata()
                return {
                    "site_id": site_id,
                    "site_name": site.name,
                    "success": True,
                    "data": userdata,
                }

            # 默认返回站点基本信息
            return {
                "site_id": site_id,
                "site_name": site.name,
                "success": True,
                "data": {
                    "site_url": site.base_url,
                    "last_check": site.last_check.isoformat() if site.last_check else None,
                    "login_status": site.login_status,
                },
                "message": "该站点类型暂不支持详细用户数据获取",
            }
        except Exception as e:
            logger.error(f"Refresh site userdata failed for {site.name}: {e}")
            return {
                "site_id": site_id,
                "site_name": site.name,
                "success": False,
                "error": str(e),
            }

    async def search_sites(
        self, keyword: str, site_ids: list[int] | None = None
    ) -> list[ResourceOut]:
        """在所有已启用站点搜索资源"""
        query = select(Site).where(Site.enabled == True)
        if site_ids:
            query = query.where(Site.id.in_(site_ids))
        query = query.order_by(Site.priority)

        result = await self.db.execute(query)
        sites = result.scalars().all()
        
        if not sites:
            logger.warning(f"[站点搜索] 没有已启用的站点，关键词: {keyword}")
            return []

        all_resources = []
        for site in sites:
            try:
                adapter = create_site_adapter(site)
                resources = await adapter.search(keyword)
                if resources:
                    logger.info(f"[站点搜索] {site.name} 返回 {len(resources)} 个结果")
                    for r in resources:
                        all_resources.append(ResourceOut(
                            site_name=r.site_name,
                            site_id=r.site_id,
                            title=r.title,
                            size=r.size,
                            seeders=r.seeders,
                            leechers=r.leechers,
                            upload_time=r.upload_time,
                            category=r.category,
                            free=r.free,
                            download_url=r.download_url,
                        ))
                else:
                    logger.info(f"[站点搜索] {site.name} 返回 0 个结果")
            except Exception as e:
                logger.error(f"[站点搜索] {site.name} 搜索失败: {e}")

        # 按做种数降序排列
        all_resources.sort(key=lambda r: r.seeders, reverse=True)
        return all_resources

    # ── 订阅管理 ──
    async def list_subscriptions(self, status: str | None = None) -> list[SubscriptionOut]:
        query = select(Subscription).order_by(Subscription.created_at.desc())
        if status:
            query = query.where(Subscription.status == status)
        result = await self.db.execute(query)
        subs = result.scalars().all()

        # 批量加载最近一条日志（每个订阅一条）
        sub_ids = [s.id for s in subs]
        log_map: dict[int, SubscriptionLog] = {}
        if sub_ids:
            log_query = (
                select(SubscriptionLog)
                .where(SubscriptionLog.subscription_id.in_(sub_ids))
                .order_by(SubscriptionLog.created_at.desc())
            )
            logs = (await self.db.execute(log_query)).scalars().all()
            # 保留每个订阅的第一条日志（即最近一条）
            seen = set()
            for log in logs:
                if log.subscription_id not in seen:
                    log_map[log.subscription_id] = log
                    seen.add(log.subscription_id)

        out = []
        for sub in subs:
            sub_out = self._sub_to_out(sub)
            log = log_map.get(sub.id)
            if log:
                sub_out.last_log = SubscriptionLogOut(
                    action=log.action,
                    resource_title=log.resource_title,
                    message=log.message,
                    success=(log.action == "download"),
                    created_at=log.created_at,
                )
            out.append(sub_out)
        return out

    async def create_subscription(self, data: SubscriptionCreate) -> SubscriptionOut:
        sub = Subscription(
            name=data.name,
            original_name=data.original_name,
            tmdb_id=data.tmdb_id,
            media_type=data.media_type,
            year=data.year,
            quality_filter=json.dumps(data.quality_filter, ensure_ascii=False),
            min_size=data.min_size,
            max_size=data.max_size,
            exclude_keywords=json.dumps(data.exclude_keywords, ensure_ascii=False),
            include_keywords=json.dumps(data.include_keywords, ensure_ascii=False),
        )
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        
        # 临时禁用自动搜索（排查问题）
        # import asyncio
        # asyncio.create_task(self._auto_search_after_create(sub.id))
        
        return self._sub_to_out(sub)
    
    async def _auto_search_after_create(self, sub_id: int):
        """创建订阅后自动搜索的后台任务"""
        try:
            # 等待一下，确保数据库事务已提交
            import asyncio
            await asyncio.sleep(1)
            
            # 重新获取数据库会话
            from app.database import get_session_factory
            from sqlalchemy.ext.asyncio import AsyncSession
            
            session_factory = get_session_factory()
            async with session_factory() as new_db:
                service = SubscriptionService(new_db)
                result = await service.process_subscription(sub_id)
                logger.info(f"[自动搜索] 订阅 {sub_id} 搜索完成: {result}")
        except Exception as e:
            logger.error(f"[自动搜索] 订阅 {sub_id} 搜索失败: {e}")

    async def update_subscription(self, sub_id: int, data: SubscriptionUpdate) -> SubscriptionOut:
        sub = await self._get_subscription(sub_id)
        updates = data.model_dump(exclude_unset=True)
        for k, v in updates.items():
            if isinstance(v, list):
                setattr(sub, k, json.dumps(v, ensure_ascii=False))
            else:
                setattr(sub, k, v)
        await self.db.flush()
        await self.db.refresh(sub)
        return self._sub_to_out(sub)

    async def delete_subscription(self, sub_id: int):
        sub = await self._get_subscription(sub_id)
        await self.db.delete(sub)
        await self.db.flush()

    async def get_subscription_by_media(
        self,
        mediaid: str,
        season: int | None = None,
        title: str | None = None,
    ) -> list[SubscriptionOut]:
        """按媒体ID查询订阅（MoviePilot API 参考）

        支持 tmdb:/douban:/bangumi: 前缀格式。
        """
        # 解析 mediaid
        media_type = "movie"
        clean_id = mediaid

        if mediaid.startswith("tmdb:"):
            clean_id = mediaid[5:]
            media_type = "tv"  # 可能是剧集，需要进一步判断
        elif mediaid.startswith("douban:"):
            clean_id = mediaid[7:]
        elif mediaid.startswith("bangumi:"):
            clean_id = mediaid[8:]
            media_type = "tv"

        query = select(Subscription).where(Subscription.tmdb_id == clean_id)
        if season is not None:
            # 剧集需要匹配季号
            query = query.where(Subscription.name.contains(f"第{season}季") |
                               Subscription.name.contains(f"S{season:02d}") |
                               Subscription.name.contains(f"Season {season}"))
        if title:
            query = query.where(Subscription.name.contains(title))

        result = await self.db.execute(query)
        subs = result.scalars().all()
        return [self._sub_to_out(s) for s in subs]

    async def share_subscription(self, sub_id: int, note: str | None = None) -> dict:
        """分享订阅（MoviePilot API 参考）

        创建订阅分享记录，供其他用户复制。
        """
        sub = await self._get_subscription(sub_id)
        # 这里可以扩展为存储分享记录到数据库
        return {
            "subscribe_id": sub.id,
            "name": sub.name,
            "tmdb_id": sub.tmdb_id,
            "media_type": sub.media_type,
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "share_url": f"/api/subscribe/fork/{sub.id}",  # 分享链接
        }

    async def fork_subscription(self, source_sub_id: int, user_id: int | None = None) -> SubscriptionOut:
        """复制订阅（MoviePilot API 参考）

        从分享链接复制订阅到本地。
        """
        source_sub = await self._get_subscription(source_sub_id)

        # 创建新的订阅副本
        new_sub = Subscription(
            name=source_sub.name,
            tmdb_id=source_sub.tmdb_id,
            media_type=source_sub.media_type,
            year=source_sub.year,
            quality_filter=source_sub.quality_filter,
            min_size=source_sub.min_size,
            max_size=source_sub.max_size,
            exclude_keywords=source_sub.exclude_keywords,
            include_keywords=source_sub.include_keywords,
            status="active",
        )
        self.db.add(new_sub)
        await self.db.flush()
        await self.db.refresh(new_sub)

        await self._log(new_sub.id, "fork", message=f"从订阅 #{source_sub_id} 复制")

        return self._sub_to_out(new_sub)

    async def process_subscription(self, sub_id: int) -> dict:
        """手动触发订阅搜索"""
        sub = await self._get_subscription(sub_id)
        return await self._process_single_subscription(sub)

    async def process_all_subscriptions(self) -> dict:
        """处理所有活跃订阅"""
        result = {"searched": 0, "downloaded": 0, "skipped": 0, "errors": 0}
        query = select(Subscription).where(Subscription.status == "active")
        subs = (await self.db.execute(query)).scalars().all()

        for sub in subs:
            try:
                sub_result = await self._process_single_subscription(sub)
                result["searched"] += sub_result.get("searched", 0)
                result["downloaded"] += sub_result.get("downloaded", 0)
                result["skipped"] += sub_result.get("skipped", 0)
                result["errors"] += sub_result.get("errors", 0)
                sub.last_search = datetime.now(timezone.utc)
                await self.db.flush()
            except Exception as e:
                result["errors"] += 1
                logger.error(f"Process subscription {sub.name} failed: {e}")
                await self._log(sub.id, "error", message=str(e))

        return result

    async def _process_single_subscription(self, sub: Subscription) -> dict:
        """搜索单个订阅并自动下载"""
        # 添加详细日志
        logger.info(f"[订阅搜索] 开始处理订阅: id={sub.id}, name={sub.name!r}, "
                    f"original_name={sub.original_name!r}, tmdb_id={sub.tmdb_id}, "
                    f"media_type={sub.media_type}")
        
        result = {"searched": 0, "downloaded": 0, "skipped": 0, "errors": 0}

        # 解析过滤条件
        quality_filter = json.loads(sub.quality_filter) if sub.quality_filter else []
        exclude_kw = json.loads(sub.exclude_keywords) if sub.exclude_keywords else []
        include_kw = json.loads(sub.include_keywords) if sub.include_keywords else []

        # ── 搜索策略：优先英文标题，中文兜底 ──
        search_keywords: list[str] = []
        
        # 1. 优先使用订阅时保存的 original_name（前端从 TMDB 搜索结果直接获取的英文名）
        if sub.original_name and sub.original_name != sub.name and self._is_english(sub.original_name):
            search_keywords.append(sub.original_name)
            logger.info(f"[订阅搜索] {sub.name} -> 使用 original_name: {sub.original_name}")
        # 2. 如果没有 original_name 或不是英文，通过 TMDB API 获取真正的英文标题
        if sub.tmdb_id and not any(self._is_english(k) for k in search_keywords):
            try:
                from app.system.api_config_service import ApiConfigService
                from app.media.scraper import TMDbClient

                api_config_service = ApiConfigService(self.db)
                tmdb_config = await api_config_service.get_effective_config("tmdb")
                tmdb_api_key = tmdb_config.get("api_key", "")
                tmdb_base_url = tmdb_config.get("base_url") or None

                if tmdb_api_key:
                    tmdb_client = TMDbClient(
                        custom_api_key=tmdb_api_key,
                        custom_base_url=tmdb_base_url,
                    )
                    english_title = await tmdb_client.get_english_title(sub.tmdb_id, sub.media_type)
                    if english_title and english_title != sub.name:
                        search_keywords.append(english_title)
                        logger.info(f"[订阅搜索] {sub.name} -> TMDB 英文标题: {english_title}")
            except Exception as e:
                logger.warning(f"[订阅搜索] 获取 TMDB 英文标题失败 {sub.name}: {e}")

        # 始终加入原始中文名作为兜底
        if sub.name not in search_keywords:
            search_keywords.append(sub.name)

        # 搜索所有站点（优先英文名，英文名搜不到再试中文名）
        all_resources = []
        for keyword in search_keywords:
            try:
                logger.info(f"[订阅搜索] 使用关键词 '{keyword}' 搜索...")
                resources = await self.search_sites(keyword)
                logger.info(f"[订阅搜索] 关键词 '{keyword}' 返回 {len(resources)} 个结果")

                # 过滤标题不相关的资源（避免 hoppers 误匹配 grasshoppers）
                relevant_resources = [
                    r for r in resources
                    if _is_title_relevant(keyword, r.title)
                ]
                logger.info(
                    f"[订阅搜索] 关键词 '{keyword}' "
                    f"过滤后 {len(relevant_resources)} 个相关结果"
                )

                # ── 中文关键词 + 英文结果 特殊处理 ──
                # 如果用中文关键词搜到资源但标题都是英文（如 Chang An），
                # 自动提取英文标题再搜索一次，提高搜索成功率
                if (_is_chinese(keyword) 
                    and resources 
                    and not relevant_resources):
                    # 从搜索结果中提取英文标题
                    extracted_english = _extract_english_title_from_results(resources)
                    if extracted_english:
                        logger.info(
                            f"[订阅搜索] 中文关键词 '{keyword}' 搜到 {len(resources)} 个英文标题资源，"
                            f"提取英文标题 '{extracted_english}' 再搜索..."
                        )
                        try:
                            second_resources = await self.search_sites(extracted_english)
                            second_relevant = [
                                r for r in second_resources
                                if _is_title_relevant(extracted_english, r.title)
                            ]
                            if second_relevant:
                                all_resources.extend(second_relevant)
                                logger.info(
                                    f"[订阅搜索] 英文标题 '{extracted_english}' "
                                    f"返回 {len(second_relevant)} 个相关结果"
                                )
                                # 用英文标题搜到后停止，避免中文名再搜一遍
                                continue
                        except Exception as e2:
                            logger.error(f"[订阅搜索] 英文标题再搜索失败: {e2}")

                if relevant_resources:
                    all_resources.extend(relevant_resources)
                    # 英文名搜到结果就停止
                    if not self._is_english(keyword) or keyword == search_keywords[-1]:
                        # 中文名或最后一个关键词，收集所有结果
                        continue
                    else:
                        logger.info(f"[订阅搜索] 英文名 '{keyword}' 搜到 {len(resources)} 个，停止搜索")
                        break
            except Exception as e:
                logger.error(f"[订阅搜索] 关键词 '{keyword}' 搜索失败: {e}")

        # 去重（按标题）
        seen_titles = set()
        unique_resources = []
        for r in all_resources:
            if r.title not in seen_titles:
                seen_titles.add(r.title)
                unique_resources.append(r)

        resources = unique_resources
        result["searched"] = len(resources)
        logger.info(f"[订阅搜索] {sub.name} 共搜到 {len(resources)} 个不重复资源")

        # ── 按画质分组：每个电影只选一个最高画质版本 ──
        # 先过滤出符合条件的资源
        candidates: list[tuple[ResourceOut, str, int]] = []  # (resource, base_title, priority)

        for resource in resources:
            # 大小过滤
            size_mb = resource.size / (1024 * 1024)
            if sub.min_size > 0 and size_mb < sub.min_size:
                logger.info(f"[订阅下载] 跳过（太小）: {resource.title[:40]}")
                continue
            if sub.max_size > 0 and size_mb > sub.max_size:
                logger.info(f"[订阅下载] 跳过（太大）: {resource.title[:40]}")
                continue

            # 排除关键词
            if any(kw.lower() in resource.title.lower() for kw in exclude_kw):
                logger.info(f"[订阅下载] 跳过（排除关键词）: {resource.title[:40]}")
                continue

            # 包含关键词
            if include_kw and not any(kw.lower() in resource.title.lower() for kw in include_kw):
                logger.info(f"[订阅下载] 跳过（不包含关键词）: {resource.title[:40]}")
                continue

            # 画质过滤
            if quality_filter:
                matched_quality = any(
                    q.lower() in resource.title.lower() for q in quality_filter
                )
                if not matched_quality:
                    logger.info(f"[订阅下载] 跳过（画质不匹配）: {resource.title[:40]}")
                    continue

            # 没有做种的跳过
            if resource.seeders == 0:
                logger.info(f"[订阅下载] 跳过（无做种）: {resource.title[:40]}")
                continue

            # 计算画质优先级
            base_title = _extract_base_title(resource.title)
            resolution_priority = _parse_resolution(resource.title)
            # 综合分数 = 画质优先级 * 1000 + 做种数（确保同画质按做种数排序）
            total_priority = resolution_priority * 1000 + resource.seeders
            
            candidates.append((resource, base_title, total_priority))
            logger.info(f"[订阅下载] 候选: {resource.title[:50]} | 画质:{resolution_priority} | 做种:{resource.seeders}")

        if not candidates:
            logger.info(f"[订阅下载] {sub.name} 没有符合条件的候选资源")
            await self._log(sub.id, "search", message=f"搜索了 {result['searched']} 个资源，无匹配")
            return result

        # 按基础标题分组，每组只选最高画质的一个
        title_groups: dict[str, list[tuple[ResourceOut, str, int]]] = defaultdict(list)
        for r, base_title, priority in candidates:
            title_groups[base_title].append((r, base_title, priority))

        # 每个基础标题选最优资源
        best_per_title: list[tuple[ResourceOut, str, int]] = []
        for base_title, items in title_groups.items():
            # 同组内按优先级降序排序
            items.sort(key=lambda x: x[2], reverse=True)
            best_per_title.append(items[0])
            logger.info(f"[订阅下载] 选中 '{base_title[:30]}' 的最高画质: {items[0][0].title[:50]}")

        # 按画质和做种数综合排序，选出最终要下载的资源
        best_per_title.sort(key=lambda x: x[2], reverse=True)
        target_resource = best_per_title[0][0]
        logger.info(f"[订阅下载] 最终选择: {target_resource.title[:60]}")

        # ── 执行下载（只下载一个） ──
        try:
            # 调用下载服务添加任务
            from app.download.models import DownloadClient
            dl_result = await self.db.execute(
                select(DownloadClient).where(DownloadClient.enabled == True).limit(1)
            )
            client = dl_result.scalar_one_or_none()
            if not client:
                result["errors"] += 1
                await self._log(sub.id, "error", message="没有可用的下载客户端")
                return result

            # 获取真实下载链接（馒头等站点需要先调用 genDlToken API）
            download_url = target_resource.download_url
            torrent_content: bytes | None = None  # 存储种子文件内容
            dl_error_msg: str | None = None

            try:
                site_result = await self.db.execute(
                    select(Site).where(Site.id == target_resource.site_id)
                )
                site = site_result.scalar_one_or_none()
                if site:
                    site_adapter = create_site_adapter(site)
                    from app.subscribe.models import SiteResource
                    site_res = SiteResource(
                        download_url=target_resource.download_url,
                        torrent_url=target_resource.download_url,
                    )
                    resolved_url, resolve_error = await site_adapter.get_download_url(site_res)

                    if resolved_url:
                        # 检查是否是种子内容（TORRENT: 前缀）
                        if resolved_url.startswith("TORRENT:"):
                            # Base64 编码的种子文件，需要在 QB 适配器中处理
                            import base64
                            try:
                                torrent_content = base64.b64decode(resolved_url[8:])
                                logger.info(f"[订阅下载] 成功解码种子文件 (大小: {len(torrent_content)} bytes)")
                                download_url = resolved_url
                            except Exception as b64_e:
                                dl_error_msg = f"种子文件解码失败: {b64_e}"
                                logger.error(f"[订阅下载] {dl_error_msg}")
                                download_url = ""
                        elif "genDlToken" in resolved_url:
                            # genDlToken 返回了 API 端点而不是下载链接
                            dl_error_msg = (
                                f"genDlToken 返回了无效链接（{resolved_url[:60]}...），"
                                f"可能是 API Key 权限不足，请检查【站点设置→M-Team→API Key】"
                            )
                            download_url = ""
                            logger.error(f"[订阅下载] {dl_error_msg}")
                        else:
                            download_url = resolved_url
                            logger.info(f"[订阅下载] genDlToken 解析成功: {resolved_url[:80]}")
                    else:
                        # genDlToken 失败时的详细错误处理
                        site_base_url = "M-Team"
                        try:
                            _site_result = await self.db.execute(
                                select(Site).where(Site.id == target_resource.site_id)
                            )
                            _site = _site_result.scalar_one_or_none()
                            if _site:
                                site_base_url = _site.base_url.rstrip("/")
                        except Exception:
                            pass

                        if target_resource.download_url and target_resource.download_url.startswith("http"):
                            # 检查是否是 M-Team 的 genDlToken API URL
                            if "/genDlToken" in target_resource.download_url:
                                dl_error_msg = (
                                    f"M-Team genDlToken 下载失败 ({resolve_error})。"
                                    f"请检查: 1) API Key 是否正确 2) 是否已登录 {site_base_url} 3) API Key 是否包含下载权限。"
                                    f"可尝试登录 {site_base_url}/api/swagger-ui.html 用相同 Key 测试接口。"
                                )
                                download_url = ""  # ⚠️ 重要：不将 genDlToken API URL 传给 QB
                                logger.error(f"[订阅下载] {dl_error_msg}")
                            else:
                                # 其他站点的直链，尝试使用
                                logger.info(
                                    f"[订阅下载] genDlToken 失败，尝试直接使用原始下载 URL: "
                                    f"{target_resource.download_url[:80]}"
                                )
                                download_url = target_resource.download_url
                                dl_error_msg = None  # 兜底成功
                        else:
                            dl_error_msg = f"下载链接解析失败（{resolve_error}），请检查站点配置"
            except Exception as url_e:
                dl_error_msg = f"下载链接解析失败: {url_e}"
                logger.warning(f"[订阅下载] Resolve download URL failed: {url_e}")

            # 无论成功失败，都创建下载任务记录
            from app.download.clients import create_client_adapter
            from app.download.models import DownloadTask

            torrent_hash = ""
            try:
                # 实际调用下载客户端添加种子
                dl_adapter = create_client_adapter(
                    client.client_type,
                    client.host,
                    client.port,
                    client.username or "",
                    client.password or "",
                )
                await dl_adapter.connect()
                torrent_hash = await dl_adapter.add_torrent(
                    url=download_url,
                    save_path=None,
                    category=client.category,
                )
                logger.info(f"[订阅下载] 成功添加到 qBittorrent: {torrent_hash}")
            except Exception as e:
                dl_error_msg = f"下载客户端添加失败: {e}"
                logger.error(f"[订阅下载] Failed to add torrent: {e}")

            # 创建下载任务记录
            task = DownloadTask(
                client_id=client.id,
                subscription_id=sub.id,
                torrent_name=target_resource.title[:200],
                torrent_url=target_resource.download_url,
                info_hash=torrent_hash if dl_error_msg is None else "",
                save_path="",
                status="failed" if dl_error_msg else "downloading",
                message=dl_error_msg,
            )
            self.db.add(task)
            await self.db.flush()

            if dl_error_msg:
                result["errors"] += 1
                await self._log(
                    sub.id, "error", resource_title=target_resource.title,
                    message=f"[下载管理] {dl_error_msg}",
                )
            else:
                # 下载成功
                sub.total_downloaded += 1
                await self.db.flush()
                result["downloaded"] += 1
                await self._log(
                    sub.id, "download", resource_title=target_resource.title,
                    message=f"已添加下载: {target_resource.title[:50]}",
                )

        except Exception as e:
            result["errors"] += 1
            logger.error(f"[订阅下载] Unexpected error: {e}")
            await self._log(sub.id, "error", resource_title=target_resource.title, message=str(e))

        return result

    async def pull_rss(self) -> dict:
        """拉取所有站点的 RSS"""
        result = {"sites": 0, "resources": 0}
        sites = (await self.db.execute(
            select(Site).where(Site.enabled == True, Site.rss_url != None)
        )).scalars().all()

        for site in sites:
            try:
                adapter = create_site_adapter(site)
                resources = await adapter.get_rss(site.rss_url)
                result["sites"] += 1
                result["resources"] += len(resources)
                site.last_check = datetime.now(timezone.utc)
                await self.db.flush()
            except Exception as e:
                logger.error(f"RSS pull {site.name} failed: {e}")

        return result

    # ── 通知渠道 ──
    async def list_notify_channels(self) -> list[NotifyChannelOut]:
        result = await self.db.execute(select(NotifyChannel).order_by(NotifyChannel.id))
        return [self._channel_to_out(c) for c in result.scalars().all()]

    async def create_notify_channel(self, data: NotifyChannelCreate) -> NotifyChannelOut:
        channel = NotifyChannel(
            name=data.name,
            channel_type=data.channel_type,
            config=json.dumps(data.config),
            enabled=data.enabled,
            events=json.dumps(data.events),
        )
        self.db.add(channel)
        await self.db.flush()
        await self.db.refresh(channel)
        return self._channel_to_out(channel)

    async def update_notify_channel(self, channel_id: int, data: NotifyChannelUpdate) -> NotifyChannelOut:
        channel = await self._get_notify_channel(channel_id)
        if data.name is not None:
            channel.name = data.name
        if data.config is not None:
            channel.config = json.dumps(data.config)
        if data.enabled is not None:
            channel.enabled = data.enabled
        if data.events is not None:
            channel.events = json.dumps(data.events)
        await self.db.flush()
        await self.db.refresh(channel)
        return self._channel_to_out(channel)

    async def delete_notify_channel(self, channel_id: int):
        channel = await self._get_notify_channel(channel_id)
        await self.db.delete(channel)
        await self.db.flush()

    async def test_notify_channel(self, channel_id: int) -> dict:
        channel = await self._get_notify_channel(channel_id)
        config = json.loads(channel.config)
        try:
            notify = create_channel_from_config(channel.channel_type, config)
            success = await notify.send("MediaStation 测试", "通知渠道测试成功 ✓", "system_error")
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 辅助 ──
    async def _get_site(self, site_id: int) -> Site:
        result = await self.db.execute(select(Site).where(Site.id == site_id))
        site = result.scalar_one_or_none()
        if not site:
            raise NotFoundError("Site", site_id)
        return site

    async def _get_subscription(self, sub_id: int) -> Subscription:
        result = await self.db.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError("Subscription", sub_id)
        return sub

    async def _get_notify_channel(self, channel_id: int) -> NotifyChannel:
        result = await self.db.execute(select(NotifyChannel).where(NotifyChannel.id == channel_id))
        ch = result.scalar_one_or_none()
        if not ch:
            raise NotFoundError("NotifyChannel", channel_id)
        return ch

    async def _log(
        self, sub_id: int, action: str,
        resource_title: str | None = None, message: str | None = None,
    ):
        log = SubscriptionLog(
            subscription_id=sub_id, action=action,
            resource_title=resource_title, message=message,
        )
        self.db.add(log)
        await self.db.flush()

    def _sub_to_out(self, sub: Subscription) -> SubscriptionOut:
        return SubscriptionOut(
            id=sub.id,
            name=sub.name,
            original_name=sub.original_name,
            tmdb_id=sub.tmdb_id,
            media_type=sub.media_type,
            year=sub.year,
            quality_filter=json.loads(sub.quality_filter) if sub.quality_filter else [],
            min_size=sub.min_size,
            max_size=sub.max_size,
            exclude_keywords=json.loads(sub.exclude_keywords) if sub.exclude_keywords else [],
            include_keywords=json.loads(sub.include_keywords) if sub.include_keywords else [],
            status=sub.status,
            last_search=sub.last_search,
            total_downloaded=sub.total_downloaded,
            created_at=sub.created_at,
        )

    def _is_english(self, text: str) -> bool:
        """判断文本是否主要是英文字符"""
        if not text:
            return False
        # 计算英文字符占比
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        # 如果超过 50% 的字符是英文字母，认为是英文
        return english_chars > len(text) * 0.5

    def _channel_to_out(self, ch: NotifyChannel) -> NotifyChannelOut:
        return NotifyChannelOut(
            id=ch.id,
            name=ch.name,
            channel_type=ch.channel_type,
            config=json.loads(ch.config) if ch.config else {},
            enabled=ch.enabled,
            events=json.loads(ch.events) if ch.events else [],
            created_at=ch.created_at,
        )

    async def _create_notifier(self) -> NotifierService:
        """创建聚合通知服务"""
        notifier = NotifierService()
        channels = (await self.db.execute(
            select(NotifyChannel).where(NotifyChannel.enabled == True)
        )).scalars().all()
        for ch in channels:
            try:
                config = json.loads(ch.config)
                channel = create_channel_from_config(ch.channel_type, config)
                notifier.add_channel(channel)
            except Exception:
                pass
        return notifier
