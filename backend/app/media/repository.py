"""
媒体库数据访问层
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, join, or_, select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.models import Favorite, MediaEpisode, MediaItem, MediaLibrary, MediaSeason, Subtitle


class MediaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 媒体库 CRUD ──
    async def get_library_by_id(self, library_id: int) -> MediaLibrary | None:
        result = await self.db.execute(select(MediaLibrary).where(MediaLibrary.id == library_id))
        return result.scalar_one_or_none()

    async def get_all_libraries(self) -> list[MediaLibrary]:
        result = await self.db.execute(select(MediaLibrary).order_by(MediaLibrary.id))
        return list(result.scalars().all())

    async def get_enabled_libraries(self) -> list[MediaLibrary]:
        result = await self.db.execute(
            select(MediaLibrary).where(MediaLibrary.enabled == True).order_by(MediaLibrary.id)
        )
        return list(result.scalars().all())

    async def create_library(self, **kwargs) -> MediaLibrary:
        lib = MediaLibrary(**kwargs)
        self.db.add(lib)
        await self.db.flush()
        await self.db.refresh(lib)
        return lib

    async def update_library(self, library_id: int, **kwargs) -> MediaLibrary | None:
        lib = await self.get_library_by_id(library_id)
        if not lib:
            return None
        for k, v in kwargs.items():
            if v is not None:
                setattr(lib, k, v)
        await self.db.flush()
        await self.db.refresh(lib)
        return lib

    async def delete_library(self, library_id: int):
        lib = await self.get_library_by_id(library_id)
        if not lib:
            return
        # 手动级联删除：先获取该库下所有 media_item 的 id
        result = await self.db.execute(
            select(MediaItem.id).where(MediaItem.library_id == library_id)
        )
        item_ids = [row[0] for row in result.all()]

        if item_ids:
            # 1. 删除观看历史（watch_history 没有 ForeignKey 声明，需手动处理）
            from app.user.models import WatchHistory
            await self.db.execute(
                delete(WatchHistory).where(WatchHistory.media_item_id.in_(item_ids))
            )
            # 2. 删除收藏
            await self.db.execute(
                delete(Favorite).where(Favorite.media_item_id.in_(item_ids))
            )
            # 3. 删除字幕
            await self.db.execute(
                delete(Subtitle).where(Subtitle.media_item_id.in_(item_ids))
            )
            # 4. 删除剧集（通过 season 关联）
            await self.db.execute(
                delete(MediaEpisode).where(
                    MediaEpisode.season_id.in_(
                        select(MediaSeason.id).where(
                            MediaSeason.media_item_id.in_(item_ids)
                        )
                    )
                )
            )
            # 5. 删除季
            await self.db.execute(
                delete(MediaSeason).where(MediaSeason.media_item_id.in_(item_ids))
            )
            # 6. 删除媒体条目
            await self.db.execute(
                delete(MediaItem).where(MediaItem.library_id == library_id)
            )

        # 7. 删除媒体库本身
        await self.db.delete(lib)
        await self.db.flush()

    async def count_library_items(self, library_id: int) -> int:
        result = await self.db.execute(
            select(func.count(MediaItem.id)).where(MediaItem.library_id == library_id)
        )
        return result.scalar() or 0

    # ── 媒体条目 CRUD ──
    async def get_item_by_id(self, item_id: int) -> MediaItem | None:
        result = await self.db.execute(select(MediaItem).where(MediaItem.id == item_id))
        return result.scalar_one_or_none()

    async def get_item_by_tmdb(self, tmdb_id: int) -> MediaItem | None:
        result = await self.db.execute(select(MediaItem).where(MediaItem.tmdb_id == tmdb_id))
        return result.scalar_one_or_none()

    async def get_item_by_path(self, file_path: str) -> MediaItem | None:
        result = await self.db.execute(select(MediaItem).where(MediaItem.file_path == file_path))
        return result.scalar_one_or_none()

    async def search_items(self, keyword: str, limit: int = 10) -> list[MediaItem]:
        """全局搜索：按标题匹配电影/剧集/动漫"""
        stmt = (
            select(MediaItem)
            .where(
                or_(
                    MediaItem.title.ilike(f"%{keyword}%"),
                    MediaItem.original_title.ilike(f"%{keyword}%"),
                )
            )
            .order_by(MediaItem.title)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_items(
        self,
        library_id: int | None = None,
        media_type: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "date_added",
        sort_order: str = "desc",
        genre: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        rating_min: float | None = None,
    ) -> tuple[list[MediaItem], int]:
        query = select(MediaItem)
        count_query = select(func.count(MediaItem.id))

        if library_id:
            query = query.where(MediaItem.library_id == library_id)
            count_query = count_query.where(MediaItem.library_id == library_id)
        if media_type:
            query = query.where(MediaItem.media_type == media_type)
            count_query = count_query.where(MediaItem.media_type == media_type)
        if search:
            search_filter = or_(
                MediaItem.title.ilike(f"%{search}%"),
                MediaItem.original_title.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        if genre:
            # genres 存储为 JSON 数组字符串或列表
            query = query.where(MediaItem.genres.cast(String).ilike(f"%{genre}%"))
            count_query = count_query.where(MediaItem.genres.cast(String).ilike(f"%{genre}%"))
        if year_min is not None:
            query = query.where(MediaItem.year >= year_min)
            count_query = count_query.where(MediaItem.year >= year_min)
        if year_max is not None:
            query = query.where(MediaItem.year <= year_max)
            count_query = count_query.where(MediaItem.year <= year_max)
        if rating_min is not None:
            query = query.where(MediaItem.rating >= rating_min)
            count_query = count_query.where(MediaItem.rating >= rating_min)

        # 排序（安全白名单）
        allowed_sort = {
            "date_added": MediaItem.date_added, "title": MediaItem.title,
            "rating": MediaItem.rating, "year": MediaItem.year, "size_bytes": MediaItem.file_size,
        }
        sort_col = allowed_sort.get(sort_by, MediaItem.date_added)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        # 总数
        total = (await self.db.execute(count_query)).scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def get_recent_items(self, limit: int = 10) -> list[MediaItem]:
        result = await self.db.execute(
            select(MediaItem)
            .order_by(MediaItem.date_added.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_item(self, **kwargs) -> MediaItem:
        item = MediaItem(**kwargs)
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def update_item(self, item_id: int, **kwargs) -> MediaItem | None:
        item = await self.get_item_by_id(item_id)
        if not item:
            return None
        for k, v in kwargs.items():
            # 允许显式设置为 None（通过 _none_fields 参数传递）
            if v is not None and v != "__NONE__":
                setattr(item, k, v)
            elif v == "__NONE__":
                setattr(item, k, None)
        item.last_scanned = datetime.now()
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def delete_item(self, item_id: int):
        item = await self.get_item_by_id(item_id)
        if item:
            await self.db.delete(item)
            await self.db.flush()

    async def delete_items_not_in_paths(self, library_id: int, valid_paths: set[str]) -> int:
        """删除不在有效路径列表中的条目"""
        stmt = (
            delete(MediaItem)
            .where(
                MediaItem.library_id == library_id,
                ~MediaItem.file_path.in_(valid_paths),
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount

    async def get_all_item_paths(self, library_id: int) -> set[str]:
        result = await self.db.execute(
            select(MediaItem.file_path).where(MediaItem.library_id == library_id)
        )
        return {row[0] for row in result.all()}

    async def get_unscraped_items(self, library_id: int, limit: int = 20) -> list[MediaItem]:
        """获取指定媒体库中未刮削的条目（用于增量刮削）"""
        result = await self.db.execute(
            select(MediaItem)
            .where(MediaItem.library_id == library_id, MediaItem.scraped == False)
            .order_by(MediaItem.date_added.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── 季/集 ──
    async def create_season(self, **kwargs) -> MediaSeason:
        # 确保 media_item_id 不为空
        if 'media_item_id' not in kwargs or kwargs['media_item_id'] is None:
            raise ValueError("create_season: media_item_id is required and cannot be None")
        season = MediaSeason(**kwargs)
        self.db.add(season)
        await self.db.flush()
        await self.db.refresh(season)
        return season

    async def get_seasons_by_item(self, media_item_id: int) -> list[MediaSeason]:
        result = await self.db.execute(
            select(MediaSeason)
            .where(MediaSeason.media_item_id == media_item_id)
            .order_by(MediaSeason.season_number)
        )
        return list(result.scalars().all())

    async def get_episodes_by_season(self, season_id: int) -> list[MediaEpisode]:
        """获取指定季的所有集"""
        result = await self.db.execute(
            select(MediaEpisode)
            .where(MediaEpisode.season_id == season_id)
            .order_by(MediaEpisode.episode_number)
        )
        return list(result.scalars().all())

    async def create_episode(self, **kwargs) -> MediaEpisode:
        ep = MediaEpisode(**kwargs)
        self.db.add(ep)
        await self.db.flush()
        await self.db.refresh(ep)
        return ep

    async def update_episode(self, episode_id: int, **kwargs) -> MediaEpisode | None:
        """更新剧集信息"""
        ep = await self.get_episode_by_id(episode_id)
        if not ep:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(ep, key, value)
        await self.db.flush()
        await self.db.refresh(ep)
        return ep

    async def get_episode_by_id(self, episode_id: int) -> MediaEpisode | None:
        result = await self.db.execute(select(MediaEpisode).where(MediaEpisode.id == episode_id))
        return result.scalar_one_or_none()

    async def delete_seasons_for_item(self, media_item_id: int):
        stmt = delete(MediaSeason).where(MediaSeason.media_item_id == media_item_id)
        await self.db.execute(stmt)

    async def get_episodes_by_item(self, media_item_id: int) -> list[MediaEpisode]:
        """获取媒体条目下的所有剧集（跨季）"""
        result = await self.db.execute(
            select(MediaEpisode)
            .join(MediaSeason, MediaEpisode.season_id == MediaSeason.id)
            .where(MediaSeason.media_item_id == media_item_id)
            .order_by(MediaSeason.season_number, MediaEpisode.episode_number)
        )
        return list(result.scalars().all())

    # ── 字幕 ──
    async def create_subtitle(self, **kwargs) -> Subtitle:
        sub = Subtitle(**kwargs)
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def get_subtitles_by_item(self, media_item_id: int) -> list[Subtitle]:
        result = await self.db.execute(
            select(Subtitle).where(Subtitle.media_item_id == media_item_id)
        )
        return list(result.scalars().all())

    async def delete_subtitles_for_item(self, media_item_id: int):
        stmt = delete(Subtitle).where(Subtitle.media_item_id == media_item_id)
        await self.db.execute(stmt)

    # ── 统计 ──
    async def get_stats(self) -> dict[str, Any]:
        total_items = (await self.db.execute(select(func.count(MediaItem.id)))).scalar() or 0
        total_movies = (await self.db.execute(
            select(func.count(MediaItem.id)).where(MediaItem.media_type == "movie")
        )).scalar() or 0
        total_tv = (await self.db.execute(
            select(func.count(MediaItem.id)).where(MediaItem.media_type.in_(["tv", "anime"]))
        )).scalar() or 0
        total_size = (await self.db.execute(select(func.sum(MediaItem.file_size)))).scalar() or 0
        return {
            "total_items": total_items,
            "total_movies": total_movies,
            "total_tv": total_tv,
            "total_size": total_size,
        }

    # ── 收藏 CRUD ──
    async def add_favorite(self, user_id: int, media_item_id: int) -> Favorite:
        """添加收藏（幂等，已存在则直接返回）"""
        existing = await self.db.execute(
            select(Favorite).where(Favorite.user_id == user_id, Favorite.media_item_id == media_item_id)
        )
        fav = existing.scalar_one_or_none()
        if fav:
            return fav
        fav = Favorite(user_id=user_id, media_item_id=media_item_id)
        self.db.add(fav)
        await self.db.flush()
        await self.db.refresh(fav)
        return fav

    async def remove_favorite(self, user_id: int, media_item_id: int) -> bool:
        """移除收藏"""
        result = await self.db.execute(
            delete(Favorite).where(Favorite.user_id == user_id, Favorite.media_item_id == media_item_id)
        )
        await self.db.flush()
        return result.rowcount > 0

    async def is_favorite(self, user_id: int, media_item_id: int) -> bool:
        """检查是否已收藏"""
        result = await self.db.execute(
            select(func.count(Favorite.id)).where(Favorite.user_id == user_id, Favorite.media_item_id == media_item_id)
        )
        return (result.scalar() or 0) > 0

    async def get_favorites(self, user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[MediaItem], int]:
        """获取用户收藏列表"""
        from sqlalchemy.orm import selectinload

        # JOIN favorites 表以获取 created_at
        count_query = select(func.count(MediaItem.id)).select_from(
            join(MediaItem, Favorite, MediaItem.id == Favorite.media_item_id)
        ).where(Favorite.user_id == user_id)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(MediaItem)
            .select_from(join(MediaItem, Favorite, MediaItem.id == Favorite.media_item_id))
            .where(Favorite.user_id == user_id)
            .order_by(desc(Favorite.created_at))
            .offset((page - 1) * page_size).limit(page_size)
        )
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def get_favorite_ids(self, user_id: int) -> set[int]:
        """获取用户所有收藏的媒体 ID 集合"""
        result = await self.db.execute(
            select(Favorite.media_item_id).where(Favorite.user_id == user_id)
        )
        return set(row[0] for row in result.all())
