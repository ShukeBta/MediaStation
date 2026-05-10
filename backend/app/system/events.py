"""
SSE 事件总线
服务端推送事件，用于前端实时更新（下载进度、扫描进度、通知等）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """进程内事件总线，支持 SSE 推送"""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def emit(self, event_type: str, data: dict[str, Any]):
        """发出事件（线程安全）"""
        message = {"type": event_type, "data": data}
        json_msg = json.dumps(message, ensure_ascii=False, default=str)
        
        # 获取当前的事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行的事件循环，记录警告并返回
            logger.warning("No running event loop, cannot emit event")
            return
        
        def _safe_put(q):
            """线程安全地向队列放入消息"""
            try:
                q.put_nowait(json_msg)
            except asyncio.QueueFull:
                logger.warning("Event queue full, dropping message")
        
        # 使用 call_soon_threadsafe 保证即使外部模块从其他线程调用，也能安全地推入队列
        for queue in self._subscribers.get(event_type, []):
            loop.call_soon_threadsafe(_safe_put, queue)
        
        # 广播到通配符订阅者
        for queue in self._subscribers.get("*", []):
            loop.call_soon_threadsafe(_safe_put, queue)

    def subscribe(
        self, event_types: list[str] | None = None, maxsize: int = 100
    ) -> asyncio.Queue:
        """订阅事件，返回消息队列"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        types = event_types or ["*"]
        for t in types:
            self._subscribers[t].append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """取消订阅"""
        for event_type, queues in self._subscribers.items():
            if queue in queues:
                queues.remove(queue)

    def on(self, event_type: str):
        """事件处理器装饰器"""
        def decorator(func: Callable):
            self._handlers[event_type].append(func)
            return func
        return decorator


# 全局单例
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def event_generator(
    event_types: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """SSE 事件生成器"""
    bus = get_event_bus()
    queue = bus.subscribe(event_types)
    try:
        while True:
            data = await queue.get()
            yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        bus.unsubscribe(queue)
