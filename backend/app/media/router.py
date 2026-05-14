"""
媒体库路由
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel

from app.deps import AdminUser, CurrentUser, DB, SettingsDep
from app.media.repository import MediaRepository
from app.media.schemas import (
    LibraryCreate,
    LibraryOut,
    LibraryUpdate,
    MediaItemDetail,
    MediaItemOut,
    MediaItemUpdate,
    PaginatedResponse,
    ScanResult,
    ScrapeRequest,
    SubtitleOut,
)
from app.media.service import MediaService
from app.system.events import get_event_bus

router = APIRouter(prefix="", tags=["media"])

# ── 媒体库 ──
@router.get("/libraries", response_model=list[LibraryOut])
async def list_libraries(user: CurrentUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.list_libraries()

@router.post("/libraries", response_model=LibraryOut)
async def create_library(data: LibraryCreate, user: AdminUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.create_library(data)

# ── 子路由（必须放在 {library_id} 之前）──
@router.post("/libraries/{library_id}/scan", response_model=ScanResult)
async def scan_library(library_id: int, user: AdminUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.scan_library(library_id, auto_scrape=True)

# ── 主路由：{library_id} 必须在子路由之后 ──
@router.put("/libraries/{library_id}", response_model=LibraryOut)
async def update_library(library_id: int, data: LibraryUpdate, user: AdminUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.update_library(library_id, data)

@router.delete("/libraries/{library_id}", status_code=204)
async def delete_library(library_id: int, user: AdminUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    await service.delete_library(library_id)

# ── 媒体条目 ──
@router.get("/media", response_model=PaginatedResponse)
async def list_media(
    user: CurrentUser,
    db: DB,
    library_id: int | None = None,
    media_type: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("date_added", pattern="^(date_added|title|rating|year|size_bytes)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    genre: str | None = None,
    year_min: int | None = Query(None, ge=1900, le=2030),
    year_max: int | None = Query(None, ge=1900, le=2030),
    rating_min: float | None = Query(None, ge=0, le=10),
):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.get_items(
        library_id=library_id, media_type=media_type, search=search,
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
        genre=genre, year_min=year_min, year_max=year_max, rating_min=rating_min,
    )

@router.get("/media/recent", response_model=list[MediaItemOut])
async def recent_media(user: CurrentUser, db: DB, limit: int = Query(10, ge=1, le=50)):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.get_recent_items(limit)

# ── 统计（必须放在 {item_id} 之前）──
@router.get("/media/stats")
async def media_stats(user: CurrentUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.get_stats()

@router.get("/media/{item_id}", response_model=MediaItemDetail)
async def get_media(item_id: int, user: CurrentUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.get_item_detail(item_id)

@router.delete("/media/{item_id}", status_code=204)
async def delete_media(item_id: int, user: AdminUser, db: DB):
    service = MediaService(MediaRepository(db), get_event_bus())
    await service.delete_item(item_id)

@router.put("/media/{item_id}", response_model=MediaItemDetail)
async def update_media(item_id: int, data: MediaItemUpdate, user: AdminUser, db: DB):
    """手动编辑媒体条目元数据"""
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.update_item_metadata(item_id, data)

# ── 刮削 ──
@router.post("/media/{item_id}/scrape", response_model=MediaItemDetail)
async def scrape_media(item_id: int, request: ScrapeRequest, user: AdminUser, db: DB):
    try:
        service = MediaService(MediaRepository(db), get_event_bus(), db)
        return await service.scrape_item(item_id, request)
    except Exception as e:
        logger.error(f"[Scrape] Error scraping item {item_id}: {e}", exc_info=True)
        raise

@router.get("/search/tmdb")
async def search_tmdb(
    user: CurrentUser,
    db: DB,
    query: str = Query(..., min_length=1),
    media_type: str = Query("movie", pattern=r"^(movie|tv)$"),
    page: int = Query(1, ge=1),
):
    service = MediaService(MediaRepository(db), get_event_bus(), db=db)
    return await service.search_tmdb(query, media_type, page)

@router.get("/search/douban")
async def search_douban(
    user: CurrentUser,
    query: str = Query(..., min_length=1),
    media_type: str = Query("movie", pattern=r"^(movie|tv)$"),
):
    """搜索豆瓣影视"""
    from app.media.douban_scraper import get_douban_client
    client = get_douban_client()
    results = await client.search(query, media_type)
    return {"results": results, "total": len(results)}

@router.get("/search/bangumi")
async def search_bangumi(
    user: CurrentUser,
    query: str = Query(..., min_length=1),
):
    """搜索 Bangumi 动漫数据库"""
    from app.media.bangumi_scraper import get_bangumi_client
    client = get_bangumi_client()
    results = await client.search(query)
    return {"results": results, "total": len(results)}

# ── 全局搜索 ──
@router.get("/search")
async def global_search(
    user: CurrentUser,
    db: DB,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=50),
):
    """全局搜索媒体库，支持电影/剧集/动漫"""
    from app.media.schemas import MediaItemOut
    repo = MediaRepository(db)
    items = await repo.search_items(q, limit=limit)
    return [MediaItemOut.model_validate(i) for i in items]

@router.get("/search/advanced")
async def advanced_search(
    user: CurrentUser,
    db: DB,
    q: str | None = Query(None, max_length=200, description="关键词"),
    media_type: str | None = Query(None, description="媒体类型: movie/tv/anime"),
    genre: str | None = Query(None, description="类型/标签"),
    year_min: int | None = Query(None, ge=1900, le=2100, description="最小年份"),
    year_max: int | None = Query(None, ge=1900, le=2100, description="最大年份"),
    rating_min: float | None = Query(None, ge=0, le=10, description="最低评分"),
    rating_max: float | None = Query(None, ge=0, le=10, description="最高评分"),
    library_id: int | None = Query(None, description="媒体库ID"),
    has_subtitle: bool | None = Query(None, description="是否有字幕"),
    resolution: str | None = Query(None, description="分辨率: 4K/1080p/720p"),
    sort_by: str = Query("date_added", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """高级多条件搜索，支持标题/类型/年份/评分/分辨率等多维度筛选"""
    from app.media.models import MediaItem, Subtitle
    from sqlalchemy import select, func, or_, and_
    from sqlalchemy.orm import aliased

    query = select(MediaItem)
    count_query = select(func.count(MediaItem.id))

    conditions = []

    if q:
        conditions.append(or_(
            MediaItem.title.ilike(f"%{q}%"),
            MediaItem.original_title.ilike(f"%{q}%"),
            MediaItem.overview.ilike(f"%{q}%"),
        ))
    if media_type:
        conditions.append(MediaItem.media_type == media_type)
    if library_id:
        conditions.append(MediaItem.library_id == library_id)
    if genre:
        conditions.append(MediaItem.genres.ilike(f"%{genre}%"))
    if year_min is not None:
        conditions.append(MediaItem.year >= year_min)
    if year_max is not None:
        conditions.append(MediaItem.year <= year_max)
    if rating_min is not None:
        conditions.append(MediaItem.rating >= rating_min)
    if rating_max is not None:
        conditions.append(MediaItem.rating <= rating_max)
    if resolution:
        res_map = {"4K": ["4K", "2160p", "UHD"], "1080p": ["1080p", "FHD"], "720p": ["720p", "HD"]}
        res_variants = res_map.get(resolution, [resolution])
        res_cond = or_(*[MediaItem.resolution.ilike(f"%{r}%") for r in res_variants])
        conditions.append(res_cond)

    if conditions:
        combined = and_(*conditions)
        query = query.where(combined)
        count_query = count_query.where(combined)

    # 字幕过滤（需要子查询）
    if has_subtitle is True:
        subtitle_subq = select(Subtitle.media_item_id).distinct()
        query = query.where(MediaItem.id.in_(subtitle_subq))
        count_query = count_query.where(MediaItem.id.in_(subtitle_subq))
    elif has_subtitle is False:
        subtitle_subq = select(Subtitle.media_item_id).distinct()
        query = query.where(~MediaItem.id.in_(subtitle_subq))
        count_query = count_query.where(~MediaItem.id.in_(subtitle_subq))

    # 排序
    allowed_sort = {
        "date_added": MediaItem.date_added, "title": MediaItem.title,
        "rating": MediaItem.rating, "year": MediaItem.year, "file_size": MediaItem.file_size,
    }
    sort_col = allowed_sort.get(sort_by, MediaItem.date_added)
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

    # 总数
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return {
        "items": [MediaItemOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }

@router.get("/search/mixed")
async def mixed_search(
    user: CurrentUser,
    db: DB,
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    limit: int = Query(20, ge=1, le=50),
):
    """混合搜索：同时搜索本地媒体库 + TMDb，返回聚合结果"""
    import asyncio
    from app.media.schemas import MediaItemOut

    repo = MediaRepository(db)

    # 并发执行本地搜索和 TMDb 搜索
    local_task = repo.search_items(q, limit=limit // 2)

    async def safe_tmdb_search():
        try:
            from app.media.service import MediaService
            service = MediaService(repo, get_event_bus())
            return await service.search_tmdb(q, page=1)
        except Exception:
            return {"results": []}

    local_items, tmdb_result = await asyncio.gather(local_task, safe_tmdb_search())

    return {
        "local": {
            "items": [MediaItemOut.model_validate(i) for i in local_items],
            "total": len(local_items),
        },
        "tmdb": {
            "results": tmdb_result.get("results", [])[:limit // 2],
            "total": tmdb_result.get("total_results", 0),
        },
    }

@router.get("/recommend")
async def get_recommendations(
    user: CurrentUser,
    db: DB,
    limit: int = Query(12, ge=1, le=50, description="推荐数量"),
    media_type: str | None = Query(None, description="媒体类型过滤"),
):
    """智能推荐：基于用户观看历史、热门内容、高评分内容综合推荐"""
    from app.media.models import MediaItem
    from sqlalchemy import select, func, desc

    repo = MediaRepository(db)

    # 策略1：高评分 + 近期添加（混合热度算法）
    stmt = select(MediaItem).where(MediaItem.rating > 6.0)
    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    # 综合评分和添加时间排序（热门指数）
    stmt = stmt.order_by(
        MediaItem.rating.desc(),
        MediaItem.date_added.desc(),
    ).limit(limit)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    # 如果高评分不够，补充最近添加的内容
    if len(items) < limit:
        existing_ids = {i.id for i in items}
        fill_stmt = select(MediaItem).where(~MediaItem.id.in_(existing_ids))
        if media_type:
            fill_stmt = fill_stmt.where(MediaItem.media_type == media_type)
        fill_stmt = fill_stmt.order_by(MediaItem.date_added.desc()).limit(limit - len(items))
        fill_result = await db.execute(fill_stmt)
        items.extend(fill_result.scalars().all())

    return {
        "items": [MediaItemOut.model_validate(i) for i in items],
        "total": len(items),
        "strategy": "rating_and_recent",
    }

@router.get("/recommend/similar/{item_id}")
async def get_similar_media(
    item_id: int,
    user: CurrentUser,
    db: DB,
    limit: int = Query(8, ge=1, le=30, description="相似媒体数量"),
):
    """获取相似媒体推荐：基于同类型、同标签、同年代的内容"""
    from app.media.models import MediaItem
    from sqlalchemy import select, func, or_, and_
    import json

    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "媒体不存在")

    # 解析当前媒体的 genres
    genres: list[str] = []
    if item.genres:
        try:
            genres = json.loads(item.genres) if isinstance(item.genres, str) else item.genres
        except Exception:
            genres = []

    # 构建相似度查询
    conditions = [
        MediaItem.id != item_id,
        MediaItem.media_type == item.media_type,
    ]

    stmt = select(MediaItem).where(and_(*conditions))

    # 同标签加权（用 genres 字符串匹配）
    genre_conditions = []
    for genre in genres[:3]:  # 最多取前3个标签
        if genre:
            genre_conditions.append(MediaItem.genres.ilike(f"%{genre}%"))

    if genre_conditions:
        stmt = stmt.where(or_(*genre_conditions))

    # 同年代加权（±5年）
    if item.year:
        year_stmt = select(MediaItem).where(
            and_(
                MediaItem.id != item_id,
                MediaItem.media_type == item.media_type,
                MediaItem.year.between(item.year - 5, item.year + 5),
            )
        ).order_by(MediaItem.rating.desc()).limit(limit // 2)
        year_result = await db.execute(year_stmt)
        year_items = list(year_result.scalars().all())
    else:
        year_items = []

    # 获取标签相似
    stmt = stmt.order_by(MediaItem.rating.desc()).limit(limit)
    result = await db.execute(stmt)
    genre_items = list(result.scalars().all())

    # 合并去重
    seen_ids = set()
    final_items = []
    for i in genre_items + year_items:
        if i.id not in seen_ids:
            seen_ids.add(i.id)
            final_items.append(i)
            if len(final_items) >= limit:
                break

    return {
        "source_item": MediaItemOut.model_validate(item),
        "similar": [MediaItemOut.model_validate(i) for i in final_items],
        "total": len(final_items),
        "based_on": {
            "genres": genres[:3],
            "media_type": item.media_type,
            "year": item.year,
        },
    }

# ── 字幕管理 ──
@router.get("/media/{item_id}/subtitles", response_model=list[SubtitleOut])
async def list_subtitles(item_id: int, user: CurrentUser, db: DB):
    """获取媒体条目的字幕列表"""
    repo = MediaRepository(db)
    subs = await repo.get_subtitles_by_item(item_id)
    return [SubtitleOut.model_validate(s) for s in subs]

@router.post("/media/{item_id}/subtitles/scan")
async def scan_subtitles(item_id: int, user: AdminUser, db: DB):
    """扫描媒体条目的外挂字幕文件"""
    from app.media.subtitle_service import SubtitleService
    service = SubtitleService(MediaRepository(db))
    found = await service.scan_external_subtitles(item_id)
    return {"found": len(found), "subtitles": [SubtitleOut.model_validate(s) for s in found]}

@router.post("/media/{item_id}/subtitles/extract")
async def extract_subtitles(item_id: int, user: AdminUser, db: DB):
    """检测内嵌字幕流"""
    from app.media.subtitle_service import SubtitleService
    service = SubtitleService(MediaRepository(db))
    streams = await service.extract_embedded_subtitles(item_id)
    return {"streams": streams, "total": len(streams)}

@router.post("/media/{item_id}/subtitles/extract/{stream_index}")
async def extract_subtitle_stream(
    item_id: int, stream_index: int, user: AdminUser, db: DB
):
    """提取内嵌字幕为 SRT 文件"""
    from app.media.subtitle_service import SubtitleService
    service = SubtitleService(MediaRepository(db))
    item = await service.repo.get_item_by_id(item_id)

    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Media item not found")

    # 获取文件路径
    file_path = item.file_path
    if not file_path:
        from fastapi import HTTPException
        raise HTTPException(400, "No file path for this media item")

    output = await service.extract_subtitle_to_file(file_path, stream_index)
    if not output:
        from fastapi import HTTPException
        raise HTTPException(500, "Subtitle extraction failed")

    # 创建字幕记录
    from app.media.subtitle_service import SUBTITLE_LANG_MAP
    lang_code = "zh"
    lang_name = "中文"
    sub = await service.repo.create_subtitle(
        media_item_id=item_id,
        language=lang_code,
        language_name=lang_name,
        path=output,
        source="embedded",
    )

    return {"path": output, "subtitle": SubtitleOut.model_validate(sub)}

@router.post("/media/{item_id}/subtitles/upload")
async def upload_subtitle(
    item_id: int,
    user: AdminUser,
    db: DB,
    file: UploadFile = File(...),
    language: str = Form("zh"),
    episode_id: int | None = Form(None),
):
    """上传字幕文件"""
    from app.media.subtitle_service import SubtitleService
    service = SubtitleService(MediaRepository(db))
    content = await file.read()
    sub = await service.upload_subtitle(
        media_item_id=item_id,
        filename=file.filename or "subtitle.srt",
        content=content,
        language=language,
        episode_id=episode_id,
    )
    return SubtitleOut.model_validate(sub)

@router.get("/subtitles/{subtitle_id}/content")
async def get_subtitle_content(subtitle_id: int, user: CurrentUser, db: DB):
    """获取字幕文件内容"""
    from app.media.subtitle_service import SubtitleService
    service = SubtitleService(MediaRepository(db))
    content = await service.read_subtitle_content(subtitle_id)
    if content is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Subtitle not found or cannot be read")
    return {"content": content}

@router.delete("/subtitles/{subtitle_id}")
async def delete_subtitle(
    subtitle_id: int, user: AdminUser, db: DB, delete_file: bool = Query(False)
):
    """删除字幕记录，可选删除文件"""
    from app.media.subtitle_service import SubtitleService
    service = SubtitleService(MediaRepository(db))
    success = await service.delete_subtitle(subtitle_id, delete_file)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(404, "Subtitle not found")
    return {"success": True}

# ── Adult Provider 测试 ──
class ScrapeTestRequest(BaseModel):
    """Adult Provider 刮削测试请求"""
    code: str = "FC2-PPV-1234"

class ScrapeTestResponse(BaseModel):
    """Adult Provider 刮削测试响应"""
    success: bool
    title: str | None = None
    poster: str | None = None
    studio: str | None = None
    message: str | None = None
    source: str | None = None  # javbus / javdb / microservice

@router.post("/media/scrape/test", response_model=ScrapeTestResponse)
async def test_adult_scrape(
    request: ScrapeTestRequest,
    user: AdminUser,
):
    """测试 Adult Provider 刮削功能"""
    from app.media.providers.adult import AdultProvider, AdultProviderConfig
    from app.system.api_config_service import ApiConfigService
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        config_service = ApiConfigService(db)
        config = await config_service.get_effective_config("adult")

        if not config.get("enabled", False):
            return ScrapeTestResponse(
                success=False,
                message="Adult Provider 未启用，请在设置中启用",
            )

        # 构建 AdultProvider 配置
        extra = config.get("extra", {}) or {}
        provider_config = AdultProviderConfig(
            enabled=True,
            adult_dirs=extra.get("adult_dirs", []),
            javbus_url=extra.get("javbus_url", "https://www.javbus.com"),
            javdb_url=extra.get("javdb_url", "https://javdb.com"),
            javdb_cookie=extra.get("javdb_cookie", ""),
            microservice_url=extra.get("microservice_url", ""),
            proxy=extra.get("proxy", ""),
        )

        provider = AdultProvider(provider_config)

        try:
            # 尝试刮削
            metadata = await provider.get_metadata(request.code, "movie")
            if metadata:
                return ScrapeTestResponse(
                    success=True,
                    title=metadata.title,
                    poster=metadata.poster_url,
                    studio=metadata.extra.get("studio") if metadata.extra else None,
                    source="javbus" if "javbus" in str(metadata) else "javdb",
                )
            else:
                return ScrapeTestResponse(
                    success=False,
                    message=f"未能在 JavBus/JavDB 找到番号 {request.code}，可能是：1) 番号不存在 2) 代理被目标网站拦截 3) 网络问题",
                )
        except Exception as e:
            logger.error(f"[ScrapeTest] Error: {e}")
            return ScrapeTestResponse(
                success=False,
                message=f"刮削出错: {type(e).__name__}: {str(e)[:100]}",
            )
        finally:
            await provider.close()

# ── 收藏/书签 ──

# ── 收藏/书签 ──
@router.post("/media/{item_id}/favorite")
async def add_favorite(item_id: int, user: CurrentUser, db: DB):
    """添加收藏"""
    repo = MediaRepository(db)
    await repo.add_favorite(user.id, item_id)
    return {"favorited": True, "media_item_id": item_id}

@router.delete("/media/{item_id}/favorite", status_code=204)
async def remove_favorite(item_id: int, user: CurrentUser, db: DB):
    """取消收藏"""
    repo = MediaRepository(db)
    success = await repo.remove_favorite(user.id, item_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(404, "未找到该收藏记录")

@router.get("/media/{item_id}/favorite/status")
async def check_favorite(item_id: int, user: CurrentUser, db: DB):
    """检查是否已收藏"""
    repo = MediaRepository(db)
    is_fav = await repo.is_favorite(user.id, item_id)
    return {"is_favorite": is_fav}

@router.get("/favorites")
async def list_favorites(
    user: CurrentUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取我的收藏列表"""
    from app.media.schemas import PaginatedResponse, MediaItemOut
    repo = MediaRepository(db)
    items, total = await repo.get_favorites(user.id, page=page, page_size=page_size)
    return PaginatedResponse.create(
        items=[MediaItemOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )

# ── 重复检测 ──
@router.post("/libraries/{library_id}/duplicates/hash")
async def compute_file_hashes(
    library_id: int,
    user: AdminUser,
    db: DB,
    limit: int = Query(100, ge=0, le=5000),
):
    """计算媒体库文件哈希值（重复检测前置步骤）"""
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.compute_file_hashes(library_id, limit)

@router.post("/libraries/{library_id}/duplicates/scan")
async def scan_duplicates(library_id: int, user: AdminUser, db: DB):
    """检测并标记媒体库中的重复文件"""
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.detect_duplicates(library_id)

@router.get("/libraries/{library_id}/duplicates")
async def get_duplicates(library_id: int, user: CurrentUser, db: DB):
    """获取媒体库的重复文件列表"""
    service = MediaService(MediaRepository(db), get_event_bus())
    return await service.get_duplicates(library_id)

@router.delete("/libraries/{library_id}/duplicates", status_code=204)
async def unmark_duplicates(library_id: int, user: AdminUser, db: DB):
    """取消媒体库中所有重复标记"""
    service = MediaService(MediaRepository(db), get_event_bus())
    await service.unmark_duplicates(library_id)

@router.post("/media/{item_id}/duplicate/unmark")
async def unmark_single_duplicate(item_id: int, user: AdminUser, db: DB):
    """取消单个媒体条目的重复标记"""
    from app.media.models import MediaItem
    repo = MediaRepository(db)
    await repo.update_item(item_id, is_duplicate=False, duplicate_of=None)
    return {"success": True, "media_item_id": item_id}

# ── 文件整理 ──
@router.post("/media/organize")
async def organize_media(
    user: AdminUser,
    db: DB,
    source_path: str = "",
):
    """手动整理文件到媒体库"""
    from app.config import get_settings
    from app.media.organizer import FileOrganizer

    settings = get_settings()

    # 获取媒体库目录配置
    movies_dir = ""
    tv_dir = ""
    anime_dir = ""

    repo = MediaRepository(db)
    libraries = await repo.get_all_libraries()
    for lib in libraries:
        if lib.media_type == "movie" and not movies_dir:
            movies_dir = lib.path
        elif lib.media_type == "tv" and not tv_dir:
            tv_dir = lib.path
        elif lib.media_type == "anime" and not anime_dir:
            anime_dir = lib.path

    organizer = FileOrganizer(
        movies_dir=movies_dir,
        tv_dir=tv_dir,
        anime_dir=anime_dir,
        download_dir=str(settings.download_dir),
    )

    if source_path:
        # 整理指定路径
        result = organizer.organize_downloaded_file(src_path=source_path, media_type="auto")
    else:
        # 整理整个下载目录
        result = organizer.organize_download_dir(media_type="auto")

    return {
        "organized": result.organized,
        "skipped": result.skipped,
        "errors": result.errors,
    }

# ── 章节 API ──

# ── 封面候选 API ──



@router.get("/media/{item_id}/thumbnail", summary="获取视频截帧")
async def get_thumbnail(
    item_id: int,
    db: DB,
    t: float = Query(0.0, description="截帧时间戳（秒）"),
    width: int = Query(400, ge=50, le=1920),
    height: int = Query(225, ge=28, le=1080),
):
    """从视频指定时间戳截取缩略图（需要 FFmpeg）"""
    from fastapi.responses import Response, FileResponse
    from fastapi import HTTPException
    import subprocess, tempfile, os

    item = await _get_media_or_404(item_id, db)

    # 检查文件是否存在
    if not item.file_path or not os.path.exists(item.file_path):
        raise HTTPException(404, "视频文件不存在")

    try:
        # 使用 FFmpeg 截帧
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        cmd = [
            "ffmpeg", "-ss", str(t), "-i", item.file_path,
            "-vframes", "1", "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            "-q:v", "2", "-y", tmp_path
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=10)

        if proc.returncode == 0 and os.path.exists(tmp_path):
            return FileResponse(tmp_path, media_type="image/jpeg")
        else:
            raise HTTPException(500, "截帧失败")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "截帧超时")
    except FileNotFoundError:
        raise HTTPException(503, "FFmpeg 未安装")
