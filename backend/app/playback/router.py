"""
播放路由
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.deps import CurrentUser, DB
from app.media.repository import MediaRepository
from app.playback.service import PlaybackService

router = APIRouter(prefix="/playback", tags=["playback"])

# ──────────────────────────────────────────────────────────────
# HLS 路由（必须在 /{media_id}/... 之前，因为 FastAPI 按声明顺序匹配）
# ──────────────────────────────────────────────────────────────

@router.get("/hls/{job_id}/playlist.m3u8")
async def get_hls_playlist(
    job_id: str,
    db: DB,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
):
    """HLS 播放列表（支持 query token 认证，供 HLS.js 使用）"""
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with async_session_factory() as session:
        await _get_user_from_token(raw_token, session)

    from app.config import get_settings
    playlist_path = Path(get_settings().transcode_cache_dir) / job_id / "playlist.m3u8"
    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="Playlist not found")
    return FileResponse(playlist_path, media_type="application/vnd.apple.mpegurl")


@router.get("/hls/{job_id}/{segment}")
async def get_hls_segment(
    job_id: str,
    segment: str,
    db: DB,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
):
    """HLS 分片（支持 query token 认证，供 HLS.js 使用）"""
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with async_session_factory() as session:
        await _get_user_from_token(raw_token, session)

    from app.config import get_settings
    seg_path = Path(get_settings().transcode_cache_dir) / job_id / segment
    if not seg_path.exists():
        raise HTTPException(status_code=404, detail="Segment not found")
    return FileResponse(seg_path, media_type="video/mp2t")


@router.get("/transcode/{job_id}/status")
async def transcode_status(job_id: str, user: CurrentUser):
    from app.playback.transcoder import Transcoder
    transcoder = Transcoder()
    return transcoder.get_job_status(job_id)


# ──────────────────────────────────────────────────────────────
# 辅助：支持 query token 的用户解析（用于 <video src> 无法携带 header 的场景）
# ──────────────────────────────────────────────────────────────

async def _get_user_from_token(token: str, db: AsyncSession):
    """根据 JWT token 字符串解析用户，不依赖 OAuth2PasswordBearer"""
    from app.user.auth import ALGORITHM
    from app.user.repository import UserRepository

    settings = get_settings()
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
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
    return user


@router.get("/{media_id}/info")
async def get_play_info(
    media_id: int,
    user: CurrentUser,
    db: DB,
    episode_id: int | None = None,
    quality: str = Query("auto"),
):
    service = PlaybackService(MediaRepository(db))
    return await service.get_play_info(media_id, episode_id, quality, user_id=user.id)


@router.get("/{media_id}/stream")
async def stream_video(
    media_id: int,
    db: DB,
    episode_id: int | None = None,
    range: str | None = Header(None),
    token: str | None = Query(None),
    authorization: str | None = Header(None),
):
    """直接视频流（支持 Range 断点续传 + query token 认证）

    认证方式（优先级顺序）：
    1. ?token=<jwt>  — 用于 <video src> / 浏览器直连
    2. Authorization: Bearer <jwt>  — 用于普通 axios 请求
    """
    # 解析 token
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with async_session_factory() as session:
        user = await _get_user_from_token(raw_token, session)

    service = PlaybackService(MediaRepository(db))
    file_path = await service.get_stream_path(media_id, episode_id)
    path = Path(file_path)

    file_size = path.stat().st_size

    # 根据文件后缀确定 MIME 类型
    _mime_map = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".m4v": "video/x-m4v",
        ".ts": "video/mp2t",
        ".flv": "video/x-flv",
    }
    mime_type = _mime_map.get(path.suffix.lower(), "video/mp4")

    if range:
        # 解析 Range: bytes=start-end
        range_parts = range.replace("bytes=", "").split("-")
        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if len(range_parts) > 1 and range_parts[1] else file_size - 1
        end = min(end, file_size - 1)

        async def file_range_sender():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                chunk_size = 64 * 1024  # 64KB chunks
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            file_range_sender(),
            status_code=206,
            media_type=mime_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
                "Cache-Control": "public, max-age=86400",
            },
        )

    return FileResponse(
        path,
        media_type=mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/{media_id}/external-url")
async def get_external_url(
    media_id: int,
    db: DB,
    episode_id: int | None = None,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
):
    """获取外部播放器直链（含 token 的完整 URL，供 Infuse/VLC 等使用）

    认证方式（优先级顺序）：
    1. ?token=<jwt>  — 用于外部播放器
    2. Authorization: Bearer <jwt> — 用于普通请求
    """
    # 解析 token
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with async_session_factory() as session:
        user = await _get_user_from_token(raw_token, session)

    settings = get_settings()
    service = PlaybackService(MediaRepository(db))
    file_path = await service.get_stream_path(media_id, episode_id)

    # 生成有效期较长的直链 token（复用标准 access token）
    from app.user.auth import create_access_token
    stream_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    base_url = getattr(settings, 'server_url', None) or "http://localhost:3001"
    stream_url = f"{base_url}/api/playback/{media_id}/stream?token={stream_token}"
    if episode_id:
        stream_url += f"&episode_id={episode_id}"

    return {
        "url": stream_url,
        "file_path": file_path,
        "media_id": media_id,
        "episode_id": episode_id,
    }


@router.get("/{media_id}/external-players")
async def get_external_players(
    media_id: int,
    db: DB,
    episode_id: int | None = None,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
):
    """获取各外部播放器的协议直链

    支持：PotPlayer, VLC, IINA, Infuse, NPlayer, MX Player, MPV, MPC-HC
    """
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with async_session_factory() as session:
        user = await _get_user_from_token(raw_token, session)

    settings = get_settings()
    service = PlaybackService(MediaRepository(db))
    file_path = await service.get_stream_path(media_id, episode_id)

    from app.user.auth import create_access_token
    stream_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    base_url = getattr(settings, 'server_url', None) or "http://localhost:3001"
    ep_query = f"&episode_id={episode_id}" if episode_id else ""
    stream_url = f"{base_url}/api/playback/{media_id}/stream?token={stream_token}{ep_query}"

    return {
        "direct_url": stream_url,
        "file_name": Path(file_path).name,
        "file_path": file_path,
        "players": {
            "potplayer": f"potplayer://{stream_url}",
            "vlc": f"vlc://{stream_url}",
            "iina": f"iina://open?url={stream_url}",
            "infuse": f"infuse://{stream_url}",
            "nplayer": f"nplayer-{stream_url}",
            "mxplayer": f"intent:play?type=video&url={stream_url}#Intent;scheme=https;package=com.mxtech.videoplayer.ad;end",
            "mpv": f"mpv://{stream_url}",
            "mpchc": stream_url,  # MPC-HC 直接打开 URL
        },
    }


@router.get("/subtitles/{subtitle_id}")
async def get_subtitle(subtitle_id: int, user: CurrentUser, db: DB):
    """获取字幕文件"""
    from app.media.models import Subtitle
    from sqlalchemy import select

    result = await db.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
    subtitle = result.scalar_one_or_none()
    if not subtitle or not subtitle.path:
        raise HTTPException(status_code=404, detail="Subtitle not found")

    path = Path(subtitle.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Subtitle file not found")

    media_types = {
        ".srt": "text/plain",
        ".ass": "text/x-ssa",
        ".ssa": "text/x-ssa",
        ".vtt": "text/vtt",
    }
    content_type = media_types.get(path.suffix.lower(), "text/plain")

    return FileResponse(
        path,
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={path.name}"},
    )


@router.post("/{media_id}/progress")
async def report_progress(
    media_id: int,
    user: CurrentUser,
    db: DB,
    progress: float = Query(..., ge=0),
    duration: float = Query(..., ge=0),
    episode_id: int | None = None,
):
    service = PlaybackService(MediaRepository(db))
    await service.report_progress(media_id, user.id, progress, duration, episode_id)
    return {"ok": True}

