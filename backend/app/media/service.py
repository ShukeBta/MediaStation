"""
媒体库业务逻辑
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.exceptions import NotFoundError, ScraperError
from app.media.models import MediaEpisode, MediaItem, MediaLibrary, MediaSeason, Subtitle
from app.media.repository import MediaRepository
from app.media.schemas import (
    LibraryCreate,
    LibraryOut,
    LibraryUpdate,
    MediaItemDetail,
    MediaItemOut,
    MediaItemUpdate,
    PaginatedResponse,
    ScanResult,
    ScrapeRequest,
    SeasonOut,
    EpisodeOut,
    SubtitleOut,
)
from app.media.scraper import TMDbClient, get_tmdb_client
from app.media.douban_scraper import DoubanClient, get_douban_client
from app.media.bangumi_scraper import BangumiClient, get_bangumi_client
from app.media.scanner import MediaScanner, check_scrape_title_safety
from app.media.parse_code import parse_code, is_adult_content
from app.system.events import EventBus

logger = logging.getLogger(__name__)


class MediaService:
    def __init__(self, repo: MediaRepository, event_bus: EventBus | None = None, db=None):
        self.repo = repo
        self.event_bus = event_bus or EventBus()
        self.db = db  # 用于需要 db session 的操作（如 ApiConfigService）
        self.scanner = MediaScanner(
            ffprobe_path=get_settings().ffprobe_path
        )
        # 缓存刮削配置（避免频繁读取数据库）
        self._scrape_config_cache: dict[str, Any] = {}

    async def _get_scrape_config(self) -> dict[str, Any]:
        """获取刮削配置（从数据库 SettingsKV 表读取）"""
        if self._scrape_config_cache:
            return self._scrape_config_cache

        try:
            from app.system.settings_service import SettingsService
            from app.database import async_session_factory

            async with async_session_factory() as db:
                service = SettingsService(db)
                self._scrape_config_cache = {
                    "providers": await service.get_list("scrape.providers"),
                    "language": await service.get("scrape.language") or "zh-CN",
                    "poster_size": await service.get("scrape.poster_size") or "w500",
                    "backdrop_size": await service.get("scrape.backdrop_size") or "original",
                    "overwrite_existing": await service.get_bool("scrape.overwrite_existing"),
                }
        except Exception as e:
            logger.warning(f"Failed to load scrape config: {e}")
            # 使用默认值
            self._scrape_config_cache = {
                "providers": ["tmdb"],
                "language": "zh-CN",
                "poster_size": "w500",
                "backdrop_size": "original",
                "overwrite_existing": False,
            }

        return self._scrape_config_cache

    def invalidate_scrape_config_cache(self):
        """清除刮削配置缓存（配置更新后调用）"""
        self._scrape_config_cache = {}

    # ── 媒体库管理 ──
    async def list_libraries(self) -> list[LibraryOut]:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("[MediaService] list_libraries() called")
        libraries = await self.repo.get_all_libraries()
        logger.info(f"[MediaService] Found {len(libraries)} libraries")
        result = []
        for lib in libraries:
            count = await self.repo.count_library_items(lib.id)
            out = LibraryOut.model_validate(lib)
            out.item_count = count
            result.append(out)
        return result

    async def create_library(self, data: LibraryCreate) -> LibraryOut:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MediaService] create_library: {data}")
        lib = await self.repo.create_library(
            name=data.name, path=data.path, media_type=data.media_type,
            scan_interval=data.scan_interval, enabled=data.enabled,
        )
        return LibraryOut.model_validate(lib)

    async def update_library(self, library_id: int, data: LibraryUpdate) -> LibraryOut:
        updates = data.model_dump(exclude_unset=True)
        lib = await self.repo.update_library(library_id, **updates)
        if not lib:
            raise NotFoundError("Library", library_id)
        count = await self.repo.count_library_items(lib.id)
        out = LibraryOut.model_validate(lib)
        out.item_count = count
        return out

    async def delete_library(self, library_id: int):
        lib = await self.repo.get_library_by_id(library_id)
        if not lib:
            raise NotFoundError("Library", library_id)
        await self.repo.delete_library(library_id)

    # ── 扫描（带自动刮削） ──
    async def scan_library(self, library_id: int, auto_scrape: bool = True) -> ScanResult:
        """
        扫描媒体库并自动刮削新增条目。
        - auto_scrape=True: 扫描后自动刮削新增条目（新增时调用）
        - auto_scrape=False: 仅扫描不刮削（定时任务调用，由 scrape_unscraped 补全）
        """
        lib = await self.repo.get_library_by_id(library_id)
        if not lib:
            raise NotFoundError("Library", library_id)

        result = ScanResult()
        self.event_bus.emit("scan_progress", {
            "library_id": library_id,
            "status": "scanning",
            "message": f"正在扫描: {lib.name}",
        })

        try:
            # 1. 扫描文件系统
            scanned = await self.scanner.scan_directory(lib.path, lib.media_type)

            # 1.5 最小文件大小过滤
            min_file_size = getattr(lib, 'min_file_size', 0) or 0
            if min_file_size > 0:
                original_count = len(scanned)
                scanned = [
                    item for item in scanned
                    if item.get("file_size", 0) >= min_file_size
                ]
                if original_count > len(scanned):
                    logger.info(f"Filtered {original_count - len(scanned)} files smaller than {min_file_size} bytes")

            scanned_paths = {item["file_path"] for item in scanned}

            # 2. 获取数据库现有条目路径
            existing_paths = await self.repo.get_all_item_paths(library_id)

            # 3. 处理新文件
            new_paths = scanned_paths - existing_paths
            new_items_ids: list[int] = []
            for path in new_paths:
                item_data = next((s for s in scanned if s["file_path"] == path), None)
                if not item_data:
                    continue
                try:
                    item = await self._add_scanned_item(library_id, item_data, lib.media_type)
                    new_items_ids.append(item.id)
                    result.added += 1
                except Exception as e:
                    result.errors.append(f"添加失败 {path}: {str(e)}")

            # 4. 处理已有文件更新
            common_paths = scanned_paths & existing_paths
            for path in common_paths:
                item_data = next((s for s in scanned if s["file_path"] == path), None)
                if not item_data:
                    continue
                existing = await self.repo.get_item_by_path(path)
                if existing:
                    update_kwargs: dict = {
                        "file_size": item_data.get("file_size", 0),
                        "duration": item_data.get("duration", 0),
                        "video_codec": item_data.get("video_codec"),
                        "audio_codec": item_data.get("audio_codec"),
                        "resolution": item_data.get("resolution"),
                    }
                    # 如果 NFO 中有 tmdb_id 且条目尚未有 tmdb_id，补充（用于后续自动刮削）
                    nfo_tmdb_id = item_data.get("tmdb_id")
                    if nfo_tmdb_id and not existing.tmdb_id:
                        update_kwargs["tmdb_id"] = nfo_tmdb_id
                        logger.info(f"NFO tmdb_id补充: {path} -> tmdb_id={nfo_tmdb_id}")
                    # 如果 NFO 有标题且条目尚未刮削，用 NFO 标题更新
                    nfo_title = item_data.get("nfo_title")
                    if nfo_title and not existing.scraped:
                        update_kwargs["title"] = nfo_title
                    await self.repo.update_item(existing.id, **update_kwargs)
                    result.updated += 1

            # 5. 删除数据库中不存在的文件
            removed_paths = existing_paths - scanned_paths
            for path in removed_paths:
                item = await self.repo.get_item_by_path(path)
                if item:
                    await self.repo.delete_item(item.id)
                    result.removed += 1

            # 6. 更新扫描时间
            await self.repo.update_library(library_id, last_scan=datetime.now())

            # 7. 自动刮削新增条目（仅新增时调用）
            if auto_scrape and new_items_ids:
                result.scraped = await self._scrape_items(new_items_ids, lib.media_type)

            # 8. 补全：刮削已有的未刮削条目（最多 50 条）
            if auto_scrape:
                unscraped = await self.repo.get_unscraped_items(library_id, limit=50)
                if unscraped:
                    unscraped_ids = [item.id for item in unscraped]
                    result.scraped += await self._scrape_items(unscraped_ids, lib.media_type)

        except (FileNotFoundError, NotADirectoryError):
            # 路径不存在或不是目录，直接抛出让前端展示错误
            raise
        except Exception as e:
            logger.error(f"Scan library {library_id} failed: {e}")
            result.errors.append(str(e))

        self.event_bus.emit("scan_progress", {
            "library_id": library_id,
            "status": "completed",
            "message": f"扫描完成: 新增 {result.added}, 更新 {result.updated}, 移除 {result.removed}, 刮削 {result.scraped}",
            "result": result.model_dump(),
        })

        return result

    async def _add_scanned_item(
        self, library_id: int, item_data: dict, media_type: str
    ) -> MediaItem:
        """添加扫描到的媒体条目"""
        # 处理剧集（即使没有 episode_number，只要是剧集类型也走这里）
        if media_type in ("tv", "anime"):
            return await self._add_tv_episode(library_id, item_data, media_type)

        # 处理电影
        item = await self.repo.create_item(
            library_id=library_id,
            title=item_data.get("parsed_name", item_data["file_name"]),
            media_type=media_type,
            file_path=item_data["file_path"],
            file_size=item_data.get("file_size", 0),
            duration=item_data.get("duration", 0),
            video_codec=item_data.get("video_codec"),
            audio_codec=item_data.get("audio_codec"),
            resolution=item_data.get("resolution"),
            container=item_data.get("container"),
            # 电影也可以使用 NFO 中的 tmdb_id
            tmdb_id=item_data.get("tmdb_id"),
        )

        # 添加字幕
        for sub_data in item_data.get("subtitles", []):
            await self.repo.create_subtitle(
                media_item_id=item.id,
                language=sub_data["language"],
                language_name=sub_data["language_name"],
                path=sub_data.get("path"),
                source=sub_data.get("source", "external"),
            )

        return item

    async def _add_tv_episode(
        self, library_id: int, item_data: dict, media_type: str
    ) -> MediaItem:
        """
        添加剧集条目（含季/集管理）
        关键逻辑：
        1. 同一部剧的多季应归为同一个 MediaItem
        2. 同一季的集应归为同一个 Season
        3. 每集对应一个 Episode，存储实际文件路径
        """
        show_name = item_data.get("parsed_name", "")
        season_num = item_data.get("season_number", 1)
        episode_num = item_data.get("episode_number")
        file_path = item_data.get("file_path", "")

        # 使用 NFO 标题（如果存在）
        if item_data.get("nfo_title"):
            show_name = item_data["nfo_title"]

        # 去重策略：
        # 1. 优先按标题精确匹配（忽略大小写和常见分隔符）
        # 2. 模糊匹配处理"哈哈哈哈（2020）"vs"哈哈哈哈哈"的情况

        # 查找已有的同名剧集
        existing_items, total = await self.repo.get_items(
            library_id=library_id, media_type=media_type, page=1, page_size=200
        )

        # 标准化标题用于比较
        def normalize_title(title: str) -> str:
            """标准化标题：去除年份、括号内容、特殊字符"""
            import re
            # 去除年份 (2020)
            title = re.sub(r"\s*\(\d{4}\)\s*", "", title)
            # 去除括号内容
            title = re.sub(r"（\d{4}）", "", title)
            # 去除特殊字符
            title = re.sub(r"[^\w\u4e00-\u9fa5]", "", title)
            return title.lower().strip()

        normalized_show = normalize_title(show_name)
        existing_item = None

        for ei in existing_items:
            # 精确匹配
            if ei.title == show_name:
                existing_item = ei
                break
            # 标准化后匹配
            if normalize_title(ei.title) == normalized_show:
                existing_item = ei
                break
            # 标题包含匹配（处理嵌套目录情况）
            if show_name in ei.title or ei.title in show_name:
                if normalize_title(ei.title) == normalized_show[:10]:  # 前10字符匹配
                    existing_item = ei
                    break

        if existing_item:
            media_item = existing_item
            logger.debug(f"Found existing series: {media_item.title} (id={media_item.id})")
        else:
            # 创建新的剧集主条目
            media_item = await self.repo.create_item(
                library_id=library_id,
                title=show_name,
                media_type=media_type,
                file_path=file_path,  # 存储第一个文件的路径
                file_size=item_data.get("file_size", 0),
            )
            logger.info(f"Created new series: {show_name} (id={media_item.id})")

        # 获取或创建季
        seasons = await self.repo.get_seasons_by_item(media_item.id)
        season = next((s for s in seasons if s.season_number == season_num), None)
        if not season:
            season = await self.repo.create_season(
                media_item_id=media_item.id,
                season_number=season_num,
                name=f"第 {season_num} 季",
            )
            logger.debug(f"Created season {season_num} for series {media_item.title}")

        # 创建或更新集
        if episode_num and file_path:
            # 获取该季已存在的集
            existing_eps = await self.repo.get_episodes_by_season(season.id)
            existing_ep = next((e for e in existing_eps if e.episode_number == episode_num), None)

            # 从NFO获取的剧集元数据
            ep_title = item_data.get("episode_title")
            ep_plot = item_data.get("episode_plot")
            ep_aired = item_data.get("episode_aired")
            ep_duration = item_data.get("duration", 0)

            # 解析播出日期
            aired_date = None
            if ep_aired:
                try:
                    from datetime import datetime
                    aired_date = datetime.strptime(ep_aired, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass

            if not existing_ep:
                # 创建新集
                await self.repo.create_episode(
                    season_id=season.id,
                    episode_number=episode_num,
                    file_path=file_path,
                    file_size=item_data.get("file_size", 0),
                    duration=ep_duration,
                    title=ep_title,
                    air_date=aired_date,
                    video_codec=item_data.get("video_codec"),
                    audio_codec=item_data.get("audio_codec"),
                )
                logger.debug(f"Added episode {episode_num} to season {season_num}")
            else:
                # 更新已有集：补充缺失的元数据
                updates = {}
                if not existing_ep.title and ep_title:
                    updates["title"] = ep_title
                if not existing_ep.air_date and aired_date:
                    updates["air_date"] = aired_date
                if existing_ep.duration == 0 and ep_duration > 0:
                    updates["duration"] = ep_duration
                if not existing_ep.video_codec and item_data.get("video_codec"):
                    updates["video_codec"] = item_data.get("video_codec")
                if not existing_ep.audio_codec and item_data.get("audio_codec"):
                    updates["audio_codec"] = item_data.get("audio_codec")

                if updates:
                    await self.repo.update_episode(existing_ep.id, **updates)
                    logger.debug(f"Updated episode {episode_num}: {list(updates.keys())}")
        elif file_path and not episode_num:
            # 没有集数信息但有文件路径：尝试按文件名解析集数
            # 如果文件名中包含集数信息
            from app.media.scanner import parse_season_episode
            _, parsed_ep, _ = parse_season_episode(item_data.get("file_name", ""))
            if parsed_ep:
                existing_eps = await self.repo.get_episodes_by_season(season.id)
                existing_ep = next((e for e in existing_eps if e.episode_number == parsed_ep), None)
                if not existing_ep:
                    await self.repo.create_episode(
                        season_id=season.id,
                        episode_number=parsed_ep,
                        file_path=file_path,
                        file_size=item_data.get("file_size", 0),
                        duration=item_data.get("duration", 0),
                    )
                    logger.debug(f"Added episode {parsed_ep} (parsed from filename) to season {season_num}")
            else:
                # 无法解析集数：将文件作为单集处理
                existing_eps = await self.repo.get_episodes_by_season(season.id)
                # 找最大集号 + 1 作为新集号
                max_ep = max([e.episode_number for e in existing_eps], default=0)
                await self.repo.create_episode(
                    season_id=season.id,
                    episode_number=max_ep + 1,
                    file_path=file_path,
                    file_size=item_data.get("file_size", 0),
                    duration=item_data.get("duration", 0),
                )
                logger.debug(f"Added file as episode {max_ep + 1} (no episode number found)")

        return media_item

    # ── 增量刮削：补全未刮削的条目 ──
    async def scrape_unscraped(self, library_id: int, limit: int = 20) -> dict[str, Any]:
        """
        增量刮削：只刮削未刮削的条目。
        定时任务调用，用于补全扫描后遗漏的条目。
        """
        unscraped = await self.repo.get_unscraped_items(library_id, limit)
        if not unscraped:
            return {"scraped": 0, "failed": 0, "skipped": 0, "details": []}

        lib = await self.repo.get_library_by_id(library_id)
        media_type = lib.media_type if lib else "movie"

        scraped, failed = 0, 0
        details = []

        for item in unscraped:
            detail = {"item_id": item.id, "title": item.title, "status": "pending"}

            # 已经刮削过的跳过
            if item.scraped:
                detail["status"] = "skipped"
                details.append(detail)
                continue

            try:
                request = ScrapeRequest(title=item.title, year=item.year)
                await self.scrape_item(item.id, request)
                detail["status"] = "success"
                scraped += 1
            except ScraperError as e:
                # 尝试用文件名刮削（去掉分辨率/编码等后缀）
                try:
                    clean_title = self._clean_title_for_scrape(item.title)
                    if clean_title != item.title:
                        request = ScrapeRequest(title=clean_title, year=item.year)
                        await self.scrape_item(item.id, request)
                        detail["status"] = "success"
                        detail["alt_title"] = clean_title
                        scraped += 1
                    else:
                        detail["status"] = "failed"
                        detail["error"] = str(e)
                        failed += 1
                except Exception:
                    detail["status"] = "failed"
                    detail["error"] = str(e)
                    failed += 1
            except Exception as e:
                detail["status"] = "failed"
                detail["error"] = str(e)
                failed += 1

            details.append(detail)

        logger.info(f"Scrape unscraped for library {library_id}: scraped={scraped}, failed={failed}")
        return {"scraped": scraped, "failed": failed, "skipped": 0, "details": details}

    def _clean_title_for_scrape(self, title: str) -> str:
        """清理标题，去除常见后缀以便 TMDb 搜索"""
        # 移除分辨率标签
        patterns = [
            r"[\.\-_]?(2160p|1080p|1080i|720p|480p|4K|4k)", r"[\.\-_]?(BluRay|BDRip|HDRip|HDTV|DVDRip|REMUX)",
            r"[\.\-_]?(WEB-?DL|WEB)", r"[\.\-_]?(HEVC|H\.?265|H\.?264|AVC|AV1)",
            r"[\.\-_]?(x265|x264)", r"[\.\-_]?(DTS|AAC|FLAC|AC3|TrueHD)",
            r"[\.\-_]?(10bit|HDR|DV|Atmos)", r"[\.\-_]?(YUV)", r"[\.\-_]?(PROPER|REPACK)",
            r"[\.\-_]?(国粤双语|国粤|双语)", r"[\.\-_]?(中英双语|中英)",
        ]
        for p in patterns:
            title = re.sub(p, "", title, flags=re.IGNORECASE)
        # 移除多余分隔符和空格
        title = re.sub(r"[\.\-_]+", ".", title)
        title = re.sub(r"\s+", " ", title).strip()
        # 移除末尾的点号
        title = title.rstrip(".")
        return title

    async def _scrape_items(self, item_ids: list[int], media_type: str) -> int:
        """
        批量刮削条目，自动处理失败重试。
        返回成功刮削的数量。

        18+ 番号内容会自动使用 AdultProvider 刮削。
        """
        from app.media.providers import get_provider_chain

        scraped = 0
        for item_id in item_ids:
            item = await self.repo.get_item_by_id(item_id)
            if not item:
                continue
            # 跳过已刮削的
            if item.scraped:
                continue

            try:
                # 检测是否是 18+ 内容
                filename = ""
                if item.path:
                    import os
                    filename = os.path.basename(item.path)

                # 🔍 调试日志：记录成人内容检测过程
                item_path = str(item.path) if item.path else ""
                is_adult = is_adult_content(filename, item_path)
                logger.info(f"[MediaService] === 刮削检测开始 ===")
                logger.info(f"[MediaService] 文件名: {filename}")
                logger.info(f"[MediaService] 完整路径: {item_path}")
                logger.info(f"[MediaService] is_adult_content 结果: {is_adult}")
                
                # 调试：检查目录名是否包含成人关键词
                if item_path:
                    import os as _os
                    dir_name = _os.path.dirname(item_path)
                    logger.info(f"[MediaService] 目录名: {dir_name}")
                    if "9KG" in dir_name.upper() or "9KG" in filename.upper():
                        logger.info(f"[MediaService] ⚠️ 检测到 9KG 目录/文件名!")

                if is_adult:
                    # 使用 AdultProvider 刮削
                    logger.info(f"[MediaService] → 使用 AdultProvider 刮削")
                    success = await self._scrape_item_adult(item_id, filename)
                    logger.info(f"[MediaService] AdultProvider 刮削结果: {success}")
                    if success:
                        scraped += 1
                    else:
                        logger.warning(f"[MediaService] AdultProvider 刮削失败，将保持 scraped=False")
                else:
                    # 使用原有的 TMDb 刮削流程
                    logger.info(f"[MediaService] → 使用 TMDb 刮削")
                    request = ScrapeRequest(
                        title=item.title,
                        year=item.year,
                        tmdb_id=item.tmdb_id,
                    )
                    await self.scrape_item(item_id, request)
                    scraped += 1

                logger.info(f"[MediaService] === 刮削检测结束 ===\n")

            except ScraperError as e:
                # 尝试清理标题重试（非 18+ 内容）
                if not is_adult_content(filename, str(item.path) if item.path else ""):
                    try:
                        clean_title = self._clean_title_for_scrape(item.title)
                        if clean_title and clean_title != item.title:
                            request = ScrapeRequest(
                                title=clean_title,
                                year=item.year,
                                tmdb_id=item.tmdb_id,
                            )
                            await self.scrape_item(item_id, request)
                            scraped += 1
                        else:
                            logger.warning(f"Scrape failed for {item.title}: {e}")
                    except Exception as e2:
                        logger.warning(f"Scrape retry failed for {item.title}: {e2}")
                else:
                    logger.warning(f"Adult scrape failed for {filename}: {e}")
            except Exception as e:
                logger.warning(f"Scrape error for {item.title or filename}: {e}")

            # 避免请求过快
            await asyncio.sleep(0.5)

        return scraped

    async def _scrape_item_adult(self, item_id: int, filename: str) -> bool:
        """
        使用 AdultProvider 刮削 18+ 内容

        Returns:
            True 如果刮削成功
        """
        from app.media.providers.adult import AdultProvider

        try:
            # 解析番号
            logger.info(f"[AdultScrape] === 开始 AdultProvider 刮削 ===")
            logger.info(f"[AdultScrape] 正在解析番号: {filename}")
            
            parsed = parse_code(filename)
            if not parsed:
                logger.warning(f"[AdultScrape] ❌ 无法从 '{filename}' 解析番号!")
                logger.warning(f"[AdultScrape] 可能原因: 文件名不符合番号格式 (如 ABC-123, FC2-PPV-xxx)")
                logger.warning(f"[AdultScrape] 提示: 请确保文件名包含标准番号格式")
                logger.info(f"[AdultScrape] === AdultProvider 刮削失败 ===\n")
                return False

            code = parsed.code
            logger.info(f"[AdultScrape] ✓ 成功解析番号: {code}")
            logger.info(f"[AdultScrape] 番号类型: {parsed.code_type}, 置信度: {parsed.confidence}")

            # 直接创建 AdultProvider 实例（从数据库加载配置）
            adult_provider = AdultProvider()

            # 检查 AdultProvider 是否已配置
            if not await adult_provider.is_configured():
                logger.warning("[AdultScrape] ⚠️ AdultProvider 未启用，请在设置中启用")
                return False

            logger.info(f"[AdultScrape] AdultProvider 已配置，开始刮削...")

            # 使用 AdultProvider 刮削
            metadata = await adult_provider.get_metadata(code, "movie")
            if not metadata:
                logger.warning(f"[AdultScrape] ❌ AdultProvider 未返回元数据 for {code}")
                logger.warning(f"[AdultScrape] 可能原因: 网络问题 / JavBus/JavDB 无法访问 / 番号不存在")
                logger.info(f"[AdultScrape] === AdultProvider 刮削失败 ===\n")
                return False

            # 更新 item 元数据
            logger.info(f"[AdultScrape] ✓ 刮削成功! 标题: {metadata.title}")
            await self._update_item_metadata(item_id, metadata)
            logger.info(f"[AdultScrape] === AdultProvider 刮削完成 ===\n")
            return True

        except Exception as e:
            logger.error(f"[MediaService] Error scraping adult content: {e}", exc_info=True)
            return False

    async def _update_item_metadata(self, item_id: int, metadata) -> None:
        """更新 item 元数据"""
        import json
        
        # 强制确保 genres 是 JSON 字符串（SQLite Text 列不支持 list）
        raw_genres = getattr(metadata, 'genres', None) or []
        if isinstance(raw_genres, str):
            genres_json = raw_genres  # 已经是字符串，直接使用
        else:
            genres_json = json.dumps(raw_genres, ensure_ascii=False) if raw_genres else "[]"
        
        # 调试日志
        logger.info(f"[UpdateItem] genres BEFORE type={type(raw_genres).__name__}, AFTER type={type(genres_json).__name__}")
        
        updates = {
            "title": metadata.title,
            "original_title": metadata.original_title,
            "year": metadata.year,
            "overview": metadata.overview,
            "poster_url": metadata.poster_url,
            "backdrop_url": metadata.backdrop_url,
            "rating": metadata.rating,
            "genres": genres_json,  # 确保是 JSON 字符串
            "duration": metadata.duration,
            "scraped": True,
        }
        await self.repo.update_item(item_id, **updates)
    async def get_items(
        self,
        library_id: int | None = None,
        media_type: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "date_added",
        sort_order: str = "desc",
        genre: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        rating_min: float | None = None,
    ) -> PaginatedResponse:
        items, total = await self.repo.get_items(
            library_id=library_id,
            media_type=media_type,
            search=search,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            genre=genre,
            year_min=year_min,
            year_max=year_max,
            rating_min=rating_min,
        )
        return PaginatedResponse.create(
            items=[MediaItemOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_item_detail(self, item_id: int) -> MediaItemDetail:
        item = await self.repo.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("MediaItem", item_id)

        detail = MediaItemDetail.model_validate(item)

        # 季/集
        if item.media_type in ("tv", "anime"):
            seasons = await self.repo.get_seasons_by_item(item.id)
            detail.seasons = []
            for season in seasons:
                s_out = SeasonOut.model_validate(season)
                # 按 episode_number 排序
                sorted_episodes = sorted(season.episodes, key=lambda ep: ep.episode_number)
                s_out.episodes = [EpisodeOut.model_validate(ep) for ep in sorted_episodes]
                s_out.episode_count = len(season.episodes)
                detail.seasons.append(s_out)

        # 字幕
        subs = await self.repo.get_subtitles_by_item(item.id)
        detail.subtitles = [SubtitleOut.model_validate(s) for s in subs]

        return detail

    async def get_recent_items(self, limit: int = 10) -> list[MediaItemOut]:
        items = await self.repo.get_recent_items(limit)
        return [MediaItemOut.model_validate(i) for i in items]

    # ── 手动编辑元数据 ──
    async def update_item_metadata(self, item_id: int, data: MediaItemUpdate) -> MediaItemDetail:
        """手动更新媒体条目的元数据（管理员操作）"""
        item = await self.repo.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("MediaItem", item_id)

        update_fields = data.model_dump(exclude_unset=True)

        # genres 需要序列化为 JSON 字符串（数据库存储为 JSON）
        if "genres" in update_fields and update_fields["genres"] is not None:
            import json
            update_fields["genres"] = json.dumps(update_fields["genres"], ensure_ascii=False)

        # 将 None 值转换为特殊标记，以便 Repository 可以将其设置为 NULL
        # Repository 层会识别 "__NONE__" 并将其设置为 None
        processed_fields = {}
        for k, v in update_fields.items():
            if v is None:
                processed_fields[k] = "__NONE__"  # 特殊标记
            else:
                processed_fields[k] = v

        if processed_fields:
            await self.repo.update_item(item_id, **processed_fields)
            logger.info(f"Metadata updated for item {item_id}: {list(update_fields.keys())}")

        return await self.get_item_detail(item_id)

    # ── 刮削（多源刮削链） ──
    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """计算两个标题的相似度 (0-1)，用于验证刮削结果"""
        if not a or not b:
            return 0.0
        a_clean = re.sub(r'[\s\.\-_\(\)（）\[\]]+', '', a.lower())
        b_clean = re.sub(r'[\s\.\-_\(\)（）\[\]]+', '', b.lower())
        if a_clean == b_clean:
            return 1.0
        # 一个是另一个的子串
        if a_clean in b_clean or b_clean in a_clean:
            return 0.9
        # 计算公共前缀比例
        common = 0
        for ca, cb in zip(a_clean, b_clean):
            if ca == cb:
                common += 1
            else:
                break
        max_len = max(len(a_clean), len(b_clean))
        prefix_ratio = common / max_len if max_len > 0 else 0
        return prefix_ratio

    def _find_best_tmdb_match(self, results: list[dict], target_title: str, target_year: int | None = None) -> dict | None:
        """从 TMDb 搜索结果中找到最佳匹配，避免子串误匹配"""
        if not results:
            return None

        # 如果有年份，优先匹配年份
        year_filtered = results
        if target_year:
            year_filtered = [
                r for r in results
                if r.get("release_date", r.get("first_air_date", "")).startswith(str(target_year))
            ]
            if year_filtered:
                results = year_filtered

        # 按相似度排序
        scored = []
        for r in results:
            r_title = r.get("title", r.get("name", ""))
            sim = self._title_similarity(target_title, r_title)
            # TMDb 本身有 popularity 排序，给高相似度加分
            scored.append((r, sim))

        # 按相似度降序排列
        scored.sort(key=lambda x: x[1], reverse=True)

        # 如果最佳匹配相似度太低（< 0.3），可能是错误匹配
        best_match, best_sim = scored[0]
        if best_sim < 0.3 and len(scored) > 1:
            logger.warning(
                f"Low similarity ({best_sim:.2f}) between '{target_title}' and "
                f"TMDb result '{best_match.get('title', best_match.get('name', ''))}'. "
                f"Top result may be incorrect."
            )

        return best_match

    async def scrape_item(self, item_id: int, request: ScrapeRequest) -> MediaItemDetail:
        """
        多源刮削链：TMDb → 豆瓣 → Bangumi
        优先使用 TMDb 作为主源，然后依次补充豆瓣和 Bangumi 数据。
        增加标题匹配验证，减少子串误匹配（如 "hoppers" 误匹配 "Grasshoppers"）。
        18+ 成人内容会自动使用 AdultProvider 刮削。
        """
        import os as _os

        item = await self.repo.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("MediaItem", item_id)

        metadata: dict[str, Any] = {}

        # ── 成人内容检测：优先使用 AdultProvider 刮削 18+ 内容 ──
        filename = ""
        item_path = ""
        if item.file_path:
            filename = _os.path.basename(item.file_path)
            item_path = str(item.file_path)

        is_adult = is_adult_content(filename, item_path)
        logger.info(f"[ScrapeItem] === 开始刮削 (item_id={item_id}) ===")
        logger.info(f"[ScrapeItem] 文件名: {filename}")
        logger.info(f"[ScrapeItem] 完整路径: {item_path}")
        logger.info(f"[ScrapeItem] is_adult_content 结果: {is_adult}")

        # 检测 9KG 目录
        if item_path and ("9KG" in item_path.upper() or "ADULT" in item_path.upper()):
            logger.info(f"[ScrapeItem] ⚠️ 检测到成人目录 (9KG/Adult)")
            is_adult = True

        if is_adult:
            logger.info(f"[ScrapeItem] → 使用 AdultProvider 刮削")
            success = await self._scrape_item_adult(item_id, filename)
            if success:
                # 重新获取更新后的条目
                updated_item = await self.repo.get_item_by_id(item_id)
                if updated_item:
                    return MediaItemDetail.model_validate(updated_item)
                return await self.get_item_detail(item_id)
            # AdultProvider 刮削失败，回退到 TMDb
            logger.warning(f"[ScrapeItem] AdultProvider 刮削失败，回退到 TMDb")
            # 不抛出错误，继续往下走 TMDb 刮削流程

        # ── 非成人内容：TMDb 刮削（主源）──
        # 使用 ApiConfigService 获取 TMDb 配置（支持数据库配置）
        from app.system.api_config_service import ApiConfigService
        api_config_service = ApiConfigService(self.db)
        tmdb_config = await api_config_service.get_effective_config("tmdb")

        tmdb_api_key = tmdb_config.get("api_key", "")
        tmdb_base_url = tmdb_config.get("base_url") or None
        tmdb_image_base = tmdb_config.get("image_base") or None
        tmdb_language = tmdb_config.get("language") or None

        if not tmdb_api_key:
            raise ScraperError(item.title, "TMDb API 密钥未配置，请在 API 配置中设置")

        from app.media.scraper import TMDbClient
        import httpx

        tmdb_client = TMDbClient(
            custom_api_key=tmdb_api_key,
            custom_base_url=tmdb_base_url,
            custom_image_base=tmdb_image_base,
            custom_language=tmdb_language,
        )

        try:
            if request.tmdb_id:
                # 直接使用指定的 TMDb ID
                tmdb_detail = await tmdb_client.get_detail(request.tmdb_id, item.media_type)
                metadata = tmdb_client.to_media_metadata(tmdb_detail, item.media_type)
            else:
                search_title = request.title or item.title
                search_year = request.year or item.year

                results = await tmdb_client.search(search_title, item.media_type, search_year)

                # 回退策略：搜索失败时，尝试从文件名提取英文标题重新搜索
                if not results:
                    import os
                    filename = os.path.basename(item.file_path)
                    english_words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", filename)
                    if english_words:
                        seen: set[str] = set()
                        for num_words in range(2, min(len(english_words), 7) + 1):
                            candidate = " ".join(english_words[:num_words])
                            if candidate in seen or candidate == search_title:
                                continue
                            seen.add(candidate)
                            logger.info(f"TMDb search fallback: trying '{candidate}' for item {item_id}")
                            results = await tmdb_client.search(candidate, item.media_type, search_year)
                            if results:
                                logger.info(f"TMDb search fallback succeeded with '{candidate}'")
                                break

                if not results:
                    raise ScraperError(search_title, "No results found on TMDb")

                # 使用智能匹配代替直接取第一个结果
                best_match = self._find_best_tmdb_match(results, search_title, search_year)
                if not best_match:
                    raise ScraperError(search_title, "No matching results found")

                match_title = best_match.get("title", best_match.get("name", ""))
                match_id = best_match["id"]
                logger.info(
                    f"TMDb match for '{search_title}': '{match_title}' (id={match_id})"
                )

                tmdb_detail = await tmdb_client.get_detail(match_id, item.media_type)
                metadata = tmdb_client.to_media_metadata(tmdb_detail, item.media_type)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500:
                logger.error(f"[ScrapeItem] TMDb API returned 500 error: {e}")
                raise ScraperError(search_title or item.title, f"TMDb 服务器错误 (500): {str(e)[:100]}")
            elif e.response.status_code == 401:
                raise ScraperError(search_title or item.title, "TMDb API 密钥无效或已过期")
            elif e.response.status_code == 404:
                raise ScraperError(search_title or item.title, f"TMDb 未找到相关资源 (404)")
            else:
                raise ScraperError(search_title or item.title, f"TMDb 请求失败 ({e.response.status_code}): {str(e)[:100]}")

        # ── 安全检查：标题差异过大时保留原始标题 ──
        original_name = request.title or item.title
        scraped_title = metadata.get("title", "")
        is_safe, reason = check_scrape_title_safety(original_name, scraped_title)
        if not is_safe:
            logger.warning(
                f"Scrape title mismatch for item {item.id} ({item.title}): {reason}. "
                f"Keeping original title '{original_name}' instead of '{scraped_title}'"
            )
            metadata["title"] = original_name  # 保留原始标题

        # ── 第二步：豆瓣补充 ──
        try:
            douban = get_douban_client()
            if douban.is_configured():
                metadata = await douban.enrich_metadata(metadata, item.media_type)
                logger.info(f"Douban enrichment completed for '{item.title}'")
        except Exception as e:
            logger.warning(f"Douban enrichment skipped for '{item.title}': {e}")

        # ── 第三步：Bangumi 补充（主要用于动漫）──
        if item.media_type in ("tv", "anime"):
            try:
                bangumi = get_bangumi_client()
                if bangumi.is_configured():
                    metadata = await bangumi.enrich_metadata(metadata, item.media_type)
                    logger.info(f"Bangumi enrichment completed for '{item.title}'")
            except Exception as e:
                logger.warning(f"Bangumi enrichment skipped for '{item.title}': {e}")

        # ── 写入数据库 ──
        update_fields: dict[str, Any] = {
            "tmdb_id": metadata.get("tmdb_id"),
            "title": metadata.get("title", item.title),
            "original_title": metadata.get("original_title"),
            "year": metadata.get("year"),
            "overview": metadata.get("overview"),
            "poster_url": metadata.get("poster_url"),
            "backdrop_url": metadata.get("backdrop_url"),
            "rating": metadata.get("rating", 0),
            "douban_rating": metadata.get("douban_rating"),
            "bangumi_rating": metadata.get("bangumi_rating"),
            "genres": json.dumps(metadata.get("genres") or []),
            "duration": metadata.get("duration") or item.duration,
            "scraped": True,
        }

        # 保存豆瓣/Bangumi ID
        if metadata.get("douban_id"):
            update_fields["douban_id"] = metadata["douban_id"]
        if metadata.get("bangumi_id"):
            update_fields["bangumi_id"] = metadata["bangumi_id"]

        await self.repo.update_item(item_id, **update_fields)

        return await self.get_item_detail(item_id)

    async def search_tmdb(
        self, query: str, media_type: str = "movie", page: int = 1
    ) -> dict:
        """搜索 TMDb（前端用，不写入数据库）"""
        from app.system.api_config_service import ApiConfigService
        from app.media.scraper import TMDbClient

        api_config_service = ApiConfigService(self.db)
        tmdb_config = await api_config_service.get_effective_config("tmdb")

        tmdb_api_key = tmdb_config.get("api_key", "")
        tmdb_base_url = tmdb_config.get("base_url") or None

        if not tmdb_api_key:
            return {"results": [], "error": "TMDb API 密钥未配置"}

        client = TMDbClient(
            custom_api_key=tmdb_api_key,
            custom_base_url=tmdb_base_url,
        )
        results = await client.search(query, media_type)
        return {
            "results": results,
            "total": len(results),
            "page": page,
        }

    # ── 统计 ──
    async def get_stats(self) -> dict:
        return await self.repo.get_stats()

    # ── 删除 ──
    async def delete_item(self, item_id: int):
        item = await self.repo.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("MediaItem", item_id)
        await self.repo.delete_item(item_id)

    # ── 重复检测 ──
    async def compute_file_hashes(self, library_id: int, limit: int = 100) -> dict:
        """
        计算媒体库文件的哈希值（用于重复检测）

        Args:
            library_id: 媒体库 ID
            limit: 每次处理的最大文件数（0 表示全部）

        Returns:
            {"computed": 成功计算数, "total": 总条目数, "skipped": 跳过数}
        """
        from app.media.duplicate import calculate_file_hash, HASH_ALGORITHM

        items = await self.repo.get_all_items(library_id)
        if limit > 0:
            items = items[:limit]

        computed = 0
        skipped = 0

        for item in items:
            # 跳过已有哈希的
            if item.file_hash:
                skipped += 1
                continue

            # 计算哈希
            file_hash = await calculate_file_hash(item.file_path)
            if file_hash:
                await self.repo.update_item(item.id, file_hash=file_hash)
                computed += 1

                # 每 10 个提交一次
                if computed % 10 == 0:
                    logger.debug(f"Hashed {computed} files...")

        logger.info(f"File hash computation completed: {computed} computed, {skipped} skipped")
        return {
            "computed": computed,
            "total": len(items),
            "skipped": skipped,
        }

    async def detect_duplicates(self, library_id: int | None = None) -> dict:
        """
        检测并标记重复文件

        Args:
            library_id: 媒体库 ID（None 表示所有库）

        Returns:
            检测结果字典
        """
        from app.media.duplicate import detect_duplicates

        return await detect_duplicates(self.repo.db, library_id)

    async def unmark_duplicates(self, library_id: int | None = None) -> int:
        """
        取消重复标记

        Args:
            library_id: 媒体库 ID（None 表示所有库）

        Returns:
            取消标记的条目数
        """
        from app.media.duplicate import unmark_duplicates

        return await unmark_duplicates(self.repo.db, library_id)

    async def get_duplicates(self, library_id: int | None = None) -> list[dict]:
        """
        获取重复文件列表

        Args:
            library_id: 媒体库 ID（None 表示所有库）

        Returns:
            重复组列表
        """
        from sqlalchemy import select, and_
        from app.media.models import MediaItem

        # 查询所有重复项
        stmt = select(MediaItem).where(MediaItem.is_duplicate == True)
        if library_id:
            stmt = stmt.where(MediaItem.library_id == library_id)

        result = await self.repo.db.execute(stmt)
        duplicates = result.scalars().all()

        # 按 duplicate_of 分组
        groups = {}
        for item in duplicates:
            primary_id = item.duplicate_of
            if primary_id not in groups:
                # 获取主条目信息
                primary = await self.repo.get_item_by_id(primary_id)
                groups[primary_id] = {
                    "primary_id": primary_id,
                    "primary_title": primary.title if primary else "Unknown",
                    "primary_path": primary.file_path if primary else "",
                    "duplicates": [],
                }
            groups[primary_id]["duplicates"].append({
                "id": item.id,
                "title": item.title,
                "path": item.file_path,
                "file_size": item.file_size,
            })

        return list(groups.values())
