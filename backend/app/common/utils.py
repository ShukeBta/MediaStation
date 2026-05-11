"""
通用工具函数
"""
import asyncio
import json
import logging
from typing import Any, Coroutine, Optional

import httpx

logger = logging.getLogger(__name__)


def safe_json(resp: httpx.Response, *, url_hint: str = "") -> Any:
    """
    安全解析 HTTP 响应为 JSON，防止 JSONDecodeError 导致整个刮削队列崩溃。

    当目标 API 返回非 JSON（如 502 HTML 错误页、Cloudflare 拦截页）时，
    原生 resp.json() 会抛出 JSONDecodeError，在批量刮削循环中直接中断后续任务。

    Args:
        resp: httpx 响应对象（应已调用过 raise_for_status）
        url_hint: 请求 URL 片段，用于日志定位

    Returns:
        解析后的 JSON 数据（dict/list），解析失败时返回 None
    """
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ct and "text/json" not in ct:
        logger.warning(
            f"[safe_json] 非 JSON Content-Type ({ct}) from {url_hint or resp.url}"
        )
        return None
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(
            f"[safe_json] JSON 解码失败 from {url_hint or resp.url}: {e}, "
            f"body[:200]={resp.text[:200]}"
        )
        return None


def safe_create_task(
    coro: Coroutine,
    name: Optional[str] = None
) -> asyncio.Task:
    """
    安全的异步任务创建器，自动捕获并记录未处理的异常。
    
    防止后台任务静默崩溃导致的问题（如定时任务死掉无人知晓）。
    所有原先使用 asyncio.create_task 的地方应替换为 safe_create_task。
    
    Args:
        coro: 要执行的协程
        name: 任务名称（用于日志标识）
        
    Returns:
        asyncio.Task: 创建的任务对象
        
    Example:
        >>> safe_create_task(_auto_sync_loop(), name="auto_sync")
        >>> safe_create_task(self._process_event(path, event_type), name="watcher_process")
    """
    # 如果没有提供名称，尝试从协程对象获取
    if name is None:
        if hasattr(coro, '__name__'):
            name = coro.__name__
        elif hasattr(coro, 'cr_code'):
            name = coro.cr_code.co_name
        else:
            name = 'unknown_task'
    
    task = asyncio.create_task(coro, name=name)

    def handle_exception(task: asyncio.Task) -> None:
        """
        任务完成时的回调函数，用于捕获未处理的异常
        """
        try:
            # 获取任务结果，如果有异常会在这里抛出
            result = task.result()
            logger.debug(f"后台任务 '{task.get_name()}' 正常完成，结果: {result}")
        except asyncio.CancelledError:
            # 任务被取消，这是正常情况
            logger.info(f"后台任务 '{task.get_name()}' 已被取消")
        except Exception as e:
            # 其他异常，记录详细错误信息
            logger.error(
                f"🚨 后台任务 '{task.get_name()}' 发生致命异常: {type(e).__name__}: {e}",
                exc_info=True  # 记录完整的堆栈跟踪
            )
        except BaseException as e:
            # 捕获更严重的异常（如 KeyboardInterrupt, SystemExit）
            logger.critical(
                f"💀 后台任务 '{task.get_name()}' 发生严重异常: {type(e).__name__}: {e}",
                exc_info=True
            )

    # 添加回调函数
    task.add_done_callback(handle_exception)
    
    logger.debug(f"✅ 已创建安全后台任务: '{task.get_name()}'")
    return task


async def safe_gather(*coros, return_exceptions: bool = False):
    """
    安全的 gather 包装器，统一处理多个并发任务
    
    Args:
        *coros: 多个协程对象
        return_exceptions: 是否返回异常而不是抛出（默认False，会记录日志）
        
    Returns:
        list: 任务结果列表
    """
    tasks = [safe_create_task(coro) for coro in coros]
    
    if return_exceptions:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # 检查是否有异常结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"并发任务 #{i} 执行失败: {type(result).__name__}: {result}")
        return results
    else:
        return await asyncio.gather(*tasks)


class TaskManager:
    """
    后台任务管理器，用于跟踪和管理所有后台任务
    """
    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        self._task_counter = 0
    
    def create_task(self, coro: Coroutine, name: Optional[str] = None) -> asyncio.Task:
        """
        创建并跟踪后台任务
        """
        self._task_counter += 1
        if name is None:
            name = f"task_{self._task_counter}"
        
        task = safe_create_task(coro, name=name)
        self._tasks.add(task)
        
        # 任务完成后自动从集合中移除
        task.add_done_callback(lambda t: self._tasks.discard(t))
        
        return task
    
    def get_active_tasks(self) -> list[asyncio.Task]:
        """
        获取当前活跃的任务列表
        """
        return list(self._tasks)
    
    def cancel_all(self):
        """
        取消所有后台任务
        """
        for task in self._tasks:
            if not task.done():
                task.cancel()
        logger.info(f"已取消 {len(self._tasks)} 个后台任务")


# 全局任务管理器实例（可选使用）
task_manager = TaskManager()
