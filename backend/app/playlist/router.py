"""
播放列表 API 路由
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body

logger = logging.getLogger(__name__)

from app.playlist.schemas import (
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistOut,
    PlaylistDetailOut,
    PlaylistItemAdd,
    PlaylistItemOut,
    PlaylistReorder,
)
from app.playlist.service import PlaylistService
from app.common.schemas import SuccessResponse, ErrorResponse
from app.deps import CurrentUser, AdminUser

router = APIRouter(prefix="/playlists", tags=["playlists"])


def get_service() -> PlaylistService:
    return PlaylistService()


# ── 播放列表 CRUD ──

@router.get(
    "",
    response_model=SuccessResponse[list[PlaylistOut]],
)
async def list_playlists(user: CurrentUser):
    """
    获取用户的播放列表
    
    返回用户创建的所有播放列表，以及公开的播放列表
    """
    try:
        service = get_service()
        playlists = await service.list_playlists(user.id)
        return SuccessResponse.ok(playlists)
    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"Playlist list error: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


# 兼容前端请求带尾部斜杠的情况
@router.get(
    "/",
    response_model=SuccessResponse[list[PlaylistOut]],
    include_in_schema=False,
)
async def list_playlists_with_slash(user: CurrentUser):
    """获取播放列表（兼容尾部斜杠）"""
    service = get_service()
    playlists = await service.list_playlists(user.id)
    return SuccessResponse.ok(playlists)


@router.get(
    "/{playlist_id}",
    response_model=SuccessResponse[PlaylistDetailOut],
    responses={
        404: {"model": ErrorResponse},
    }
)
async def get_playlist(
    playlist_id: Annotated[int, Path(description="播放列表 ID")],
    user: CurrentUser,
):
    """
    获取播放列表详情
    
    包括所有媒体项及其详细信息
    """
    service = get_service()
    playlist = await service.get_playlist(playlist_id, user.id)
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return SuccessResponse.ok(playlist)


@router.post(
    "",
    response_model=SuccessResponse[PlaylistOut],
    status_code=201,
)
async def create_playlist(
    data: PlaylistCreate,
    user: CurrentUser,
):
    """
    创建播放列表
    
    创建后自动属于当前用户
    """
    service = get_service()
    playlist = await service.create_playlist(user.id, data)
    return SuccessResponse.ok(playlist)


# 兼容前端请求带尾部斜杠的情况
@router.post(
    "/",
    response_model=SuccessResponse[PlaylistOut],
    status_code=201,
    include_in_schema=False,
)
async def create_playlist_with_slash(
    data: PlaylistCreate,
    user: CurrentUser,
):
    """创建播放列表（兼容尾部斜杠）"""
    service = get_service()
    playlist = await service.create_playlist(user.id, data)
    return SuccessResponse.ok(playlist)


@router.put(
    "/{playlist_id}",
    response_model=SuccessResponse[PlaylistOut],
    responses={
        404: {"model": ErrorResponse},
    }
)
async def update_playlist(
    playlist_id: Annotated[int, Path(description="播放列表 ID")],
    data: PlaylistUpdate,
    user: CurrentUser,
):
    """
    更新播放列表
    
    只能更新自己创建的播放列表
    """
    service = get_service()
    playlist = await service.update_playlist(playlist_id, user.id, data)
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return SuccessResponse.ok(playlist)


@router.delete(
    "/{playlist_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
    }
)
async def delete_playlist(
    playlist_id: Annotated[int, Path(description="播放列表 ID")],
    user: CurrentUser,
):
    """
    删除播放列表
    
    只能删除自己创建的播放列表
    """
    service = get_service()
    success = await service.delete_playlist(playlist_id, user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found")


# ── 播放列表项 ──

@router.post(
    "/{playlist_id}/items",
    response_model=SuccessResponse[PlaylistItemOut],
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    }
)
async def add_playlist_item(
    playlist_id: Annotated[int, Path(description="播放列表 ID")],
    data: PlaylistItemAdd,
    user: CurrentUser,
):
    """
    添加项目到播放列表
    
    - media_id: 媒体 ID
    - position: 插入位置（可选，默认追加到末尾）
    """
    service = get_service()
    try:
        item = await service.add_item(playlist_id, user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not item:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return SuccessResponse.ok(item)


@router.delete(
    "/{playlist_id}/items/{item_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
    }
)
async def remove_playlist_item(
    playlist_id: Annotated[int, Path(description="播放列表 ID")],
    item_id: Annotated[int, Path(description="列表项 ID")],
    user: CurrentUser,
):
    """
    从播放列表移除项目
    """
    service = get_service()
    success = await service.remove_item(playlist_id, item_id, user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist or item not found")


@router.put(
    "/{playlist_id}/reorder",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
    }
)
async def reorder_playlist(
    playlist_id: Annotated[int, Path(description="播放列表 ID")],
    data: PlaylistReorder,
    user: CurrentUser,
):
    """
    重新排序播放列表
    
    传入新的项 ID 顺序
    """
    service = get_service()
    success = await service.reorder_items(playlist_id, user.id, data.item_ids)
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found")
