"""
实时文件监控模块
使用 watchdog 监控媒体库目录的文件变化，
自动触发增量扫描。
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Set

from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
)
from watchdog.observers import Observer

from app.common import safe_create_task
from app.media.scanner import VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS

logger = logging.getLogger(__name__)

# 文件变化去重时间窗口（秒）
DEBOUNCE_SECONDS = 2.0


class MediaWatchHandler(FileSystemEventHandler):
    """
    媒体库文件变化处理器

    监控：
    - 视频文件创建/修改（触发扫描）
    - 字幕文件创建/修改（触发字幕扫描）
    - 目录创建（递归监控）
    - 目录删除（从数据库删除）
    """

    def __init__(
        self,
        library_id: int,
        library_path: str,
        on_change: Callable[[str, str, str], None] | None = None,
    ):
        """
        Args:
            library_id: 媒体库 ID
            library_path: 媒体库根路径
            on_change: 变化回调函数 (event_type, path, library_id)
        """
        super().__init__()
        self.library_id = library_id
        self.library_path = Path(library_path).resolve()
        self.on_change = on_change

        # 跟踪待处理的文件变化（去重）
        self._pending_events: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    def _should_process(self, path: str) -> bool:
        """判断路径是否应该处理"""
        p = Path(path)
        ext = p.suffix.lower()

        # 只处理视频和字幕文件
        is_video = ext in VIDEO_EXTENSIONS
        is_subtitle = ext in SUBTITLE_EXTENSIONS

        return is_video or is_subtitle

    def _schedule_event(self, path: str, event_type: str):
        """调度事件处理（带去重）"""
        # 使用安全包装器，防止事件处理异常静默崩溃
        safe_create_task(
            self._process_event(path, event_type),
            name=f"watcher_event_{event_type}"
        )

    async def _process_event(self, path: str, event_type: str):
        """处理文件变化事件"""
        now = datetime.now()

        async with self._lock:
            # 去重检查
            last_time = self._pending_events.get(path)
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < DEBOUNCE_SECONDS:
                    logger.debug(f"Debounce: {event_type} for {path}")
                    return

            self._pending_events[path] = now

        # 清理旧事件
        await self._cleanup_old_events()

        # 触发回调
        if self.on_change:
            try:
                if asyncio.iscoroutinefunction(self.on_change):
                    await self.on_change(event_type, path, self.library_id)
                else:
                    self.on_change(event_type, path, self.library_id)
            except Exception as e:
                logger.error(f"Watch handler error for {path}: {e}")

        logger.info(f"File watch: {event_type} - {path}")

    async def _cleanup_old_events(self):
        """清理过期的去重记录"""
        now = datetime.now()
        expired = [
            path for path, t in self._pending_events.items()
            if (now - t).total_seconds() > DEBOUNCE_SECONDS * 2
        ]
        for path in expired:
            self._pending_events.pop(path, None)

    def on_created(self, event: FileSystemEvent):
        """文件/目录创建"""
        path = str(event.src_path)

        # 检查是否是应该监控的文件
        if not event.is_directory and not self._should_process(path):
            return

        # 递归监控新目录
        if isinstance(event, DirCreatedEvent):
            logger.debug(f"New directory: {path}")

        event_type = "created"
        self._schedule_event(path, event_type)

    def on_modified(self, event: FileSystemEvent):
        """文件修改"""
        if event.is_directory:
            return

        path = str(event.src_path)
        if not self._should_process(path):
            return

        self._schedule_event(path, "modified")

    def on_deleted(self, event: FileSystemEvent):
        """文件/目录删除"""
        if event.is_directory:
            return

        path = str(event.src_path)
        if not self._should_process(path):
            return

        self._schedule_event(path, "deleted")

    def on_moved(self, event: FileSystemEvent):
        """文件移动"""
        if event.is_directory:
            return

        path = str(event.dest_path)
        if not self._should_process(path):
            return

        # 移动 = 删除旧 + 创建新
        self._schedule_event(str(event.src_path), "deleted")
        self._schedule_event(path, "created")


class MediaWatcher:
    """
    媒体库文件监控器

    使用 watchdog 监控多个媒体库目录，
    自动触发增量扫描。
    """

    def __init__(self):
        self._observers: dict[int, Observer] = {}  # library_id -> Observer
        self._handlers: dict[int, MediaWatchHandler] = {}  # library_id -> Handler
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    def start(self, libraries: list[dict]):
        """
        启动文件监控

        Args:
            libraries: 媒体库列表 [{"id": int, "path": str, "enabled": bool}]
        """
        if self._running:
            logger.warning("Watcher already running")
            return

        self._running = True
        self._loop = asyncio.get_event_loop()

        for lib in libraries:
            if not lib.get("enabled", True):
                continue

            lib_id = lib["id"]
            lib_path = lib["path"]

            if not os.path.exists(lib_path):
                logger.warning(f"Library path not found: {lib_path}")
                continue

            self._add_watch(lib_id, lib_path)

        logger.info(f"MediaWatcher started, monitoring {len(self._observers)} libraries")

    def stop(self):
        """停止文件监控"""
        if not self._running:
            return

        for lib_id, observer in list(self._observers.items()):
            try:
                observer.stop()
                observer.join(timeout=2)
                logger.info(f"Stopped watching library {lib_id}")
            except Exception as e:
                logger.error(f"Error stopping watcher for library {lib_id}: {e}")

        self._observers.clear()
        self._handlers.clear()
        self._running = False

        logger.info("MediaWatcher stopped")

    def add_library(self, library_id: int, library_path: str):
        """动态添加监控目录"""
        if library_id in self._observers:
            logger.warning(f"Library {library_id} already being watched")
            return

        if not os.path.exists(library_path):
            logger.warning(f"Library path not found: {library_path}")
            return

        if not self._running:
            logger.warning("Watcher not running, call start() first")
            return

        self._add_watch(library_id, library_path)

    def remove_library(self, library_id: int):
        """移除监控目录"""
        if library_id not in self._observers:
            return

        observer = self._observers.pop(library_id)
        handler = self._handlers.pop(library_id, None)

        try:
            observer.stop()
            observer.join(timeout=2)
            logger.info(f"Removed library {library_id} from watch")
        except Exception as e:
            logger.error(f"Error removing watcher for library {library_id}: {e}")

    def reload(self, libraries: list[dict]):
        """重新加载所有监控"""
        self.stop()
        self.start(libraries)

    def _add_watch(self, library_id: int, library_path: str):
        """添加监控"""
        try:
            handler = MediaWatchHandler(
                library_id=library_id,
                library_path=library_path,
            )
            observer = Observer()
            observer.schedule(
                handler,
                library_path,
                recursive=True,  # 递归监控子目录
            )
            observer.start()

            self._observers[library_id] = observer
            self._handlers[library_id] = handler

            logger.info(f"Watching library {library_id}: {library_path}")

        except Exception as e:
            logger.error(f"Failed to watch library {library_id}: {e}")


# ── 全局单例 ──
_watcher: MediaWatcher | None = None


def get_watcher() -> MediaWatcher:
    """获取全局文件监控器实例"""
    global _watcher
    if _watcher is None:
        _watcher = MediaWatcher()
    return _watcher


def start_watcher(libraries: list[dict]):
    """启动文件监控"""
    watcher = get_watcher()
    watcher.start(libraries)


def stop_watcher():
    """停止文件监控"""
    watcher = get_watcher()
    watcher.stop()
