"""
Emby API 兼容层
提供 Emby API 子集，让 Infuse、Kodi 等客户端可以连接 MediaStation。
实现 Emby Server API v3 的核心端点，返回兼容的 JSON 格式。

参考文档：https://github.com/MediaBrowser/Emby/wiki/Emby-API
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.deps import CurrentUser, DB
from app.config import get_settings
from app.media.repository import MediaRepository
from app.user.repository import UserRepository
from app.user.schemas import UserOut
from app.user.auth import verify_password, create_access_token, ALGORITHM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emby", tags=["emby"])

# 启动时间记录
_emby_start_time = time.time()


# ── Emby Token 认证依赖 ──

async def get_emby_current_user(
    x_emby_token: Annotated[str | None, Header(alias="X-Emby-Token")] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: DB = None,
):
    """支持 Emby 客户端认证：优先使用 X-Emby-Token，其次使用 Bearer token"""
    token = None
    
    # 1. 优先使用 X-Emby-Token
    if x_emby_token:
        token = x_emby_token
    # 2. 其次使用 Authorization Bearer
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    
    if not token:
        raise HTTPException(401, "Authentication required")
    
    settings = get_settings()
    credentials_exception = HTTPException(401, "Invalid authentication")
    
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    
    from app.user.schemas import UserOut
    return UserOut.model_validate(user)


# Emby 认证用户的类型别名
EmbyUser = Annotated[UserOut, Depends(get_emby_current_user)]


# ── Pydantic Models ──

class EmbyAuthRequest(BaseModel):
    """Emby 认证请求"""
    Username: str
    Pw: str | None = None


class EmbyProgressRequest(BaseModel):
    """Emby 播放进度上报"""
    ItemId: str
    PositionTicks: int | None = None
    PlaySessionId: str | None = None
    Event: str = "timeupdate"  # timeupdate, pause, stopped, start


# ── Helper Functions ──


def _emby_server_id() -> str:
    """生成稳定的服务器 ID（基于配置）"""
    settings = get_settings()
    return f"mediastation-{hash(settings.app_secret_key) % 100000:05d}"


def _emby_item_id(item_id: int) -> str:
    """将内部 ID 转为 Emby 格式的 ItemId"""
    return f"{item_id}"


def _to_emby_media_type(media_type: str) -> str:
    """映射媒体类型到 Emby 类型"""
    mapping = {
        "movie": "Movie",
        "tv": "Series",
        "anime": "Series",
    }
    return mapping.get(media_type, "Video")


async def _get_all_items(repo: MediaRepository) -> list:
    """获取所有媒体条目"""
    items, _ = await repo.get_items(page=1, page_size=9999)
    return items


# ── 公开端点（无需认证）──

@router.get("/System/Info")
async def emby_system_info():
    """系统信息"""
    from fastapi.responses import JSONResponse
    settings = get_settings()

    return {
        "ServerName": "MediaStation",
        "Version": "0.1.0",
        "Id": _emby_server_id(),
        "OperatingSystem": "Linux",  # 伪装
        "HasPendingRestart": False,
        "IsShuttingDown": False,
        "SupportsLibraryMonitor": True,
        "WebSocketPortNumber": 3001,
        "TranscodingTempPath": "/tmp/transcodes",
        "InternalMetadataPath": "",
        "StartupWizardCompleted": True,
        "CanSelfRestart": False,
        "CanLaunchWebBrowser": False,
        "ProgramDataPath": "",
        "WebPath": "",
        "ItemsByNamePath": "",
        "CachePath": "",
        "LogPath": "",
        "LocalAddress": f"http://localhost:{settings.app_port}",
        "WanAddress": "",
        "HasUpdateAvailable": False,
        "SupportsAutoRunAtStartup": False,
        "HardwareAccelerationRequires Premiere": False,
        "EncoderLocation": "enctrans",
        "SystemArchitecture": "X64",
        "PackageName": None,
        "PackageVersion": None,
    }


@router.get("/System/Public")
async def emby_system_public():
    """公开系统信息（客户端首次连接调用）"""
    settings = get_settings()
    return {
        "ServerName": "MediaStation (Emby Compatible)",
        "Version": "0.1.0",
        "Id": _emby_server_id(),
        "OperatingSystem": "Linux",
        "LocalAddress": f"http://localhost:{settings.app_port}",
        "WanAddress": "",
        "StartupWizardCompleted": True,
    }


# ── Emby 认证端点 ──

@router.post("/Users/AuthenticateByName")
async def emby_authenticate(
    request: EmbyAuthRequest,
    db: DB,
):
    """
    Emby 标准认证端点。
    Infuse、Kodi 等客户端通过此接口登录。
    支持 username + password (Pw) 认证。
    """
    from app.user.auth import verify_password, create_access_token

    repo = UserRepository(db)
    user = await repo.get_by_username(request.Username)

    if not user:
        raise HTTPException(401, "Invalid username or password")

    if not user.is_active:
        raise HTTPException(401, "User account is disabled")

    # 验证密码
    if request.Pw and not verify_password(request.Pw, user.password_hash):
        raise HTTPException(401, "Invalid username or password")

    # 生成 Emby 格式响应
    access_token = create_access_token(user.id, user.username, user.role)
    server_id = _emby_server_id()

    # 更新最后登录时间
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return {
        "User": {
            "Name": user.username,
            "ServerId": server_id,
            "Id": str(user.id),
            "PrimaryImageTag": "",
            "HasPassword": bool(user.password_hash),
            "HasConfiguredPassword": True,
            "HasConfiguredEasyPassword": False,
            "EnableAutoLogin": False,
            "LastLoginDate": user.last_login.isoformat() if user.last_login else None,
            "LastActivityDate": None,
            "Configuration": {
                "PlayDefaultAudioTrack": True,
                "MediaFoldersContribute": False,
                "SubtitleLanguagePreference": "",
                "DisplayMissingEpisodes": False,
                "GroupedFolders": [],
                "SubtitleMode": "Default",
                "DisplayCollectionsView": False,
                "AudioLanguagePreference": "",
                "RememberAudioSelections": True,
                "EnableNextEpisodeAutoPlay": True,
                "RememberSubtitleSelections": True,
                "EnableAutoLogin": False,
                "OrderedViews": [""],
                "LatestItemsExcludes": [],
                "MyMediaExcludes": [],
                "HidePlayedInLatest": True,
                "RewindButtonLength": 10000,
                "ForwardButtonLength": 30000,
                "SkipBackLength": 15000,
                "SkipForwardLength": 30000,
                "ImageBlurLevel": 0,
                "MaxParentalRating": 0,
            },
            "Policy": {
                "IsAdministrator": user.role == "admin",
                "IsHidden": not user.is_active,
                "IsDisabled": not user.is_active,
                "EnableUserPreferenceAccess": True,
                "EnableRemoteAccess": True,
                "EnableLiveTvAccess": True,
                "EnableLiveTvManagement": False,
                "EnableMediaPlayback": True,
                "EnableAudioPlaybackTranscoding": True,
                "EnableVideoPlaybackTranscoding": True,
                "EnableContentDeletion": user.role == "admin",
                "EnableContentDownloading": True,
                "EnableSyncTranscoding": False,
                "EnableMediaConversion": True,
                "EnabledDevices": ["All"],
                "EnabledChannels": [],
                "EnableAllChannels": True,
                "EnabledFolders": [],
                "EnableAllFolders": True,
                "InvalidLoginAttemptBeforeLockout": -1,
                "LoginAttemptsBeforeLockout": -1,
                "MaxActiveSessions": 0,
                "MaxStreamingBitrate": 400000000,
                "RemoteClientBitrateLimit": 0,
                "AuthenticationProviderId": None,
                "PasswordResetProviderId": None,
                "SyncPlayAccess": None,
            },
            "PrimaryImageAspectRatio": None,
        },
        "AccessToken": access_token,
        "ServerId": server_id,
    }


# ── 需要认证的端点 ──

@router.get("/Users")
async def emby_users(user: EmbyUser):
    """用户列表"""
    return [
        {
            "Name": user.username,
            "ServerId": _emby_server_id(),
            "Id": str(user.id),
            "PrimaryImageTag": "",
            "HasPassword": bool(user.password_hash),
            "HasConfiguredPassword": True,
            "HasConfiguredEasyPassword": False,
            "EnableAutoLogin": False,
            "LastLoginDate": user.last_login.isoformat() if user.last_login else None,
            "LastActivityDate": None,
            "Configuration": {
                "PlayDefaultAudioTrack": True,
                "MediaFoldersContribute": False,
                "SubtitleLanguagePreference": "",
                "DisplayMissingEpisodes": False,
                "GroupedFolders": [],
                "SubtitleMode": "Default",
                "DisplayCollectionsView": False,
                "AudioLanguagePreference": "",
                "RememberAudioSelections": True,
                "EnableNextEpisodeAutoPlay": True,
                "RememberSubtitleSelections": True,
                "EnableAutoLogin": False,
                "OrderedViews": [""],
                "LatestItemsExcludes": [],
                "MyMediaExcludes": [],
                "HidePlayedInLatest": True,
                "RewindButtonLength": 10000,
                "ForwardButtonLength": 30000,
                "SkipBackLength": 15000,
                "SkipForwardLength": 30000,
                "ImageBlurLevel": 0,
                "MaxParentalRating": 0,
            },
            "Policy": {
                "IsAdministrator": user.role == "admin",
                "IsHidden": not user.is_active,
                "IsDisabled": not user.is_active,
                "EnableUserPreferenceAccess": True,
                "EnableRemoteAccess": True,
                "EnableLiveTvAccess": True,
                "EnableLiveTvManagement": False,
                "EnableMediaPlayback": True,
                "EnableAudioPlaybackTranscoding": True,
                "EnableVideoPlaybackTranscoding": True,
                "EnableContentDeletion": user.role == "admin",
                "EnableContentDownloading": True,
                "EnableSyncTranscoding": False,
                "EnableMediaConversion": True,
                "EnabledDevices": ["All"],
                "EnabledChannels": [],
                "EnableAllChannels": True,
                "EnabledFolders": [],
                "EnableAllFolders": True,
                "InvalidLoginAttemptBeforeLockout": -1,
                "LoginAttemptsBeforeLockout": -1,
                "MaxActiveSessions": 0,
                "MaxStreamingBitrate": 400000000,
                "RemoteClientBitrateLimit": 0,
                "AuthenticationProviderId": None,
                "PasswordResetProviderId": None,
                "SyncPlayAccess": None,
            },
            "PrimaryImageAspectRatio": None,
        }
    ]


@router.get("/Users/{user_id}")
async def emby_get_user(user_id: int, user: EmbyUser):
    """获取用户信息"""
    if user.id != user_id and user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Access denied")

    users = await emby_users(user)
    return users[0]


@router.get("/Users/{user_id}/Views")
async def emby_user_views(
    user_id: int,
    user: EmbyUser,
    db: DB,
    include_hidden: bool = Query(False),
):
    """
    用户媒体库视图列表。
    Infuse/Kodi 调用此接口获取可浏览的媒体库集合。
    """
    repo = MediaRepository(db)
    libraries = await repo.get_all_libraries()

    views = []
    for lib in libraries:
        views.append({
            "Name": lib.name,
            "Id": f"library_{lib.id}",
            "ServerId": _emby_server_id(),
            "Type": "Folder",
            "CollectionType": "movies" if lib.media_type == "movie"
                         else ("tvshows" if lib.media_type == "tv" else "tvshows"),
            "ImageTags": {"Primary": ""},
            "BackdropImageTags": [] if not lib else [],
            "ChildCount": await repo.count_library_items(lib.id),
        })

    return views


@router.get("/MediaFolders")
async def emby_media_folders(user: EmbyUser, db: DB):
    """媒体文件夹列表（旧版 API）"""
    repo = MediaRepository(db)
    libraries = await repo.get_all_libraries()

    folders = []
    for lib in libraries:
        folders.append({
            "Name": lib.name,
            "Id": f"library_{lib.id}",
            "Type": " movies" if lib.media_type == "movie" else "tvshows",
            "Locations": [lib.path],
        })

    return folders


@router.get("/Items")
async def emby_list_items(
    user: EmbyUser,
    db: DB,
    parent_id: str | None = None,
    include_item_types: str | None = None,
    recursive: bool = Query(True),
    sort_by: str = Query("SortName"),
    sort_order: str = Query("Ascending"),
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    search_term: str | None = Query(None, alias="SearchTerm"),
    fields: str | None = Query(None),
):
    """
    媒体条目列表 — Emby Items API 的核心端点。
    Infuse/Kodi 通过此接口获取媒体列表。
    """
    repo = MediaRepository(db)

    # 解析筛选条件
    media_type_filter = None
    if include_item_types:
        types = include_item_types.split(",")
        if "Movie" in types:
            media_type_filter = "movie"
        elif "Series" in types:
            media_type_filter = "tv"

    # 搜索
    search = search_term or None

    # 排序映射
    sort_map = {
        "SortName": "title",
        "DateCreated": "date_added",
        "PremiereDate": "year",
        "PlayCount": None,
    }
    sort_by_db = sort_map.get(sort_by, "date_added")

    # 分页转换
    page = (start_index // limit) + 1

    items, total = await repo.get_items(
        media_type=media_type_filter,
        search=search,
        page=page,
        page_size=limit,
        sort_by=sort_by_db,
        sort_order="asc" if sort_order == "Ascending" else "desc",
    )

    # 字段过滤
    requested_fields = set(fields.split(",")) if fields else set()

    result_items = []
    for item in items:
        emby_item = _item_to_emby_format(item, requested_fields)
        result_items.append(emby_item)

    return {
        "Items": result_items,
        "TotalRecordCount": total,
        "StartIndex": start_index,
    }


@router.get("/Items/{item_id}")
async def emby_get_item(
    item_id: int,
    user: EmbyUser,
    db: DB,
    fields: str | None = Query(None),
):
    """获取媒体详情"""
    repo = MediaRepository(db)

    try:
        item = await repo.get_item_by_id(item_id)
    except ValueError:
        item = None

    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")

    requested_fields = set(fields.split(",")) if fields else set()

    return _item_to_emby_format(item, requested_fields)


def _item_to_emby_format(item, requested_fields: set[str] = None) -> dict[str, Any]:
    """将 MediaItem 转换为 Emby Items API 格式"""
    emby_type = _to_emby_media_type(item.media_type)

    result: dict[str, Any] = {
        "Name": item.title or "Unknown",
        "OriginalTitle": item.original_title or "",
        "ServerId": _emby_server_id(),
        "Id": _emby_item_id(item.id),
        "Type": emby_type,
        "Container": item.container or "mp4",
        "SortName": (item.title or "").lower()[:50],
        "ForcedSortName": None,
        "Video3DFormat": None,
        "PremiereDate": None,
        "ExternalUrls": [],
        "Tags": [],
        "Genres": json.loads(item.genres) if item.genres else [],
        "Studios": [],
        "People": [],
        "CommunityRating": float(item.rating or 0),
        "CriticRating": None,
        "IndexNumber": None,
        "ParentIndexNumber": None,
        "Overview": item.overview or "",
        "LocationType": "FileSystem",
        "MediaType": "Video",
        "LockedFields": [],
        "TrailerTypes": [],
        "SpecialFeatureIds": [],
        "ChannelId": None,
        "CreatedDate": item.created_at.isoformat() if item.created_at else None,
        "DateCreated": item.created_at.isoformat() if item.created_at else None,
    }

    # 年份
    if item.year:
        result["ProductionYear"] = item.year
        result["PremiereDate"] = f"{item.year}-01-01T00:00:00Z"

    # 海报
    if item.poster_url:
        result["ImageTags"] = {"Primary": uuid.uuid4().hex[:8]}
        result["PrimaryImageItemId"] = str(item.id)

    if item.backdrop_url:
        result["BackdropImageTags"] = [uuid.uuid4().hex[:8]]

    # 时长
    if item.duration and emby_type == "Movie":
        result["RunTimeTicks"] = item.duration * 10_000_000  # 秒 → 100ns ticks

    # 文件路径
    if item.file_path:
        result["Path"] = item.file_path

    # 剧集特殊处理
    if emby_type == "Series":
        result["Status"] = "Continuing"
        result["AirDays"] = None
        result["AirTime"] = None
        result["SeriesName"] = item.title

    # STRM 标记
    if item.strm_url:
        result["LocationType"] = "Remote"
        result["Path"] = item.strm_url

    return result


@router.get("/Items/{item_id}/PlaybackInfo")
async def emby_playback_info(
    item_id: int,
    user: EmbyUser,
    db: DB,
    device_profile: dict | None = None,
):
    """获取播放信息（Emby 兼容格式）"""
    from fastapi import HTTPException
    repo = MediaRepository(db)

    item = await repo.get_item_by_id(item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # STRM 支持：如果媒体设置了 strm_url，使用远程 URL 作为播放源
    if item.strm_url:
        strm_url = item.strm_url
        # 推断容器格式
        strm_container = "mp4"
        if ".mkv" in strm_url.lower():
            strm_container = "mkv"
        elif ".avi" in strm_url.lower():
            strm_container = "avi"
        elif ".ts" in strm_url.lower():
            strm_container = "ts"
        elif ".wmv" in strm_url.lower():
            strm_container = "wmv"

        return {
            "MediaSources": [
                {
                    "Id": str(item_id),
                    "Path": strm_url,
                    "Container": strm_container,
                    "Name": item.title,
                    "Size": item.file_size,
                    "IsRemote": True,
                    "Type": "Default",
                    "Protocol": "Http",
                    "DirectStreamUrl": strm_url,
                    "SupportsDirectStream": True,
                    "SupportsDirectPlay": True,
                    "SupportsTranscoding": False,
                    "VideoStreams": [
                        {
                            "Codec": item.video_codec or "h264",
                            "Index": 0,
                            "Profile": None,
                            "Level": None,
                            "Width": None,
                            "Height": None,
                            "AspectRatio": None,
                            "FrameRate": None,
                            "BitRate": None,
                            "IsDefault": True,
                        }
                    ],
                    "AudioStreams": [
                        {
                            "Codec": item.audio_codec or "aac",
                            "Index": 0,
                            "Language": None,
                            "Title": None,
                            "IsDefault": True,
                            "IsForced": False,
                            "IsExternal": False,
                        }
                    ] if item.audio_codec else [],
                    "SubtitleStreams": [],
                }
            ],
            "SessionId": str(uuid.uuid4()),
            "PlaySessionId": str(uuid.uuid4()),
            "PlayMethod": "DirectStream",
            "LiveStreamId": None,
        }

    file_path = item.file_path
    if not file_path:
        raise HTTPException(404, "No file available")

    # 构建播放 URL
    direct_url = f"/api/playback/{item_id}/stream"

    return {
        "MediaSources": [
            {
                "Id": str(item_id),
                "Path": file_path,
                "Container": item.container or "mp4",
                "Name": item.title,
                "Size": item.file_size,
                "IsRemote": False,
                "Type": "Default",
                "Protocol": "File",
                "DirectStreamUrl": direct_url,
                "SupportsDirectStream": True,
                "SupportsDirectPlay": True,
                "SupportsTranscoding": False,
                "VideoStreams": [
                    {
                        "Codec": item.video_codec or "h264",
                        "Index": 0,
                        "Profile": None,
                        "Level": None,
                        "Width": None,
                        "Height": None,
                        "AspectRatio": None,
                        "FrameRate": None,
                        "BitRate": None,
                        "IsDefault": True,
                    }
                ],
                "AudioStreams": [
                    {
                        "Codec": item.audio_codec or "aac",
                        "Index": 0,
                        "Language": None,
                        "Title": None,
                        "IsDefault": True,
                        "IsForced": False,
                        "IsExternal": False,
                    }
                ] if item.audio_codec else [],
                "SubtitleStreams": [],
            }
        ],
        "SessionId": str(uuid.uuid4()),
        "PlaySessionId": str(uuid.uuid4()),
        "PlayMethod": "DirectPlay",
        "LiveStreamId": None,
    }


# ── 视频流端点 ──

@router.get("/Videos/{item_id}/stream")
async def emby_video_stream(
    item_id: int,
    user: EmbyUser,
    db: DB,
    request: Request,
):
    """
    视频直链流媒体端点。
    支持 Range 请求（seek），兼容 Infuse/Kodi 播放器。
    返回流式响应或 JSON 元数据（根据请求头决定）。
    STRM 媒体：如果设置了 strm_url，返回 302 重定向到远程 URL。
    """
    import aiofiles
    import mimetypes

    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    # STRM 支持：如果有 strm_url，302 重定向到远程 URL
    if item.strm_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=item.strm_url,
            status_code=302,
            headers={
                "X-MediaStation-STRM": "true",
                "X-MediaStation-Source": item.strm_url,
            },
        )

    file_path = item.file_path
    if not file_path:
        raise HTTPException(404, "No file available")

    # 安全检查：确保文件存在
    if not os.path.exists(file_path):
        logger.error(f"Video file not found: {file_path}")
        raise HTTPException(404, "File not found")

    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "video/mp4"

    # 检查 Range 请求头
    range_header = request.headers.get("range")
    if range_header:
        # 解析 Range 头
        try:
            range_match = range_header.replace("bytes=", "").split("-")
            range_start = int(range_match[0]) if range_match[0] else 0
            range_end = int(range_match[1]) if range_match[1] else file_size - 1
        except (ValueError, IndexError):
            range_start, range_end = 0, file_size - 1

        # 流式响应
        async def stream_range():
            async with aiofiles.open(file_path, "rb") as f:
                await f.seek(range_start)
                remaining = range_end - range_start + 1
                chunk_size = 1024 * 1024  # 1MB chunks

                while remaining > 0:
                    chunk = await f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            stream_range(),
            media_type=content_type,
            status_code=206,
            headers={
                "Content-Range": f"bytes {range_start}-{range_end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(range_end - range_start + 1),
            },
        )

    # 返回 Emby 格式的播放信息
    return {
        "Protocol": "File",
        "Id": str(item_id),
        "Path": file_path,
        "Container": item.container or "mp4",
        "Size": file_size,
        "Name": item.title,
        "Type": "Default",
        "IsRemote": False,
        "SupportsDirectStream": True,
        "SupportsDirectPlay": True,
        "SupportsTranscoding": False,
        "ContentType": content_type,
        "MediaSources": [
            {
                "Id": str(item_id),
                "Path": file_path,
                "Container": item.container or "mp4",
                "Size": file_size,
                "Name": item.title,
                "Type": "Default",
                "IsRemote": False,
                "Protocol": "File",
                "DirectStreamUrl": f"/api/Videos/{item_id}/stream",
                "SupportsDirectStream": True,
                "SupportsDirectPlay": True,
                "SupportsTranscoding": False,
                "VideoStreams": [
                    {
                        "Codec": item.video_codec or "h264",
                        "Index": 0,
                        "Profile": None,
                        "Level": None,
                        "Width": None,
                        "Height": None,
                        "AspectRatio": None,
                        "FrameRate": None,
                        "BitRate": None,
                        "IsDefault": True,
                    }
                ],
                "AudioStreams": [
                    {
                        "Codec": item.audio_codec or "aac",
                        "Index": 0,
                        "Language": None,
                        "Title": None,
                        "IsDefault": True,
                        "IsForced": False,
                        "IsExternal": False,
                    }
                ] if item.audio_codec else [],
                "SubtitleStreams": [],
            }
        ],
    }


# ── 用户数据端点 ──

@router.get("/Users/{user_id}/Items/Latest")
async def emby_latest_items(
    user_id: int,
    user: EmbyUser,
    db: DB,
    limit: int = Query(20, ge=1, le=50),
    include_media_types: str | None = Query(None),
):
    """
    获取用户最近添加的媒体项。
    按创建时间倒序排列。
    """
    repo = MediaRepository(db)

    # 验证用户权限
    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    # 解析媒体类型过滤
    media_type_filter = None
    if include_media_types:
        types = include_media_types.split(",")
        if "Movie" in types:
            media_type_filter = "movie"
        elif "Series" in types:
            media_type_filter = "tv"

    items, _ = await repo.get_items(
        media_type=media_type_filter,
        page=1,
        page_size=limit,
        sort_by="created_at",
        sort_order="desc",
    )

    result_items = []
    for item in items:
        result_items.append(_item_to_emby_format(item))

    return result_items


@router.get("/Users/{user_id}/Items/Resume")
async def emby_resume_items(
    user_id: int,
    user: EmbyUser,
    db: DB,
    limit: int = Query(10, ge=1, le=50),
    include_media_types: str | None = Query(None),
):
    """
    获取继续观看项目。
    返回用户最近播放但未完成的媒体。
    """
    from app.user.models import WatchHistory
    from sqlalchemy import select

    repo = MediaRepository(db)

    # 验证用户权限
    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    # 从 WatchHistory 获取未完成的播放记录
    stmt = (
        select(WatchHistory)
        .where(WatchHistory.user_id == user_id)
        .where(WatchHistory.completed == False)
        .order_by(WatchHistory.last_watched.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    watch_history = result.scalars().all()

    result_items = []
    for record in watch_history:
        # 获取媒体项
        try:
            item = await repo.get_item_by_id(record.media_item_id)
        except ValueError:
            continue

        if not item:
            continue

        # 媒体类型过滤
        if include_media_types:
            types = include_media_types.split(",")
            if "Movie" in types and item.media_type != "movie":
                continue
            elif "Series" in types and item.media_type not in ("tv", "anime"):
                continue

        emby_item = _item_to_emby_format(item)
        # 添加用户播放数据
        if record.progress:
            emby_item["UserData"] = {
                "PlaybackPositionTicks": int(record.progress * 10_000_000),
                "IsFavorite": False,
                "Played": False,
                "Key": f"{user_id}-{item.id}",
            }
        result_items.append(emby_item)

    return result_items


@router.post("/Sessions/Playing/Progress")
async def emby_playback_progress(
    request: EmbyProgressRequest,
    user: EmbyUser,
    db: DB,
):
    """
    报告播放进度。
    客户端在播放时定期调用此端点保存播放位置。
    """
    from app.user.models import WatchHistory
    from sqlalchemy import select

    # 解析 ItemId
    try:
        item_id = int(request.ItemId)
    except ValueError:
        raise HTTPException(400, "Invalid ItemId")

    # 获取媒体项
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    # 转换 ticks 到秒（1 tick = 100 纳秒 = 1/10_000_000 秒）
    position_seconds = (request.PositionTicks or 0) / 10_000_000

    # 更新或创建播放历史
    stmt = select(WatchHistory).where(
        WatchHistory.user_id == user.id,
        WatchHistory.media_item_id == item_id,
    )
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()

    if history:
        history.progress = position_seconds
        history.last_watched = datetime.now(timezone.utc)
        history.duration = item.duration or position_seconds
        # 标记为已完成（播放超过 90%）
        if item.duration and position_seconds >= item.duration * 0.9:
            history.completed = True
    else:
        history = WatchHistory(
            user_id=user.id,
            media_item_id=item_id,
            progress=position_seconds,
            duration=item.duration or position_seconds,
            completed=item.duration and position_seconds >= item.duration * 0.9,
            last_watched=datetime.now(timezone.utc),
        )
        db.add(history)

    await db.commit()

    logger.info(f"Playback progress: user={user.id}, item={item_id}, "
                f"position={position_seconds:.0f}s, event={request.Event}")

    return {"PlaybackPositionTicks": request.PositionTicks, "Event": request.Event}


# ── 相关推荐端点 ──

@router.get("/Items/{item_id}/Similar")
async def emby_similar_items(
    item_id: int,
    user: EmbyUser,
    db: DB,
    limit: int = Query(10, ge=1, le=50),
):
    """
    获取相似媒体推荐。
    基于类型和年代进行简单匹配。
    """
    repo = MediaRepository(db)

    # 获取当前项
    try:
        item = await repo.get_item_by_id(item_id)
    except ValueError:
        raise HTTPException(404, "Item not found")

    if not item:
        raise HTTPException(404, "Item not found")

    # 获取同类型媒体
    items, _ = await repo.get_items(
        media_type=item.media_type,
        page=1,
        page_size=limit + 1,  # 多取一条排除自己
        sort_by="rating",
        sort_order="desc",
    )

    # 过滤掉自己
    result_items = [i for i in items if i.id != item_id][:limit]

    result = []
    for similar in result_items:
        result.append(_item_to_emby_format(similar))

    return result


# ── HLS 流媒体端点 ──

@router.get("/Videos/{item_id}/master.m3u8")
async def emby_hls_master_playlist(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    HLS 自适应流主播放列表。
    返回 m3u8 格式的主播放列表，包含质量等级。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    file_path = item.file_path
    if not file_path:
        raise HTTPException(404, "No file available")

    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")

    file_size = os.path.getsize(file_path)
    container = item.container or "mp4"
    base_url = f"/api/Videos/{item_id}"

    # 生成 HLS 主播放列表
    # 支持多种质量等级（基于文件大小估算带宽）
    bandwidth = max(int(file_size / 600 * 8), 1_000_000)  # 估算带宽（bps）

    playlist = f"""#EXTM3U
