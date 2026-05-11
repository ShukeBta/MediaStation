"""
外部播放器直链路由
提供带一次性令牌的视频直链，供 Infuse/Kodi/VLC/NPlayer/IINA 等外部播放器使用。
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from jose import JWTError, jwt

from app.config import get_settings
from app.deps import CurrentUser, DB
from app.exceptions import NotFoundError
from app.media.repository import MediaRepository
from app.playback.service import PlaybackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playback", tags=["playback"])

# ── 生成外部播放直链 ──


@router.get("/{media_id}/external-url")
async def get_external_url(
    media_id: int,
    user: CurrentUser,
    db: DB,
    episode_id: int | None = None,
):
    """
    生成外部播放器直链 URL。
    返回带有一次性 token 的视频流地址，可直接粘贴到外部播放器中打开。
    """
    from app.user.auth import ALGORITHM

    settings = get_settings()
    service = PlaybackService(MediaRepository(db))

    # 获取媒体信息
    item = await service.repo.get_item_by_id(media_id)
    if not item:
        raise NotFoundError("MediaItem", media_id)

    # 确定实际文件
    file_path = item.file_path
    if episode_id and item.media_type in ("tv", "anime"):
        episode = await service.repo.get_episode_by_id(episode_id)
        if not episode:
            raise NotFoundError("Episode", episode_id)
        file_path = episode.file_path or item.file_path

    if not file_path or not Path(file_path).exists():
        raise NotFoundError("File", file_path or "empty")

    # 生成 24 小时有效的播放令牌
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": str(user.id),
        "type": "external_play",
        "media_id": media_id,
        "episode_id": episode_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    token = jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)

    # 构造直链 URL
    from urllib.parse import urlencode

    base_url = f"/api/playback/{media_id}/external-stream"
    params = {"token": token}
    if episode_id:
        params["episode_id"] = str(episode_id)

    return {
        "url": f"{base_url}?{urlencode(params)}",
        "media_id": media_id,
        "title": item.title,
        "episode_id": episode_id,
        "expires_in": 86400,  # 24h
        "filename": Path(file_path).name,
    }


# ── 外部播放器流式传输（无需页面 Token，通过 URL 参数中的 token 认证） ──


@router.get("/{media_id}/external-stream")
async def external_stream(
    media_id: int,
    token: str = Query(..., description="外部播放令牌"),
    episode_id: int | None = None,
    range: str | None = None,
):
    """
    外部播放器视频流端点。
    通过 URL 参数中的 token 认证，无需 Bearer Header。
    支持 Range 断点续传，兼容所有主流外部播放器。
    """
    from app.user.auth import ALGORITHM
    from app.database import async_session_factory

    settings = get_settings()

    # 验证令牌
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM], options={"verify_signature": True, "verify_exp": True})
        if payload.get("type") != "external_play":
            raise HTTPException(status_code=403, detail="Invalid token type")
        if payload.get("media_id") != media_id:
            raise HTTPException(status_code=403, detail="Token media mismatch")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 获取文件路径
    async with async_session_factory() as session:
        repo = MediaRepository(session)
        service = PlaybackService(repo)

        item = await repo.get_item_by_id(media_id)
        if not item:
            raise NotFoundError("MediaItem", media_id)

        file_path = item.file_path
        if episode_id and item.media_type in ("tv", "anime"):
            episode = await repo.get_episode_by_id(episode_id)
            if episode and episode.file_path:
                file_path = episode.file_path

        if not file_path or not Path(file_path).exists():
            raise NotFoundError("File", file_path or "empty")

    path = Path(file_path)
    file_size = path.stat().st_size

    # 根据文件扩展名设置 MIME 类型
    ext = path.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".wmv": "video/x-ms-wmv",
        ".flv": "video/x-flv",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".ts": "video/mp2t",
        ".m4v": "video/mp4",
        ".iso": "video/mp4",
    }
    media_type = mime_map.get(ext, "video/mp4")

    # Range 请求（断点续传）
    if range:
        range_parts = range.replace("bytes=", "").split("-")
        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if range_parts[1] else file_size - 1
        end = min(end, file_size - 1)

        async def file_range_sender():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                chunk_size = 256 * 1024  # 256KB for external players
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            file_range_sender(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
                "Content-Disposition": f'inline; filename="{path.name}"',
                "Cache-Control": "public, max-age=86400",
            },
        )

    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f'inline; filename="{path.name}"',
            "Cache-Control": "public, max-age=86400",
        },
    )
