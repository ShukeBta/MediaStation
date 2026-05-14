"""
播放业务逻辑

播放模式：
- direct: 直连源文件播放，不做任何转码（默认模式）
- hls: HLS 转码播放（需开启转码功能）

前端可通过 quality 参数控制：
- "original" / "direct": 强制直连
- "auto": 浏览器能播则直连，否则转码（转码开启时）
- "480p" / "720p" / "1080p" / "4k": 强制指定画质转码（转码开启时）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.exceptions import NotFoundError
from app.media.models import MediaItem
from app.media.repository import MediaRepository
from app.playback.transcoder import TranscodeProfile, Transcoder

# 全局转码器实例
_transcoder_instance: "Transcoder | None" = None

def get_transcoder() -> "Transcoder | None":
    """获取转码器实例（用于关闭）"""
    global _transcoder_instance
    # 如果实例不存在，创建一个
    if _transcoder_instance is None:
        from app.playback.transcoder import Transcoder
        _transcoder_instance = Transcoder()
    return _transcoder_instance

logger = logging.getLogger(__name__)

# 浏览器原生支持的容器格式
BROWSER_NATIVE_CONTAINERS = {"mp4", "webm", "m4v", "ogg", "mov"}
# 浏览器原生支持的视频编码
BROWSER_NATIVE_VIDEO_CODECS = {"h264", "avc", "vp8", "vp9", "av1"}
# 浏览器原生支持的音频编码
BROWSER_NATIVE_AUDIO_CODECS = {"aac", "mp3", "opus", "vorbis", "flac"}

# Chrome/Edge 支持通过 MSE 直连的 MKV 格式（不需要转码）
# Chrome 支持 MKV + H264/VP8/VP9 + AAC/MP3/Opus/Vorbis
MKV_SUPPORTED_VIDEO = {"h264", "avc", "vp8", "vp9", "av1"}
MKV_SUPPORTED_AUDIO = {"aac", "mp3", "opus", "vorbis", "flac", ""}


class PlaybackService:
    def __init__(self, repo: MediaRepository):
        self.repo = repo
        self.transcoder = Transcoder()

    def _can_direct_play(self, item: MediaItem) -> bool:
        """判断是否可直连播放（浏览器原生支持）"""
        # container 优先用数据库字段，为空时从文件路径扩展名推断
        container = (item.container or Path(item.file_path or "").suffix.lstrip(".") or "").lower()
        video_codec = (item.video_codec or "").lower()
        audio_codec = (item.audio_codec or "").lower()

        # MP4 + H264 + AAC = 最佳浏览器兼容性
        if container == "mp4" and video_codec in ("h264", "avc") and (not audio_codec or audio_codec == "aac"):
            return True

        # WebM + VP8/VP9/AV1 = 现代浏览器支持
        if container == "webm" and video_codec in ("vp8", "vp9", "av1"):
            return True

        # MP4 容器 + 任意常见视频编码（HEVC 在 Safari/Edge 支持）
        if container == "mp4" and video_codec in BROWSER_NATIVE_VIDEO_CODECS:
            return True

        # 其他容器 + 完全兼容的编码组合
        if container in BROWSER_NATIVE_CONTAINERS and video_codec in BROWSER_NATIVE_VIDEO_CODECS:
            return True

        # MKV 容器：Chrome/Edge 通过 MSE 支持 H264/VP8/VP9/AV1
        # 注意：MKV + HEVC 在 Chrome 中不支持，MKV + DTS/AC3 音频也不支持
        if container == "mkv" and video_codec in MKV_SUPPORTED_VIDEO:
            if not audio_codec or audio_codec in MKV_SUPPORTED_AUDIO:
                return True

        # MP4 容器 + 任意编码（让浏览器自行判断，通常能播）
        if container in ("mp4", "m4v"):
            return True

        return False

    def _get_playback_warning(self, item: MediaItem, can_direct: bool, transcode_enabled: bool) -> str | None:
        """获取播放警告信息（当无法直连播放且转码未开启时）"""
        if can_direct or transcode_enabled:
            return None
        container = (item.container or "").lower()
        audio_codec = (item.audio_codec or "").lower()
        video_codec = (item.video_codec or "").lower()

        issues = []
        if container in ("ts", "m2ts", "mts"):
            issues.append(f"MPEG-TS (.{container}) 容器浏览器不支持直接播放")
        elif container == "mkv":
            if audio_codec in ("dts", "truehd", "ac3", "eac3"):
                issues.append(f"{audio_codec.upper()} 音频格式浏览器不支持")
            if video_codec in ("hevc", "h265"):
                issues.append("HEVC/H.265 视频在 Chrome 中可能不支持（Windows 需付费解码器）")
        elif container in ("avi", "rmvb", "flv", "wmv"):
            issues.append(f".{container} 容器浏览器不支持")

        if issues:
            return f"播放可能失败：{'；'.join(issues)}。建议开启服务端转码（设置→系统）。"
        return None

    def _resolve_stream_mode(
        self, quality: str, can_direct: bool, transcode_enabled: bool
    ) -> str:
        """
        决定播放模式：
        - 转码关闭 → 始终 direct
        - quality=original/direct → 强制 direct
        - quality=auto + 可直连 → direct
        - quality=auto + 不可直连 + 转码开启 → hls
        - quality=480p/720p/1080p/4k + 转码开启 → hls
        """
        # 转码功能关闭，永远直连
        if not transcode_enabled:
            return "direct"

        # 用户主动要求原画/直连
        if quality in ("original", "direct"):
            return "direct"

        # auto 模式：能直连就直连
        if quality == "auto" and can_direct:
            return "direct"

        # 其余情况走转码
        return "hls"

    async def get_play_info(
        self, media_id: int, episode_id: int | None = None, quality: str = "auto",
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """获取播放信息"""
        settings = get_settings()
        item = await self.repo.get_item_by_id(media_id)
        if not item:
            raise NotFoundError("MediaItem", media_id)

        # 获取实际文件路径
        file_path = item.file_path
        media_type = item.media_type

        # 如果是剧集且有指定集
        if episode_id and media_type in ("tv", "anime"):
            episode = await self.repo.get_episode_by_id(episode_id)
            if not episode:
                raise NotFoundError("Episode", episode_id)
            file_path = episode.file_path or item.file_path

        if not file_path or not Path(file_path).exists():
            raise NotFoundError("File", file_path or "empty")

        # 获取所有剧集列表（剧集模式）
        episodes = []
        if media_type in ("tv", "anime"):
            episodes = await self.repo.get_episodes_by_item(media_id)

        # 获取字幕
        subtitles = await self._get_subtitle_urls(media_id, episode_id)

        # 获取播放进度
        watch_progress = 0
        if user_id:
            from app.user.models import WatchHistory
            from sqlalchemy import select
            from app.database import async_session_factory

            async with async_session_factory() as session:
                stmt = select(WatchHistory).where(
                    WatchHistory.user_id == user_id,
                    WatchHistory.media_item_id == media_id,
                )
                if episode_id:
                    stmt = stmt.where(WatchHistory.episode_id == episode_id)
                result = await session.execute(stmt)
                history = result.scalars().first()
                if history:
                    watch_progress = history.progress or 0

        # 判断播放模式
        can_direct = self._can_direct_play(item)
        transcode_enabled = settings.transcode_enabled
        stream_mode = self._resolve_stream_mode(quality, can_direct, transcode_enabled)
        playback_warning = self._get_playback_warning(item, can_direct, transcode_enabled)

        # 文件元数据（供前端展示）
        file_info = {
            "container": item.container or Path(file_path).suffix.lstrip("."),
            "video_codec": item.video_codec,
            "audio_codec": item.audio_codec,
            "resolution": item.resolution,
        }

        if stream_mode == "direct":
            # 直连播放：浏览器直接请求原始文件，支持 Range 断点续传
            direct_url = f"/api/playback/{media_id}/stream"
            if episode_id:
                direct_url += f"?episode_id={episode_id}"

            return {
                "id": media_id,
                "title": item.title,
                "original_title": item.original_title,
                "media_type": media_type,
                "stream_mode": "direct",
                "direct_url": direct_url,
                "can_direct_play": can_direct,
                "transcode_enabled": transcode_enabled,
                "playback_warning": playback_warning,
                "file_info": file_info,
                "subtitles": subtitles,
                "episodes": episodes,
                "watch_progress": watch_progress,
            }

        # HLS 转码播放
        result = await self.transcoder.get_or_create_hls(
            media_id, file_path, quality or "720p"
        )
        return {
            "id": media_id,
            "title": item.title,
            "original_title": item.original_title,
            "media_type": media_type,
            "stream_mode": "hls",
            "hls_playlist_url": result.get("playlist_url", ""),
            "status": result.get("status", "unknown"),
            "can_direct_play": can_direct,
            "transcode_enabled": transcode_enabled,
            "playback_warning": playback_warning,
            "file_info": file_info,
            "subtitles": subtitles,
            "episodes": episodes,
            "watch_progress": watch_progress,
        }

    async def get_stream_path(
        self, media_id: int, episode_id: int | None = None
    ) -> str:
        """获取实际文件路径（用于流式传输）"""
        item = await self.repo.get_item_by_id(media_id)
        if not item:
            raise NotFoundError("MediaItem", media_id)

        file_path = item.file_path

        if episode_id and item.media_type in ("tv", "anime"):
            episode = await self.repo.get_episode_by_id(episode_id)
            if episode and episode.file_path:
                file_path = episode.file_path

        if not file_path or not Path(file_path).exists():
            raise NotFoundError("File", file_path or "empty")

        return file_path

    async def _get_subtitle_urls(
        self, media_id: int, episode_id: int | None = None
    ) -> list[dict]:
        """获取字幕 URL 列表"""
        subs = await self.repo.get_subtitles_by_item(media_id)
        result = []
        for sub in subs:
            if sub.path and Path(sub.path).exists():
                result.append({
                    "id": sub.id,
                    "language": sub.language,
                    "language_name": sub.language_name,
                    "url": f"/api/playback/subtitles/{sub.id}",
                    "source": sub.source,
                })
        return result

    async def report_progress(
        self, media_id: int, user_id: int, progress: float, duration: float,
        episode_id: int | None = None,
    ):
        """上报播放进度"""
        from app.user.models import WatchHistory
        from datetime import datetime, timezone

        from sqlalchemy import select
        from app.database import async_session_factory

        async with async_session_factory() as session:
            stmt = select(WatchHistory).where(
                WatchHistory.user_id == user_id,
                WatchHistory.media_item_id == media_id,
            )
            if episode_id:
                stmt = stmt.where(WatchHistory.episode_id == episode_id)
            result = await session.execute(stmt)
            history = result.scalar_one_or_none()

            completed = progress >= duration * 0.9 if duration > 0 else False

            if history:
                history.progress = progress
                history.duration = duration
                history.completed = completed
                history.last_watched = datetime.now(timezone.utc)
            else:
                history = WatchHistory(
                    user_id=user_id,
                    media_item_id=media_id,
                    episode_id=episode_id,
                    progress=progress,
                    duration=duration,
                    completed=completed,
                )
                session.add(history)
            await session.commit()

    def get_transcode_status(self, job_id: str) -> dict:
        return self.transcoder.get_job_status(job_id)