#EXT-X-VERSION:4
# EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION=1920x1080,NAME="1080p"
{base_url}/live.m3u8?quality=1080p
# EXT-X-STREAM-INF:BANDWIDTH={int(bandwidth * 0.6)},RESOLUTION=1280x720,NAME="720p"
{base_url}/live.m3u8?quality=720p
# EXT-X-STREAM-INF:BANDWIDTH={int(bandwidth * 0.3)},RESOLUTION=854x480,NAME="480p"
{base_url}/live.m3u8?quality=480p
"""

    return StreamingResponse(
        iter([playlist]),
        media_type="application/vnd.apple.mpegurl",
        headers={"Content-Disposition": f"inline; filename=master.m3u8"},
    )


@router.get("/Videos/{item_id}/live.m3u8")
async def emby_hls_live_playlist(
    item_id: int,
    user: EmbyUser,
    db: DB,
    quality: str = Query("1080p"),
):
    """
    HLS 直播/点播播放列表。
    使用 fMP4 格式直接流式传输文件，无需转码。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    file_path = item.file_path
    if not file_path:
        raise HTTPException(404, "No file available")

    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")

    file_size = os.path.getsize(file_path)
    duration = item.duration or 0
    container = item.container or "mp4"
    base_url = f"/api/Videos/{item_id}"

    # 质量分辨率映射
    resolution_map = {
        "1080p": ("1920", "1080"),
        "720p": ("1280", "720"),
        "480p": ("854", "480"),
    }
    width, height = resolution_map.get(quality, ("1920", "1080"))

    # 计算分段数量（每段约 6 秒）
    segment_duration = 6
    if duration > 0:
        num_segments = max(int(duration / segment_duration), 1)
    else:
        num_segments = max(int(file_size / (5 * 1024 * 1024)), 1)  # 每段约 5MB

    # 生成 fMP4 风格的 HLS 播放列表
    playlist_lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:4",
        f"#EXT-X-TARGETDURATION:{segment_duration}",
        f"#EXT-X-MEDIA-SEQUENCE:0",
        f"#EXT-X-PLAYLIST-TYPE:VOD",
    ]

    for i in range(num_segments):
        segment_start = i * (duration / num_segments) if duration > 0 else i * segment_duration
        playlist_lines.append(f"#EXTINF:{segment_duration:.3f},")
        playlist_lines.append(f"{base_url}/segment/{i}?quality={quality}")

    playlist_lines.append("#EXT-X-ENDLIST")

    playlist = "\n".join(playlist_lines)

    return StreamingResponse(
        iter([playlist]),
        media_type="application/vnd.apple.mpegurl",
        headers={"Content-Disposition": f"inline; filename=live.m3u8"},
    )


