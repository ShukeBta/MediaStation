#!/usr/bin/env python3
"""
修复 Issue #41: 重构 sync_task_status 为批量查询，消除 N+1 问题
"""
import re

filepath = r"c:\Users\Administrator\WorkBuddy\20260428130330\backend\app\download\service.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 定义新的 sync_task_status 方法（批量查询版本）
new_sync_method = '''    async def sync_task_status(self):
        """同步所有客户端的任务状态，并联动更新订阅状态（批量查询优化版）"""
        from app.system.events import get_event_bus
        from sqlalchemy import or_

        clients = await self.list_clients()
        all_updates = []
        newly_completed_sub_ids: set[int] = set()  # 本次同步中新完成的订阅 ID

        # ── 第一阶段：收集所有 torrent 的 hash 和 name ──
        client_adapters = []
        all_hashes: list[str] = []
        all_names: list[tuple[int, str]] = []  # (client_id, name)

        for client_out in clients:
            client_db = await self._get_client(client_out.id)
            try:
                adapter = await self._get_adapter(client_db)
                await adapter.connect()
                torrents = await adapter.get_torrents()

                for torrent in torrents:
                    if torrent.hash and len(torrent.hash) in (32, 40):
                        all_hashes.append(torrent.hash)
                    if torrent.name:
                        all_names.append((client_db.id, torrent.name))

                client_adapters.append((client_db, adapter, torrents))
            except Exception as e:
                logger.error(f"Sync client {client_db.name} failed: {e}")

        # ── 第二阶段：批量查询 DB ──
        # 按 hash 匹配
        task_by_hash: dict[str, DownloadTask] = {}
        if all_hashes:
            result = await self.db.execute(
                select(DownloadTask).where(
                    DownloadTask.info_hash.in_(all_hashes)
                )
            )
            for task in result.scalars().all():
                if task.info_hash:
                    task_by_hash[task.info_hash] = task

        # 按 (client_id, torrent_name) 匹配
        task_by_name: dict[tuple[int, str], DownloadTask] = {}
        if all_names:
            conditions = [
                (DownloadTask.client_id == cid) & (DownloadTask.torrent_name == name)
                for cid, name in all_names
            ]
            result = await self.db.execute(
                select(DownloadTask).where(or_(*conditions))
            )
            for task in result.scalars().all():
                if task.torrent_name and task.client_id:
                    task_by_name[(task.client_id, task.torrent_name)] = task

        # ── 第三阶段：内存匹配 & 更新 ──
        for client_db, adapter, torrents in client_adapters:
            for torrent in torrents:
                # 优先按 hash 匹配
                task = None
                if torrent.hash and len(torrent.hash) in (32, 40):
                    task = task_by_hash.get(torrent.hash)

                # 回退：按名称 + 客户端 ID 匹配
                if not task and torrent.name:
                    task = task_by_name.get((client_db.id, torrent.name))

                if task:
                    old_status = task.status
                    task.status = torrent.status
                    task.progress = torrent.progress
                    task.total_size = torrent.size
                    task.downloaded = torrent.downloaded
                    task.speed = torrent.speed
                    task.seeders = torrent.seeders
                    task.eta = torrent.eta
                    task.torrent_name = torrent.name
                    task.save_path = torrent.save_path
                    if torrent.hash and len(torrent.hash) in (32, 40):
                        task.info_hash = torrent.hash

                    if (torrent.status == "completed"
                            and old_status != "completed"
                            and task.subscription_id):
                        newly_completed_sub_ids.add(task.subscription_id)

                    await self.db.flush()

                    all_updates.append({
                        "id": task.id,
                        "torrent_name": torrent.name,
                        "status": torrent.status,
                        "progress": torrent.progress,
                        "total_size": torrent.size,
                        "downloaded": torrent.downloaded,
                        "speed": torrent.speed,
                        "upload_speed": getattr(torrent, 'upload_speed', 0),
                        "seeders": torrent.seeders,
                        "eta": torrent.eta,
                    })
                else:
                    logger.debug(f"[同步] 跳过未管理的种子: {torrent.name} (hash={torrent.hash})")

        # ── 联动更新订阅状态 ──
        if newly_completed_sub_ids:
            await self._mark_subscriptions_completed(newly_completed_sub_ids)

        # 通过 SSE 广播下载进度更新
        if all_updates:
            try:
                get_event_bus().emit("download_progress", {
                    "tasks": all_updates,
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                })
            except Exception:
                pass

'''

# 找到旧的 sync_task_status 方法并开始替换
# 方法签名模式
pattern_start = "    async def sync_task_status(self):"

if pattern_start in content:
    # 找到方法开始位置
    start_pos = content.find(pattern_start)
    
    # 找到方法结束位置（下一个方法的开始或文件结束）
    # 查找下一个 async def 或 def 或类结束
    next_method_patterns = ['\n    async def ', '\n    def ', '\nclass ']
    
    end_pos = len(content)
    for pattern in next_method_patterns:
        pos = content.find(pattern, start_pos + len(pattern_start))
        if pos != -1 and pos < end_pos:
            end_pos = pos
    
    # 替换整个方法
    content = content[:start_pos] + new_sync_method + content[end_pos:]
    
    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("SUCCESS: Replaced sync_task_status with batch query version (Issue #41 fixed)")
else:
    print("ERROR: Could not find sync_task_status method")
