"""
播放路由
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.config import get_settings
from app.database import async_session_factory
from app.deps import CurrentUser, DB
from app.media.repository import MediaRepository
from app.playback.service import PlaybackService

router = APIRouter(prefix="/playback", tags=["playback"])


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
        payload = jwt.decode(
            token, settings.app_secret_key,
            algorithms=[ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
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


async def _resolve_token_user(
    token: str | None = Query(None),
    authorization: str | None = Header(None),
):
    """
    FastAPI Depends：从 query ?token= 或 Authorization: Bearer 中提取并验证用户。
    供所有需要 query-token 认证的端点复用，避免重复解析逻辑。
    """
    raw_token: str | None = None
    if token:
        raw_token = token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with async_session_factory() as session:
        return await _get_user_from_token(raw_token, session)


# 便捷类型别名
TokenUser = Annotated[object, Depends(_resolve_token_user)]


# ──────────────────────────────────────────────────────────────
# HLS 路由（必须在 /{media_id}/... 之前，因为 FastAPI 按声明顺序匹配）
# ──────────────────────────────────────────────────────────────

@router.get("/hls/{job_id}/playlist.m3u8")
async def get_hls_playlist(
    job_id: str,
    db: DB,
    user: TokenUser,
):
    """HLS 播放列表（支持 query token 认证，供 HLS.js 使用）"""
    playlist_path = Path(get_settings().transcode_cache_dir) / job_id / "playlist.m3u8"
    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="Playlist not found")
    return FileResponse(playlist_path, media_type="application/vnd.apple.mpegurl")


@router.get("/hls/{job_id}/{segment}")
async def get_hls_segment(
    job_id: str,
    segment: str,
    db: DB,
    user: TokenUser,
):
    """HLS 分片（支持 query token 认证，供 HLS.js 使用）"""
    seg_path = Path(get_settings().transcode_cache_dir) / job_id / segment
    if not seg_path.exists():
        raise HTTPException(status_code=404, detail="Segment not found")
    return FileResponse(seg_path, media_type="video/mp2t")


@router.get("/transcode/{job_id}/status")
async def transcode_status(job_id: str, user: CurrentUser):
    from app.playback.transcoder import Transcoder
    transcoder = Transcoder()
    return transcoder.get_job_status(job_id)


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


def range_requests_response(
    request: Request, file_path: str, content_type: str
) -> StreamingResponse | FileResponse:
    """处理 HTTP Range 请求，返回 206 Partial Content 或完整文件

    防止内存溢出：限制单次读取块大小（最大 2MB）
    """
    path = Path(file_path)
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Encoding": "identity",
        "Content-Length": str(file_size),
        "Access-Control-Expose-Headers": (
            "Accept-Ranges, Content-Encoding, Content-Length, Content-Range"
        ),
    }

    if range_header is None:
        return FileResponse(path, media_type=content_type, headers=headers)

    # 安全地解析 Range 请求，避免用户恶意传入极大值导致内存崩溃
    try:
        byte_range = range_header.strip().split("=")[1]
        start_str, end_str = byte_range.split("-")
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
    except ValueError:
        return Response(status_code=416, headers=headers)  # Requested Range Not Satisfiable

    if start >= file_size or end >= file_size or start > end:
        return Response(status_code=416, headers=headers)

    # 限制单次读取的 Chunk 大小（最大 2MB，防止并发引发 OOM）
    chunk_size = min(end - start + 1, 2 * 1024 * 1024)
    end = start + chunk_size - 1

    headers["Content-Length"] = str(chunk_size)
    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    def file_iterator(path, offset, bytes_to_read):
        with open(path, "rb") as f:
            f.seek(offset, 0)
            yield f.read(bytes_to_read)

    return StreamingResponse(
        file_iterator(file_path, start, chunk_size),
        headers=headers,
        status_code=206,
        media_type=content_type,
    )


@router.get("/{media_id}/stream")
async def stream_video(
    media_id: int,
    request: Request,
    db: DB,
    episode_id: int | None = None,
    user: TokenUser = None,
):
    """直接视频流（支持 Range 断点续传 + query token 认证）

    认证方式（优先级顺序）：
    1. ?token=<jwt>  — 用于 <video src> / 浏览器直连
    2. Authorization: Bearer <jwt>  — 用于普通 axios 请求
    """
    service = PlaybackService(MediaRepository(db))
    file_path = await service.get_stream_path(media_id, episode_id)
    path = Path(file_path)

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
    return range_requests_response(request, file_path, mime_type)


@router.get("/{media_id}/external-url")
async def get_external_url(
    media_id: int,
    db: DB,
    episode_id: int | None = None,
    user: TokenUser = None,
):
    """获取外部播放器直链（含 token 的完整 URL，供 Infuse/VLC 等使用）"""
    from app.user.auth import create_access_token

    settings = get_settings()
    service = PlaybackService(MediaRepository(db))
    file_path = await service.get_stream_path(media_id, episode_id)

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
    user: TokenUser = None,
):
    """获取各外部播放器的协议直链

    支持：PotPlayer, VLC, IINA, Infuse, NPlayer, MX Player, MPV, MPC-HC
    """
    from app.user.auth import create_access_token

    settings = get_settings()
    service = PlaybackService(MediaRepository(db))
    file_path = await service.get_stream_path(media_id, episode_id)

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
            "mpchc": stream_url,
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