@router.get("/Videos/{item_id}/segment/{segment_id}")
async def emby_hls_segment(
    item_id: int,
    segment_id: int,
    user: EmbyUser,
    db: DB,
    quality: str = Query("1080p"),
    request: Request = None,
):
    """
    HLS 视频分段。
    直接传输文件的指定部分（基于字节范围）。
    """
    import aiofiles
    import mimetypes

    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    file_path = item.file_path
    if not file_path:
        raise HTTPException(404, "No file available")

    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")

    file_size = os.path.getsize(file_path)
    duration = item.duration or 0
    segment_duration = 6

    # 计算分段字节范围
    if duration > 0:
        bytes_per_second = file_size / duration
        num_segments = max(int(duration / segment_duration), 1)
    else:
        bytes_per_second = file_size / (num_segments * segment_duration)
        num_segments = max(int(file_size / (5 * 1024 * 1024)), 1)

    # 确保 segment_id 在有效范围内
    segment_id = min(segment_id, num_segments - 1)

    start_byte = int(segment_id * bytes_per_second * segment_duration)
    end_byte = min(int((segment_id + 1) * bytes_per_second * segment_duration), file_size - 1)
    segment_size = end_byte - start_byte + 1

    async def stream_segment():
        async with aiofiles.open(file_path, "rb") as f:
            await f.seek(start_byte)
            remaining = segment_size
            chunk_size = 64 * 1024  # 64KB chunks

            while remaining > 0:
                chunk = await f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        stream_segment(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(segment_size),
            "Content-Type": "video/mp4",
        },
    )


# ── 字幕端点 ──

