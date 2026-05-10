"""
播放列表服务
"""
import logging
from typing import Any

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.playlist.models import Playlist, PlaylistItem
from app.playlist.schemas import (
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistOut,
    PlaylistDetailOut,
    PlaylistItemAdd,
    PlaylistItemOut,
)
from app.media.models import MediaItem

logger = logging.getLogger(__name__)


class PlaylistService:
    """播放列表服务"""

    async def list_playlists(self, user_id: int, include_public: bool = True) -> list[PlaylistOut]:
        """列出用户的播放列表"""
        async with async_session_factory() as db:
            query = select(Playlist).where(
                Playlist.user_id == user_id
            )
            if include_public:
                query = query.where(
                    (Playlist.user_id == user_id) | (Playlist.is_public == True)
                )
            
            query = query.order_by(Playlist.updated_at.desc())
            result = await db.execute(query)
            playlists = result.scalars().all()
            
            outputs = []
            for p in playlists:
                # 统计项数量和总时长
                count_result = await db.execute(
                    select(func.count(PlaylistItem.id))
                    .where(PlaylistItem.playlist_id == p.id)
                )
                item_count = count_result.scalar() or 0
                
                duration_result = await db.execute(
                    select(func.sum(MediaItem.duration))
                    .join(PlaylistItem, PlaylistItem.media_item_id == MediaItem.id)
                    .where(PlaylistItem.playlist_id == p.id)
                )
                total_duration = duration_result.scalar() or 0
                
                outputs.append(PlaylistOut(
                    id=p.id,
                    user_id=p.user_id,
                    name=p.name,
                    description=p.description,
                    cover_url=p.cover_url,
                    is_public=p.is_public,
                    item_count=item_count,
                    total_duration=total_duration,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                ))
            
            return outputs

    async def get_playlist(self, playlist_id: int, user_id: int) -> PlaylistDetailOut | None:
        """获取播放列表详情"""
        async with async_session_factory() as db:
            # 查询播放列表
            query = select(Playlist).where(Playlist.id == playlist_id)
            result = await db.execute(query)
            playlist = result.scalar_one_or_none()
            
            if not playlist:
                return None
            
            # 检查权限
            if not playlist.is_public and playlist.user_id != user_id:
                return None
            
            # 查询列表项
            items_query = (
                select(PlaylistItem)
                .where(PlaylistItem.playlist_id == playlist_id)
                .order_by(PlaylistItem.position)
            )
            items_result = await db.execute(items_query)
            items = items_result.scalars().all()
            
            # 获取媒体详情
            item_outs = []
            for item in items:
                media = await db.get(MediaItem, item.media_item_id)
                item_outs.append(PlaylistItemOut(
                    id=item.id,
                    playlist_id=item.playlist_id,
                    media_item_id=item.media_item_id,
                    position=item.position,
                    added_at=item.added_at,
                    media_title=media.title if media else None,
                    media_poster=media.poster_url if media else None,
                    media_type=media.media_type if media else None,
                    media_duration=media.duration if media else None,
                ))
            
            return PlaylistDetailOut(
                id=playlist.id,
                user_id=playlist.user_id,
                name=playlist.name,
                description=playlist.description,
                cover_url=playlist.cover_url,
                is_public=playlist.is_public,
                item_count=len(items),
                total_duration=sum(i.media_duration or 0 for i in item_outs),
                created_at=playlist.created_at,
                updated_at=playlist.updated_at,
                items=item_outs,
            )

    async def create_playlist(self, user_id: int, data: PlaylistCreate) -> PlaylistOut:
        """创建播放列表"""
        async with async_session_factory() as db:
            playlist = Playlist(
                user_id=user_id,
                name=data.name,
                description=data.description,
                is_public=data.is_public,
            )
            db.add(playlist)
            await db.commit()
            await db.refresh(playlist)
            
            return PlaylistOut(
                id=playlist.id,
                user_id=playlist.user_id,
                name=playlist.name,
                description=playlist.description,
                cover_url=playlist.cover_url,
                is_public=playlist.is_public,
                item_count=0,
                total_duration=0,
                created_at=playlist.created_at,
                updated_at=playlist.updated_at,
            )

    async def update_playlist(
        self, 
        playlist_id: int, 
        user_id: int, 
        data: PlaylistUpdate
    ) -> PlaylistOut | None:
        """更新播放列表"""
        async with async_session_factory() as db:
            playlist = await db.get(Playlist, playlist_id)
            
            if not playlist or playlist.user_id != user_id:
                return None
            
            if data.name is not None:
                playlist.name = data.name
            if data.description is not None:
                playlist.description = data.description
            if data.cover_url is not None:
                playlist.cover_url = data.cover_url
            if data.is_public is not None:
                playlist.is_public = data.is_public
            
            await db.commit()
            await db.refresh(playlist)
            
            # 统计
            count_result = await db.execute(
                select(func.count(PlaylistItem.id))
                .where(PlaylistItem.playlist_id == playlist_id)
            )
            item_count = count_result.scalar() or 0
            
            return PlaylistOut(
                id=playlist.id,
                user_id=playlist.user_id,
                name=playlist.name,
                description=playlist.description,
                cover_url=playlist.cover_url,
                is_public=playlist.is_public,
                item_count=item_count,
                total_duration=0,
                created_at=playlist.created_at,
                updated_at=playlist.updated_at,
            )

    async def delete_playlist(self, playlist_id: int, user_id: int) -> bool:
        """删除播放列表"""
        async with async_session_factory() as db:
            playlist = await db.get(Playlist, playlist_id)
            
            if not playlist or playlist.user_id != user_id:
                return False
            
            await db.delete(playlist)
            await db.commit()
            return True

    async def add_item(
        self, 
        playlist_id: int, 
        user_id: int, 
        data: PlaylistItemAdd
    ) -> PlaylistItemOut | None:
        """添加项目到播放列表"""
        async with async_session_factory() as db:
            playlist = await db.get(Playlist, playlist_id)
            
            if not playlist or playlist.user_id != user_id:
                return None
            
            # 检查是否已存在
            existing = await db.execute(
                select(PlaylistItem).where(
                    PlaylistItem.playlist_id == playlist_id,
                    PlaylistItem.media_item_id == data.media_id
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Media already in playlist")
            
            # 获取当前位置
            if data.position is not None:
                position = data.position
            else:
                max_pos = await db.scalar(
                    select(func.max(PlaylistItem.position))
                    .where(PlaylistItem.playlist_id == playlist_id)
                )
                position = (max_pos or 0) + 1
            
            # 创建项
            item = PlaylistItem(
                playlist_id=playlist_id,
                media_item_id=data.media_id,
                position=position,
            )
            db.add(item)
            
            # 更新播放列表时间
            playlist.updated_at = func.now()
            
            await db.commit()
            await db.refresh(item)
            
            # 获取媒体详情
            media = await db.get(MediaItem, data.media_id)
            
            return PlaylistItemOut(
                id=item.id,
                playlist_id=item.playlist_id,
                media_item_id=item.media_item_id,
                position=item.position,
                added_at=item.added_at,
                media_title=media.title if media else None,
                media_poster=media.poster_url if media else None,
                media_type=media.media_type if media else None,
                media_duration=media.duration if media else None,
            )

    async def remove_item(
        self, 
        playlist_id: int, 
        item_id: int, 
        user_id: int
    ) -> bool:
        """从播放列表移除项目"""
        async with async_session_factory() as db:
            playlist = await db.get(Playlist, playlist_id)
            
            if not playlist or playlist.user_id != user_id:
                return False
            
            item = await db.get(PlaylistItem, item_id)
            
            if not item or item.playlist_id != playlist_id:
                return False
            
            await db.delete(item)
            await db.commit()
            return True

    async def reorder_items(
        self, 
        playlist_id: int, 
        user_id: int, 
        item_ids: list[int]
    ) -> bool:
        """重新排序播放列表项"""
        async with async_session_factory() as db:
            playlist = await db.get(Playlist, playlist_id)
            
            if not playlist or playlist.user_id != user_id:
                return False
            
            # 更新位置
            for position, item_id in enumerate(item_ids):
                item = await db.get(PlaylistItem, item_id)
                if item and item.playlist_id == playlist_id:
                    item.position = position
            
            # 更新播放列表时间
            playlist.updated_at = func.now()
            
            await db.commit()
            return True
