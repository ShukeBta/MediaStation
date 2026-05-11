"""
管理后台服务
"""
import logging
import os
import pathlib
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.admin.schemas import *
from app.common.schemas import PathValidator
from app.config import get_settings
from app.database import async_session_factory
from app.media.repository import MediaRepository
from app.media.service import MediaService
from app.system.events import get_event_bus

logger = logging.getLogger(__name__)


class AdminService:
    """管理后台服务"""

    def __init__(self):
        self.settings = get_settings()

    # ── 定时任务 ──

    async def list_tasks(self) -> list[TaskResponse]:
        """列出所有定时任务"""
        from app.system.scheduler import get_scheduler

        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()

        tasks = []
        for job in jobs:
            task_type = self._parse_task_type(job.name)
            tasks.append(TaskResponse(
                id=job.id,
                name=job.name,
                type=task_type,
                schedule=self._format_trigger(job.trigger),
                next_run=job.next_run_time,
                enabled=job.next_run_time is not None,
                status="running" if hasattr(job, 'running') and job.running else "idle",
            ))

        return tasks

    async def create_task(self, data: TaskCreate) -> TaskResponse:
        """创建定时任务"""
        from app.system.scheduler import get_scheduler

        scheduler = get_scheduler()

        # 解析触发器
        trigger = self._parse_schedule(data.schedule)

        # 创建任务
        job = scheduler.add_job(
            func=self._get_task_func(data.type),
            trigger=trigger,
            id=f"task_{data.name}_{datetime.now().timestamp()}",
            name=data.name,
            replace_existing=True,
        )

        return TaskResponse(
            id=job.id,
            name=job.name,
            type=data.type,
            schedule=data.schedule,
            next_run=job.next_run_time,
            enabled=data.enabled,
            status="idle",
        )

    async def update_task(self, task_id: str, data: TaskUpdate) -> TaskResponse:
        """更新定时任务"""
        from app.system.scheduler import get_scheduler

        scheduler = get_scheduler()
        job = scheduler.get_job(task_id)

        if not job:
            raise ValueError(f"Task not found: {task_id}")

        # 更新任务
        if data.name is not None:
            job.modify(name=data.name)
        if data.schedule is not None:
            trigger = self._parse_schedule(data.schedule)
            job.reschedule(trigger)
        if data.enabled is not None:
            if data.enabled:
                job.resume()
            else:
                job.pause()

        return TaskResponse(
            id=job.id,
            name=job.name,
            type=self._parse_task_type(job.name),
            schedule=self._format_trigger(job.trigger),
            next_run=job.next_run_time,
            enabled=job.next_run_time is not None,
            status="idle",
        )

    async def delete_task(self, task_id: str):
        """删除定时任务"""
        from app.system.scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.remove_job(task_id)

    async def run_task_now(self, task_id: str):
        """立即执行任务"""
        from app.system.scheduler import get_scheduler

        scheduler = get_scheduler()
        job = scheduler.get_job(task_id)

        if not job:
            raise ValueError(f"Task not found: {task_id}")

        # 在后台运行任务
        job.modify(next_run_time=None)
        scheduler.add_job(
            func=job.func,
            trigger=IntervalTrigger(seconds=1),
            id=f"one_time_{job.id}",
            name=f"{job.name}_now",
            replace_existing=True,
        )

        return {"message": f"Task {job.name} started", "task_id": task_id}

    # ── 批量操作 ──

    async def batch_scan(self, data: BatchScanRequest) -> BatchOperationResult:
        """批量扫描媒体库"""
        started = []
        errors = []

        event_bus = get_event_bus()

        for library_id in data.library_ids:
            try:
                async with async_session_factory() as db:
                    service = MediaService(MediaRepository(db), event_bus)
                    await service.scan_library(library_id, auto_scrape=False)
                    started.append(library_id)
            except Exception as e:
                logger.error(f"Batch scan failed for library {library_id}: {e}")
                errors.append({"id": library_id, "error": str(e)})

        return BatchOperationResult(
            message="Batch scan completed",
            started=started,
            errors=errors,
            total=len(data.library_ids),
            success_count=len(started),
            error_count=len(errors),
        )

    async def batch_scrape(self, data: BatchScrapeRequest) -> BatchOperationResult:
        """批量刮削元数据"""
        started = []
        errors = []

        event_bus = get_event_bus()

        for media_id in data.media_ids:
            try:
                async with async_session_factory() as db:
                    service = MediaService(MediaRepository(db), event_bus)
                    from app.media.schemas import ScrapeRequest
                    await service.scrape_item(media_id, ScrapeRequest())
                    started.append(media_id)
            except Exception as e:
                logger.error(f"Batch scrape failed for media {media_id}: {e}")
                errors.append({"id": media_id, "error": str(e)})

        return BatchOperationResult(
            message="Batch scrape completed",
            started=started,
            errors=errors,
            total=len(data.media_ids),
            success_count=len(started),
            error_count=len(errors),
        )

    async def batch_delete(self, data: BatchDeleteRequest) -> BatchOperationResult:
        """批量删除媒体"""
        deleted = []
        errors = []

        event_bus = get_event_bus()

        for media_id in data.media_ids:
            try:
                async with async_session_factory() as db:
                    service = MediaService(MediaRepository(db), event_bus)
                    await service.delete_item(media_id, force=data.force)
                    deleted.append(media_id)
            except Exception as e:
                logger.error(f"Batch delete failed for media {media_id}: {e}")
                errors.append({"id": media_id, "error": str(e)})

        return BatchOperationResult(
            message="Batch delete completed",
            started=deleted,
            errors=errors,
            total=len(data.media_ids),
            success_count=len(deleted),
            error_count=len(errors),
        )

    async def batch_move(self, data: BatchMoveRequest) -> BatchOperationResult:
        """批量移动媒体"""
        moved = []
        errors = []

        for media_id in data.media_ids:
            try:
                async with async_session_factory() as db:
                    repo = MediaRepository(db)
                    await repo.move_to_library(media_id, data.target_library_id)
                    moved.append(media_id)
            except Exception as e:
                logger.error(f"Batch move failed for media {media_id}: {e}")
                errors.append({"id": media_id, "error": str(e)})

        return BatchOperationResult(
            message="Batch move completed",
            started=moved,
            errors=errors,
            total=len(data.media_ids),
            success_count=len(moved),
            error_count=len(errors),
        )

    # ── 系统设置 ──

    async def get_settings(self) -> SystemSettings:
        """获取系统设置"""
        return SystemSettings(
            app_name=self.settings.app_name,
            version="0.1.0",
            enable_gpu=self.settings.hw_accel is not None,
            max_transcode=self.settings.max_transcode_jobs,
            transcode_enabled=self.settings.transcode_enabled,
            cache_path=str(self.settings.cache_dir),
            data_path=str(self.settings.data_dir),
            tmdb_configured=bool(self.settings.tmdb_api_key),
            adult_enabled=True,
            max_upload_size=1024 * 1024 * 1024,
        )

    async def update_settings(self, data: SystemSettingsUpdate) -> SystemSettings:
        """更新系统设置"""
        # TODO: 实现设置更新逻辑
        # 注意：某些设置需要重启才能生效
        return await self.get_settings()

    # ── 系统统计 ──

    async def get_stats(self) -> AdminStatsResponse:
        """获取系统统计"""
        import psutil

        # 媒体统计
        async with async_session_factory() as db:
            repo = MediaRepository(db)
            media_stats = await repo.get_stats()

        # 用户统计
        from app.user.models import User
        from sqlalchemy import select, func
        async with async_session_factory() as db:
            result = await db.execute(select(func.count(User.id)))
            user_count = result.scalar() or 0

        # 下载统计
        download_count = 0  # TODO: 实现下载统计

        # 订阅统计
        subscription_count = 0  # TODO: 实现订阅统计

        # 系统统计
        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage("/").percent
        except Exception:
            cpu_percent = memory_percent = disk_percent = 0

        return AdminStatsResponse(
            media=MediaStats(
                total=media_stats.get("total", 0),
                movies=media_stats.get("movies", 0),
                tv_shows=media_stats.get("tv_shows", 0),
                episodes=media_stats.get("episodes", 0),
                total_size=media_stats.get("total_size", 0),
            ),
            system=SystemStats(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                uptime=self._get_uptime(),
            ),
            users=user_count,
            downloads=download_count,
            subscriptions=subscription_count,
            timestamp=datetime.now(),
        )

    # ── 内容分级 ──

    async def get_content_rating(self) -> ContentRatingResponse:
        """获取内容分级配置"""
        return ContentRatingResponse(
            enabled=True,
            default_level="R18",
            allowed_levels=["General", "R15", "R18"],
        )

    async def update_content_rating(self, data: ContentRatingUpdate) -> ContentRatingResponse:
        """更新内容分级配置"""
        # TODO: 实现内容分级更新
        return await self.get_content_rating()

    # ── 文件浏览 ──

    async def browse_files(self, path: str = ".") -> BrowseResponse:
        """浏览目录"""

        # 安全检查
        if not self._is_safe_path(path):
            raise ValueError("Path not allowed")

        path = pathlib.Path(path).resolve()

        if not path.exists():
            raise ValueError("Path not found")

        items = []
        parent = str(path.parent) if path.parent != path else None

        try:
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    stat = item.stat()
                    items.append(FileItem(
                        name=item.name,
                        path=str(item),
                        is_dir=item.is_dir(),
                        size=stat.st_size if item.is_file() else None,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        permissions=oct(stat.st_mode)[-3:],
                    ))
                except PermissionError:
                    continue
        except PermissionError:
            raise ValueError("Permission denied")

        return BrowseResponse(
            current=str(path),
            parent=parent,
            items=items,
        )

    async def create_directory(self, path: str) -> FileItem:
        """创建目录"""

        if not self._is_safe_path(path):
            raise ValueError("Path not allowed")

        pathlib.Path(path).mkdir(parents=True, exist_ok=True)
        stat = pathlib.Path(path).stat()

        return FileItem(
            name=pathlib.Path(path).name,
            path=path,
            is_dir=True,
            modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def rename_file(self, path: str, new_name: str) -> FileItem:
        """重命名文件"""

        if not self._is_safe_path(path):
            raise ValueError("Path not allowed")

        old_path = pathlib.Path(path)
        new_path = old_path.parent / new_name

        if new_path.exists():
            raise ValueError("Target already exists")

        new_path = old_path.rename(new_path)
        stat = new_path.stat()

        return FileItem(
            name=new_path.name,
            path=str(new_path),
            is_dir=new_path.is_dir(),
            size=stat.st_size if new_path.is_file() else None,
            modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def delete_file(self, path: str, force: bool = False) -> dict:
        """删除文件"""
        import shutil

        if not self._is_safe_path(path):
            raise ValueError("Path not allowed")

        p = pathlib.Path(path)

        if not p.exists():
            raise ValueError("File not found")

        if p.is_dir():
            if force:
                shutil.rmtree(p)
            else:
                p.rmdir()
        else:
            p.unlink()

        return {"message": f"Deleted: {path}", "success": True}

    async def move_file(self, path: str, target: str) -> FileItem:
        """移动文件"""
        import shutil

        if not self._is_safe_path(path) or not self._is_safe_path(target):
            raise ValueError("Path not allowed")

        src = pathlib.Path(path)
        dst = pathlib.Path(target)

        if not src.exists():
            raise ValueError("Source not found")

        if dst.exists():
            raise ValueError("Target already exists")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        stat = dst.stat()
        return FileItem(
            name=dst.name,
            path=str(dst),
            is_dir=dst.is_dir(),
            size=stat.st_size if dst.is_file() else None,
            modified=datetime.fromtimestamp(stat.st_mtime),
        )

    # ── 批量收藏/已看 ──

    async def batch_favorite(self, data) -> BatchOperationResult:
        """批量收藏/取消收藏"""
        from app.user.models import Favorite
        
        success = []
        errors = []
        
        for media_id in data.media_ids:
            try:
                async with async_session_factory() as db:
                    from sqlalchemy import select, delete
                    
                    if data.action == "add":
                        # 添加收藏
                        fav = Favorite(user_id=1, media_item_id=media_id)  # TODO: 使用实际 user_id
                        db.add(fav)
                    else:
                        # 移除收藏
                        await db.execute(
                            delete(Favorite).where(
                                Favorite.media_item_id == media_id
                            )
                        )
                    await db.commit()
                    success.append(media_id)
            except Exception as e:
                logger.error(f"Batch favorite failed for media {media_id}: {e}")
                errors.append({"id": media_id, "error": str(e)})
        
        return BatchOperationResult(
            message=f"Batch favorite {data.action} completed",
            started=success,
            errors=errors,
            total=len(data.media_ids),
            success_count=len(success),
            error_count=len(errors),
        )

    async def batch_watched(self, data) -> BatchOperationResult:
        """批量标记已看/未看"""
        success = []
        errors = []
        
        for media_id in data.media_ids:
            try:
                async with async_session_factory() as db:
                    from app.user.models import WatchHistory
                    from sqlalchemy import select, delete, update
                    
                    if data.action == "mark":
                        # 标记为已看
                        history = WatchHistory(
                            user_id=1,  # TODO: 使用实际 user_id
                            media_item_id=media_id,
                            progress=100,
                            duration=0,
                        )
                        db.add(history)
                    else:
                        # 标记为未看
                        await db.execute(
                            delete(WatchHistory).where(
                                WatchHistory.media_item_id == media_id
                            )
                        )
                    await db.commit()
                    success.append(media_id)
            except Exception as e:
                logger.error(f"Batch watched failed for media {media_id}: {e}")
                errors.append({"id": media_id, "error": str(e)})
        
        return BatchOperationResult(
            message=f"Batch watched {data.action} completed",
            started=success,
            errors=errors,
            total=len(data.media_ids),
            success_count=len(success),
            error_count=len(errors),
        )

    # ── 文件重命名预览 ──

    async def preview_rename(self, path: str, new_name: str) -> dict:
        """预览重命名结果"""
        
        p = pathlib.Path(path)
        if not p.exists():
            raise ValueError("File not found")
        
        new_path = p.parent / new_name
        result = {
            "original": str(p),
            "renamed": str(new_path),
            "exists": new_path.exists(),
            "warning": None,
        }
        
        if result["exists"]:
            result["warning"] = "Target file already exists, will be overwritten"
        
        return result

    async def batch_rename_preview(self, operations: list) -> BatchOperationResult:
        """批量重命名预览"""
        from app.admin.schemas import FileRenamePreview
        
        started = []
        errors = []
        
        for op in operations:
            try:
                p = pathlib.Path(op.path)
                new_path = p.parent / op.new_name
                
                started.append({
                    "original": op.path,
                    "renamed": str(new_path),
                    "exists": new_path.exists(),
                })
            except Exception as e:
                errors.append({"path": op.path, "error": str(e)})
        
        return BatchOperationResult(
            message="Batch rename preview generated",
            started=[],  # 预览模式不返回实际数据
            errors=errors,
            total=len(operations),
            success_count=len(started),
            error_count=len(errors),
        )

    async def batch_rename_execute(self, operations: list) -> BatchOperationResult:
        """批量重命名执行"""
        
        success = []
        errors = []
        
        for op in operations:
            try:
                p = pathlib.Path(op.path)
                new_path = p.parent / op.new_name
                
                if new_path.exists():
                    raise ValueError(f"Target already exists: {new_path}")
                
                p.rename(new_path)
                success.append(op.path)
            except Exception as e:
                logger.error(f"Batch rename failed for {op.path}: {e}")
                errors.append({"path": op.path, "error": str(e)})
        
        return BatchOperationResult(
            message="Batch rename completed",
            started=success,
            errors=errors,
            total=len(operations),
            success_count=len(success),
            error_count=len(errors),
        )

    async def batch_scrape_files(self, paths: list[str]) -> BatchOperationResult:
        """批量刮削文件"""
        from app.media.scanner import MediaScanner
        from app.media.repository import MediaRepository
        
        success = []
        errors = []
        
        event_bus = get_event_bus()
        
        for path in paths:
            try:
                async with async_session_factory() as db:
                    repo = MediaRepository(db)
                    scanner = MediaScanner(repo, event_bus)
                    
                    # 扫描文件并入库
                    await scanner.scan_file(path)
                    success.append(path)
            except Exception as e:
                logger.error(f"Batch scrape failed for {path}: {e}")
                errors.append({"path": path, "error": str(e)})
        
        return BatchOperationResult(
            message="Batch scrape completed",
            started=success,
            errors=errors,
            total=len(paths),
            success_count=len(success),
            error_count=len(errors),
        )

    async def get_media_folders(self) -> list[str]:
        """获取文件管理器可浏览的根目录列表
        
        优先级：
        1. 用户通过 MEDIA_DIRS 环境变量配置的目录
        2. 数据库中已创建的媒体库路径（MediaLibrary.path）
        3. 回退到 data_dir 下的默认媒体子目录
        """
        folders: list[str] = []
        seen: set[str] = set()

        def _add(p: str) -> None:
            resolved = str(pathlib.Path(p).resolve())
            if resolved not in seen:
                seen.add(resolved)
                folders.append(resolved)

        # 1. MEDIA_DIRS 环境变量配置的目录（用户明确指定）
        if self.settings.media_dirs_env.strip():
            for raw in self.settings.media_dirs_env.split(","):
                raw = raw.strip()
                if raw:
                    _add(raw)

        # 2. 数据库中已有的媒体库路径
        try:
            from app.media.models import MediaLibrary
            from sqlalchemy import select
            async with async_session_factory() as db:
                result = await db.execute(
                    select(MediaLibrary.path).where(MediaLibrary.enabled == True)
                )
                for (lib_path,) in result.fetchall():
                    if lib_path:
                        _add(lib_path)
        except Exception as e:
            logger.warning(f"Failed to load media library paths from DB: {e}")

        # 3. 如果以上均无结果，回退到 config.media_dirs（默认子目录或 MEDIA_DIRS 解析结果）
        if not folders:
            for d in self.settings.media_dirs:
                _add(str(d))

        return folders

    # ── AI 重命名 ──

    async def ai_rename_files(self, data: "AIRenameRequest") -> "AIRenameResponse":
        """
        AI 生成重命名建议

        对每个文件调用 LLM 分析文件名，返回规范化的媒体文件名建议。
        仅生成建议，不执行实际重命名。
        """
        import json
        import httpx

        from app.admin.schemas import AIRenameCandidate, AIRenameResponse

        # 获取 AI 配置：优先 api_config_service，回退到 settings 环境变量
        api_key, base_url, model = await self._get_ai_config()

        if not api_key:
            raise RuntimeError(
                "AI 服务未配置，请在「设置 → API 配置」中配置 OpenAI/硅基流动/DeepSeek 的 API Key"
            )

        candidates: list[AIRenameCandidate] = []
        total_tokens = 0

        # 构建系统提示
        style_hints = {
            "media": "使用媒体行业规范格式，如 Movie.Name.2023.1080p.BluRay.mkv 或 Show.Name.S01E01.Episode.Title.720p.mp4",
            "clean": "使用简洁可读格式，如「电影名 (2023).mkv」或「剧集名 S01E01.mkv」",
            "original": "尽量保留原始文件名结构，只修正明显错误",
        }
        lang_hints = {
            "zh": "优先使用中文标题（如果有对应中文名），中英混排时使用点号分隔",
            "en": "使用英文标题，遵循英文媒体命名惯例",
        }

        system_prompt = f"""你是一个专业的媒体文件命名助手。
用户会提供媒体文件名，你需要分析并生成规范化的新文件名建议。

命名风格：{style_hints.get(data.style, style_hints['media'])}
语言偏好：{lang_hints.get(data.language, lang_hints['zh'])}
{f'补充提示：{data.extra_hint}' if data.extra_hint else ''}

输出格式（严格 JSON，不要 markdown 代码块）：
{{
  "suggested_name": "建议的文件名（含扩展名）",
  "confidence": 0.95,
  "reason": "简短说明，如：识别为电影《xxx》(2023)，补充年份和分辨率"
}}

规则：
- 保留原始扩展名（.mkv/.mp4/.avi 等）
- 如果无法识别媒体信息，设 confidence < 0.5 并在 reason 中说明
- 不要在 reason 中使用换行符
"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            for file_path in data.paths:
                p = pathlib.Path(file_path)
                original_name = p.name
                parent_dir = str(p.parent)

                try:
                    user_content = f"文件名：{original_name}"

                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "max_tokens": 256,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    }

                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }

                    resp = await client.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    resp_data = resp.json()

                    # 解析 AI 结果
                    choice = resp_data.get("choices", [{}])[0]
                    ai_text = choice.get("message", {}).get("content", "{}")
                    usage = resp_data.get("usage", {})
                    total_tokens += usage.get("total_tokens", 0)

                    try:
                        ai_result = json.loads(ai_text)
                    except json.JSONDecodeError:
                        import re
                        match = re.search(r'\{.*?\}', ai_text, re.DOTALL)
                        ai_result = json.loads(match.group()) if match else {}

                    suggested_name = ai_result.get("suggested_name", original_name)
                    confidence = float(ai_result.get("confidence", 0.5))
                    reason = ai_result.get("reason", "")

                    # 安全检查：确保扩展名不变
                    orig_ext = p.suffix.lower()
                    sug_p = pathlib.Path(suggested_name)
                    if sug_p.suffix.lower() != orig_ext and orig_ext:
                        suggested_name = sug_p.stem + orig_ext

                    suggested_path = str(pathlib.Path(parent_dir) / suggested_name)
                    exists = pathlib.Path(suggested_path).exists() and suggested_path != file_path

                    candidates.append(AIRenameCandidate(
                        original=original_name,
                        original_path=file_path,
                        suggested=suggested_name,
                        suggested_path=suggested_path,
                        confidence=confidence,
                        reason=reason,
                        exists=exists,
                    ))

                except httpx.HTTPStatusError as e:
                    logger.error(f"AI rename HTTP error for {original_name}: {e.response.status_code}")
                    candidates.append(AIRenameCandidate(
                        original=original_name,
                        original_path=file_path,
                        suggested=original_name,
                        suggested_path=file_path,
                        confidence=0.0,
                        reason="",
                        exists=False,
                        error=f"HTTP {e.response.status_code}: AI 服务请求失败",
                    ))
                except Exception as e:
                    logger.error(f"AI rename error for {original_name}: {e}")
                    candidates.append(AIRenameCandidate(
                        original=original_name,
                        original_path=file_path,
                        suggested=original_name,
                        suggested_path=file_path,
                        confidence=0.0,
                        reason="",
                        exists=False,
                        error=str(e),
                    ))

        success_count = sum(1 for c in candidates if not c.error)
        failed_count = len(candidates) - success_count

        return AIRenameResponse(
            total=len(candidates),
            success=success_count,
            failed=failed_count,
            candidates=candidates,
            model_used=model,
            tokens_used=total_tokens,
        )

    async def _get_ai_config(self) -> tuple[str, str, str]:
        """
        获取 AI 配置（api_key, base_url, model）
        优先从 api_config_service 读取，回退到 settings 环境变量
        """
        api_key = ""
        base_url = "https://api.openai.com/v1"
        model = "gpt-4o-mini"

        # 优先读取 api_config_service（数据库配置）
        try:
            from app.database import async_session_factory
            from app.system.api_config_service import ApiConfigService

            # 按优先级依次尝试 AI 提供商
            providers_priority = ["openai", "siliconflow", "deepseek"]

            async with async_session_factory() as db:
                svc = ApiConfigService(db)
                for provider in providers_priority:
                    cfg = await svc.get_config_full(provider)
                    if cfg and cfg.api_key and cfg.enabled:
                        api_key = cfg.api_key
                        if cfg.base_url:
                            base_url = cfg.base_url
                        else:
                            # 已知 provider 的默认地址
                            defaults = {
                                "siliconflow": "https://api.siliconflow.cn/v1",
                                "deepseek": "https://api.deepseek.com/v1",
                                "openai": "https://api.openai.com/v1",
                            }
                            base_url = defaults.get(provider, base_url)
                        # 模型偏好
                        model_defaults = {
                            "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
                            "deepseek": "deepseek-chat",
                            "openai": "gpt-4o-mini",
                        }
                        model = model_defaults.get(provider, model)
                        logger.info(f"AI rename using provider: {provider}, model: {model}")
                        break
        except Exception as e:
            logger.warning(f"Failed to load AI config from database: {e}")

        # 回退：使用 settings 环境变量
        if not api_key:
            api_key = getattr(self.settings, "openai_api_key", "") or ""
            env_base_url = getattr(self.settings, "openai_base_url", "")
            env_model = getattr(self.settings, "openai_model", "")
            if env_base_url:
                base_url = env_base_url
            if env_model:
                model = env_model

        return api_key, base_url, model

    def _parse_task_type(self, name: str) -> str:
        """解析任务类型"""
        name_lower = name.lower()
        if "scan" in name_lower:
            return "scan"
        elif "scrape" in name_lower:
            return "scrape"
        elif "cleanup" in name_lower:
            return "cleanup"
        elif "backup" in name_lower:
            return "backup"
        return "unknown"

    def _parse_schedule(self, schedule: str):
        """解析 Cron 表达式"""
        # 支持简写格式
        shortcuts = {
            "@hourly": "0 * * * *",
            "@daily": "0 0 * * *",
            "@weekly": "0 0 * * 0",
            "@monthly": "0 0 1 * *",
        }

        if schedule in shortcuts:
            schedule = shortcuts[schedule]

        parts = schedule.split()
        if len(parts) == 5:
            return CronTrigger.from_crontab(schedule)
        elif len(parts) == 1 and schedule.startswith("@every"):
            minutes = int(schedule.split()[1].rstrip("m"))
            return IntervalTrigger(minutes=minutes)

        raise ValueError(f"Invalid schedule: {schedule}")

    def _format_trigger(self, trigger) -> str:
        """格式化触发器"""
        if isinstance(trigger, CronTrigger):
            return trigger.to_crontab()
        elif isinstance(trigger, IntervalTrigger):
            seconds = trigger.interval.total_seconds()
            if seconds >= 3600:
                return f"@every {int(seconds / 3600)}h"
            elif seconds >= 60:
                return f"@every {int(seconds / 60)}m"
            return f"@every {int(seconds)}s"
        return str(trigger)

    def _get_task_func(self, task_type: str):
        """获取任务函数"""
        from app.system.scheduler import run_scheduler_task

        task_map = {
            "scan": "run_scan",
            "scrape": "run_scrape",
            "cleanup": "run_cleanup",
            "backup": "run_backup",
        }

        return run_scheduler_task

    def _get_uptime(self) -> str:
        """获取运行时间"""
        import time
        uptime_seconds = int(time.time() - getattr(self, '_start_time', time.time()))
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m {seconds}s"

    def _is_safe_path(self, path: str) -> bool:
        """检查路径安全性（委托给 PathValidator，与 router 层保持一致）"""
        validator = PathValidator(
            media_dirs=[str(d) for d in self.settings.media_dirs],
            data_dir=self.settings.data_dir,
        )
        safe, _ = validator.is_safe(path)
        return safe