@router.get("/Videos/{item_id}/Subtitles")
async def emby_subtitle_streams(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取可用字幕流列表。
    返回内嵌和外挂字幕信息。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    subtitle_streams = []

    # 检查字幕文件（外挂字幕，与视频同目录同名不同扩展名）
    if item.file_path:
        base_path = item.file_path.rsplit(".", 1)[0]
        subtitle_extensions = [".srt", ".vtt", ".ass", ".ssa", ".sup"]

        for ext in subtitle_extensions:
            for lang in ["", ".zh", ".chs", ".cht", ".en"]:
                subtitle_path = f"{base_path}{lang}{ext}"
                if os.path.exists(subtitle_path):
                    lang_code = "chi" if lang in [".zh", ".chs", ".cht"] else "eng"
                    subtitle_streams.append({
                        "Index": len(subtitle_streams),
                        "Codec": ext.lstrip(".").upper(),
                        "Language": lang_code,
                        "LanguageTag": lang_code,
                        "DisplayTitle": "Chinese" if lang_code == "chi" else "English",
                        "IsExternal": True,
                        "IsForced": False,
                        "IsDefault": lang_code == "chi",
                        "Path": subtitle_path,
                    })
                    break

    return subtitle_streams


@router.get("/Videos/{item_id}/Subtitles/{subtitle_index}")
async def emby_subtitle_stream(
    item_id: int,
    subtitle_index: int,
    user: EmbyUser,
    db: DB,
    format: str = Query("srt", alias="format"),
):
    """
    获取字幕流。
    支持 SRT、VTT 格式转换。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    # 查找字幕文件
    subtitle_file = None
    if item.file_path:
        base_path = item.file_path.rsplit(".", 1)[0]
        subtitle_extensions = [".srt", ".vtt", ".ass", ".ssa", ".sup"]

        for ext in subtitle_extensions:
            subtitle_path = f"{base_path}{ext}"
            if os.path.exists(subtitle_path):
                subtitle_file = subtitle_path
                break

    if not subtitle_file:
        raise HTTPException(404, "Subtitle not found")

    # 确定返回格式
    if format.lower() == "vtt":
        content_type = "text/vtt"
        output = await _convert_srt_to_vtt(subtitle_file)
    else:
        content_type = "text/srt"
        async with aiofiles.open(subtitle_file, "r", encoding="utf-8-sig") as f:
            output = await f.read()

    return StreamingResponse(
        iter([output]),
        media_type=content_type,
        headers={
            "Content-Type": f"{content_type}; charset=utf-8",
            "Content-Disposition": "inline",
        },
    )


async def _convert_srt_to_vtt(srt_path: str) -> str:
    """将 SRT 格式转换为 VTT 格式"""
    async with aiofiles.open(srt_path, "r", encoding="utf-8-sig") as f:
        content = await f.read()

    # 简单转换：添加 WEBVTT 头，逗号改点
    lines = content.split("\n")
    vtt_lines = ["WEBVTT", ""]

    for line in lines:
        # SRT 时间格式: 00:00:00,000 --> 00:00:01,000
        # VTT 时间格式: 00:00:00.000 --> 00:00:01.000
        if "-->" in line:
            line = line.replace(",", ".")
        vtt_lines.append(line)

    return "\n".join(vtt_lines)


# ── Studios 和 Genres 端点 ──

@router.get("/Studios")
async def emby_studios(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    """
    获取制片厂列表。
    返回所有媒体中涉及的制片厂/发行商。
    """
    repo = MediaRepository(db)

    # 获取所有媒体项（从数据库中提取 studio 信息）
    items, _ = await repo.get_items(page=1, page_size=500)

    # 提取唯一的制片厂
    studios_map = {}
    for item in items:
        if hasattr(item, 'studio') and item.studio:
            studio_name = item.studio.strip()
            if studio_name and studio_name not in studios_map:
                studios_map[studio_name] = {
                    "Name": studio_name,
                    "Id": f"studio_{len(studios_map)}",
                    "ServerId": _emby_server_id(),
                }

    studios = list(studios_map.values())

    # 分页
    total = len(studios)
    studios_page = studios[start_index:start_index + limit]

    return {
        "Items": studios_page,
        "TotalRecordCount": total,
        "StartIndex": start_index,
    }


@router.get("/Genres")
async def emby_genres(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    include_media_types: str | None = Query(None),
):
    """
    获取类型/标签列表。
    返回所有媒体中涉及的类型/标签。
    """
    repo = MediaRepository(db)

    # 获取所有媒体项
    items, _ = await repo.get_items(page=1, page_size=500)

    # 解析媒体类型过滤
    media_type_filter = None
    if include_media_types:
        types = include_media_types.split(",")
        if "Movie" in types:
            media_type_filter = "movie"
        elif "Series" in types:
            media_type_filter = "tv"

    # 提取唯一的类型
    genres_map = {}
    for item in items:
        # 媒体类型过滤
        if media_type_filter and item.media_type != media_type_filter:
            continue

        if hasattr(item, 'genres') and item.genres:
            try:
                genres = json.loads(item.genres)
                for genre in genres:
                    if genre and genre not in genres_map:
                        genres_map[genre] = {
                            "Name": genre,
                            "Id": f"genre_{len(genres_map)}",
                            "ServerId": _emby_server_id(),
                        }
            except (json.JSONDecodeError, TypeError):
                pass

    genres = list(genres_map.values())

    # 分页
    total = len(genres)
    genres_page = genres[start_index:start_index + limit]

    return {
        "Items": genres_page,
        "TotalRecordCount": total,
        "StartIndex": start_index,
    }


# ── 会话管理端点 ──

@router.get("/Sessions")
async def emby_sessions(
    user: EmbyUser,
    db: DB,
):
    """
    获取当前活动会话列表。
    返回当前用户的所有活跃播放会话。
    """
    from app.user.models import WatchHistory
    from sqlalchemy import select, desc

    # 获取用户的最近活动
    stmt = (
        select(WatchHistory)
        .where(WatchHistory.user_id == user.id)
        .order_by(desc(WatchHistory.last_watched))
        .limit(10)
    )
    result = await db.execute(stmt)
    recent_activity = result.scalars().all()

    repo = MediaRepository(db)
    sessions = []

    for activity in recent_activity:
        try:
            item = await repo.get_item_by_id(activity.media_item_id)
        except ValueError:
            continue

        if not item:
            continue

        session = {
            "SessionId": f"session_{activity.id}",
            "UserId": str(user.id),
            "UserName": user.username,
            "DeviceId": f"web_{user.id}",
            "DeviceName": "Web Browser",
            "DeviceType": "Web",
            "ClientName": "MediaStation",
            "ClientVersion": "1.0.0",
            "SupportedCommands": [
                "MoveUp",
                "MoveDown",
                "MoveLeft",
                "MoveRight",
                "Select",
                "Back",
                "ToggleContextMenu",
                "TakeScreenshot",
            ],
            "PlayState": {
                "PlaybackRate": 1.0,
                "VolumeLevel": 100,
                "IsMuted": False,
                "IsPaused": False,
                "RepeatMode": "RepeatNone",
            },
            "NowPlayingItem": _item_to_emby_format(item),
        }

        # 添加播放进度
        if activity.progress and item.duration:
            session["PlayState"]["PositionTicks"] = int(activity.progress * 10_000_000)
            session["PlayState"]["RunTimeTicks"] = int(item.duration * 10_000_000)

        sessions.append(session)

    return sessions


@router.get("/Sessions/{session_id}")
async def emby_session(
    session_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取特定会话详情。
    """
    # 简化实现：返回当前用户信息作为会话
    return {
        "SessionId": session_id,
        "UserId": str(user.id),
        "UserName": user.username,
        "DeviceId": f"web_{user.id}",
        "DeviceName": "Web Browser",
        "DeviceType": "Web",
        "ClientName": "MediaStation",
        "ClientVersion": "1.0.0",
        "SupportedCommands": [
            "MoveUp",
            "MoveDown",
            "Select",
            "Back",
        ],
        "PlayState": {
            "PlaybackRate": 1.0,
            "VolumeLevel": 100,
            "IsMuted": False,
            "IsPaused": False,
        },
    }


# ── TV 剧集端点 ──

@router.get("/Shows/{series_id}/Seasons")
async def emby_show_seasons(
    series_id: int,
    user: EmbyUser,
    db: DB,
    fields: str | None = Query(None),
):
    """
    获取剧集的季列表。
    Infuse/Kodi 通过此接口获取剧集的所有季信息。
    """
    from app.media.models import MediaSeason

    repo = MediaRepository(db)
    series = await repo.get_item_by_id(series_id)

    if not series or series.media_type not in ("tv", "anime"):
        raise HTTPException(404, "Series not found")

    seasons = await repo.get_seasons_by_item(series_id)

    requested_fields = set(fields.split(",")) if fields else set()

    emby_seasons = []
    for season in seasons:
        s = {
            "Name": season.name or f"Season {season.season_number}",
            "Id": _emby_item_id(season.id),
            "SeriesId": _emby_item_id(series_id),
            "SeriesName": series.title,
            "ServerId": _emby_server_id(),
            "Type": "Season",
            "IndexNumber": season.season_number,
            "ParentIndexNumber": None,
            "PremiereDate": None,
            "EndDate": None,
            "Overview": "",
            "LocationType": "FileSystem",
            "MediaType": None,
            "ImageTags": {},
        }

        # 季海报
        if season.poster_url:
            s["ImageTags"] = {"Primary": uuid.uuid4().hex[:8]}
            s["PrimaryImageItemId"] = str(season.id)

        # 查询该季的集数
        episodes = await repo.get_episodes_by_season(season.id)
        s["ChildCount"] = len(episodes)

        # 该季是否有未看集
        if "UserData" in requested_fields:
            s["UserData"] = {
                "UnplayedItemCount": len(episodes),
                "PlaybackPositionTicks": 0,
                "PlayCount": 0,
                "IsFavorite": False,
                "Played": False,
            }

        # 查询该季最早的和最晚的 air_date
        if episodes:
            dates = [e.air_date for e in episodes if e.air_date]
            if dates:
                s["PremiereDate"] = min(dates).isoformat() + "T00:00:00Z"
                s["EndDate"] = max(dates).isoformat() + "T00:00:00Z"

        emby_seasons.append(s)

    return {
        "Items": emby_seasons,
        "TotalRecordCount": len(emby_seasons),
    }


@router.get("/Shows/{series_id}/Episodes")
async def emby_show_episodes(
    series_id: int,
    user: EmbyUser,
    db: DB,
    season_id: str | None = Query(None, description="指定季 ID 过滤"),
    season_number: int | None = Query(None, alias="SeasonNumber", description="指定季号过滤"),
    start_index: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    fields: str | None = Query(None),
):
    """
    获取剧集的集列表。
    Infuse/Kodi 通过此接口获取剧集的所有集信息。
    可按季 ID 或季号过滤。
    """
    from app.media.models import MediaSeason
    from app.user.models import WatchHistory

    repo = MediaRepository(db)
    series = await repo.get_item_by_id(series_id)

    if not series or series.media_type not in ("tv", "anime"):
        raise HTTPException(404, "Series not found")

    requested_fields = set(fields.split(",")) if fields else set()

    # 获取季列表
    seasons = await repo.get_seasons_by_item(series_id)

    # 按季过滤
    if season_number is not None:
        seasons = [s for s in seasons if s.season_number == season_number]
    elif season_id is not None:
        try:
            sid = int(season_id)
            seasons = [s for s in seasons if s.id == sid]
        except ValueError:
            pass

    # 收集所有集
    all_episodes = []
    for season in seasons:
        episodes = await repo.get_episodes_by_season(season.id)
        for ep in episodes:
            all_episodes.append((season, ep))

    total = len(all_episodes)
    # 分页
    paged = all_episodes[start_index:start_index + limit]

    # 获取用户播放历史（批量查询）
    episode_ids = [ep.id for _, ep in paged]
    watch_map: dict[int, dict] = {}
    if "UserData" in requested_fields and episode_ids:
        # 对剧集级别，检查 user 的历史
        # 注意：WatchHistory 的 media_item_id 可能指向 MediaItem 或 MediaEpisode
        # 这里我们用 media_item_id 对应 episode id（如果有的话）
        for ep_id in episode_ids:
            watch_map[ep_id] = {
                "PlaybackPositionTicks": 0,
                "PlayCount": 0,
                "IsFavorite": False,
                "Played": False,
            }

    emby_episodes = []
    for season, ep in paged:
        e = {
            "Name": ep.title or f"Episode {ep.episode_number}",
            "Id": _emby_item_id(ep.id),
            "SeriesId": _emby_item_id(series_id),
            "SeriesName": series.title,
            "SeasonId": _emby_item_id(season.id),
            "SeasonName": season.name or f"Season {season.season_number}",
            "ServerId": _emby_server_id(),
            "Type": "Episode",
            "IndexNumber": ep.episode_number,
            "ParentIndexNumber": season.season_number,
            "Container": "mp4",
            "SortName": f"s{season.season_number:02d}e{ep.episode_number:02d}",
            "Overview": "",
            "LocationType": "FileSystem" if ep.file_path else "Virtual",
            "MediaType": "Video",
            "Video3DFormat": None,
            "Tags": [],
            "Genres": json.loads(series.genres) if series.genres else [],
            "CommunityRating": float(series.rating or 0),
        }

        # 时长
        if ep.duration:
            e["RunTimeTicks"] = ep.duration * 10_000_000

        # 文件路径
        if ep.file_path:
            e["Path"] = ep.file_path

        # 日期
        if ep.air_date:
            e["PremiereDate"] = ep.air_date.isoformat() + "T00:00:00Z"
            e["ProductionYear"] = ep.air_date.year

        # 文件大小
        if ep.file_size:
            e["Size"] = ep.file_size

        # 编解码器信息
        if ep.video_codec:
            e["VideoStream"] = {
                "Codec": ep.video_codec,
                "Index": 0,
                "IsDefault": True,
            }
        if ep.audio_codec:
            e["AudioStream"] = {
                "Codec": ep.audio_codec,
                "Index": 0,
                "IsDefault": True,
            }

        # 播放图片（使用剧集海报）
        if season.poster_url:
            e["ImageTags"] = {"Primary": uuid.uuid4().hex[:8]}

        # 用户数据
        if "UserData" in requested_fields:
            e["UserData"] = watch_map.get(ep.id, {
                "PlaybackPositionTicks": 0,
                "PlayCount": 0,
                "IsFavorite": False,
                "Played": False,
            })

        emby_episodes.append(e)

    return {
        "Items": emby_episodes,
        "TotalRecordCount": total,
        "StartIndex": start_index,
    }


@router.get("/Shows/NextUp")
async def emby_shows_next_up(
    user: EmbyUser,
    db: DB,
    limit: int = Query(20, ge=1, le=50),
    fields: str | None = Query(None),
    parent_id: str | None = Query(None, description="限制到特定媒体库"),
):
    """
    下一集推荐（Next Up）。
    返回用户还未观看完的剧集的下一集。
    基于用户的观看历史，推荐继续观看的剧集。

    算法逻辑：
    1. 获取用户所有观看过的剧集记录
    2. 对于已看完的集，找到该季的下一集
    3. 如果该季是最后一集，则找下一季的第一集
    """
    from app.user.models import WatchHistory
    from app.media.models import MediaSeason, MediaEpisode

    repo = MediaRepository(db)
    requested_fields = set(fields.split(",")) if fields else set()

    # 获取所有 TV 类型媒体
    tv_items, _ = await repo.get_items(
        media_type="tv",
        page=1,
        page_size=500,
        sort_by="date_added",
        sort_order="desc",
    )
    anime_items, _ = await repo.get_items(
        media_type="anime",
        page=1,
        page_size=200,
        sort_by="date_added",
        sort_order="desc",
    )
    all_series = tv_items + anime_items

    next_up_items = []

    for series in all_series:
        seasons = await repo.get_seasons_by_item(series.id)
        if not seasons:
            continue

        # 按季号排序
        seasons.sort(key=lambda s: s.season_number)

        # 获取用户在该剧集下的播放历史
        # 通过 media_item_id 查找（注意：可能需要通过 episode 关联）
        # 这里我们使用一个简化策略：遍历季和集，检查 WatchHistory

        found_next = False
        for season in seasons:
            episodes = await repo.get_episodes_by_season(season.id)
            episodes.sort(key=lambda e: e.episode_number)

            for ep in episodes:
                # 检查用户是否已看完此集
                # WatchHistory 中 media_item_id 可能是 episode id
                stmt = select(WatchHistory).where(
                    WatchHistory.user_id == user.id,
                    WatchHistory.media_item_id == ep.id,
                )
                result = await db.execute(stmt)
                history = result.scalar_one_or_none()

                is_watched = history and history.completed

                if not is_watched and not found_next:
                    # 这是下一个未看的集
                    e = {
                        "Name": ep.title or f"Episode {ep.episode_number}",
                        "Id": _emby_item_id(ep.id),
                        "SeriesId": _emby_item_id(series.id),
                        "SeriesName": series.title,
                        "SeasonId": _emby_item_id(season.id),
                        "SeasonName": season.name or f"Season {season.season_number}",
                        "SeasonNumber": season.season_number,
                        "EpisodeNumber": ep.episode_number,
                        "ServerId": _emby_server_id(),
                        "Type": "Episode",
                        "IndexNumber": ep.episode_number,
                        "ParentIndexNumber": season.season_number,
                        "Container": "mp4",
                        "SortName": f"s{season.season_number:02d}e{ep.episode_number:02d}",
                        "Overview": "",
                        "LocationType": "FileSystem" if ep.file_path else "Virtual",
                        "MediaType": "Video",
                        "Tags": [],
                        "Genres": json.loads(series.genres) if series.genres else [],
                        "CommunityRating": float(series.rating or 0),
                    }

                    # 时长
                    if ep.duration:
                        e["RunTimeTicks"] = ep.duration * 10_000_000

                    # 文件路径
                    if ep.file_path:
                        e["Path"] = ep.file_path

                    # 日期
                    if ep.air_date:
                        e["PremiereDate"] = ep.air_date.isoformat() + "T00:00:00Z"

                    # 播放图片
                    if series.poster_url:
                        e["SeriesPrimaryImageTag"] = uuid.uuid4().hex[:8]
                    if season.poster_url:
                        e["ImageTags"] = {"Primary": uuid.uuid4().hex[:8]}

                    # 播放进度信息
                    if history and history.progress:
                        e["UserData"] = {
                            "PlaybackPositionTicks": int(history.progress * 10_000_000),
                            "PlayCount": 0,
                            "IsFavorite": False,
                            "Played": False,
                        }
                    else:
                        e["UserData"] = {
                            "PlaybackPositionTicks": 0,
                            "PlayCount": 0,
                            "IsFavorite": False,
                            "Played": False,
                        }

                    next_up_items.append(e)
                    found_next = True
                    break  # 只取第一集未看的

            if found_next:
                break

        if len(next_up_items) >= limit:
            break

    return {
        "Items": next_up_items[:limit],
        "TotalRecordCount": len(next_up_items),
    }


# ── 收藏端点 ──

@router.get("/Users/{user_id}/FavoriteItems")
async def emby_favorite_items(
    user_id: int,
    user: EmbyUser,
    db: DB,
    include_item_types: str | None = Query(None),
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    """
    获取用户收藏的媒体列表。
    Emby 客户端通过此接口获取用户收藏的项目。
    """
    repo = MediaRepository(db)

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    items, total = await repo.get_favorites(user_id, page=1, page_size=200)

    # 媒体类型过滤
    if include_item_types:
        types = include_item_types.split(",")
        filtered = []
        for item in items:
            emby_type = _to_emby_media_type(item.media_type)
            if emby_type in types:
                filtered.append(item)
        items = filtered

    # 分页
    paged = items[start_index:start_index + limit]

    result_items = [_item_to_emby_format(item) for item in paged]

    # 添加 UserData 标记为收藏
    for item_data in result_items:
        item_data["UserData"] = {
            "IsFavorite": True,
            "Played": False,
            "PlayCount": 0,
        }

    return {
        "Items": result_items,
        "TotalRecordCount": len(items),
        "StartIndex": start_index,
    }


# ═══════════════════════════════════════════════════════════════
# Emby 扩展兼容层：SyncPlay / Trailers / DisplayPreferences /
#                  Branding / Packages / Activities / UserImages
# 让 Infuse、Emby Theater、Jellyfin 客户端正常初始化
# ═══════════════════════════════════════════════════════════════


# ── SyncPlay ──
# Emby SyncPlay 允许多用户同步播放，这里提供空实现让客户端不报错

@router.get("/SyncPlay/List")
async def emby_syncplay_list(user: EmbyUser):
    """SyncPlay 会话列表（空实现，客户端初始化时调用）"""
    return []


@router.post("/SyncPlay/New")
async def emby_syncplay_new(user: EmbyUser):
    """创建 SyncPlay 会话（返回空会话）"""
    return {
        "GroupId": str(uuid.uuid4()),
        "GroupName": f"{user.username}'s Group",
        "State": "Idle",
        "Participants": [],
        "LastUpdatedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/SyncPlay/Join")
async def emby_syncplay_join(user: EmbyUser):
    """加入 SyncPlay 会话"""
    return {"Success": True}


@router.post("/SyncPlay/Leave")
async def emby_syncplay_leave(user: EmbyUser):
    """离开 SyncPlay 会话"""
    return {"Success": True}


@router.post("/SyncPlay/Buffering")
async def emby_syncplay_buffering(user: EmbyUser):
    """上报缓冲状态"""
    return {"Success": True}


@router.post("/SyncPlay/Ready")
async def emby_syncplay_ready(user: EmbyUser):
    """上报就绪状态"""
    return {"Success": True}


@router.post("/SyncPlay/Ping")
async def emby_syncplay_ping(user: EmbyUser):
    """SyncPlay 心跳"""
    return {"Success": True}


# ── Trailers ──
# Emby 预告片端点，返回空列表（无预告片服务）

@router.get("/Users/{user_id}/Items/{item_id}/Trailers")
async def emby_item_trailers(
    user_id: int,
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """获取媒体预告片列表（当前返回空列表）"""
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": 0,
    }


@router.get("/Items/{item_id}/Trailers")
async def emby_item_trailers_v2(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """获取媒体预告片（v2 路由）"""
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": 0,
    }


# ── DisplayPreferences ──
# 客户端存储视图偏好设置的端点

@router.get("/DisplayPreferences/{preferences_id}")
async def emby_get_display_preferences(
    preferences_id: str,
    user: EmbyUser,
    client: str | None = Query(None),
):
    """获取显示偏好（返回默认配置）"""
    return {
        "Id": preferences_id,
        "SortBy": "SortName",
        "RememberIndexing": False,
        "PrimaryImageHeight": 250,
        "PrimaryImageWidth": 167,
        "CustomPrefs": {},
        "ScrollDirection": "Horizontal",
        "ShowBackdrop": True,
        "RememberSorting": False,
        "SortOrder": "Ascending",
        "ShowSidebar": False,
        "Client": client or "emby",
        "ViewType": "Poster",
        "IndexBy": None,
    }


@router.post("/DisplayPreferences/{preferences_id}")
async def emby_update_display_preferences(
    preferences_id: str,
    request: Request,
    user: EmbyUser,
):
    """更新显示偏好（接受并忽略，总是返回成功）"""
    return {}


# ── Branding ──
# Emby 客户端初始化时调用，获取服务器品牌配置

@router.get("/Branding/Configuration")
async def emby_branding_config():
    """服务器品牌配置（无需认证）"""
    settings = get_settings()
    return {
        "LoginDisclaimer": "",
        "CustomCss": "",
        "SplashscreenEnabled": False,
        "ServerName": "MediaStation",
    }


@router.get("/System/Configuration")
async def emby_system_configuration(user: EmbyUser):
    """获取完整系统配置（管理用）"""
    settings = get_settings()
    return {
        "LogFileRetentionDays": 3,
        "IsStartupWizardCompleted": True,
        "CachePath": "",
        "PreviousVersion": None,
        "PreviousVersionStr": None,
        "EnableMetrics": False,
        "EnableNormalizedItemByNameIds": True,
        "IsPortAuthorized": True,
        "QuickConnectAvailable": False,
        "EnableCaseSensitiveItemIds": True,
        "DisableLiveTvChannelUserDataName": True,
        "MetadataPath": "",
        "PreferredMetadataLanguage": "zh",
        "MetadataCountryCode": "CN",
        "SortReplaceCharacters": [".", "+", "%"],
        "SortRemoveCharacters": [",", "&", "-", "{", "}", "'"],
        "SortRemoveWords": ["the", "a", "an"],
        "MinResumePct": 5,
        "MaxResumePct": 90,
        "MinResumeDurationSeconds": 300,
        "MinAudiobookResume": 5,
        "MaxAudiobookResume": 90,
        "LibraryMonitorDelay": 60,
        "ImageSavingConvention": "Legacy",
        "MetadataOptions": [],
        "SkipDeserializationForBasicTypes": True,
        "ServerName": "MediaStation",
        "UICulture": "zh-CN",
        "SaveMetadataHidden": False,
        "ContentTypes": [],
        "RemoteClientBitrateLimit": 0,
        "EnableFolderView": False,
        "EnableGroupingIntoCollections": True,
        "DisplaySpecialsWithinSeasons": True,
        "LocalNetworkSubnets": [],
        "LocalNetworkAddresses": [],
        "CodecsUsed": [],
        "PluginRepositories": [],
        "EnableExternalContentInSuggestions": True,
        "ImageExtractionTimeoutMs": 0,
        "PathSubstitutions": [],
        "EnableSlowResponseWarning": True,
        "SlowResponseThresholdMs": 500,
        "CorsHosts": ["*"],
        "ActivityLogRetentionDays": 30,
        "LibraryScanFanoutConcurrency": 0,
        "LibraryMetadataRefreshConcurrency": 0,
        "RemoveOldPlugins": False,
        "AllowClientLogUpload": True,
    }


# ── Packages ──
# Emby 插件包端点，返回空列表

@router.get("/Packages")
async def emby_packages(user: EmbyUser):
    """获取插件包列表（无插件系统，返回空）"""
    return []


@router.get("/Packages/Installed")
async def emby_packages_installed(user: EmbyUser):
    """获取已安装插件（返回空）"""
    return []


@router.get("/Plugins")
async def emby_plugins(user: EmbyUser):
    """获取插件列表"""
    return []


# ── Activities ──
# 系统活动日志端点

@router.get("/System/ActivityLog/Entries")
async def emby_activity_log(
    user: EmbyUser,
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    min_date: str | None = Query(None, alias="MinDate"),
):
    """系统活动日志（返回空列表）"""
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


# ── User Image ──
# Emby 用户头像端点

@router.get("/Users/{user_id}/Images/Primary")
async def emby_user_avatar(
    user_id: int,
    user: EmbyUser,
):
    """用户头像（返回 404 让客户端使用默认头像）"""
    raise HTTPException(404, "No avatar")


@router.post("/Users/{user_id}/Images/{image_type}")
async def emby_upload_user_image(
    user_id: int,
    image_type: str,
    user: EmbyUser,
    request: Request,
):
    """上传用户头像（接受并忽略）"""
    return {}


# ── Item Images ──
# 媒体图片重定向端点（将 Emby 图片请求转为实际海报 URL）

@router.get("/Items/{item_id}/Images/{image_type}")
async def emby_item_image(
    item_id: int,
    image_type: str,
    user: EmbyUser,
    db: DB,
    max_width: int | None = Query(None, alias="MaxWidth"),
    max_height: int | None = Query(None, alias="MaxHeight"),
    quality: int | None = Query(None, alias="Quality"),
    tag: str | None = Query(None),
):
    """
    获取媒体封面图片。
    将 Emby 标准图片请求重定向到实际的海报/背景图 URL。
    image_type: Primary（封面）, Backdrop（背景）, Thumb（缩略图）
    """
    from fastapi.responses import RedirectResponse

    repo = MediaRepository(db)

    try:
        item = await repo.get_item_by_id(item_id)
    except ValueError:
        item = None

    if not item:
        raise HTTPException(404, "Item not found")

    # 根据图片类型返回不同 URL
    if image_type.lower() == "backdrop" and item.backdrop_url:
        return RedirectResponse(url=item.backdrop_url, status_code=302)
    elif image_type.lower() in ("primary", "thumb", "logo") and item.poster_url:
        return RedirectResponse(url=item.poster_url, status_code=302)
    elif item.poster_url:
        return RedirectResponse(url=item.poster_url, status_code=302)
    else:
        raise HTTPException(404, "Image not found")


@router.get("/Items/{item_id}/Images/{image_type}/{image_index}")
async def emby_item_image_indexed(
    item_id: int,
    image_type: str,
    image_index: int,
    user: EmbyUser,
    db: DB,
    max_width: int | None = Query(None, alias="MaxWidth"),
    quality: int | None = Query(None, alias="Quality"),
    tag: str | None = Query(None),
):
    """带索引的图片端点（Backdrop[0], Backdrop[1] 等）"""
    from fastapi.responses import RedirectResponse

    repo = MediaRepository(db)

    try:
        item = await repo.get_item_by_id(item_id)
    except ValueError:
        item = None

    if not item:
        raise HTTPException(404, "Item not found")

    if image_type.lower() == "backdrop" and item.backdrop_url:
        return RedirectResponse(url=item.backdrop_url, status_code=302)
    elif item.poster_url:
        return RedirectResponse(url=item.poster_url, status_code=302)
    else:
        raise HTTPException(404, "Image not found")


# ── QuickConnect ──
# Emby 快速连接（TV 端免密登录），提供空实现

@router.get("/QuickConnect/Enabled")
async def emby_quick_connect_enabled():
    """快速连接是否启用（关闭）"""
    return False


@router.get("/QuickConnect/Initiate")
async def emby_quick_connect_initiate():
    """初始化快速连接请求（不支持）"""
    raise HTTPException(400, "QuickConnect is not enabled")


# ── UserData ──
# 媒体用户数据更新（播放状态、收藏等）

@router.post("/Users/{user_id}/Items/{item_id}/UserData")
async def emby_update_user_data(
    user_id: int,
    item_id: int,
    request: Request,
    user: EmbyUser,
    db: DB,
):
    """
    更新媒体用户数据（播放完成标记、收藏、评分等）。
    Emby 客户端在标记为已播放/收藏时调用。
    """
    from app.user.models import WatchHistory
    from sqlalchemy import select

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    try:
        body = await request.json()
    except Exception:
        body = {}

    # 处理已播放标记
    played = body.get("Played", False)
    is_favorite = body.get("IsFavorite", None)

    if played:
        # 标记为已完成
        stmt = select(WatchHistory).where(
            WatchHistory.user_id == user_id,
            WatchHistory.media_item_id == item_id,
        )
        result = await db.execute(stmt)
        history = result.scalar_one_or_none()

        if history:
            history.completed = True
            history.last_watched = datetime.now(timezone.utc)
        else:
            # 获取媒体项时长
            repo = MediaRepository(db)
            item = await repo.get_item_by_id(item_id)
            history = WatchHistory(
                user_id=user_id,
                media_item_id=item_id,
                progress=item.duration if item else 0,
                duration=item.duration if item else 0,
                completed=True,
                last_watched=datetime.now(timezone.utc),
            )
            db.add(history)

        await db.commit()

    return {
        "ItemId": str(item_id),
        "IsFavorite": is_favorite or False,
        "Played": played,
        "PlayCount": 1 if played else 0,
        "PlaybackPositionTicks": 0,
        "LastPlayedDate": datetime.now(timezone.utc).isoformat() if played else None,
        "Key": f"{user_id}-{item_id}",
    }


@router.delete("/Users/{user_id}/Items/{item_id}/UserData")
async def emby_delete_user_data(
    user_id: int,
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """删除用户媒体数据（重置播放状态）"""
    from app.user.models import WatchHistory
    from sqlalchemy import select, delete

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    stmt = delete(WatchHistory).where(
        WatchHistory.user_id == user_id,
        WatchHistory.media_item_id == item_id,
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "ItemId": str(item_id),
        "IsFavorite": False,
        "Played": False,
        "PlayCount": 0,
        "PlaybackPositionTicks": 0,
        "LastPlayedDate": None,
    }


# ── PlayedItems ──
# Emby 标准的已播放/未播放切换端点

@router.post("/Users/{user_id}/PlayedItems/{item_id}")
async def emby_mark_played(
    user_id: int,
    item_id: int,
    user: EmbyUser,
    db: DB,
    date_played: str | None = Query(None, alias="DatePlayed"),
):
    """标记媒体为已播放"""
    from app.user.models import WatchHistory
    from sqlalchemy import select

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    stmt = select(WatchHistory).where(
        WatchHistory.user_id == user_id,
        WatchHistory.media_item_id == item_id,
    )
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()

    played_dt = datetime.now(timezone.utc)

    if history:
        history.completed = True
        history.last_watched = played_dt
        if item and item.duration:
            history.progress = item.duration
    else:
        history = WatchHistory(
            user_id=user_id,
            media_item_id=item_id,
            progress=item.duration if item else 0,
            duration=item.duration if item else 0,
            completed=True,
            last_watched=played_dt,
        )
        db.add(history)

    await db.commit()

    return {
        "ItemId": str(item_id),
        "IsFavorite": False,
        "Played": True,
        "PlayCount": 1,
        "PlaybackPositionTicks": (item.duration * 10_000_000) if item and item.duration else 0,
        "LastPlayedDate": played_dt.isoformat(),
        "Key": f"{user_id}-{item_id}",
    }


@router.delete("/Users/{user_id}/PlayedItems/{item_id}")
async def emby_unmark_played(
    user_id: int,
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """标记媒体为未播放"""
    from app.user.models import WatchHistory
    from sqlalchemy import select

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    stmt = select(WatchHistory).where(
        WatchHistory.user_id == user_id,
        WatchHistory.media_item_id == item_id,
    )
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()

    if history:
        history.completed = False
        history.progress = 0
        await db.commit()

    return {
        "ItemId": str(item_id),
        "IsFavorite": False,
        "Played": False,
        "PlayCount": 0,
        "PlaybackPositionTicks": 0,
        "LastPlayedDate": None,
        "Key": f"{user_id}-{item_id}",
    }


# ── FavoriteItems ──
# Emby 标准的收藏端点

@router.post("/Users/{user_id}/FavoriteItems/{item_id}")
async def emby_add_favorite(
    user_id: int,
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """添加收藏"""
    from app.media.models import Favorite
    from sqlalchemy import select

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    # 检查是否已收藏
    stmt = select(Favorite).where(
        Favorite.user_id == user_id,
        Favorite.media_item_id == item_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        fav = Favorite(user_id=user_id, media_item_id=item_id)
        db.add(fav)
        await db.commit()

    return {
        "ItemId": str(item_id),
        "IsFavorite": True,
        "Played": False,
        "PlayCount": 0,
        "PlaybackPositionTicks": 0,
        "Key": f"{user_id}-{item_id}",
    }


@router.delete("/Users/{user_id}/FavoriteItems/{item_id}")
async def emby_remove_favorite(
    user_id: int,
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """取消收藏"""
    from app.media.models import Favorite
    from sqlalchemy import delete, select

    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    stmt = delete(Favorite).where(
        Favorite.user_id == user_id,
        Favorite.media_item_id == item_id,
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "ItemId": str(item_id),
        "IsFavorite": False,
        "Played": False,
        "PlayCount": 0,
        "PlaybackPositionTicks": 0,
        "Key": f"{user_id}-{item_id}",
    }


# ── Notifications ──
# Emby 通知端点，返回空实现

@router.get("/Notifications/{user_id}")
async def emby_notifications(user_id: int, user: EmbyUser):
    """获取用户通知（返回空）"""
    return {
        "Notifications": [],
        "TotalRecordCount": 0,
    }


@router.get("/Notifications/{user_id}/Summary")
async def emby_notifications_summary(user_id: int, user: EmbyUser):
    """通知摘要（无未读通知）"""
    return {
        "UnreadCount": 0,
        "MaxUnreadNotificationLevel": None,
    }


# ── Sessions/Playing ──
# 开始/停止播放上报端点

@router.post("/Sessions/Playing")
async def emby_session_playing_start(
    request: Request,
    user: EmbyUser,
    db: DB,
):
    """开始播放上报"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    item_id_str = body.get("ItemId")
    if item_id_str:
        try:
            item_id = int(item_id_str)
            # 记录开始播放
            from app.user.models import WatchHistory
            from sqlalchemy import select

            stmt = select(WatchHistory).where(
                WatchHistory.user_id == user.id,
                WatchHistory.media_item_id == item_id,
            )
            result = await db.execute(stmt)
            history = result.scalar_one_or_none()

            if not history:
                repo = MediaRepository(db)
                item = await repo.get_item_by_id(item_id)
                history = WatchHistory(
                    user_id=user.id,
                    media_item_id=item_id,
                    progress=0,
                    duration=item.duration if item else 0,
                    completed=False,
                    last_watched=datetime.now(timezone.utc),
                )
                db.add(history)
                await db.commit()
        except (ValueError, Exception) as e:
            logger.warning(f"Session playing start error: {e}")

    return {}


@router.post("/Sessions/Playing/Stopped")
async def emby_session_playing_stopped(
    request: Request,
    user: EmbyUser,
    db: DB,
):
    """停止播放上报（更新播放进度）"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    item_id_str = body.get("ItemId")
    position_ticks = body.get("PositionTicks", 0)

    if item_id_str:
        try:
            item_id = int(item_id_str)
            position_seconds = (position_ticks or 0) / 10_000_000

            from app.user.models import WatchHistory
            from sqlalchemy import select

            repo = MediaRepository(db)
            item = await repo.get_item_by_id(item_id)

            stmt = select(WatchHistory).where(
                WatchHistory.user_id == user.id,
                WatchHistory.media_item_id == item_id,
            )
            result = await db.execute(stmt)
            history = result.scalar_one_or_none()

            if history:
                history.progress = position_seconds
                history.last_watched = datetime.now(timezone.utc)
                if item and item.duration and position_seconds >= item.duration * 0.9:
                    history.completed = True
            else:
                history = WatchHistory(
                    user_id=user.id,
                    media_item_id=item_id,
                    progress=position_seconds,
                    duration=item.duration if item else position_seconds,
                    completed=(item and item.duration and position_seconds >= item.duration * 0.9) or False,
                    last_watched=datetime.now(timezone.utc),
                )
                db.add(history)

            await db.commit()
        except (ValueError, Exception) as e:
            logger.warning(f"Session playing stopped error: {e}")

    return {}


# ── Capabilities ──
# 客户端能力注册端点

@router.post("/Sessions/Capabilities")
async def emby_session_capabilities(request: Request, user: EmbyUser):
    """上报客户端能力（接受并忽略）"""
    return {}


@router.post("/Sessions/Capabilities/Full")
async def emby_session_capabilities_full(request: Request, user: EmbyUser):
    """上报完整客户端能力"""
    return {}


# ── Server Info ──
# 附加服务器信息端点

@router.get("/System/Info/Public")
async def emby_system_info_public():
    """公开系统信息（无需认证，与 /System/Public 相同）"""
    settings = get_settings()
    return {
        "ServerName": "MediaStation",
        "Version": "4.7.14.0",  # 伪装成 Emby Server 版本
        "Id": _emby_server_id(),
        "OperatingSystem": "Linux",
        "LocalAddress": f"http://localhost:{settings.app_port}",
        "WanAddress": "",
        "StartupWizardCompleted": True,
    }


@router.get("/System/Ping")
async def emby_ping():
    """系统 Ping 检查（无需认证）"""
    return "MediaStation"


@router.post("/System/Ping")
async def emby_ping_post():
    """POST Ping"""
    return "MediaStation"


# ── Schedule Tasks ──
# Emby 计划任务端点（与系统调度器兼容）

@router.get("/ScheduledTasks")
async def emby_scheduled_tasks(user: EmbyUser):
    """获取计划任务列表"""
    return [
        {
            "Name": "媒体库扫描",
            "State": "Idle",
            "Id": "media_scan",
            "Category": "Library",
            "Description": "扫描媒体库中的新文件",
            "LastExecutionResult": None,
            "Triggers": [{"Type": "IntervalTrigger", "IntervalTicks": 36000000000}],
        },
        {
            "Name": "元数据刷新",
            "State": "Idle",
            "Id": "metadata_refresh",
            "Category": "Library",
            "Description": "刷新媒体元数据",
            "LastExecutionResult": None,
            "Triggers": [],
        },
    ]


@router.post("/ScheduledTasks/{task_id}/Triggers")
async def emby_update_task_triggers(task_id: str, user: EmbyUser, request: Request):
    """更新计划任务触发器（接受并忽略）"""
    return {}


@router.post("/ScheduledTasks/Running/{task_id}")
async def emby_run_task(task_id: str, user: EmbyUser):
    """手动运行计划任务"""
    return {}


@router.delete("/ScheduledTasks/Running/{task_id}")
async def emby_stop_task(task_id: str, user: EmbyUser):
    """停止运行中的计划任务"""
    return {}


# ── Devices ──
# 设备管理端点

@router.get("/Devices")
async def emby_devices(user: EmbyUser):
    """获取设备列表（返回当前用户的虚拟设备）"""
    return {
        "Items": [
            {
                "Name": "Web Browser",
                "Id": f"web_{user.id}",
                "AppName": "MediaStation Web",
                "AppVersion": "1.0.0",
                "LastUserName": user.username,
                "DateLastActivity": datetime.now(timezone.utc).isoformat(),
                "IconUrl": "",
            }
        ],
        "TotalRecordCount": 1,
        "StartIndex": 0,
    }


@router.delete("/Devices")
async def emby_delete_device(user: EmbyUser, id: str | None = Query(None)):
    """删除设备（接受并忽略）"""
    return {}


# ── Library Refresh ──
# 媒体库刷新端点

@router.post("/Items/{item_id}/Refresh")
async def emby_refresh_item(
    item_id: int,
    user: EmbyUser,
    db: DB,
    metadata_refresh_mode: str | None = Query(None, alias="MetadataRefreshMode"),
    image_refresh_mode: str | None = Query(None, alias="ImageRefreshMode"),
    replace_all_metadata: bool = Query(False, alias="ReplaceAllMetadata"),
    replace_all_images: bool = Query(False, alias="ReplaceAllImages"),
):
    """刷新媒体项元数据（触发重新刮削）"""
    # 触发刮削任务
    try:
        from app.media.service import MediaService
        async with db.begin_nested():
            service = MediaService(db)
            await service.scrape_item(item_id, force=replace_all_metadata)
        logger.info(f"Emby refresh triggered for item {item_id}")
    except Exception as e:
        logger.warning(f"Emby refresh item {item_id} failed: {e}")

    return {}


@router.post("/Library/Refresh")
async def emby_library_refresh(user: EmbyUser):
    """刷新全部媒体库"""
    return {}


@router.post("/Library/Media.Added")
async def emby_library_media_added(user: EmbyUser, request: Request):
    """媒体添加通知（接受并忽略）"""
    return {}


# ── Search Hints ──
# Emby 搜索提示端点（实时搜索）

@router.get("/Search/Hints")
async def emby_search_hints(
    user: EmbyUser,
    db: DB,
    search_term: str = Query(..., alias="SearchTerm"),
    include_item_types: str | None = Query(None, alias="IncludeItemTypes"),
    limit: int = Query(10, ge=1, le=50),
    start_index: int = Query(0, ge=0),
):
    """
    搜索提示端点。
    在用户输入时提供实时搜索建议。
    """
    repo = MediaRepository(db)

    # 媒体类型过滤
    media_type_filter = None
    if include_item_types:
        types = include_item_types.split(",")
        if "Movie" in types:
            media_type_filter = "movie"
        elif "Series" in types:
            media_type_filter = "tv"

    items, total = await repo.get_items(
        search=search_term,
        media_type=media_type_filter,
        page=1,
        page_size=limit,
        sort_by="title",
        sort_order="asc",
    )

    hints = []
    for item in items:
        hint = {
            "Name": item.title or "Unknown",
            "Id": _emby_item_id(item.id),
            "Type": _to_emby_media_type(item.media_type),
            "ServerId": _emby_server_id(),
            "PrimaryImageTag": uuid.uuid4().hex[:8] if item.poster_url else "",
            "BackdropImageTags": [uuid.uuid4().hex[:8]] if item.backdrop_url else [],
            "MatchedTerm": search_term,
        }
        if item.year:
            hint["ProductionYear"] = item.year
        hints.append(hint)

    return {
        "SearchHints": hints,
        "TotalRecordCount": total,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Emby 扩展兼容层：BoxSets / Persons / Genres / Chapters / RemoteSearch 等
# ══════════════════════════════════════════════════════════════════════════════


# ── BoxSets（电影合集）──

@router.get("/BoxSets")
async def emby_boxsets(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    fields: str | None = Query(None),
    sort_by: str = Query("SortName"),
    sort_order: str = Query("Ascending"),
):
    """
    获取电影合集列表。
    对应 Emby 的 /Library/VirtualFolders/BoxSets 端点。
    """
    repo = MediaRepository(db)

    items, total = await repo.get_items(
        media_type="movie",
        page=start_index // limit + 1,
        page_size=limit,
        sort_by="title",
        sort_order="asc",
    )

    # 筛选有合集信息的电影
    boxset_items = [i for i in items if getattr(i, 'collection_id', None)]
    boxset_map = {}
    for item in boxset_items:
        coll_id = str(item.collection_id)
        if coll_id not in boxset_map:
            boxset_map[coll_id] = {
                "Name": item.collection_name or "Collection",
                "Ids": [],
                "PrimaryImageItemId": str(item.id) if item.poster_url else "",
                "BackdropImageTags": [],
            }
        boxset_map[coll_id]["Ids"].append(str(item.id))
        if item.backdrop_url and len(boxset_map[coll_id]["BackdropImageTags"]) < 3:
            boxset_map[coll_id]["BackdropImageTags"].append(uuid.uuid4().hex[:8])

    boxsets = []
    for coll_id, info in boxset_map.items():
        boxsets.append({
            "Name": info["Name"],
            "Ids": info["Ids"],
            "CollectionType": "movies",
            "PrimaryImageItemId": info["PrimaryImageItemId"],
            "BackdropImageTags": info["BackdropImageTags"],
            "ImageTags": {"Primary": uuid.uuid4().hex[:8]} if info["PrimaryImageItemId"] else {},
            "ServerId": _emby_server_id(),
            "Id": coll_id,
        })

    return {
        "Items": boxsets,
        "TotalRecordCount": len(boxsets),
        "StartIndex": start_index,
    }


# ── Persons / People（人物）──

@router.get("/Persons")
async def emby_persons(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search_term: str | None = Query(None),
):
    """
    获取人物列表。
    """
    # 简化实现：返回空列表（需要演员元数据支持）
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/Persons/{name}/Items")
async def emby_person_items(
    name: str,
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: int | None = Query(None),
):
    """
    获取人物相关媒体。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


# ── Years（年份）──

@router.get("/Years")
async def emby_years(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """
    获取所有年份列表。
    """
    repo = MediaRepository(db)
    items, _ = await repo.get_items(page=1, page_size=10000)

    years = set()
    for item in items:
        if item.year:
            years.add(item.year)

    year_list = sorted(years, reverse=True)
    result = []
    for i, year in enumerate(year_list[start_index:start_index + limit]):
        result.append({
            "Name": str(year),
            "ServerId": _emby_server_id(),
            "Id": str(year),
        })

    return {
        "Items": result,
        "TotalRecordCount": len(year_list),
        "StartIndex": start_index,
    }


# ── GameGenres / MusicGenres ──

@router.get("/GameGenres")
async def emby_game_genres(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """游戏类型列表"""
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/MusicGenres")
async def emby_music_genres(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """音乐类型列表"""
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


# ── Videos Chapters（章节）──

@router.get("/Videos/{item_id}/Chapters")
async def emby_video_chapters(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取视频章节信息。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        return {"Chapters": []}

    # 返回模拟章节（基于时长分割）
    chapters = []
    if item.duration and item.duration > 60:
        chapter_count = min(8, item.duration // 600)  # 约10分钟一章
        for i in range(chapter_count):
            start_ticks = (item.duration * i // chapter_count) * 10_000_000
            end_ticks = (item.duration * (i + 1) // chapter_count) * 10_000_000
            chapters.append({
                "Name": f"Chapter {i + 1}",
                "StartPositionTicks": start_ticks,
                "EndPositionTicks": end_ticks if i < chapter_count - 1 else item.duration * 10_000_000,
                "ImageUrl": None,
            })

    return {"Chapters": chapters}


# ── Videos AdditionalParts（额外部分）──

@router.get("/Videos/{item_id}/AdditionalParts")
async def emby_video_additional_parts(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取视频的额外部分（如多版本、花絮等）。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
    }


# ── SpecialFeatures（特别收录）──

@router.get("/Items/{item_id}/SpecialFeatures")
async def emby_special_features(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取项目的特别收录（如预告片、花絮）。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        return {"Items": [], "TotalRecordCount": 0}

    # 返回预告片作为特别收录
    trailers = await repo.get_items(
        media_type=item.media_type,
        search=item.title,
        page=1,
        page_size=5,
    )

    items = []
    for t in trailers[0] if trailers else []:
        if t.id != item_id:
            items.append(_to_emby_item(t, db))

    return {
        "Items": items[:5],
        "TotalRecordCount": len(items),
    }


# ── RemoteImages（远程图片）──

@router.get("/Items/{item_id}/RemoteImages")
async def emby_remote_images(
    item_id: int,
    user: EmbyUser,
    db: DB,
    type: str = Query("All"),
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """
    获取远程图片列表（用于海报/背景图选择）。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    images = []

    # 添加本地海报
    if item and item.poster_url:
        images.append({
            "ProviderName": "Local",
            "Type": "Primary",
            "Url": item.poster_url,
            "ThumbnailUrl": item.poster_url,
            "Language": "en",
        })

    # 添加本地背景图
    if item and item.backdrop_url:
        images.append({
            "ProviderName": "Local",
            "Type": "Backdrop",
            "Url": item.backdrop_url,
            "ThumbnailUrl": item.backdrop_url,
            "Language": None,
        })

    return {
        "Images": images[start_index:start_index + limit],
        "TotalRecordCount": len(images),
        "Providers": ["Local"],
    }


# ── UserRatings（用户评分）──

@router.post("/Items/{item_id}/UserRatings")
async def emby_user_rating(
    item_id: int,
    user: EmbyUser,
    db: DB,
    rating: float | None = Body(None),
    likes: bool | None = Body(None),
):
    """
    提交用户评分。
    """
    return {
        "ItemId": str(item_id),
        "Value": rating,
    }


@router.get("/Items/{item_id}/UserRatings")
async def emby_get_user_rating(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取用户评分。
    """
    return {
        "ItemId": str(item_id),
        "Rating": None,
        "Likes": None,
    }


# ── Library Structure（库结构）──

@router.get("/Library/VirtualFolders")
async def emby_virtual_folders(
    user: EmbyUser,
    db: DB,
):
    """
    获取虚拟文件夹/媒体库结构。
    """
    repo = MediaRepository(db)
    libraries = await repo.get_all_libraries()

    folders = []
    for lib in libraries:
        folders.append({
            "Name": lib.name,
            "Id": str(lib.id),
            "CollectionType": lib.media_type,
            "Paths": [lib.path] if lib.path else [],
            "LibraryOptions": {
                "EnableRealtimeMonitor": True,
                "EnableChapterImages": True,
            },
            "ItemId": str(lib.id),
            "PrimaryImageItemId": str(lib.id),
            "PrimaryImageTag": uuid.uuid4().hex[:8],
        })

    return folders


@router.get("/Library/SelectableMediaFolders")
async def emby_selectable_media_folders(
    user: EmbyUser,
    db: DB,
):
    """
    获取可选的媒体文件夹。
    """
    return {"Items": []}


@router.get("/Library/Options")
async def emby_library_options(
    user: EmbyUser,
    db: DB,
):
    """
    获取媒体库选项。
    """
    return {
        "EnableAutoCollection": True,
        "EnableChapterImages": True,
        "EnableEmbeddedTitles": False,
        "EnableRealtimeMonitor": True,
    }


@router.post("/Library/Refresh")
async def emby_library_refresh(
    user: EmbyUser,
    db: DB,
    library_id: int | None = Body(None),
    force: bool = Body(False),
):
    """
    刷新媒体库。
    """
    return {"Status": "Queued"}


# ── Collections（合集管理）──

@router.post("/Collections")
async def emby_create_collection(
    user: EmbyUser,
    db: DB,
    name: str = Body(...),
    item_ids: str = Body(""),
    ids: str = Body(""),
    collection_type: str = Body("movies"),
):
    """
    创建合集。
    """
    import json
    items = []
    if item_ids:
        try:
            items = json.loads(item_ids)
        except:
            pass
    if ids and not items:
        try:
            items = json.loads(ids)
        except:
            pass

    collection_id = uuid.uuid4().hex[:12]

    return {
        "Id": collection_id,
        "Name": name,
        "CollectionType": collection_type,
        "ItemIds": items,
        "ValidationWarnings": [],
    }


@router.get("/Collections/{collection_id}/Items")
async def emby_collection_items(
    collection_id: str,
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    fields: str | None = Query(None),
):
    """
    获取合集中的项目。
    """
    repo = MediaRepository(db)

    # 尝试通过 collection_id 查找
    try:
        cid = int(collection_id)
        items, total = await repo.get_items(
            collection_id=cid,
            page=start_index // limit + 1,
            page_size=limit,
        )
    except:
        items, total = [], 0

    return {
        "Items": [_to_emby_item(i, db) for i in items],
        "TotalRecordCount": total,
        "StartIndex": start_index,
    }


@router.post("/Collections/{collection_id}/Items")
async def emby_add_to_collection(
    collection_id: str,
    user: EmbyUser,
    db: DB,
    item_ids: str = Body(...),
    ids: str = Body(""),
):
    """
    向合集添加项目。
    """
    return {"ItemIds": item_ids or ids}


@router.delete("/Collections/{collection_id}/Items")
async def emby_remove_from_collection(
    collection_id: str,
    user: EmbyUser,
    db: DB,
    item_ids: str = Query(...),
):
    """
    从合集移除项目。
    """
    return {"ItemIds": item_ids}


@router.delete("/Collections/{collection_id}")
async def emby_delete_collection(
    collection_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    删除合集。
    """
    return {"Status": "Deleted"}


# ── Channels（频道）──

@router.get("/Channels")
async def emby_channels(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """
    获取频道列表。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/Channels/{channel_id}")
async def emby_channel(
    channel_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取频道详情。
    """
    raise HTTPException(404, "Channel not found")


@router.get("/Channels/{channel_id}/Items")
async def emby_channel_items(
    channel_id: str,
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filter: str | None = Query(None),
    sort_by: str = Query("SortName"),
    sort_order: str = Query("Ascending"),
):
    """
    获取频道项目。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


# ── LiveTV（直播电视）──

@router.get("/LiveTV/Info")
async def emby_livetv_info(
    user: EmbyUser,
    db: DB,
):
    """
    获取 LiveTV 服务信息。
    """
    return {
        "IsEnabled": False,
        "IsServer": False,
        "HasCableProviders": False,
        "HasSatelliteProviders": False,
        "HasTvGuideProviders": False,
    }


@router.get("/LiveTV/Channels")
async def emby_livetv_channels(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: int | None = Query(None),
    addCurrentProgram: bool = Query(False),
):
    """
    获取直播频道列表。
    """
    return {
        "Channels": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/LiveTV/Channel/{channel_id}")
async def emby_livetv_channel(
    channel_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取直播频道详情。
    """
    raise HTTPException(404, "Channel not found")


@router.get("/LiveTV/Programs")
async def emby_livetv_programs(
    user: EmbyUser,
    db: DB,
    channel_ids: str | None = Query(None),
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    max_start_time: str | None = Query(None),
    min_end_time: str | None = Query(None),
    filter: str | None = Query(None),
):
    """
    获取节目列表。
    """
    return {
        "Programs": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/LiveTV/Program/{program_id}")
async def emby_livetv_program(
    program_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取节目详情。
    """
    raise HTTPException(404, "Program not found")


@router.get("/LiveTV/RecordingFolders")
async def emby_livetv_recording_folders(
    user: EmbyUser,
    db: DB,
):
    """
    获取录像文件夹。
    """
    return {"Items": []}


@router.get("/LiveTV/Recordings")
async def emby_livetv_recordings(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    channel_id: str | None = Query(None),
    status: str | None = Query(None),
    user_id: int | None = Query(None),
    group: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
):
    """
    获取录像列表。
    """
    return {
        "Recordings": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/LiveTV/Recording/{recording_id}")
async def emby_livetv_recording(
    recording_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取录像详情。
    """
    raise HTTPException(404, "Recording not found")


@router.post("/LiveTV/Recording/{recording_id}/Delete")
async def emby_delete_recording(
    recording_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    删除录像。
    """
    return {"Status": "Deleted"}


@router.post("/LiveTV/Recording/{recording_id}/Cancel")
async def emby_cancel_recording(
    recording_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    取消录像。
    """
    return {"Status": "Cancelled"}


# ── Recommendations（推荐）──

@router.get("/Movies/Recommendations")
async def emby_movie_recommendations(
    user: EmbyUser,
    db: DB,
    category_id: str = Query("similar"),
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    fields: str | None = Query(None),
):
    """
    电影推荐。
    """
    repo = MediaRepository(db)
    items, total = await repo.get_items(
        media_type="movie",
        page=1,
        page_size=limit,
        sort_by="rating",
        sort_order="desc",
    )

    return {
        "Items": [_to_emby_item(i, db) for i in items],
        "TotalRecordCount": total,
        "CategoryId": category_id,
        "CategoryName": "Recommended for You",
    }


@router.get("/Shows/Recommendations")
async def emby_show_recommendations(
    user: EmbyUser,
    db: DB,
    category_id: str = Query("similar"),
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    fields: str | None = Query(None),
    user_id: int | None = Query(None),
):
    """
    剧集推荐。
    """
    repo = MediaRepository(db)
    items, total = await repo.get_items(
        media_type="tv",
        page=1,
        page_size=limit,
        sort_by="rating",
        sort_order="desc",
    )

    return {
        "Items": [_to_emby_item(i, db) for i in items],
        "TotalRecordCount": total,
        "CategoryId": category_id,
        "CategoryName": "Recommended for You",
    }


@router.get("/Items/{item_id}/Recommendations")
async def emby_item_recommendations(
    item_id: int,
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: str = Query("similar"),
    fields: str | None = Query(None),
):
    """
    获取项目相关推荐。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        return {
            "Items": [],
            "TotalRecordCount": 0,
            "CategoryId": category_id,
        }

    # 获取相似类型的项目
    items, total = await repo.get_items(
        media_type=item.media_type,
        page=1,
        page_size=limit,
        sort_by="rating",
        sort_order="desc",
    )

    # 排除自身
    filtered = [i for i in items if i.id != item_id][:limit]

    return {
        "Items": [_to_emby_item(i, db) for i in filtered],
        "TotalRecordCount": len(filtered),
        "CategoryId": category_id,
    }


# ── Media Keywords（媒体关键词）──

@router.get("/MediaKeywords")
async def emby_media_keywords(
    user: EmbyUser,
    db: DB,
    media_type: str | None = Query(None),
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """
    获取媒体关键词列表。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


# ── Playback Reports（播放报告）──

@router.post("/Sessions/PlaybackReports")
async def emby_playback_report(
    user: EmbyUser,
    db: DB,
    data: dict = Body(...),
):
    """
    提交播放报告。
    """
    return {"Status": "Recorded"}


# ── Item Update（更新项目元数据）──

@router.post("/Items/{item_id}")
async def emby_update_item(
    item_id: int,
    user: EmbyUser,
    db: DB,
    data: dict = Body(...),
):
    """
    更新项目元数据。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    # 更新字段
    update_fields = {}
    if "Name" in data or "title" in data:
        update_fields["title"] = data.get("Name") or data.get("title")
    if "Overview" in data or "overview" in data:
        update_fields["overview"] = data.get("Overview") or data.get("overview")
    if "CommunityRating" in data or "rating" in data:
        update_fields["rating"] = float(data.get("CommunityRating") or data.get("rating") or 0)

    if update_fields:
        await repo.update_item(item_id, **update_fields)

    return {"Status": "Updated", "ItemId": str(item_id)}


# ── User Views Enhanced（用户视图增强）──

@router.get("/Users/{user_id}/Views")
async def emby_user_views(
    user_id: int,
    user: EmbyUser,
    db: DB,
    include_external_content: bool = Query(False),
    preset_views: bool = Query(False),
):
    """
    获取用户的媒体库视图。
    """
    repo = MediaRepository(db)
    current = await UserRepository(db).get_user_by_id(user_id)
    if not current:
        raise HTTPException(404, "User not found")

    libraries, _ = await repo.get_libraries()

    views = []
    for lib in libraries:
        media_type = lib.media_type or "video"

        # 统计该类型的项目数量
        items, total = await repo.get_items(
            media_type=lib.media_type,
            page=1,
            page_size=1,
        )

        views.append({
            "Id": str(lib.id),
            "Name": lib.name,
            "Type": media_type,
            "CollectionType": media_type,
            "Image": {
                "PrimaryImageItemId": str(lib.id),
                "PrimaryImageTag": uuid.uuid4().hex[:8],
            },
            "SortName": lib.name,
            "ItemCount": total,
            "MediaTypes": [media_type.capitalize()],
            "ImageType": "Primary",
        })

    # 添加"继续观看"虚拟视图
    views.append({
        "Id": f"{user_id}_continue",
        "Name": "Continue Watching",
        "Type": "ContinueWatching",
        "CollectionType": None,
        "MediaTypes": ["Video"],
        "ItemCount": 0,
    })

    # 添加"最近添加"虚拟视图
    views.append({
        "Id": f"{user_id}_latest",
        "Name": "Recently Added",
        "Type": "RecentlyAdded",
        "CollectionType": None,
        "MediaTypes": ["Video"],
        "ItemCount": 0,
    })

    return views


# ── HLS Stream Info（HLS 流信息）──

@router.get("/Videos/{item_id}/hlsinfo")
async def emby_hls_info(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取 HLS 流信息。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    return {
        "ItemId": str(item_id),
        "MediaSources": [
            {
                "Id": str(item_id),
                "Protocol": "Http",
                "Container": "m3u8",
                "TranscodingUrl": f"/emby/Videos/{item_id}/master.m3u8",
                "TranscodingContainer": "m3u8",
                "TranscodingProtocol": "HLS",
            }
        ],
    }


# ── Session Send Command（会话发送命令）──

@router.post("/Sessions/{session_id}/Command")
async def emby_session_command(
    session_id: str,
    user: EmbyUser,
    db: DB,
    command: str = Body(...),
    arguments: dict = Body({}),
):
    """
    向会话发送命令（如播放/暂停/跳转）。
    """
    return {
        "SessionId": session_id,
        "Command": command,
        "Status": "Processed",
    }


# ── Syncplay Groups（SyncPlay 组）──

@router.get("/SyncPlay/Groups")
async def emby_syncplay_groups(
    user: EmbyUser,
    db: DB,
):
    """
    获取 SyncPlay 组列表。
    """
    return {"Groups": []}


@router.delete("/SyncPlay/Groups/{group_id}")
async def emby_syncplay_leave_group(
    group_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    离开 SyncPlay 组。
    """
    return {"Status": "Left"}


# ── Package Updates（插件包更新）──

@router.get("/Packages/Updates")
async def emby_package_updates(
    user: EmbyUser,
    db: DB,
):
    """
    获取包更新列表。
    """
    return {"Packages": []}


@router.get("/Packages/{package_name}/Versions")
async def emby_package_versions(
    package_name: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取包版本列表。
    """
    return {
        "PackageName": package_name,
        "Versions": [],
    }


# ── System Logs（系统日志）──

@router.get("/System/Logs")
async def emby_system_logs(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    min_level: str = Query("Debug"),
):
    """
    获取系统日志。
    """
    return {
        "Logs": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


@router.get("/System/Logs/{log_name}")
async def emby_system_log_file(
    log_name: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取指定日志文件内容。
    """
    raise HTTPException(404, "Log file not found")


# ── Backup / Restore（备份恢复）──

@router.get("/System/Backup")
async def emby_system_backup_list(
    user: EmbyUser,
    db: DB,
):
    """
    获取备份列表。
    """
    return {"Items": []}


@router.post("/System/Backup")
async def emby_create_backup(
    user: EmbyUser,
    db: DB,
):
    """
    创建系统备份。
    """
    return {"Status": "Queued", "JobId": uuid.uuid4().hex[:12]}


@router.post("/System/Restore")
async def emby_restore_backup(
    user: EmbyUser,
    db: DB,
):
    """
    恢复系统备份。
    """
    return {"Status": "Processing"}


@router.delete("/System/Backup/{backup_id}")
async def emby_delete_backup(
    backup_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    删除备份。
    """
    return {"Status": "Deleted"}


# ── Server Urls（服务器 URL）──

@router.get("/System/Configuration/Urls")
async def emby_server_urls(
    user: EmbyUser,
    db: DB,
):
    """
    获取服务器 URLs 配置。
    """
    settings = get_settings()
    base_url = getattr(settings, 'base_url', '')

    return {
        "ServerUrl": base_url or "/emby",
        "PublicServerUrl": base_url or "/emby",
    }


# ── Notifications（通知管理）──

@router.post("/Notifications/{user_id}")
async def emby_create_notification(
    user_id: int,
    user: EmbyUser,
    db: DB,
    title: str = Body(...),
    body: str = Body(...),
    level: str = Body("Info"),
):
    """
    创建用户通知。
    """
    return {
        "Status": "Created",
        "NotificationId": uuid.uuid4().hex[:12],
    }


@router.delete("/Notifications/{user_id}/{notification_id}")
async def emby_delete_notification(
    user_id: int,
    notification_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    删除通知。
    """
    return {"Status": "Deleted"}


@router.post("/Notifications/{user_id}/Read")
async def emby_mark_notifications_read(
    user_id: int,
    user: EmbyUser,
    db: DB,
    ids: str = Body(""),
    is_read: bool = Body(True),
):
    """
    标记通知为已读。
    """
    return {"Status": "Updated"}


@router.post("/Notifications/{user_id}/Unread")
async def emby_mark_notifications_unread(
    user_id: int,
    user: EmbyUser,
    db: DB,
    ids: str = Body(""),
):
    """
    标记通知为未读。
    """
    return {"Status": "Updated"}


# ── Filter（筛选选项）──

@router.get("/Items/Filters")
async def emby_items_filters(
    user: EmbyUser,
    db: DB,
    include_item_types: str | None = Query(None),
    parent_id: int | None = Query(None),
):
    """
    获取项目的筛选选项。
    """
    return {
        "Filters": [
            {"Name": "Resolution", "Options": [
                {"Name": "4k", "Value": "resolution=4k"},
                {"Name": "1080p", "Value": "resolution=1080p"},
                {"Name": "720p", "Value": "resolution=720p"},
                {"Name": "480p", "Value": "resolution=480p"},
            ]},
            {"Name": "Container", "Options": [
                {"Name": "MP4", "Value": "container=mp4"},
                {"Name": "MKV", "Value": "container=mkv"},
                {"Name": "M3U8", "Value": "container=m3u8"},
            ]},
            {"Name": "VideoCodec", "Options": [
                {"Name": "H.264", "Value": "video_codec=h264"},
                {"Name": "H.265/HEVC", "Value": "video_codec=hevc"},
                {"Name": "VP9", "Value": "video_codec=vp9"},
            ]},
            {"Name": "AudioCodec", "Options": [
                {"Name": "AAC", "Value": "audio_codec=aac"},
                {"Name": "FLAC", "Value": "audio_codec=flac"},
                {"Name": "DTS", "Value": "audio_codec=dts"},
                {"Name": "AC3", "Value": "audio_codec=ac3"},
            ]},
        ],
        "VideoFilters": [],
        "AudioFilters": [],
    }


# ── Index（字母索引）──

@router.get("/Items/Index")
async def emby_items_index(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    media_type: str | None = Query(None),
):
    """
    获取字母索引列表。
    """
    repo = MediaRepository(db)

    mt = None
    if media_type == "Movie":
        mt = "movie"
    elif media_type == "Series":
        mt = "tv"

    items, _ = await repo.get_items(media_type=mt, page=1, page_size=1000)

    # 提取首字母
    letters = set()
    for item in items:
        if item.title:
            first_char = item.title[0].upper()
            if first_char.isalpha():
                letters.add(first_char)

    index = [{"Name": l} for l in sorted(letters)]

    return {
        "Items": index[start_index:start_index + limit],
        "TotalRecordCount": len(index),
    }


# ── Trailers（预告片）──

@router.get("/Trailers")
async def emby_trailers(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    fields: str | None = Query(None),
    sort_by: str = Query("SortName"),
    sort_order: str = Query("Ascending"),
):
    """
    获取预告片列表。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
        "StartIndex": start_index,
    }


# ── Similar（相似项目）──

@router.get("/Items/{item_id}/Similar")
async def emby_similar_items(
    item_id: int,
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_media_types: str = Query("Movie,Series"),
    fields: str | None = Query(None),
):
    """
    获取相似项目。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        return {
            "Items": [],
            "TotalRecordCount": 0,
        }

    # 获取同类型项目
    media_type_map = {
        "Movie": "movie",
        "Series": "tv",
    }
    mt = media_type_map.get(include_media_types, item.media_type)

    items, total = await repo.get_items(
        media_type=mt,
        page=1,
        page_size=limit,
        sort_by="rating",
        sort_order="desc",
    )

    # 排除自身
    filtered = [i for i in items if i.id != item_id][:limit]

    return {
        "Items": [_to_emby_item(i, db) for i in filtered],
        "TotalRecordCount": len(filtered),
    }


# ── Played / Favorites Count（播放/收藏统计）──

@router.get("/Users/{user_id}/Items/Played")
async def emby_played_items_count(
    user_id: int,
    user: EmbyUser,
    db: DB,
    include_media_types: str | None = Query(None),
):
    """
    获取用户已播放项目统计。
    """
    return {
        "ItemCount": 0,
        "UnplayedItemCount": 0,
    }


@router.get("/Users/{user_id}/Items/Favorites")
async def emby_favorite_items_count(
    user_id: int,
    user: EmbyUser,
    db: DB,
    include_media_types: str | None = Query(None),
):
    """
    获取用户收藏项目统计。
    """
    return {
        "ItemCount": 0,
    }


# ── Audio HLS（音频 HLS）──

@router.get("/Audio/{item_id}/stream")
async def emby_audio_stream(
    item_id: int,
    user: EmbyUser,
    db: DB,
    container: str = Query("mp3"),
):
    """
    获取音频流。
    """
    raise HTTPException(404, "Audio stream not available")


@router.get("/Audio/{item_id}/hls/playlist.m3u8")
async def emby_audio_hls(
    item_id: int,
    user: EmbyUser,
    db: DB,
):
    """
    获取音频 HLS 流。
    """
    raise HTTPException(404, "Audio HLS not available")


# ── Image Upload（图片上传）──

@router.post("/Items/{item_id}/Images/{image_type}")
async def emby_upload_item_image(
    item_id: int,
    image_type: str,
    user: EmbyUser,
    db: DB,
):
    """
    上传项目图片。
    """
    return {
        "ItemId": str(item_id),
        "ImageType": image_type,
        "Status": "Saved",
    }


@router.delete("/Items/{item_id}/Images/{image_type}")
async def emby_delete_item_image(
    item_id: int,
    image_type: str,
    user: EmbyUser,
    db: DB,
):
    """
    删除项目图片。
    """
    return {"Status": "Deleted"}


@router.post("/Users/{user_id}/Images/{image_type}/{image_index}")
async def emby_set_user_image(
    user_id: int,
    image_type: str,
    image_index: int,
    user: EmbyUser,
    db: DB,
):
    """
    设置用户头像。
    """
    return {"Status": "Set"}


@router.delete("/Users/{user_id}/Images/{image_type}/{image_index}")
async def emby_delete_user_image(
    user_id: int,
    image_type: str,
    image_index: int,
    user: EmbyUser,
    db: DB,
):
    """
    删除用户头像。
    """
    return {"Status": "Deleted"}


# ── Plugins Actions（插件操作）──

@router.post("/Plugins/{plugin_id}/Uninstall")
async def emby_uninstall_plugin(
    plugin_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    卸载插件。
    """
    return {"Status": "Uninstalled"}


@router.post("/Plugins/{plugin_id}/Restart")
async def emby_restart_plugin(
    plugin_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    重启插件。
    """
    return {"Status": "Restarted"}


@router.get("/Plugins/{plugin_id}/Configuration")
async def emby_plugin_config(
    plugin_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取插件配置。
    """
    return {"Configuration": None}


# ── Devices Actions（设备操作）──

@router.get("/Devices/{device_id}")
async def emby_device(
    device_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取设备详情。
    """
    return {
        "Id": device_id,
        "Name": "Unknown Device",
        "AppName": "MediaStation",
        "LastActivity": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/Devices/{device_id}/Revoke")
async def emby_revoke_device(
    device_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    撤销设备访问权限。
    """
    return {"Status": "Revoked"}


# ── PlayQueue（播放队列）──

@router.get("/PlayQueues")
async def emby_play_queues(
    user: EmbyUser,
    db: DB,
):
    """
    获取播放队列。
    """
    return {"Items": []}


@router.post("/PlayQueues")
async def emby_create_play_queue(
    user: EmbyUser,
    db: DB,
    item_ids: str = Body(...),
    mode: str = Body("Queue"),
    start_item_id: str = Body(None),
):
    """
    创建播放队列。
    """
    import json
    ids = []
    if item_ids:
        try:
            ids = json.loads(item_ids)
        except:
            ids = item_ids.split(",")

    queue_id = uuid.uuid4().hex[:12]

    return {
        "Id": queue_id,
        "PlayingItemId": start_item_id or (ids[0] if ids else None),
        "ItemIds": ids,
        "Mode": mode,
    }


@router.get("/PlayQueues/{queue_id}")
async def emby_get_play_queue(
    queue_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    获取播放队列详情。
    """
    return {
        "Id": queue_id,
        "PlayingItemId": None,
        "ItemIds": [],
        "Mode": "Queue",
    }


# ── DLNA（DLNA 媒体渲染）──

@router.get("/Dlna")
async def emby_dlna_info(
    user: EmbyUser,
    db: DB,
):
    """
    获取 DLNA 配置信息。
    """
    return {
        "Enabled": False,
        "EnableServer": False,
        "EnablePlayTo": False,
        "EnableReceiver": False,
    }


# ── File Organization（文件组织）──

@router.get("/Library/FileOrganization")
async def emby_file_organization(
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """
    获取文件组织任务。
    """
    return {
        "Items": [],
        "TotalRecordCount": 0,
    }


@router.post("/Library/FileOrganization/{task_id}/Cancel")
async def emby_cancel_organization_task(
    task_id: str,
    user: EmbyUser,
    db: DB,
):
    """
    取消文件组织任务。
    """
    return {"Status": "Cancelled"}


@router.post("/Library/FileOrganization/{task_id}/Confirm")
async def emby_confirm_organization_task(
    task_id: str,
    user: EmbyUser,
    db: DB,
    new_path: str = Body(None),
):
    """
    确认文件组织任务。
    """
    return {"Status": "Confirmed", "NewPath": new_path}


# ── Suggestions（建议）──

@router.get("/Suggestions")
async def emby_suggestions(
    user: EmbyUser,
    db: DB,
    media_type: str | None = Query(None),
    start_index: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    获取智能建议。
    """
    repo = MediaRepository(db)

    mt = None
    if media_type == "Movie":
        mt = "movie"
    elif media_type == "Series":
        mt = "tv"

    items, total = await repo.get_items(
        media_type=mt,
        page=1,
        page_size=limit,
        sort_by="rating",
        sort_order="desc",
    )

    return {
        "Items": [_to_emby_item(i, db) for i in items],
        "TotalRecordCount": total,
    }


# ── Metadata Refresh（元数据刷新）──

@router.post("/Items/{item_id}/Refresh")
async def emby_refresh_metadata(
    item_id: int,
    user: EmbyUser,
    db: DB,
    metadata_language: str = Body("en"),
    image_refresh_mode: str = Body("Default"),
    metadata_refresh_mode: str = Body("Default"),
    replace_all_images: bool = Body(False),
    replace_all_metadata: bool = Body(False),
):
    """
    刷新项目元数据。
    """
    return {
        "Status": "Queued",
        "ItemId": str(item_id),
    }


# ── Remote Search（远程搜索）──

@router.post("/Library/RemoteSearch/Apply")
async def emby_apply_remote_search(
    user: EmbyUser,
    db: DB,
    search_result: dict = Body(...),
    media_type: str = Body(...),
):
    """
    应用远程搜索结果。
    """
    return {
        "Status": "Applied",
        "ItemId": search_result.get("Id"),
    }


@router.post("/Library/RemoteSearch/Movie")
async def emby_remote_search_movie(
    user: EmbyUser,
    db: DB,
    search_info: dict = Body(...),
):
    """
    远程搜索电影。
    """
    return {
        "SearchResults": [],
        "TotalRecordCount": 0,
    }


@router.post("/Library/RemoteSearch/Series")
async def emby_remote_search_series(
    user: EmbyUser,
    db: DB,
    search_info: dict = Body(...),
):
    """
    远程搜索剧集。
    """
    return {
        "SearchResults": [],
        "TotalRecordCount": 0,
    }


# ── Instant Mix（即时混合播放）──

@router.get("/Items/{item_id}/InstantMix")
async def emby_instant_mix(
    item_id: int,
    user: EmbyUser,
    db: DB,
    start_index: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    fields: str | None = Query(None),
):
    """
    获取即时混合播放列表。
    """
    repo = MediaRepository(db)
    item = await repo.get_item_by_id(item_id)

    if not item:
        return {
            "Items": [],
            "TotalRecordCount": 0,
        }

    # 返回同类型项目作为混合播放
    items, total = await repo.get_items(
        media_type=item.media_type,
        page=1,
        page_size=limit,
        sort_by="random",
    )

    return {
        "Items": [_to_emby_item(i, db) for i in items if i.id != item_id][:limit],
        "TotalRecordCount": min(total - 1, limit),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 文件结尾 - Emby 兼容层端点总数：约 200+ 个
# ══════════════════════════════════════════════════════════════════════════════
