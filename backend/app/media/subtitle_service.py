"""
字幕管理服务
- 外挂字幕扫描与关联
- 内嵌字幕提取（ffprobe）
- 字幕上传
- 字幕内容读取
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.media.models import Subtitle
from app.media.repository import MediaRepository

logger = logging.getLogger(__name__)

# 字幕语言映射
SUBTITLE_LANG_MAP: dict[str, tuple[str, str]] = {
    "zh": ("zh", "中文"),
    "chi": ("zh", "中文"),
    "chinese": ("zh", "中文"),
    "zht": ("zh-TW", "繁体中文"),
    "zh-tw": ("zh-TW", "繁体中文"),
    "big5": ("zh-TW", "繁体中文"),
    "en": ("en", "English"),
    "eng": ("en", "English"),
    "english": ("en", "English"),
    "ja": ("ja", "日本語"),
    "jpn": ("ja", "日本語"),
    "japanese": ("ja", "日本語"),
    "ko": ("ko", "한국어"),
    "kor": ("ko", "한국어"),
    "korean": ("ko", "한국어"),
    "fr": ("fr", "Français"),
    "fre": ("fr", "Français"),
    "de": ("de", "Deutsch"),
    "ger": ("de", "Deutsch"),
    "es": ("es", "Español"),
    "spa": ("es", "Español"),
    "pt": ("pt", "Português"),
    "por": ("pt", "Português"),
    "ru": ("ru", "Русский"),
    "rus": ("ru", "Русский"),
    "th": ("th", "ไทย"),
    "tha": ("th", "ไทย"),
    "vi": ("vi", "Tiếng Việt"),
    "vie": ("vi", "Tiếng Việt"),
}

# 支持的字幕文件扩展名
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".vtt", ".lrc"}


class SubtitleService:
    def __init__(self, repo: MediaRepository):
        self.repo = repo
        self.settings = get_settings()

    # ── 扫描外挂字幕 ──
    async def scan_external_subtitles(self, media_item_id: int) -> list[Subtitle]:
        """扫描媒体条目关联的外挂字幕文件"""
        item = await self.repo.get_item_by_id(media_item_id)
        if not item:
            return []

        # 对于电视剧，扫描每一集
        if item.media_type in ("tv", "anime"):
            return await self._scan_tv_subtitles(item)

        # 电影：扫描同目录下的字幕文件
        return await self._scan_movie_subtitles(item)

    async def _scan_movie_subtitles(self, item) -> list[Subtitle]:
        """扫描电影的外挂字幕"""
        file_path = Path(item.file_path)
        if not file_path.exists():
            return []

        video_stem = file_path.stem
        video_dir = file_path.parent

        found_subs: list[Subtitle] = []

        # 清除旧的外挂字幕记录
        existing_subs = await self.repo.get_subtitles_by_item(item.id)
        external_subs = [s for s in existing_subs if s.source == "external"]

        # 搜索同目录下的字幕文件
        for sub_file in video_dir.iterdir():
            if not sub_file.is_file():
                continue
            if sub_file.suffix.lower() not in SUBTITLE_EXTENSIONS:
                continue

            # 检查是否匹配视频文件名
            sub_stem = sub_file.stem
            if not sub_stem.startswith(video_stem):
                continue

            # 解析语言标签
            # 格式: video.zh.srt, video.chi.ass, video.en.srt, video.srt (默认中文)
            lang_code, lang_name = self._parse_subtitle_language(sub_stem, video_stem)

            # 检查是否已存在
            existing = next(
                (s for s in external_subs if s.path == str(sub_file)), None
            )
            if existing:
                found_subs.append(existing)
                continue

            # 创建新字幕记录
            sub = await self.repo.create_subtitle(
                media_item_id=item.id,
                language=lang_code,
                language_name=lang_name,
                path=str(sub_file),
                source="external",
            )
            found_subs.append(sub)

        return found_subs

    async def _scan_tv_subtitles(self, item) -> list[Subtitle]:
        """扫描电视剧/动漫的外挂字幕"""
        found_subs: list[Subtitle] = []

        episodes = await self.repo.get_episodes_by_item(item.id)
        for ep in episodes:
            if not ep.file_path:
                continue
            ep_path = Path(ep.file_path)
            if not ep_path.exists():
                continue

            video_stem = ep_path.stem
            video_dir = ep_path.parent

            for sub_file in video_dir.iterdir():
                if not sub_file.is_file():
                    continue
                if sub_file.suffix.lower() not in SUBTITLE_EXTENSIONS:
                    continue

                sub_stem = sub_file.stem
                if not sub_stem.startswith(video_stem):
                    continue

                lang_code, lang_name = self._parse_subtitle_language(sub_stem, video_stem)

                # 检查是否已存在
                existing_subs = await self.repo.get_subtitles_by_item(item.id)
                already = next(
                    (s for s in existing_subs if s.path == str(sub_file)), None
                )
                if already:
                    found_subs.append(already)
                    continue

                sub = await self.repo.create_subtitle(
                    media_item_id=item.id,
                    language=lang_code,
                    language_name=lang_name,
                    path=str(sub_file),
                    source="external",
                    episode_id=ep.id,
                )
                found_subs.append(sub)

        return found_subs

    def _parse_subtitle_language(self, sub_stem: str, video_stem: str) -> tuple[str, str]:
        """
        从字幕文件名解析语言代码。
        例如: "Movie.2024.zh.srt" -> ("zh", "中文")
              "Movie.2024.en.ass" -> ("en", "English")
              "Movie.2024.srt"    -> ("zh", "中文")  # 默认中文
        """
        # 去掉视频文件名前缀
        remainder = sub_stem[len(video_stem):].lstrip(".")

        if not remainder:
            # 无语言标签，默认中文
            return ("zh", "中文")

        # 按 . 分割，取第一个非空部分作为语言标签
        parts = remainder.split(".")
        if parts:
            lang_tag = parts[0].lower()
            if lang_tag in SUBTITLE_LANG_MAP:
                return SUBTITLE_LANG_MAP[lang_tag]

        # 无法识别，默认中文
        return ("zh", "中文")

    # ── 内嵌字幕提取 ──
    async def extract_embedded_subtitles(self, media_item_id: int) -> list[dict]:
        """使用 ffprobe 检测内嵌字幕流"""
        item = await self.repo.get_item_by_id(media_item_id)
        if not item:
            return []

        # 收集需要检测的文件路径
        file_paths = []
        if item.media_type in ("tv", "anime"):
            episodes = await self.repo.get_episodes_by_item(item.id)
            for ep in episodes:
                if ep.file_path:
                    file_paths.append(ep.file_path)
        else:
            if item.file_path:
                file_paths.append(item.file_path)

        results = []
        for fpath in file_paths:
            streams = await self._probe_subtitle_streams(fpath)
            for stream in streams:
                results.append({
                    "file_path": fpath,
                    **stream,
                })

        return results

    async def _probe_subtitle_streams(self, file_path: str) -> list[dict]:
        """使用 ffprobe 检测文件中的字幕流"""
        try:
            cmd = [
                self.settings.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "s",  # 只取字幕流
                file_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode != 0:
                return []

            data = json.loads(stdout.decode("utf-8", errors="replace"))
            streams = data.get("streams", [])

            result = []
            for stream in streams:
                index = stream.get("index", 0)
                codec = stream.get("codec_name", "unknown")
                lang = stream.get("tags", {}).get("language", "und")
                title = stream.get("tags", {}).get("title", "")

                # 映射语言代码
                lang_lower = lang.lower()
                lang_code, lang_name = SUBTITLE_LANG_MAP.get(
                    lang_lower, (lang_lower, title or lang)
                )

                result.append({
                    "stream_index": index,
                    "codec": codec,
                    "language": lang_code,
                    "language_name": lang_name,
                    "title": title,
                    "source": "embedded",
                })

            return result
        except Exception as e:
            logger.warning(f"ffprobe subtitle detection failed for {file_path}: {e}")
            return []

    # ── 提取内嵌字幕到文件 ──
    async def extract_subtitle_to_file(
        self, file_path: str, stream_index: int, output_dir: str | None = None
    ) -> str | None:
        """将内嵌字幕提取为 SRT 文件"""
        try:
            video_path = Path(file_path)
            if not video_path.exists():
                return None

            if output_dir:
                out_dir = Path(output_dir)
            else:
                out_dir = video_path.parent

            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"{video_path.stem}.sub{stream_index}.srt"

            cmd = [
                self.settings.ffmpeg_path,
                "-i", str(video_path),
                "-map", f"0:{stream_index}",
                "-f", "srt",
                str(output_path),
                "-y",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            if proc.returncode != 0:
                logger.warning(f"Subtitle extraction failed: {stderr.decode()[:200]}")
                return None

            return str(output_path)
        except Exception as e:
            logger.warning(f"Subtitle extraction error: {e}")
            return None

    # ── 字幕上传 ──
    async def upload_subtitle(
        self, media_item_id: int, filename: str, content: bytes,
        language: str = "zh", episode_id: int | None = None,
    ) -> Subtitle:
        """上传字幕文件"""
        item = await self.repo.get_item_by_id(media_item_id)
        if not item:
            raise ValueError(f"MediaItem {media_item_id} not found")

        # 确定保存路径：与视频同目录
        if item.media_type in ("tv", "anime") and episode_id:
            ep = await self.repo.get_episode_by_id(episode_id)
            if ep and ep.file_path:
                save_dir = Path(ep.file_path).parent
            else:
                save_dir = Path(item.file_path).parent if item.file_path else Path(self.settings.data_dir) / "subtitles"
        else:
            if item.file_path:
                save_dir = Path(item.file_path).parent
            else:
                save_dir = Path(self.settings.data_dir) / "subtitles"

        save_dir.mkdir(parents=True, exist_ok=True)

        # 构建字幕文件名
        video_stem = ""
        if item.media_type in ("tv", "anime") and episode_id:
            ep = await self.repo.get_episode_by_id(episode_id)
            if ep and ep.file_path:
                video_stem = Path(ep.file_path).stem
        if not video_stem and item.file_path:
            video_stem = Path(item.file_path).stem

        if video_stem:
            sub_filename = f"{video_stem}.{language}{Path(filename).suffix}"
        else:
            sub_filename = filename

        sub_path = save_dir / sub_filename
        sub_path.write_bytes(content)

        # 映射语言名称
        _, lang_name = SUBTITLE_LANG_MAP.get(language, (language, language))

        # 创建数据库记录
        sub = await self.repo.create_subtitle(
            media_item_id=media_item_id,
            language=language,
            language_name=lang_name,
            path=str(sub_path),
            source="external",
            episode_id=episode_id,
        )

        return sub

    # ── 读取字幕内容 ──
    async def read_subtitle_content(self, subtitle_id: int) -> str | None:
        """读取字幕文件内容"""
        subs = await self.repo.get_subtitles_by_item(0)  # 需要单独获取
        # 直接查
        from sqlalchemy import select
        from app.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                select(Subtitle).where(Subtitle.id == subtitle_id)
            )
            sub = result.scalar_one_or_none()
            if not sub or not sub.path:
                return None

            path = Path(sub.path)
            if not path.exists():
                return None

            try:
                # 尝试多种编码
                for encoding in ("utf-8", "gbk", "gb2312", "big5", "utf-16"):
                    try:
                        return path.read_text(encoding=encoding)
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                # 二进制回退
                return path.read_bytes().decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning(f"Failed to read subtitle {sub.path}: {e}")
                return None

    # ── 删除字幕 ──
    async def delete_subtitle(self, subtitle_id: int, delete_file: bool = False) -> bool:
        """删除字幕记录，可选删除文件"""
        from sqlalchemy import select
        from app.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                select(Subtitle).where(Subtitle.id == subtitle_id)
            )
            sub = result.scalar_one_or_none()
            if not sub:
                return False

            if delete_file and sub.path:
                try:
                    Path(sub.path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to delete subtitle file {sub.path}: {e}")

            await session.delete(sub)
            await session.commit()
            return True
