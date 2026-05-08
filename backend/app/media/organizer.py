"""
文件整理器
下载完成后，将文件从下载目录移动/重命名到媒体库规范目录结构中。
支持电影和剧集的标准命名和目录组织。

自定义重命名格式支持 Jinja2 模板语法。
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Template

from app.media.scanner import (
    VIDEO_EXTENSIONS,
    SUBTITLE_EXTENSIONS,
    parse_media_name,
    parse_season_episode,
    guess_resolution,
)

logger = logging.getLogger(__name__)

# ── 命名模板 ──
# 电影: {title} ({year})/{title} ({year}) - {resolution}.{ext}
# 剧集: {title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d} - {resolution}.{ext}


class OrganizeResult:
    """整理结果"""

    def __init__(self):
        self.organized: int = 0       # 成功整理的文件数
        self.skipped: int = 0         # 跳过的文件数（无需整理）
        self.errors: list[str] = []   # 错误信息

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class FileOrganizer:
    """文件整理器：将下载完成的文件整理到媒体库目录"""

    # 默认 Jinja2 重命名模板
    DEFAULT_MOVIE_TEMPLATE = "{{title}}{% if year %} ({{year}}){% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if resolution %} - {{resolution}}{% endif %}{{fileExt}}"

    DEFAULT_TV_TEMPLATE = "{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{% if episode %} - 第 {{episode}} 集{% endif %}{{fileExt}}"

    DEFAULT_ANIME_TEMPLATE = "{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/[{{season_episode}}] {{title}}{{fileExt}}"

    def __init__(
        self,
        movies_dir: str | None = None,
        tv_dir: str | None = None,
        anime_dir: str | None = None,
        download_dir: str | None = None,
        rename_templates: dict[str, str] | None = None,
    ):
        self.movies_dir = movies_dir or ""
        self.tv_dir = tv_dir or ""
        self.anime_dir = anime_dir or ""
        self.download_dir = download_dir or ""
        # 自定义重命名模板 {media_type: template_str}
        self._rename_templates: dict[str, str] = rename_templates or {}

    def set_rename_template(self, media_type: str, template: str):
        """动态设置重命名模板"""
        self._rename_templates[media_type] = template

    @classmethod
    async def from_settings(cls, db_session) -> "FileOrganizer":
        """从数据库设置创建 FileOrganizer 实例"""
        from app.config import get_settings
        from app.system.settings_service import SettingsService

        settings = get_settings()

        # 获取媒体库目录
        movies_dir = ""
        tv_dir = ""
        anime_dir = ""

        try:
            service = SettingsService(db_session)
            # 从设置获取媒体库路径（如果有的话）
            # 目前使用 config 中的 media_dirs
        except Exception:
            pass

        # 获取重命名模板
        rename_templates = {}
        try:
            service = SettingsService(db_session)
            rename_templates["movie"] = await service.get("organize.movie_rename_format") or cls.DEFAULT_MOVIE_TEMPLATE
            rename_templates["tv"] = await service.get("organize.tv_rename_format") or cls.DEFAULT_TV_TEMPLATE
            rename_templates["anime"] = await service.get("organize.anime_rename_format") or cls.DEFAULT_ANIME_TEMPLATE
        except Exception:
            # 使用默认值
            pass

        return cls(
            movies_dir=movies_dir,
            tv_dir=tv_dir,
            anime_dir=anime_dir,
            download_dir=str(settings.download_dir),
            rename_templates=rename_templates,
        )

    def organize_downloaded_file(
        self,
        src_path: str,
        media_type: str = "movie",
        title: str | None = None,
        year: int | None = None,
        season: int | None = None,
        episode: int | None = None,
    ) -> OrganizeResult:
        """
        整理单个已下载文件到媒体库目录

        Args:
            src_path: 源文件路径
            media_type: movie / tv / anime
            title: 媒体标题（如果不提供，从文件名推断）
            year: 年份
            season: 季号（剧集）
            episode: 集号（剧集）

        Returns:
            OrganizeResult
        """
        result = OrganizeResult()
        src = Path(src_path)

        if not src.exists():
            result.errors.append(f"源文件不存在: {src_path}")
            return result

        if not src.is_file():
            result.errors.append(f"路径不是文件: {src_path}")
            return result

        # 检查是否为视频文件
        if src.suffix.lower() not in VIDEO_EXTENSIONS:
            result.skipped += 1
            return result

        # 推断媒体信息
        if not title:
            title = parse_media_name(src.name)

        if media_type in ("tv", "anime") and season is None:
            parsed_season, parsed_episode, _ = parse_season_episode(src.name)
            season = parsed_season or 1
            episode = episode or parsed_episode

        # 确定目标目录
        dest_dir = self._get_target_dir(media_type, title, year, season)
        if not dest_dir:
            result.errors.append(f"未配置 {media_type} 类型的媒体目录")
            return result

        # 确定目标文件名（使用 Jinja2 模板）
        dest_filename = self._build_target_filename(
            title=title,
            year=year,
            season=season,
            episode=episode,
            resolution=guess_resolution(src.name),
            ext=src.suffix,
            media_type=media_type,
        )

        dest_path = dest_dir / dest_filename

        # 如果源和目标相同，跳过
        try:
            if src.resolve() == dest_path.resolve():
                result.skipped += 1
                return result
        except OSError:
            pass

        # 如果目标已存在，跳过
        if dest_path.exists():
            result.skipped += 1
            logger.info(f"目标文件已存在，跳过: {dest_path}")
            return result

        # 创建目标目录
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 移动文件
        try:
            shutil.move(str(src), str(dest_path))
            logger.info(f"整理文件: {src} -> {dest_path}")
            result.organized += 1
        except Exception as e:
            result.errors.append(f"移动文件失败 {src} -> {dest_path}: {e}")
            return result

        # 同时移动关联的字幕文件
        self._move_associated_subtitles(src, dest_path, result)

        return result

    def organize_download_dir(
        self,
        download_path: str | None = None,
        media_type: str = "auto",
    ) -> OrganizeResult:
        """
        扫描下载目录并整理所有视频文件

        Args:
            download_path: 下载目录路径（不提供则使用配置的下载目录）
            media_type: auto / movie / tv / anime（auto 会根据文件名推断）

        Returns:
            OrganizeResult
        """
        result = OrganizeResult()
        scan_dir = Path(download_path or self.download_dir)

        if not scan_dir.exists():
            result.errors.append(f"下载目录不存在: {scan_dir}")
            return result

        # 递归查找视频文件
        video_files = []
        try:
            for entry in scan_dir.rglob("*"):
                if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
                    # 跳过 sample/trailer
                    if any(kw in entry.name.lower() for kw in ["sample", "trailer", "preview"]):
                        continue
                    video_files.append(entry)
        except PermissionError:
            result.errors.append(f"无权限扫描: {scan_dir}")

        if not video_files:
            result.skipped = 0
            return result

        for vf in video_files:
            try:
                # 推断媒体类型
                inferred_type = media_type
                if media_type == "auto":
                    inferred_type = self._infer_media_type(vf)

                file_result = self.organize_downloaded_file(
                    src_path=str(vf),
                    media_type=inferred_type,
                )
                result.organized += file_result.organized
                result.skipped += file_result.skipped
                result.errors.extend(file_result.errors)

            except Exception as e:
                result.errors.append(f"整理文件 {vf} 失败: {e}")

        return result

    def organize_completed_task(
        self,
        save_path: str | None,
        torrent_name: str | None,
    ) -> OrganizeResult:
        """
        处理下载完成的任务：整理文件到媒体库

        Args:
            save_path: 下载保存路径
            torrent_name: 种子名称

        Returns:
            OrganizeResult
        """
        result = OrganizeResult()

        if not save_path:
            result.errors.append("下载任务无保存路径")
            return result

        save_dir = Path(save_path)

        # 如果 save_path 是文件直接整理
        if save_dir.is_file() and save_dir.suffix.lower() in VIDEO_EXTENSIONS:
            return self.organize_downloaded_file(
                src_path=str(save_dir),
                media_type="auto",
                title=parse_media_name(torrent_name) if torrent_name else None,
            )

        # 如果是目录，扫描其中的视频文件
        if save_dir.is_dir():
            return self.organize_download_dir(
                download_path=str(save_dir),
                media_type="auto",
            )

        # 尝试从下载目录查找
        if self.download_dir:
            download_root = Path(self.download_dir)
            # 尝试根据 torrent_name 在下载目录中查找
            if torrent_name:
                candidate = download_root / torrent_name
                if candidate.exists():
                    return self.organize_download_dir(
                        download_path=str(candidate),
                        media_type="auto",
                    )

            # 扫描整个下载目录
            return self.organize_download_dir(media_type="auto")

        result.errors.append(f"无法定位下载文件: {save_path}")
        return result

    def _get_target_dir(
        self,
        media_type: str,
        title: str,
        year: int | None = None,
        season: int | None = None,
    ) -> Path | None:
        """确定目标目录路径"""
        if media_type == "movie":
            base = self.movies_dir
        elif media_type == "tv":
            base = self.tv_dir
        elif media_type == "anime":
            base = self.anime_dir
        else:
            base = self.movies_dir

        if not base:
            return None

        if media_type == "movie":
            # 电影: Movies/Title (Year)/
            dir_name = f"{title}"
            if year:
                dir_name = f"{title} ({year})"
            return Path(base) / dir_name
        else:
            # 剧集: TV/Title/Season NN/
            show_dir = Path(base) / title
            if season is not None:
                return show_dir / f"Season {season:02d}"
            return show_dir

    def _build_target_filename(
        self,
        title: str,
        year: int | None = None,
        season: int | None = None,
        episode: int | None = None,
        resolution: str | None = None,
        ext: str = ".mkv",
        media_type: str = "movie",
    ) -> str:
        """
        构建目标文件名（使用 Jinja2 模板渲染）

        可用变量:
        - title: 标题
        - year: 年份
        - season: 季号 (1, 2, ...)
        - episode: 集号 (1, 2, ...)
        - season_episode: 季集格式 (S01E01)
        - resolution: 分辨率 (1080p, 4K, ...)
        - part: 分部序号 (蓝光分集等)
        - fileExt: 文件扩展名 (含点号)
        """
        # 确保 year 是字符串用于模板渲染
        year_str = str(year) if year else ""

        # 季集格式化
        season_episode_str = ""
        if season is not None and episode is not None:
            season_episode_str = f"S{season:02d}E{episode:02d}"

        # 获取模板字符串
        template_str = self._get_rename_template(media_type)

        try:
            template = Template(template_str)
            filename = template.render(
                title=title or "",
                year=year_str,
                season=season or 1,
                episode=episode or 1,
                season_episode=season_episode_str,
                resolution=resolution or "",
                part="",
                fileExt=ext,
            )
            # 清理路径中的多余斜杠和空格
            filename = filename.strip()
            # 确保文件名不为空
            if not filename:
                filename = f"{title}{ext}"
            return filename
        except Exception as e:
            logger.warning(f"Jinja2 模板渲染失败，使用默认命名: {e}")
            # 回退到默认命名
            return self._build_default_filename(
                title, year, season, episode, resolution, ext
            )

    def _build_default_filename(
        self,
        title: str,
        year: int | None = None,
        season: int | None = None,
        episode: int | None = None,
        resolution: str | None = None,
        ext: str = ".mkv",
    ) -> str:
        """构建默认文件名（模板渲染失败时的回退）"""
        if season is not None and episode is not None:
            # 剧集: Title - S01E01 - 1080p.mkv
            name = f"{title} - S{season:02d}E{episode:02d}"
            if resolution:
                name += f" - {resolution}"
        else:
            # 电影: Title (2024) - 1080p.mkv
            name = f"{title}"
            if year:
                name += f" ({year})"
            if resolution:
                name += f" - {resolution}"

        return name + ext

    def _get_rename_template(self, media_type: str) -> str:
        """获取指定媒体类型的重命名模板"""
        # 优先使用实例配置的模板
        if hasattr(self, '_rename_templates') and self._rename_templates:
            template = self._rename_templates.get(media_type)
            if template:
                return template

        # 使用内置默认值
        if media_type == "movie":
            return self.DEFAULT_MOVIE_TEMPLATE
        elif media_type == "tv":
            return self.DEFAULT_TV_TEMPLATE
        elif media_type == "anime":
            return self.DEFAULT_ANIME_TEMPLATE
        else:
            return self.DEFAULT_MOVIE_TEMPLATE

    def _move_associated_subtitles(
        self,
        src_video: Path,
        dest_video: Path,
        result: OrganizeResult,
    ):
        """移动与视频文件关联的字幕文件"""
        src_dir = src_video.parent
        src_stem = src_video.stem
        dest_dir = dest_video.parent
        dest_stem = dest_video.stem

        if not src_dir.exists():
            return

        try:
            for f in src_dir.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in SUBTITLE_EXTENSIONS:
                    continue
                # 字幕文件名以视频文件名为前缀
                if f.stem.startswith(src_stem) or src_stem.startswith(f.stem):
                    # 保留语言后缀部分
                    lang_suffix = f.stem[len(src_stem):].strip(".-_ ")
                    new_name = dest_stem
                    if lang_suffix:
                        new_name += f".{lang_suffix}"
                    new_name += f.suffix
                    dest_sub = dest_dir / new_name
                    try:
                        shutil.move(str(f), str(dest_sub))
                        logger.info(f"移动字幕: {f} -> {dest_sub}")
                    except Exception as e:
                        result.errors.append(f"移动字幕失败 {f}: {e}")
        except PermissionError:
            logger.warning(f"无法扫描字幕目录: {src_dir}")

    def _infer_media_type(self, file_path: Path) -> str:
        """从文件路径推断媒体类型"""
        path_str = str(file_path)

        # 路径中包含关键目录名
        path_lower = path_str.lower()
        if "/movie" in path_lower or "\\movie" in path_lower or "/电影" in path_lower:
            return "movie"
        if "/anime" in path_lower or "\\anime" in path_lower or "/动漫" in path_lower or "/番剧" in path_lower:
            return "anime"
        if "/tv" in path_lower or "\\tv" in path_lower or "/剧集" in path_lower or "/电视剧" in path_lower:
            return "tv"

        # 根据文件名中的季集信息判断
        season, episode, _ = parse_season_episode(file_path.name)
        if season is not None and episode is not None:
            return "tv"

        # 默认为电影
        return "movie"

    def cleanup_empty_dirs(self, root_path: str | None = None):
        """清理空目录（下载目录中整理后残留的空文件夹）"""
        scan_dir = Path(root_path or self.download_dir)
        if not scan_dir.exists():
            return

        # 从最深层开始删除空目录
        removed = 0
        for dirpath, dirnames, filenames in os.walk(str(scan_dir), topdown=False):
            dir = Path(dirpath)
            if dir == scan_dir:
                continue
            try:
                if dir.exists() and not any(dir.iterdir()):
                    dir.rmdir()
                    removed += 1
            except Exception:
                pass

        if removed > 0:
            logger.info(f"清理了 {removed} 个空目录")
