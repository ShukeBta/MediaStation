"""
媒体文件扫描器
递归扫描媒体目录，识别视频文件，提取元数据。
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.media.models import MediaItem

logger = logging.getLogger(__name__)

# 支持的视频格式
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".ts", ".rmvb", ".rm", ".m4v", ".mpg", ".mpeg", ".3gp",
}

# 字幕格式
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".sup"}

# NFO元数据文件格式
NFO_EXTENSIONS = {".nfo"}

# 海报图片格式和命名
POSTER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
POSTER_NAMES = ["poster", "cover", "folder", "thumb", "fanart", "backdrop", "movie"]

# TMDb/IMDB ID正则
TMDB_ID_PATTERN = re.compile(r"themoviedb\.org/movie/(\d+)", re.IGNORECASE)
TMDB_TV_PATTERN = re.compile(r"themoviedb\.org/tv/(\d+)", re.IGNORECASE)
IMDB_ID_PATTERN = re.compile(r"imdb\.com/title/(tt\d+)", re.IGNORECASE)
TMDB_ID_PATTERN_SIMPLE = re.compile(r"/movie/(\d+)", re.IGNORECASE)
TMDB_TV_PATTERN_SIMPLE = re.compile(r"/tv/(\d+)", re.IGNORECASE)

# 字幕语言映射
SUBTITLE_LANG_MAP = {
    "zh": "中文",
    "zh-CN": "简体中文",
    "zh-TW": "繁体中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}

# 剧集命名模式 - 增强版
SEASON_EPISODE_PATTERNS = [
    # S01E01, S01.E01, S01 E01 (标准格式)
    re.compile(r"[Ss](\d{1,2})\s*[.\s]?[Ee](\d{1,4})", re.IGNORECASE),
    # 1x01 (1x01格式)
    re.compile(r"(\d{1,2})[xX](\d{1,4})"),
    # EP01, ep01, Ep01 (EP格式)
    re.compile(r"[Ee][Pp](\d{1,4})", re.IGNORECASE),
    # 第01集, 第1集 (中文格式)
    re.compile(r"第\s*(\d{1,4})\s*集"),
    # E01E02, E01-E02, E01.E02 (多集连播)
    re.compile(r"[Ee](\d{1,4})[-._]?[Ee](\d{1,4})", re.IGNORECASE),
    # S01E01-E02, S01E01E02 (季内多集)
    re.compile(r"[Ss](\d{1,2})[Ee](\d{1,4})(?:[-._]?[Ee](\d{1,4}))*", re.IGNORECASE),
    # 01.E02, 01-02 (无季号的多集)
    re.compile(r"(\d{1,2})[.\-][Ee]?(\d{1,4})(?:[.\-][Ee]?(\d{1,4}))*", re.IGNORECASE),
    # 四位纯数字 01-9999（需结合目录名判断）
    re.compile(r"[.\s](\d{2,4})[.\s]"),
    # 01x02x03 (多集x格式)
    re.compile(r"(\d{1,2})[xX](\d{1,4})(?:[xX](\d{1,4}))*"),
]

# Anime 动漫剧集命名模式
ANIME_EPISODE_PATTERNS = [
    # 第01话, 第1话 (日语动漫常用)
    re.compile(r"第\s*(\d{1,4})\s*话"),
    # 第01episode (混合格式)
    re.compile(r"第\s*(\d{1,4})\s*[episode]*", re.IGNORECASE),
    # [01], (01) (方括号/圆括号格式)
    re.compile(r"[\[\(](\d{1,4})[\]\)]"),
    # 01v2, 01a, 01b (版本/片段标识)
    re.compile(r"(\d{1,4})[vVaAbBcC]"),
    # 第01卷 第01话 (OVA/BD收藏)
    re.compile(r"\d{1,2}[\-话集]\s*(\d{1,4})", re.IGNORECASE),
]

# Season文件夹识别模式 - 增强版
SEASON_FOLDER_PATTERNS = [
    # Season X, Season XX, Season 01-05 (范围)
    re.compile(r"[Ss]eason\s*(\d{1,2})(?:\s*[-~]\s*(\d{1,2}))?", re.IGNORECASE),
    # S01, S1, S01-S05 (范围)
    re.compile(r"^[Ss](\d{1,2})(?:\s*[-~]\s*(\d{1,2}))?$"),
    # 第X季, 第1-3季 (范围)
    re.compile(r"第\s*(\d{1,2})\s*季(?:\s*[-~]\s*(\d{1,2}))?", re.IGNORECASE),
    # 季 X, 季01
    re.compile(r"^季\s*(\d{1,2})$", re.IGNORECASE),
    # Season 1 Pack, Complete Season (关键字匹配)
    re.compile(r"[Ss]eason\s*\d+", re.IGNORECASE),
    # 第X辑 (国产剧/综艺)
    re.compile(r"第\s*(\d{1,2})\s*辑", re.IGNORECASE),
]

# 多季合集标识 (用于识别多季文件夹)
MULTI_SEASON_INDICATORS = [
    "Complete", "All Seasons", "全季", "全集",
    "Season 1", "S01", "Season 01",  # 完整季标识（非范围）
]

# Season 名称 -> 季号映射表 (常见别名)
SEASON_ALIAS_MAP = {
    "season 1": 1, "season one": 1, "first season": 1,
    "season 2": 2, "season two": 2, "second season": 2,
    "season 3": 3, "season three": 3, "third season": 3,
    "s1": 1, "s2": 2, "s3": 3, "s4": 4, "s5": 5,
    "final": None,  # 需要从目录结构推断
}

# 分辨率模式（预编译正则，提升扫描性能）
_RES_PATTERNS = [
    (re.compile(r"2160[pP]|4[Kk]", re.IGNORECASE), "4K"),
    (re.compile(r"1080[pi]", re.IGNORECASE), "1080p"),
    (re.compile(r"1080[iI]", re.IGNORECASE), "1080i"),
    (re.compile(r"720[pP]", re.IGNORECASE), "720p"),
    (re.compile(r"480[pP]", re.IGNORECASE), "480p"),
    (re.compile(r"\bSD\b", re.IGNORECASE), "SD"),
]


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_subtitle_file(path: Path) -> bool:
    return path.suffix.lower() in SUBTITLE_EXTENSIONS


def is_nfo_file(path: Path) -> bool:
    return path.suffix.lower() in NFO_EXTENSIONS


def is_poster_file(path: Path) -> bool:
    """判断文件是否是海报图片"""
    return path.suffix.lower() in POSTER_EXTENSIONS and path.stem.lower() in POSTER_NAMES


def find_poster(video_path: Path) -> Path | None:
    """
    查找视频关联的优先级最高的海报图片。
    Issue #32 修复：直接复用 find_all_posters 取第一个结果，消除重复磁盘 I/O。
    """
    posters = find_all_posters(video_path)
    return posters[0] if posters else None


def find_all_posters(video_path: Path) -> list[Path]:
    """
    查找视频关联的所有海报图片

    返回所有找到的海报图片，按优先级排序
    """
    posters = []
    parent = video_path.parent
    grandparent = parent.parent if parent.parent != parent else None
    video_stem = video_path.stem

    # 同名图片
    for ext in POSTER_EXTENSIONS:
        poster_path = parent / f"{video_stem}{ext}"
        if poster_path.exists():
            posters.append(poster_path)

    # 标准命名
    for name in POSTER_NAMES:
        for ext in POSTER_EXTENSIONS:
            poster_path = parent / f"{name}{ext}"
            if poster_path.exists() and poster_path not in posters:
                posters.append(poster_path)

    # 父目录查找
    if grandparent:
        for name in POSTER_NAMES:
            for ext in POSTER_EXTENSIONS:
                poster_path = grandparent / f"{name}{ext}"
                if poster_path.exists() and poster_path not in posters:
                    posters.append(poster_path)

    return posters


def parse_nfo_file(nfo_path: Path) -> dict | None:
    """
    解析NFO文件，提取元数据
    - 电影NFO: TMDb/IMDB ID, 标题
    - 剧集NFO: TMDb ID, 剧集标题, plot, 播出日期, 季号, 集号
    返回格式: {"tmdb_id": int, "imdb_id": str, "title": str, "plot": str, "aired": str, "season": int, "episode": int} 或 None
    """
    try:
        content = nfo_path.read_text(encoding="utf-8", errors="ignore")
        result = {}

        # 检查是否是XML格式的episode NFO
        if content.strip().startswith("<?xml") or "<episodedetails>" in content:
            # 使用XML解析
            try:
                import xml.etree.ElementTree as ET
                # 移除CDATA标记
                content_clean = re.sub(r"<!\[CDATA\[|\]\]>", "", content)
                root = ET.fromstring(content_clean)

                # 提取TMDB ID
                for uid in root.findall(".//uniqueid"):
                    if uid.get("type") == "tmdb" or uid.get("default") == "true":
                        tmdb_text = uid.text
                        if tmdb_text:
                            result["tmdb_id"] = int(tmdb_text)
                            result["media_type"] = "tv"
                            break
                if not result.get("tmdb_id"):
                    tmdb_elem = root.find(".//tmdbid")
                    if tmdb_elem is not None and tmdb_elem.text:
                        result["tmdb_id"] = int(tmdb_elem.text)
                        result["media_type"] = "tv"

                # 提取剧集标题
                title_elem = root.find(".//title")
                if title_elem is not None and title_elem.text:
                    result["title"] = title_elem.text.strip()

                # 提取plot
                plot_elem = root.find(".//plot")
                if plot_elem is not None and plot_elem.text:
                    result["plot"] = plot_elem.text.strip()

                # 提取outline
                outline_elem = root.find(".//outline")
                if outline_elem is not None and outline_elem.text and "plot" not in result:
                    result["plot"] = outline_elem.text.strip()

                # 提取播出日期
                aired_elem = root.find(".//aired")
                if aired_elem is not None and aired_elem.text:
                    result["aired"] = aired_elem.text.strip()

                # 提取季号
                season_elem = root.find(".//season")
                if season_elem is not None and season_elem.text:
                    try:
                        result["season"] = int(season_elem.text)
                    except ValueError:
                        pass

                # 提取集号
                episode_elem = root.find(".//episode")
                if episode_elem is not None and episode_elem.text:
                    try:
                        result["episode"] = int(episode_elem.text)
                    except ValueError:
                        pass

                return result if result else None
            except Exception as e:
                logger.debug(f"Failed to parse XML NFO {nfo_path}: {e}")
                # 回退到正则解析

        # 尝试提取TMDb ID (适用于非XML格式或XML解析失败)
        for pattern in [TMDB_ID_PATTERN, TMDB_ID_PATTERN_SIMPLE]:
            match = pattern.search(content)
            if match:
                result["tmdb_id"] = int(match.group(1))
                result["media_type"] = "movie"
                break

        if not result.get("tmdb_id"):
            for pattern in [TMDB_TV_PATTERN, TMDB_TV_PATTERN_SIMPLE]:
                match = pattern.search(content)
                if match:
                    result["tmdb_id"] = int(match.group(1))
                    result["media_type"] = "tv"
                    break

        # 尝试提取IMDB ID
        match = IMDB_ID_PATTERN.search(content)
        if match:
            result["imdb_id"] = match.group(1)

        # 尝试提取标题（第一个非空行通常是标题）
        for line in content.split("\n")[:20]:
            line = line.strip()
            if line and not line.startswith("http") and len(line) > 1:
                # 过滤掉明显不是标题的文本
                if not any(kw in line.lower() for kw in ["<", "tv show", "movie", "nfo"]):
                    result["title"] = line
                    break

        return result if result else None
    except Exception as e:
        logger.debug(f"Failed to parse NFO {nfo_path}: {e}")
        return None


def find_nfo_file(video_path: Path) -> Path | None:
    """查找与视频关联的NFO文件（优先使用剧集NFO）"""
    parent = video_path.parent

    # 查找同名的.nfo文件（剧集NFO）
    nfo_path = parent / f"{video_path.stem}.nfo"
    if nfo_path.exists():
        return nfo_path

    # 查找tvshow.nfo（通常在剧集根目录）
    tvshow_path = parent / "tvshow.nfo"
    if tvshow_path.exists():
        return tvshow_path

    # 查找movie.nfo
    movie_path = parent / "movie.nfo"
    if movie_path.exists():
        return movie_path

    return None


def find_show_nfo(video_path: Path) -> Path | None:
    """查找节目标NFO文件（tvshow.nfo）"""
    parent = video_path.parent

    # 查找tvshow.nfo
    tvshow_path = parent / "tvshow.nfo"
    if tvshow_path.exists():
        return tvshow_path

    # 向上查找一级目录
    grandparent = parent.parent
    if grandparent != parent:
        tvshow_path = grandparent / "tvshow.nfo"
        if tvshow_path.exists():
            return tvshow_path

    return None


def guess_resolution(filename: str) -> str | None:
    for pattern, res in _RES_PATTERNS:
        if pattern.search(filename):
            return res
    return None


def guess_video_codec(filename: str) -> str | None:
    fn = filename.lower()
    if "hevc" in fn or "h265" in fn or "x265" in fn:
        return "hevc"
    if "h264" in fn or "x264" in fn or "avc" in fn:
        return "h264"
    if "av1" in fn:
        return "av1"
    return None


def guess_audio_codec(filename: str) -> str | None:
    fn = filename.lower()
    if "dts" in fn:
        return "dts"
    if "truehd" in fn:
        return "truehd"
    if "flac" in fn:
        return "flac"
    if "aac" in fn:
        return "aac"
    if "ac3" in fn or "dd" in fn:
        return "ac3"
    return None


def detect_subtitle_language(filename: str) -> tuple[str, str]:
    """检测字幕语言，返回 (code, name)"""
    fn = filename.lower()
    for code, name in SUBTITLE_LANG_MAP.items():
        if code.lower().replace("-", "") in fn.replace("-", "").replace("_", ""):
            return code, name
    # 默认中英
    if "chi" in fn or "chs" in fn or "简" in fn:
        return "zh-CN", "简体中文"
    if "cht" in fn or "繁" in fn:
        return "zh-TW", "繁体中文"
    if "eng" in fn:
        return "en", "English"
    return "und", "Unknown"


def parse_season_episode(filename: str, include_multi: bool = False) -> tuple[int | None, int | None, list[int] | None]:
    """
    从文件名解析季和集号，返回 (season, episode, extra_episodes)

    Args:
        filename: 文件名
        include_multi: 是否返回多集列表

    Returns:
        (season, episode, extra_episodes) - 如果 include_multi=True
        (season, episode, None) - 如果 include_multi=False
        extra_episodes: 额外的集号列表（用于多集连播文件）
    """
    basename = Path(filename).stem

    # 优先尝试标准模式 (S01E01, 1x01 等)
    for i, pattern in enumerate(SEASON_EPISODE_PATTERNS):
        match = pattern.search(basename)
        if match:
            groups = match.groups()

            # EP01 格式 - 只有集号，没有季号
            if i == 2:  # EP01 pattern index
                season = 1  # 默认第1季
                episodes = [int(groups[0])]
            elif len(groups) >= 2:
                season = int(groups[0])
                episodes = [int(groups[1])]
            else:
                continue

            # 检查是否有额外集号 (多集格式)
            if len(groups) > 2 and groups[2]:
                for g in groups[2:]:
                    if g:
                        episodes.append(int(g))

            # 如果是 x 格式但没有 Sxx，使用 1
            if pattern.pattern.startswith(r"(\d{1,2})[xX]"):
                # 检查是否包含 Sxx 模式
                if not re.search(r"[Ss]\d", basename):
                    season = 1

            return season, episodes[0], episodes if include_multi else None

    # 尝试动漫模式
    for pattern in ANIME_EPISODE_PATTERNS:
        match = pattern.search(basename)
        if match:
            # 动漫通常默认第1季
            return 1, int(match.group(1)), [int(match.group(1))] if include_multi else None

    return None, None, None


def parse_multi_episodes(filename: str) -> list[int]:
    """
    从文件名解析所有集号（用于多集连播文件）
    例如: "S01E01E02E03.mp4" -> [1, 2, 3]
         "01x02x03.mp4" -> [1, 2, 3]
    """
    basename = Path(filename).stem
    episodes = []

    # 01x02x03 格式 - 纯数字x格式
    match = re.match(r"^(\d{1,2})x(\d{1,4})(?:x(\d{1,4}))*(?:\.|$)", basename, re.IGNORECASE)
    if match:
        episodes = [int(match.group(1))]
        for g in match.groups()[1:]:
            if g:
                episodes.append(int(g))
        if len(episodes) > 1:
            return episodes

    # S01E01E02E03 格式 - 直接连接所有集号
    match = re.match(r"^S(\d{1,2})E(\d{1,4})(E\d{1,4})+", basename, re.IGNORECASE)
    if match:
        season = int(match.group(1))
        ep_str = match.group(0)[match.group(0).find('E'):]  # 从第一个E开始
        ep_matches = re.findall(r"E(\d{1,4})", ep_str, re.IGNORECASE)
        if len(ep_matches) > 1:
            return [int(e) for e in ep_matches]

    # S01E01-E02-E03 格式 - 带分隔符
    match = re.match(r"^S(\d{1,2})E(\d{1,4})(?:[-._ ]?E(\d{1,4}))+", basename, re.IGNORECASE)
    if match:
        ep_str = match.group(0)[match.group(0).find('E'):]
        ep_matches = re.findall(r"E(\d{1,4})", ep_str, re.IGNORECASE)
        if len(ep_matches) > 1:
            return [int(e) for e in ep_matches]

    # E01E02E03 格式
    match = re.match(r"^E(\d{1,4})(E\d{1,4})+", basename, re.IGNORECASE)
    if match:
        ep_str = match.group(0)
        ep_matches = re.findall(r"E(\d{1,4})", ep_str, re.IGNORECASE)
        if len(ep_matches) > 1:
            return [int(e) for e in ep_matches]

    # 01-02-03 纯数字格式
    match = re.match(r"^(\d{2,4})(?:[-._ ](\d{2,4}))+", basename)
    if match:
        ep_matches = [match.group(1)] + list(match.groups()[1:])
        if len(ep_matches) > 1:
            return [int(e) for e in ep_matches if e]

    return episodes


def parse_season_folder(folder_name: str) -> int | None:
    """
    从文件夹名解析季号。

    Args:
        folder_name: 文件夹名称

    Returns:
        int: 单一季号
        None: 无法解析

    Note:
        季号范围（如 Season 1-5）只返回起始季号。
        多季合集也返回 None。

    Examples:
        "Season 6" -> 6
        "S01" -> 1
        "Season 1-5" -> 1 (只取起始季号)
        "第3季" -> 3
    """
    name_lower = folder_name.lower().strip()

    # 优先检查范围模式
    # Season 范围模式: "Season 1-5", "S01-S05"
    range_match = re.search(r"[Ss]eason\s*(\d{1,2})\s*[-~]\s*(\d{1,2})", folder_name, re.IGNORECASE)
    if range_match:
        return int(range_match.group(1))  # 返回起始季号

    # S 范围模式: "S01-S05"
    s_range_match = re.search(r"^[Ss](\d{1,2})\s*[-~]\s*(\d{1,2})$", folder_name, re.IGNORECASE)
    if s_range_match:
        return int(s_range_match.group(1))  # 返回起始季号

    # 第X季范围: "第1-3季"
    chinese_range_match = re.search(r"第\s*(\d{1,2})\s*季\s*[-~]\s*(\d{1,2})\s*季?", folder_name, re.IGNORECASE)
    if chinese_range_match:
        return int(chinese_range_match.group(1))  # 返回起始季号

    # 检查是否是多季合集
    for indicator in MULTI_SEASON_INDICATORS:
        if indicator.lower() in name_lower:
            logger.debug(f"[parse_season_folder] Detected multi-season collection: {folder_name}")
            return None

    # 检查别名映射
    for alias, season in SEASON_ALIAS_MAP.items():
        if alias.lower() in name_lower:
            return season  # 可能返回 None

    # 标准季节模式
    for pattern in SEASON_FOLDER_PATTERNS[:4]:
        match = pattern.search(folder_name)
        if match:
            groups = match.groups()
            if groups[0]:
                return int(groups[0])
            if len(groups) > 1 and groups[1]:
                return int(groups[1])

    return None


def is_multi_season_folder(folder_name: str) -> bool:
    """
    判断文件夹是否是包含多季的合集
    注意：带有范围标记的文件夹（如 Season 1-5）不属于多季合集
    """
    name_lower = folder_name.lower().strip()

    # 范围模式不算多季合集
    if re.search(r"\d{1,2}\s*[-~]\s*\d{1,2}", folder_name):
        return False

    # 检查多季指示器
    for indicator in MULTI_SEASON_INDICATORS:
        if indicator.lower() in name_lower:
            return True

    return False


def is_season_folder(name: str) -> bool:
    """判断文件夹名是否是Season格式"""
    return parse_season_folder(name) is not None


def is_multi_episode_file(filename: str) -> bool:
    """
    判断文件是否是包含多集的文件
    例如: "S01E01E02.mp4" -> True
         "S01E01.mp4" -> False
    """
    basename = Path(filename).stem
    episodes = parse_multi_episodes(basename)
    return len(episodes) > 1


def parse_media_name(filename: str) -> str:
    """
    从文件名提取媒体名称（去除季节集号、分辨率、编码等后缀）。
    支持格式：[中文名]英文名 年份 编码信息 发布组
    例如：[御用杀手]Remo Williams The Adventure Begins 1985 Blu ray AVC HD MA 5 1 BTSCHOOL
    """
    name = Path(filename).stem

    # ── 预处理：提取有意义的部分 ──
    # 处理 [中文名]英文名 格式
    chinese_part = ""
    bracket_match = re.search(r"\[([^\]]+)\]", name)
    if bracket_match:
        chinese_part = bracket_match.group(1).strip()
        name = name[bracket_match.end():].strip()

    # ── 移除季集信息 ──
    name = re.sub(r"[Ss]\d{1,2}\s*[.\s]?[Ee]\d{1,4}", "", name)
    name = re.sub(r"\d{1,2}[xX]\d{1,4}", "", name)
    name = re.sub(r"[Ee][Pp]\d{1,4}", "", name)
    name = re.sub(r"第\s*\d{1,4}\s*集", "", name)

    # ── 移除常见后缀标签（逐个处理，支持空格分隔的写法）──
    # 分辨率
    for p in [r"2160p?", r"1080[pi]", r"720p", r"480p", r"\b4K\b", r"\bUHD\b", r"\bHD\b"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 片源
    for p in [r"WEB-?DL", r"Blu[.\- ]?Ray", r"BDRip", r"HDRip", r"HDTV", r"DVDRip", r"REMUX"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 编码
    for p in [r"HEVC", r"H\.?265", r"H\.?264", r"\bAVC\b", r"\bAV1\b", r"DTS", r"AAC", r"FLAC", r"AC3",
              r"TrueHD", r"HDR", r"\bDV\b", r"Dolby", r"Atmos", r"x265", r"x264", r"10bit"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 版本/地区
    for p in [r"PROPER", r"REPACK", r"RERIP", r"INTERNAL", r"FINAL", r"REMASTERED", r"CUSTOM",
              r"\bEUR\b", r"\bSDR\b", r"\bHDR\b", r"\bHQ\b", r"\bCHN\b", r"\bKOR\b"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 发布组（覆盖常见发布组名）
    for p in [r"BTSCHOOL", r"BtsHD", r"Bts", r"CHDBits", r"OurTV", r"PTHome", r"TGx",
              r"SPARKS", r"Flux", r"ADWeb", r"HDWing", r"Ptcool", r"BeiTai",
              r"FRDS", r"HDCTV", r"HDS", r"HDTime", r"HDU", r"HDC", r"MTeam",
              r"Pegasus", r"Hqui", r"Lol", r"Yts", r"Rarbg", r"VXT", r"CM8",
              r"FGT", r"SHORTBRED", r"MixHD", r"FraMeSTOR", r"NiK", r"DiMENSION",
              r"WAF", r"FLOCLIP", r"POD", r"LTT"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 音频信息
    for p in [r"MA(?:\s*\d+\.?\d?)?", r"\bDDP\b", r"\bPCM\b", r"\bLCPM\b"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 末尾附加信息
    for p in [r"Zone\s*\d+", r"READ\/?NFO", r"SAMPLE", r"TRAILER", r"PREVIEW"]:
        name = re.sub(p, "", name, flags=re.IGNORECASE)
    # 音频声道（7.1 5.1 2.0 等）
    name = re.sub(r"\b\d+\.?\d*\s*(?:CH|声道)?", "", name, flags=re.IGNORECASE)

    # 年份（括号内和末尾的 4 位数字）
    name = re.sub(r"\s*\(\d{4}\)\s*", " ", name).strip()
    name = re.sub(r"\s+\d{4}\s*$", " ", name).strip()  # 末尾 4 位数字
    name = re.sub(r"\s+\d{3}\s*$", " ", name).strip()  # 末尾 3 位数字

    # ── 根据中英文混合情况决定返回标题 ──
    # TMDb 对英文搜索更可靠；中文标题会在刮削后从 TMDb 正确获取（language=zh-CN）
    # 因此：混合标题时优先返回英文部分用于搜索
    has_chinese_in_original = bool(re.search(r"[\u4e00-\u9fa5]", Path(filename).stem))
    has_english_in_original = bool(re.search(r"[a-zA-Z]", Path(filename).stem))

    if has_chinese_in_original and has_english_in_original:
        # 混合标题：尝试返回英文部分（TMDb 搜索更可靠）
        # 情况A：括号内是英文，括号外是中文 → 返回括号内容
        # 情况B：括号内是中文，括号外是英文 → 返回括号外的内容
        if bracket_match:
            bracket_content = bracket_match.group(1).strip()
            remaining = name  # 已移除括号后的部分
            bracket_is_chinese = bool(re.search(r"[\u4e00-\u9fa5]", bracket_content))
            bracket_is_english = bool(re.search(r"[a-zA-Z]", bracket_content))
            remaining_is_english = bool(re.search(r"[a-zA-Z]", remaining))

            if not bracket_is_chinese and bracket_is_english:
                # 情况A：[Inception]盗梦空间 → 返回 Inception
                return bracket_content
            if bracket_is_chinese and remaining_is_english:
                # 情况B：[盗梦空间]Inception → 返回 Inception
                english_title = re.sub(r"[\.\-_]+", " ", remaining).strip()
                english_title = re.sub(r"\s+", " ", english_title).strip()
                return english_title
            # 无法判断时，尝试从 remaining 提取英文
            if remaining_is_english:
                english_title = re.sub(r"[\.\-_]+", " ", remaining).strip()
                english_title = re.sub(r"\s+", " ", english_title).strip()
                return english_title

    # 只有中文：返回中文名
    if has_chinese_in_original and not has_english_in_original:
        return "".join(re.findall(r"[\u4e00-\u9fa5，。！？；：""''【】（）、…—～·]+", Path(filename).stem))

    # ── 清理分隔符和空格 ──
    name = re.sub(r"[\.\-_]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(".-_").strip()

    # 英文名：取第一个完整词组（到数字或特殊词为止）
    # 例如 "Remo Williams The Adventure Begins 1985 MA" → "Remo Williams The Adventure Begins"
    if re.search(r"[a-zA-Z]", name):
        # 移除末尾的数字和残留小词
        name = re.sub(r"\s+\d+\s*$", "", name).strip()
        name = re.sub(r"\s+(?:MA|DV|HDR|HD|UHD)$", "", name, flags=re.IGNORECASE).strip()

    return name


def check_scrape_title_safety(original_name: str, scraped_title: str) -> tuple[bool, str]:
    """
    检查刮削标题与原始名称的安全性。
    如果标题差异过大，返回 (False, reason)，防止错误覆盖。
    触发条件（任一满足即告警）：
    1. 中文标题完全不同（公共字符占比 < 30%）
    2. 英文标题的 similarity < 0.3
    3. 原始标题含中文但刮削结果无中文（反之亦然）→ 谨慎处理
    """
    if not original_name or not scraped_title:
        return True, ""

    # 清理标题（保留中文字符，仅移除空白/分隔符/括号）
    orig_clean = re.sub(r'[\s\.\-_\(\)（）\[\]]+', '', original_name.lower())
    scraped_clean = re.sub(r'[\s\.\-_\(\)（）\[\]]+', '', scraped_title.lower())

    # 提取中文
    orig_chinese = set(re.findall(r"[\u4e00-\u9fa5]", original_name))
    scraped_chinese = set(re.findall(r"[\u4e00-\u9fa5]", scraped_title))

    # 情况1：原始有中文，刮削结果无中文 → 危险
    if orig_chinese and not scraped_chinese:
        return False, f"原始标题含有中文但刮削结果无中文: 原始='{original_name}', 刮削='{scraped_title}'"

    # 情况2：两者都有中文，但公共字符占比过低 → 危险
    if orig_chinese and scraped_chinese:
        common = orig_chinese & scraped_chinese
        common_ratio = len(common) / max(len(orig_chinese), 1)
        if common_ratio < 0.3:
            return False, f"中文标题公共字符占比过低 ({common_ratio:.2f}): 原始='{original_name}', 刮削='{scraped_title}'"

    # 情况3：英文标题相似度检查（仅当两者都有字母数字时）
    orig_alnum = re.sub(r"[^\w]", "", original_name.lower())
    scraped_alnum = re.sub(r"[^\w]", "", scraped_title.lower())
    if orig_alnum and scraped_alnum:
        # 使用 SequenceMatcher 计算相似度（容忍前缀/位移）
        matcher = difflib.SequenceMatcher(None, orig_alnum, scraped_alnum)
        similarity = matcher.ratio()
        if similarity < 0.3:
            return False, f"英文标题相似度过低 ({similarity:.2f}): 原始='{original_name}', 刮削='{scraped_title}'"

    return True, ""


class MediaScanner:
    """媒体文件扫描器"""

    def __init__(self, ffprobe_path: str = "ffprobe", max_concurrency: int = 4):
        self.ffprobe_path = ffprobe_path
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def _process_movie_file(self, vf: Path) -> dict | None:
        """处理单个电影文件（带信号量，限制并发）"""
        async with self._semaphore:
            try:
                stat = await asyncio.to_thread(vf.stat)
                info = {
                    "file_path": str(vf),
                    "file_name": vf.name,
                    "file_size": stat.st_size,
                    "media_type": "movie",
                    "container": vf.suffix.lstrip(".").lower(),
                    "resolution": guess_resolution(vf.name),
                    "video_codec": guess_video_codec(vf.name),
                    "audio_codec": guess_audio_codec(vf.name),
                }

                # 尝试用 ffprobe 获取精确信息
                probe_data = await self._ffprobe(vf)
                if probe_data:
                    info["duration"] = probe_data.get("duration", 0)
                    info["video_codec"] = probe_data.get("video_codec") or info["video_codec"]
                    info["audio_codec"] = probe_data.get("audio_codec") or info["audio_codec"]
                    info["resolution"] = probe_data.get("resolution") or info["resolution"]
                else:
                    info["duration"] = 0

                # 解析名称
                info["parsed_name"] = parse_media_name(vf.name)

                # 优先使用NFO元数据
                nfo_path = find_nfo_file(vf)
                if nfo_path:
                    nfo_data = parse_nfo_file(nfo_path)
                    if nfo_data:
                        info["nfo_path"] = str(nfo_path)
                        if nfo_data.get("tmdb_id"):
                            info["tmdb_id"] = nfo_data["tmdb_id"]
                        if nfo_data.get("imdb_id"):
                            info["imdb_id"] = nfo_data["imdb_id"]
                        if nfo_data.get("title"):
                            info["nfo_title"] = nfo_data["title"]

                # 查找关联字幕
                info["subtitles"] = self._find_subtitles(vf)

                # 查找海报
                all_posters = find_all_posters(vf)
                if all_posters:
                    info["local_poster"] = str(all_posters[0])
                    info["all_posters"] = [str(p) for p in all_posters]

                return info
            except Exception as e:
                logger.warning(f"处理文件失败 {vf}: {e}")
                return None

    async def scan_directory(
        self, library_path: str, media_type: str
    ) -> list[dict[str, Any]]:
        """扫描目录，返回发现的媒体文件信息列表"""
        root = Path(library_path)
        if not root.exists():
            raise FileNotFoundError(f"媒体库路径不存在: {library_path}")
        if not root.is_dir():
            raise NotADirectoryError(f"路径不是目录: {library_path}")

        results = []
        # 按媒体类型决定扫描策略
        if media_type == "movie":
            results = await self._scan_movies(root)
        else:
            results = await self._scan_tv_shows(root, media_type)

        logger.info(f"Scanned {library_path}: found {len(results)} media files")
        return results

    async def _scan_movies(self, root: Path) -> list[dict]:
        """扫描电影文件，支持NFO元数据（并发处理）"""
        video_files = await asyncio.to_thread(self._find_video_files, root)
        
        # 并发处理所有文件（信号量限制并发数）
        tasks = [self._process_movie_file(vf) for vf in video_files]
        results_list = await asyncio.gather(*tasks)
        
        # 过滤掉处理失败的文件
        results = [r for r in results_list if r is not None]
        return results

    async def _scan_tv_shows(self, root: Path, media_type: str) -> list[dict]:
        """扫描剧集文件，支持 Season X 文件夹结构"""
        results = []
        # 递归查找所有视频文件
        video_files = await asyncio.to_thread(self._find_video_files, root)

        # 收集所有Season文件夹信息
        season_folders = await asyncio.to_thread(self._find_season_folders, root)
        logger.info(f"Found {len(season_folders)} season folders in {root}")

        # 按目录分组，同时处理嵌套结构
        # 结构示例: root/Season 6/哈哈哈哈哈（2020）/01.mkv
        # 或者: root/哈哈哈哈哈（2020）/Season 1/01.mkv
        show_dirs: dict[Path, dict] = {}
        for vf in video_files:
            # 构建路径链
            path_parts = vf.relative_to(root).parts
            parent = vf.parent
            grandparent = parent.parent if parent != root else None

            # 检测Season文件夹层级
            season_num = None
            show_dir = parent

            # 情况1: Season X/剧名/视频.mkv -> show_dir = parent (剧名文件夹)
            # 情况2: 剧名/Season X/视频.mkv -> show_dir = grandparent
            # 情况3: Season X/视频.mkv -> show_dir = parent (Season文件夹本身是show_dir)
            # 情况4: 剧名/视频.mkv -> show_dir = parent

            if grandparent and grandparent != root:
                parent_name = parent.name
                grandparent_name = grandparent.name

                # Season文件夹在中间层级: 剧名/Season X/视频
                if is_season_folder(parent_name) and not is_season_folder(grandparent_name):
                    season_num = parse_season_folder(parent_name)
                    show_dir = grandparent
                    logger.debug(f"Case 2: Season {season_num} folder at {parent_name}, show at {grandparent_name}")
                # Season文件夹在顶层: Season X/剧名/视频
                elif is_season_folder(grandparent_name) and not is_season_folder(parent_name):
                    season_num = parse_season_folder(grandparent_name)
                    show_dir = parent
                    logger.debug(f"Case 1: Season {season_num} folder at {grandparent_name}, show at {parent_name}")
                # 两个都是非Season: 剧名/子文件夹/视频
                else:
                    season_num = None
                    show_dir = parent
            elif parent != root:
                parent_name = parent.name
                # Season X/视频.mkv (Season文件夹直接包含视频)
                if is_season_folder(parent_name):
                    season_num = parse_season_folder(parent_name)
                    show_dir = parent
                    logger.debug(f"Case 3: Season {season_num} folder contains video directly")
                else:
                    season_num = None
                    show_dir = parent

            # 检查是否是Season文件夹本身作为show_dir
            if is_season_folder(show_dir.name) and show_dir != root:
                # Season文件夹本身作为show_dir，需要往上再找一层
                if grandparent and grandparent != root and not is_season_folder(grandparent.name):
                    show_dir = grandparent
                    season_num = parse_season_folder(parent.name) or season_num

            if show_dir not in show_dirs:
                show_dirs[show_dir] = {"season_num": season_num, "files": []}
            show_dirs[show_dir]["files"].append(vf)

        # 处理每个show_dir
        for show_dir, info in show_dirs.items():
            files = info["files"]
            folder_season_num = info["season_num"]

            # 优先使用节目标NFO（tvshow.nfo）中的标题和TMDB ID
            show_nfo_path = show_dir / "tvshow.nfo"
            if not show_nfo_path.exists():
                # 向上查找一级
                parent = show_dir.parent
                if parent != root:
                    show_nfo_path = parent / "tvshow.nfo"

            show_nfo_data = None
            if show_nfo_path.exists():
                show_nfo_data = parse_nfo_file(show_nfo_path)
                if show_nfo_data:
                    logger.debug(f"Found show NFO: {show_nfo_path}, tmdb_id={show_nfo_data.get('tmdb_id')}")

            # 解析show名称：优先使用NFO中的标题
            if show_dir == root:
                # 扁平结构，使用第一个文件名
                show_name = parse_media_name(files[0].name)
            else:
                # 使用文件夹名作为show名
                show_name = parse_media_name(show_dir.name)
                # 如果文件夹名是Season格式，尝试用父目录名
                if is_season_folder(show_dir.name):
                    parent_name = show_dir.parent.name
                    if parent_name != root.name:
                        show_name = parse_media_name(parent_name)

            # 如果节目标NFO有标题，使用NFO的标题
            if show_nfo_data and show_nfo_data.get("title"):
                # 节目标NFO的title是show标题
                nfo_show_title = show_nfo_data["title"]
                # 检查是否更像节目标标题（而不是文件名）
                if len(nfo_show_title) > 2 and not nfo_show_title.startswith("<"):
                    show_name = nfo_show_title
                    logger.debug(f"Using show title from NFO: {show_name}")

            for vf in files:
                season_num, episode_num, _ = parse_season_episode(vf.name, include_multi=True)

                # 如果文件名没有季号但文件夹有Season信息，使用文件夹的
                if season_num is None and folder_season_num is not None:
                    season_num = folder_season_num

                # 使用 asyncio.to_thread 包装阻塞 I/O 调用
                stat = await asyncio.to_thread(vf.stat)
                _ = await asyncio.to_thread(vf.exists)  # 检查文件是否存在

                info = {
                    "file_path": str(vf),
                    "file_name": vf.name,
                    "file_size": stat.st_size,
                    "media_type": media_type,
                    "container": vf.suffix.lstrip(".").lower(),
                    "resolution": guess_resolution(vf.name),
                    "video_codec": guess_video_codec(vf.name),
                    "audio_codec": guess_audio_codec(vf.name),
                    "parsed_name": show_name,
                    "season_number": season_num,
                    "episode_number": episode_num,
                    "subtitles": await asyncio.to_thread(self._find_subtitles, vf),
                }

                probe_data = await self._ffprobe(vf)
                if probe_data:
                    info["duration"] = probe_data.get("duration", 0)
                    info["video_codec"] = probe_data.get("video_codec") or info["video_codec"]
                    info["audio_codec"] = probe_data.get("audio_codec") or info["audio_codec"]
                    info["resolution"] = probe_data.get("resolution") or info["resolution"]
                else:
                    info["duration"] = 0

                # 解析剧集NFO文件（{视频文件名}.nfo）获取剧集标题、plot、播出日期
                ep_nfo_path = vf.parent / f"{vf.stem}.nfo"
                if ep_nfo_path.exists():
                    ep_nfo_data = parse_nfo_file(ep_nfo_path)
                    if ep_nfo_data:
                        # 剧集NFO包含剧集标题
                        if ep_nfo_data.get("title"):
                            info["episode_title"] = ep_nfo_data["title"]
                        if ep_nfo_data.get("plot"):
                            info["episode_plot"] = ep_nfo_data["plot"]
                        if ep_nfo_data.get("aired"):
                            info["episode_aired"] = ep_nfo_data["aired"]
                        if ep_nfo_data.get("tmdb_id"):
                            info["tmdb_id"] = ep_nfo_data["tmdb_id"]
                        logger.debug(f"Episode NFO for {vf.name}: title={ep_nfo_data.get('title')}")

                # 如果节目标NFO有tmdb_id，使用它
                if show_nfo_data and show_nfo_data.get("tmdb_id"):
                    if not info.get("tmdb_id"):
                        info["tmdb_id"] = show_nfo_data["tmdb_id"]

                results.append(info)

        logger.info(f"Scanned TV shows in {root}: found {len(results)} episodes from {len(show_dirs)} shows")
        return results

    def _find_season_folders(self, root: Path) -> list[dict]:
        """查找所有Season格式的文件夹"""
        season_folders = []
        try:
            for entry in root.rglob("*"):
                if entry.is_dir() and is_season_folder(entry.name):
                    season_num = parse_season_folder(entry.name)
                    season_folders.append({
                        "path": entry,
                        "name": entry.name,
                        "season_number": season_num,
                    })
        except PermissionError:
            logger.warning(f"Permission denied scanning season folders: {root}")
        return season_folders

    def _find_video_files(self, root: Path) -> list[Path]:
        """递归查找视频文件"""
        files = []
        if root.is_file() and is_video_file(root):
            return [root]
        try:
            for entry in root.rglob("*"):
                if entry.is_file() and is_video_file(entry):
                    # 跳过 sample 和 trailer
                    if any(kw in entry.name.lower() for kw in ["sample", "trailer", "preview"]):
                        continue
                    files.append(entry)
        except PermissionError:
            logger.warning(f"Permission denied scanning: {root}")
        return files

    def _find_subtitles(self, video_path: Path) -> list[dict]:
        """查找与视频关联的字幕文件"""
        subtitles = []
        video_stem = video_path.stem
        parent = video_path.parent

        for sub_file in parent.iterdir():
            if not is_subtitle_file(sub_file):
                continue
            # 匹配规则：字幕文件名以视频文件名开头
            if sub_file.stem.startswith(video_stem) or video_stem.startswith(sub_file.stem):
                lang_code, lang_name = detect_subtitle_language(sub_file.name)
                subtitles.append({
                    "path": str(sub_file),
                    "language": lang_code,
                    "language_name": lang_name,
                    "source": "external",
                })
        return subtitles

    async def _ffprobe(self, file_path: Path) -> dict | None:
        """使用 ffprobe 获取完整视频信息"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                # 超时时必须杀死子进程，防止僵尸进程
                logger.error(f"ffprobe timeout for {file_path}, killing process...")
                try:
                    proc.kill()
                    await proc.wait()  # 必须 wait 以回收僵尸进程
                except ProcessLookupError:
                    pass
                return None
            
            if proc.returncode != 0:
                return None

            data = json.loads(stdout.decode("utf-8", errors="ignore"))
            result = {}

            # 格式信息
            fmt = data.get("format", {})
            result["duration"] = int(float(fmt.get("duration", 0)))
            result["file_size"] = int(fmt.get("size", 0))

            # 流信息
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    result["video_codec"] = stream.get("codec_name", "")
                    width = stream.get("width", 0)
                    height = stream.get("height", 0)
                    if width and height:
                        if height >= 2160:
                            result["resolution"] = "4K"
                        elif height >= 1080:
                            result["resolution"] = "1080p"
                        elif height >= 720:
                            result["resolution"] = "720p"
                        elif height >= 480:
                            result["resolution"] = "480p"

                    # 帧率
                    fps_str = stream.get("r_frame_rate", "0/1")
                    if "/" in fps_str:
                        try:
                            num, denom = fps_str.split("/")
                            if int(denom) > 0:
                                result["frame_rate"] = round(int(num) / int(denom), 3)
                        except (ValueError, ZeroDivisionError):
                            pass

                    # 色彩空间
                    color_space = stream.get("color_space")
                    if color_space:
                        result["color_space"] = color_space

                    # 位深
                    bits = stream.get("bits_per_raw_sample")
                    if bits:
                        try:
                            result["bit_depth"] = int(bits)
                        except ValueError:
                            pass

                    # HDR 格式检测
                    profile = stream.get("profile", "").lower()
                    if "hdr10" in profile or "hdr10+" in profile:
                        result["hdr_format"] = "HDR10+" if "hdr10+" in profile else "HDR10"
                    elif "hlg" in profile:
                        result["hdr_format"] = "HLG"
                    elif "dolby vision" in profile.lower() or stream.get("codec_name", "").lower() == "hevc":
                        # Dolby Vision 可能在 profile 或 side_data 中
                        result["hdr_format"] = "Dolby Vision"

                    # 检查 side_data 中的 HDR 信息
                    side_data = stream.get("side_data_list", [])
                    for sd in side_data:
                        if sd.get("side_data_type"):
                            sd_type = sd["side_data_type"].lower()
                            if "hdr" in sd_type or "dolby" in sd_type:
                                if "dolby" in sd_type:
                                    result["hdr_format"] = "Dolby Vision"
                                elif "hlg" in sd_type:
                                    result["hdr_format"] = "HLG"
                                elif "hdr10" in sd_type:
                                    result["hdr_format"] = "HDR10"

                elif stream.get("codec_type") == "audio":
                    if not result.get("audio_codec"):
                        result["audio_codec"] = stream.get("codec_name", "")

                    # 音频通道数
                    if not result.get("audio_channels"):
                        channel_layout = stream.get("channel_layout", "")
                        if channel_layout:
                            # 标准化通道布局名称
                            channel_layout = channel_layout.lower().replace(" ", "")
                            if "7.1" in channel_layout or "stereo" not in channel_layout and stream.get("channels", 0) >= 8:
                                result["audio_channels"] = "7.1"
                            elif "5.1" in channel_layout or stream.get("channels", 0) >= 6:
                                result["audio_channels"] = "5.1"
                            elif "stereo" in channel_layout or stream.get("channels", 0) == 2:
                                result["audio_channels"] = "2.0"
                            elif "mono" in channel_layout or stream.get("channels", 0) == 1:
                                result["audio_channels"] = "1.0"
                            else:
                                result["audio_channels"] = f"{stream.get('channels', 0)}.0"
                        else:
                            channels = stream.get("channels", 0)
                            if channels:
                                result["audio_channels"] = f"{channels}.0"

            return result
        except Exception as e:
            logger.debug(f"ffprobe failed for {file_path}: {e}")
            return None
