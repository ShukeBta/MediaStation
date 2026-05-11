"""
SSE 事件总线
服务端推送事件，用于前端实时更新（下载进度、扫描进度、通知等）。

增强修复：
- 防止僵尸订阅者导致内存泄漏
- 自动清理断开的客户端队列
- 安全的异常处理
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator, Callable, Set

logger = logging.getLogger(__name__)


class EventBus:
    """
    进程内事件总线，支持 SSE 推送
    
    增强特性：
    - 自动检测并清理僵尸队列（队列满且无人消费）
    - 防止内存泄漏
    - 安全的并发写入
    """
    
    # 队列满次数阈值，超过则认为该队列已僵尸
    ZOMBIE_THRESHOLD = 3
    
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        # 追踪每个队列的满次计数，用于识别僵尸队列
        self._queue_full_counts: dict[int, int] = defaultdict(int)
        # 追踪有效的队列引用，用于快速查找
        self._all_queues: Set[asyncio.Queue] = set()

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
        
        # 收集需要通知的队列
        queues_to_notify = []
        queues_to_notify.extend(self._subscribers.get(event_type, []))
        queues_to_notify.extend(self._subscribers.get("*", []))
        
        # 去重
        queues_to_notify = list(set(queues_to_notify))
        
        # 追踪需要清理的僵尸队列
        dead_queues: Set[asyncio.Queue] = set()
        
        def _safe_put(q: asyncio.Queue) -> bool:
            """
            线程安全地向队列放入消息
            返回 True 表示成功，False 表示队列已满/有问题
            """
            try:
                q.put_nowait(json_msg)
                # 成功放入，重置计数器
                queue_id = id(q)
                if queue_id in self._queue_full_counts:
                    del self._queue_full_counts[queue_id]
                return True
            except asyncio.QueueFull:
                # 队列满了，增加计数
                queue_id = id(q)
                self._queue_full_counts[queue_id] += 1
                logger.warning(
                    f"EventBus: 队列已满 (count={self._queue_full_counts[queue_id]}), "
                    f"event_type={event_type}"
                )
                
                # 如果队列持续满，标记为僵尸
                if self._queue_full_counts[queue_id] >= self.ZOMBIE_THRESHOLD:
                    logger.warning(
                        f"EventBus: 检测到僵尸队列，将在下一次清理时移除"
                    )
                    dead_queues.add(q)
                return False
            except Exception as e:
                logger.error(f"EventBus: 向队列写入失败: {e}")
                dead_queues.add(q)
                return False
        
        # 使用 call_soon_threadsafe 保证即使外部模块从其他线程调用，也能安全地推入队列
        for queue in queues_to_notify:
            if queue not in dead_queues:
                loop.call_soon_threadsafe(_safe_put, queue)
        
        # 强制清理僵尸队列，防止内存溢出
        self._cleanup_dead_queues(dead_queues)
    
    def _cleanup_dead_queues(self, dead_queues: Set[asyncio.Queue] = None):
        """
        清理僵尸队列
        
        Args:
            dead_queues: 指定要清理的队列集合，如果为 None 则自动检测
        """
        if dead_queues is None:
            dead_queues = set()
        
        # 自动检测：清理已经不在活跃订阅列表中的队列
        if not dead_queues:
            for queue_id, full_count in list(self._queue_full_counts.items()):
                if full_count >= self.ZOMBIE_THRESHOLD:
                    # 找到对应的队列
                    for queue in self._all_queues:
                        if id(queue) == queue_id:
                            dead_queues.add(queue)
                            break
        
        for dead_q in dead_queues:
            self._remove_queue(dead_q)
            queue_id = id(dead_q)
            if queue_id in self._queue_full_counts:
                del self._queue_full_counts[queue_id]
    
    def _remove_queue(self, queue: asyncio.Queue):
        """从所有订阅列表中移除指定队列"""
        queue_id = id(queue)
        for event_type, queues in list(self._subscribers.items()):
            if queue in queues:
                queues.remove(queue)
                logger.info(f"EventBus: 已清理僵尸队列 from event_type={event_type}")
        
        # 从全局队列集合中移除
        self._all_queues.discard(queue)

    def subscribe(
        self, event_types: list[str] | None = None, maxsize: int = 100
    ) -> asyncio.Queue:
        """
        订阅事件，返回消息队列
        
        Args:
            event_types: 订阅的事件类型列表，None 表示订阅所有事件
            maxsize: 队列最大长度，超过会丢弃消息
            
        Returns:
            asyncio.Queue: 消息队列
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        types = event_types or ["*"]
        for t in types:
            self._subscribers[t].append(queue)
        # 追踪所有活跃队列
        self._all_queues.add(queue)
        logger.debug(f"EventBus: 新订阅者 registered for types={types}, queue_id={id(queue)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """
        取消订阅
        
        Args:
            queue: 要取消订阅的队列
        """
        queue_id = id(queue)
        self._remove_queue(queue)
        
        # 清理计数器
        if queue_id in self._queue_full_counts:
            del self._queue_full_counts[queue_id]
        
        logger.debug(f"EventBus: 订阅者已取消订阅, queue_id={queue_id}")

    def on(self, event_type: str):
        """事件处理器装饰器"""
        def decorator(func: Callable):
            self._handlers[event_type].append(func)
            return func
        return decorator
    
    def get_stats(self) -> dict[str, Any]:
        """获取事件总线统计信息（用于监控）"""
        total_queues = len(self._all_queues)
        zombie_count = sum(
            1 for count in self._queue_full_counts.values() 
            if count >= self.ZOMBIE_THRESHOLD
        )
        return {
            "total_subscribers": total_queues,
            "event_types_subscribed": list(self._subscribers.keys()),
            "zombie_queues": zombie_count,
            "queue_full_counts": dict(self._queue_full_counts),
        }
    
    def cleanup_inactive_queues(self):
        """
        定期清理检查（可由定时任务调用）
        检测并清理长时间满的队列
        """
        self._cleanup_dead_queues()


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
    """
    SSE 事件生成器
    
    使用 try-finally 确保即使客户端异常断开，也能正确清理订阅
    """
    bus = get_event_bus()
    queue = bus.subscribe(event_types)
    queue_id = id(queue)
    
    logger.debug(f"EventBus SSE: 新连接已订阅, queue_id={queue_id}")
    
    try:
        while True:
            try:
                # 带超时的 get，允许定期检查队列健康状态
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                # 定期发送心跳，保持连接活跃
                yield f": heartbeat\n\n"
            except asyncio.CancelledError:
                # 客户端断开连接
                logger.info(f"EventBus SSE: 客户端断开, queue_id={queue_id}")
                raise
    except asyncio.CancelledError:
        # 重新抛出 CancelledError 让 FastAPI 处理
        pass
    except GeneratorExit:
        # 生成器被外部关闭
        pass
    except Exception as e:
        logger.error(f"EventBus SSE: 意外错误 queue_id={queue_id}: {e}", exc_info=True)
    finally:
        # 确保无论如何都清理订阅
        bus.unsubscribe(queue)
        logger.debug(f"EventBus SSE: 连接已清理, queue_id={queue_id}")
