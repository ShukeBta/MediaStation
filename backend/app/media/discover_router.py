"""
发现/探索页 API
聚合多数据源（TMDB / 豆瓣 / Bangumi）的推荐内容。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import safe_create_task
from app.common.utils import safe_json
from app.deps import CurrentUser, DB
from app.config import get_settings
from app.media.models import MediaItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover", tags=["discover"])

# ── 允许代理的图片域名白名单 ──
_IMAGE_PROXY_DOMAINS = {
    "img3.doubanio.com",
    "img9.doubanio.com",
    "img1.doubanio.com",
    "img2.doubanio.com",
}

# ── 可用区块定义 ──
AVAILABLE_SECTIONS = [
    # 本地数据源（始终可用）
    {"key": "recent_movies", "label": "最近添加电影", "icon": "🆕", "source": "local"},
    {"key": "recent_tv", "label": "最近添加剧集", "icon": "📺", "source": "local"},
    {"key": "top_rated", "label": "评分最高", "icon": "⭐", "source": "local"},
    {"key": "anime", "label": "动漫推荐", "icon": "🌸", "source": "local"},
    # TMDB 数据源
    {"key": "tmdb_trending", "label": "流行趋势", "icon": "🔥", "source": "tmdb"},
    {"key": "tmdb_now_playing", "label": "正在热映", "icon": "🎬", "source": "tmdb"},
    {"key": "tmdb_popular_movies", "label": "TMDB热门电影", "icon": "🎥", "source": "tmdb"},
    {"key": "tmdb_popular_tv", "label": "TMDB热门电视剧", "icon": "📺", "source": "tmdb"},
    # 豆瓣数据源
    {"key": "douban_hot_movies", "label": "豆瓣热门电影", "icon": "🍿", "source": "douban"},
    {"key": "douban_hot_tv", "label": "豆瓣热门电视剧", "icon": "📽", "source": "douban"},
    {"key": "douban_hot_anime", "label": "豆瓣热门动漫", "icon": "🌸", "source": "douban"},
    {"key": "douban_top250", "label": "豆瓣电影TOP250", "icon": "🏆", "source": "douban"},
    # Bangumi 数据源
    {"key": "bangumi_daily", "label": "Bangumi每日放送", "icon": "📡", "source": "bangumi"},
]


@router.get("/sections")
async def list_available_sections(user: CurrentUser, db: DB):
    """获取所有可用的推荐区块（含可用状态）"""
    from app.system.api_config_service import ApiConfigService

    api_config_service = ApiConfigService(db)

    # 获取各数据源的有效配置
    tmdb_config = await api_config_service.get_effective_config("tmdb")
    bangumi_config = await api_config_service.get_effective_config("bangumi")

    # 检查各数据源是否可用（使用统一配置系统）
    sources_status = {
        "tmdb": bool(tmdb_config.get("api_key")),
        "douban": True,  # 豆瓣无需配置即可基础使用
        "bangumi": bool(bangumi_config.get("api_key")),
        "local": True,  # 本地数据源始终可用
    }

    sections = []
    for sec in AVAILABLE_SECTIONS:
        sections.append({
            **sec,
            "enabled": sources_status.get(sec["source"], False),
        })

    return {"sections": sections}


@router.get("/feed")
async def discover_feed(
    user: CurrentUser,
    db: DB,
    sections: str | None = Query(None, description="逗号分隔的区块 key 列表，如 tmdb_trending,douban_top250"),
):
    """
    聚合发现页各区块数据。

    不传 sections 则返回所有可用区块的数据。
    每个数据源独立请求，失败不阻塞其他区块。
    """
    import asyncio

    from app.media.douban_scraper import get_douban_client
    from app.media.bangumi_scraper import get_bangumi_client
    from app.system.api_config_service import ApiConfigService

    api_config_service = ApiConfigService(db)

    # 获取各数据源的有效配置
    tmdb_config = await api_config_service.get_effective_config("tmdb")
    bangumi_config = await api_config_service.get_effective_config("bangumi")

    # 确定要加载的区块
    requested = None
    if sections:
        requested = set(s.strip() for s in sections.split(",") if s.strip())

    results: dict[str, Any] = {}
    tasks: dict[str, Any] = {}

    for sec in AVAILABLE_SECTIONS:
        key = sec["key"]
        if requested and key not in requested:
            continue

        source = sec["source"]

        # 本地数据源
        if source == "local":
            tasks[key] = _fetch_local_section(db, key)
        elif source == "tmdb" and tmdb_config.get("api_key"):
            tasks[key] = _fetch_tmdb_section(key, tmdb_config)
        elif source == "douban":
            tasks[key] = _fetch_douban_section(key)
        elif source == "bangumi" and bangumi_config.get("api_key"):
            tasks[key] = _fetch_bangumi_section(key)

    # 并行执行所有任务（使用安全包装器，防止异常静默崩溃）
    if tasks:
        coros = {k: safe_create_task(v, name=f"discover_fetch_{k}") for k, v in tasks.items()}
        for key, task in coros.items():
            try:
                results[key] = await task
            except Exception as e:
                logger.warning(f"Discover section '{key}' failed: {e}")
                results[key] = {"items": [], "error": str(e)}

    return results


# ── 本地数据源 ──

async def _fetch_local_section(db: AsyncSession, section_key: str) -> dict:
    """从本地数据库获取指定区块数据"""
    items = []

    try:
        if section_key == "recent_movies":
            # 最近添加的电影
            stmt = (
                select(MediaItem)
                .where(MediaItem.media_type == "movie")
                .order_by(desc(MediaItem.created_at))
                .limit(20)
            )
            result = await db.execute(stmt)
            movies = result.scalars().all()
            for item in movies:
                items.append({
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "source": "local",
                    "external": False,
                })

        elif section_key == "recent_tv":
            # 最近添加的剧集
            stmt = (
                select(MediaItem)
                .where(MediaItem.media_type == "tv")
                .order_by(desc(MediaItem.created_at))
                .limit(20)
            )
            result = await db.execute(stmt)
            tv_shows = result.scalars().all()
            for item in tv_shows:
                items.append({
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "source": "local",
                    "external": False,
                })

        elif section_key == "top_rated":
            # 评分最高的内容
            stmt = (
                select(MediaItem)
                .where(MediaItem.rating > 0)
                .order_by(desc(MediaItem.rating))
                .limit(20)
            )
            result = await db.execute(stmt)
            rated = result.scalars().all()
            for item in rated:
                items.append({
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "source": "local",
                    "external": False,
                })

        elif section_key == "anime":
            # 动漫推荐（优先 anime 类型，否则返回高评分内容）
            stmt = (
                select(MediaItem)
                .where(MediaItem.media_type == "anime")
                .order_by(desc(MediaItem.created_at))
                .limit(20)
            )
            result = await db.execute(stmt)
            animes = result.scalars().all()
            
            # 如果没有动漫，返回评分>8的内容
            if not animes:
                stmt = (
                    select(MediaItem)
                    .where(MediaItem.rating > 8.0)
                    .order_by(desc(MediaItem.rating))
                    .limit(20)
                )
                result = await db.execute(stmt)
                animes = result.scalars().all()
            
            for item in animes:
                items.append({
                    "id": item.id,
                    "title": item.title,
                    "poster_url": item.poster_url,
                    "backdrop_url": item.backdrop_url,
                    "rating": item.rating or 0,
                    "year": item.year,
                    "media_type": item.media_type,
                    "source": "local",
                    "external": False,
                })

    except Exception as e:
        logger.warning(f"Local fetch failed for {section_key}: {e}")

    return {"items": items}


# ── TMDB 数据源 ──

async def _fetch_tmdb_section(section_key: str, tmdb_config: dict) -> dict:
    """从 TMDb 获取指定区块数据"""
    from app.media.scraper import TMDbClient

    # 使用配置中的 API Key 和 Base URL
    api_key = tmdb_config.get("api_key", "")
    base_url = tmdb_config.get("base_url") or "https://api.themoviedb.org/3"

    client = TMDbClient(custom_api_key=api_key, custom_base_url=base_url)
    items = []

    try:
        if section_key == "tmdb_trending":
            # TMDB trending (all media)
            resp = await client.client.get("/trending/all/day", params={"language": "zh-CN"})
            data = safe_json(resp, url_hint="tmdb_trending")
            if not data:
                return {"items": items}
            raw = data.get("results", [])[:12]
            for r in raw:
                mt = r.get("media_type", "")
                if mt not in ("movie", "tv"):
                    continue
                poster = r.get("poster_path")
                backdrop = r.get("backdrop_path")
                items.append({
                    "id": f"tmdb_{r['id']}",
                    "tmdb_id": r["id"],
                    "title": r.get("title") or r.get("name", ""),
                    "original_title": r.get("original_title") or r.get("original_name", ""),
                    "overview": r.get("overview", "") or "",
                    "poster_url": client._poster_url(poster) if poster else None,
                    "backdrop_url": client._poster_url(backdrop, "original") if backdrop else None,
                    "media_type": "movie" if mt == "movie" else "tv",
                    "rating": round(r.get("vote_average", 0), 1),
                    "year": _extract_year(r),
                    "popularity": r.get("popularity", 0),
                    "source": "tmdb",
                    "external": True,
                })

        elif section_key == "tmdb_now_playing":
            resp = await client.client.get("/movie/now_playing", params={"language": "zh-CN"})
            data = safe_json(resp, url_hint="tmdb_now_playing")
            if not data:
                return {"items": items}
            raw = data.get("results", [])[:20]
            for r in raw:
                poster = r.get("poster_path")
                items.append({
                    "id": f"tmdb_np_{r['id']}",
                    "tmdb_id": r["id"],
                    "title": r.get("title", ""),
                    "original_title": r.get("original_title", ""),
                    "overview": r.get("overview", "") or "",
                    "poster_url": client._poster_url(poster) if poster else None,
                    "media_type": "movie",
                    "rating": round(r.get("vote_average", 0), 1),
                    "year": _extract_year(r),
                    "release_date": r.get("release_date", ""),
                    "source": "tmdb",
                    "external": True,
                })

        elif section_key == "tmdb_popular_movies":
            resp = await client.client.get("/movie/popular", params={"language": "zh-CN"})
            data = safe_json(resp, url_hint="tmdb_popular_movies")
            if not data:
                return {"items": items}
            raw = data.get("results", [])[:12]
            for r in raw:
                poster = r.get("poster_path")
                items.append({
                    "id": f"tmdb_pm_{r['id']}",
                    "tmdb_id": r["id"],
                    "title": r.get("title", ""),
                    "original_title": r.get("original_title", ""),
                    "overview": r.get("overview", "") or "",
                    "poster_url": client._poster_url(poster) if poster else None,
                    "media_type": "movie",
                    "rating": round(r.get("vote_average", 0), 1),
                    "year": _extract_year(r),
                    "source": "tmdb",
                    "external": True,
                })

        elif section_key == "tmdb_popular_tv":
            resp = await client.client.get("/tv/popular", params={"language": "zh-CN"})
            data = safe_json(resp, url_hint="tmdb_popular_tv")
            if not data:
                return {"items": items}
            raw = data.get("results", [])[:12]
            for r in raw:
                poster = r.get("poster_path")
                items.append({
                    "id": f"tmdb_ptv_{r['id']}",
                    "tmdb_id": r["id"],
                    "title": r.get("name", ""),
                    "original_title": r.get("original_name", ""),
                    "overview": r.get("overview", "") or "",
                    "poster_url": client._poster_url(poster) if poster else None,
                    "media_type": "tv",
                    "rating": round(r.get("vote_average", 0), 1),
                    "year": _extract_year(r),
                    "source": "tmdb",
                    "external": True,
                })
    except Exception as e:
        logger.warning(f"TMDb fetch failed for {section_key}: {e}")

    return {"items": items}


def _extract_year(r: dict) -> int | None:
    """从 TMDb 结果中提取年份"""
    date_str = r.get("release_date") or r.get("first_air_date", "")
    if date_str and len(date_str) >= 4:
        try:
            return int(date_str[:4])
        except ValueError:
            pass
    return None


# ── 豆瓣数据源 ──

async def _fetch_douban_section(section_key: str) -> dict:
    """从豆瓣获取指定区块数据"""
    from app.media.douban_scraper import get_douban_client
    client = get_douban_client()
    items = []

    try:
        if section_key in ("douban_hot_movies", "douban_hot_tv", "douban_hot_anime"):
            # 豆瓣热门榜单 - 通过搜索页面抓取
            # 注意：豆瓣 j/search_subjects API 的 type 参数基本无效，
            # 真正靠 tag 来区分类别
            cat_map = {
                "douban_hot_movies": ("电影", "热门", "movie"),
                "douban_hot_tv": ("电视剧", "国产剧", "tv"),      # 用"国产剧"标签获取电视剧
                "douban_hot_anime": ("", "动漫", "anime"),         # type 留空，用"动漫"标签
            }
            cat_label, tag, media_type = cat_map[section_key]

            # 构建请求参数：只有电影需要 type=电影，其他留空靠 tag 区分
            params = {
                "tag": tag,
                "sort": "recommend",
                "page_limit": 12,
                "page_start": 0,
            }
            if cat_label:
                params["type"] = cat_label

            # 使用 get_hot_subjects（带限流和正确 Headers）
            resp_data = await client.get_hot_subjects(params)
            if resp_data:
                for s in resp_data.get("subjects", []):
                    items.append({
                        "id": f"douban_{section_key}_{s.get('id', '')}",
                        "douban_id": s.get("id"),
                        "title": s.get("title", ""),
                        "poster_url": s.get("cover", ""),
                        "rating": s.get("rate", 0),
                        "media_type": media_type,
                        "source": "douban",
                        "external": True,
                    })

        elif section_key == "douban_top250":
            # 豆瓣 TOP250
            resp_data = await client.get_hot_subjects({
                "type": "movie",
                "tag": "豆瓣Top250",
                "sort": "score",
                "page_limit": 20,
                "page_start": 0,
            })
            if resp_data:
                for idx, s in enumerate(resp_data.get("subjects", [])):
                    items.append({
                        "id": f"douban_top250_{s.get('id', '')}",
                        "douban_id": s.get("id"),
                        "rank": idx + 1,
                        "title": s.get("title", ""),
                        "poster_url": s.get("cover", ""),
                        "rating": s.get("rate", 0),
                        "media_type": "movie",
                        "source": "douban",
                        "external": True,
                    })
    except Exception as e:
        logger.warning(f"Douban fetch failed for {section_key}: {e}")

    return {"items": items}


# ── Bangumi 数据源 ──

async def _fetch_bangumi_section(section_key: str) -> dict:
    """从 Bangumi 获取指定区块数据"""
    from app.media.bangumi_scraper import get_bangumi_client
    client = get_bangumi_client()
    items = []

    try:
        if section_key == "bangumi_daily":
            # Bangumi 每日放送（当前播出动画）
            resp = await client.client.get("/v0/calendar")
            if resp.status_code == 200:
                data = safe_json(resp, url_hint="bangumi_calendar")
                if data:
                    for week_entry in data:
                        weekday_items = week_entry.get("items", [])
                        for item in weekday_items[:5]:  # 每天最多取 5 部
                            meta = item.get("metadata", {}) or {}
                            bgm_id = meta.get("subject_id") or item.get("id", "")
                            images = meta.get("images", {}) or {}
                            rating_data = meta.get("rating", {}) or {}
                            name_cn = meta.get("name_cn") or ""
                            name = meta.get("name") or ""

                            items.append({
                                "id": f"bgm_{bgm_id}",
                                "bangumi_id": bgm_id,
                                "title": name_cn or name,
                                "original_title": name if name_cn else "",
                                "poster_url": (
                                    images.get("large")
                                    or images.get("common")
                                    or images.get("small")
                                    or None
                                ),
                                "rating": rating_data.get("score", 0) if isinstance(rating_data, dict) else 0,
                                "media_type": "anime",
                                "weekday": week_entry.get("weekday", {}).get("cn", ""),
                                "air_time": meta.get("air_time", ""),
                                "source": "bangumi",
                                "external": True,
                            })
    except Exception as e:
        logger.warning(f"Bangumi fetch failed for {section_key}: {e}")

    return {"items": items}


# ── 图片代理（解决豆瓣防盗链） ──

@router.get("/image-proxy")
async def image_proxy(url: str = Query(..., description="要代理的图片 URL")):
    """
    代理外部图片请求，解决豆瓣等网站的防盗链问题。
    前端将 poster_url 通过此端点转发，后端带正确的 Referer 请求。
    仅允许白名单域名。
    """
    parsed = urlparse(url)
    if parsed.hostname not in _IMAGE_PROXY_DOMAINS:
        return Response(status_code=403, content="Domain not allowed")

    # 根据目标域名选择 Referer（支持 img*.doubanio.com 通配）
    referer_map = {
        "doubanio.com": "https://movie.douban.com/",
    }
    referer = referer_map.get(parsed.hostname, "")
    # fallback: 如果 hostname 不在 map 中，尝试用后缀匹配（如 img3.doubanio.com → doubanio.com）
    if not referer:
        for domain, ref in referer_map.items():
            if parsed.hostname.endswith(domain):
                referer = ref
                break

    try:
        # 使用 subprocess 调用 curl（TLS 指纹与浏览器一致，可绕过豆瓣 CDN 限制）
        import subprocess as sp
        import os

        # 清除可能影响 curl 的代理环境变量
        env = {k: v for k, v in os.environ.items() if not k.lower().endswith('_proxy')}

        headers_args = [
            "-H", f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-H", f"Accept: image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        ]
        if referer:
            headers_args += ["-H", f"Referer: {referer}"]

        result = sp.run(
            ["curl", "-sL", "-o", "-", "--max-time", "15",
             "--noproxy", "*",
             ] + headers_args + [url],
            capture_output=True, timeout=20,
            env=env,
        )
        logger.info(f"Image proxy: rc={result.returncode}, size={len(result.stdout)}")
        if result.returncode != 0 or len(result.stdout) < 100:
            return Response(status_code=502, content="Image fetch failed")

        content_type = "image/jpeg"
        body = result.stdout
        if body[:4] == b'\x89PNG':
            content_type = "image/png"
        elif body[:2] in (b'\xff\xd8',):
            content_type = "image/jpeg"
        elif body[:4] == b'GIF8':
            content_type = "image/gif"
        elif body[:4] == b'RIFF':
            content_type = "image/webp"

        return Response(
            content=body,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Proxy-Source": parsed.hostname,
            },
        )
    except sp.TimeoutExpired:
        logger.warning(f"Image proxy timeout for {url}")
        return Response(status_code=504, content="Image fetch timeout")
    except Exception as e:
        logger.warning(f"Image proxy failed for {url}: {e}")
        return Response(status_code=502, content="Failed to fetch image")
