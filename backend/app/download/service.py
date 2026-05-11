"""
下载模块业务逻辑
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.download.clients import Aria2Adapter, DownloadClientAdapter, create_client_adapter
from app.download.models import DownloadClient, DownloadTask
from app.download.schemas import (
    DownloadClientCreate,
    DownloadClientOut,
    DownloadClientUpdate,
    DownloadTaskCreate,
    DownloadTaskOut,
)
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client_cache: dict[int, DownloadClientAdapter] = {}

    # ── 客户端管理 ──
    async def list_clients(self) -> list[DownloadClientOut]:
        result = await self.db.execute(select(DownloadClient).order_by(DownloadClient.id))
        return [DownloadClientOut.model_validate(c) for c in result.scalars().all()]

    async def create_client(self, data: DownloadClientCreate) -> DownloadClientOut:
        client = DownloadClient(**data.model_dump())
        self.db.add(client)
        await self.db.commit()  # 显式提交
        await self.db.refresh(client)
        logger.info(f"[下载] 创建客户端: {client.name} (id={client.id})")
        return DownloadClientOut.model_validate(client)

    async def update_client(self, client_id: int, data: DownloadClientUpdate) -> DownloadClientOut:
        client = await self._get_client(client_id)
        updates = data.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(client, k, v)
        await self.db.commit()  # 显式提交
        await self.db.refresh(client)
        # 清除缓存
        self._client_cache.pop(client_id, None)
        logger.info(f"[下载] 更新客户端: {client.name} (id={client_id})")
        return DownloadClientOut.model_validate(client)

    async def delete_client(self, client_id: int):
        client = await self._get_client(client_id)
        await self.db.delete(client)
        await self.db.commit()  # 显式提交
        self._client_cache.pop(client_id, None)
        logger.info(f"[下载] 删除客户端 id={client_id}")

    async def test_client(self, client_id: int) -> dict:
        """测试客户端连接"""
        client_db = await self._get_client(client_id)
        adapter = await self._get_adapter(client_db)
        try:
            connected = await adapter.connect()
            version = "" if not connected else await adapter.get_client_version()
            return {"connected": connected, "version": version}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def get_default_client(self) -> DownloadClient | None:
        """获取默认下载客户端（第一个启用的）"""
        result = await self.db.execute(
            select(DownloadClient)
            .where(DownloadClient.enabled == True)
            .order_by(DownloadClient.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── 下载任务 ──
    async def add_task(self, data: DownloadTaskCreate) -> DownloadTaskOut:
        """添加下载任务
        
        如果提供了 site_id，会尝试解析站点下载链接（如 genDlToken）。
        """
        # 确定使用哪个客户端
        client_db: DownloadClient | None = None
        if data.client_id:
            client_db = await self._get_client(data.client_id)
        else:
            client_db = await self.get_default_client()

        if not client_db:
            raise NotFoundError("DownloadClient", "no available client")

        # 解析下载 URL（如果提供了站点信息，优先解析 genDlToken 等认证下载链接）
        final_url = data.torrent_url
        download_error: str | None = None

        if data.site_id:
            try:
                from app.subscribe.models import Site
                site_result = await self.db.execute(
                    select(Site).where(Site.id == data.site_id)
                )
                site = site_result.scalar_one_or_none()
                if site:
                    from app.subscribe.site_adapter import create_site_adapter
                    adapter = create_site_adapter(site)
                    from app.subscribe.models import SiteResource
                    site_res = SiteResource(
                        download_url=data.torrent_url,
                        torrent_url=data.torrent_url,
                        title=data.title or "",
                    )
                    resolved_url, resolve_error = await adapter.get_download_url(site_res)
                    if resolved_url:
                        final_url = resolved_url
                        logger.info(f"[下载] 解析下载链接成功: {resolved_url[:80]}")
                    elif resolve_error:
                        download_error = resolve_error
                        logger.warning(f"[下载] 解析下载链接失败: {resolve_error}")
            except Exception as e:
                logger.warning(f"[下载] 解析下载链接时出错: {e}")

        # 添加到下载客户端
        adapter = await self._get_adapter(client_db)
        await adapter.connect()
        torrent_hash = ""
        add_error: str | None = None
        try:
            torrent_hash = await adapter.add_torrent(
                url=final_url,
                save_path=data.save_path,
                category=data.category or client_db.category,
            )
        except Exception as add_e:
            add_error = str(add_e)
            logger.error(f"[下载] add_torrent 失败: {add_e}")
            # 不立即抛出，继续记录到数据库

        # 合并错误消息
        if add_error:
            error_msg = f"[下载] 下载客户端添加失败: {add_error}"
            if download_error:
                error_msg = f"{download_error}; {add_error}"
            task = DownloadTask(
                client_id=client_db.id,
                torrent_name=data.title or data.torrent_url.split("/")[-1][:200],
                torrent_url=data.torrent_url,
                info_hash="",
                save_path=data.save_path or "",
                status="failed",
                message=error_msg[:500],
            )
            self.db.add(task)
            await self.db.commit()  # 显式提交
            await self.db.refresh(task)
            logger.warning(f"[下载] 任务添加失败，已记录到数据库: {error_msg}")
            return DownloadTaskOut.model_validate(task)

        # 如果 hash 是占位符（Base64/HTTP/tracker 等方式添加），尝试获取真实 hash
        # 注意：只有 QBittorrentAdapter 有 _get_latest_torrent_hash 方法
        if torrent_hash in ("torrent-base64", "http-torrent", "tracker-download", "tracker-magnet", "http-url", "unknown"):
            try:
                # 检查适配器是否有 _get_latest_torrent_hash 方法
                if hasattr(adapter, '_get_latest_torrent_hash'):
                    real_hash = await adapter._get_latest_torrent_hash()
                    if real_hash:
                        torrent_hash = real_hash
                        logger.info(f"[下载] 获取到真实 hash: {torrent_hash}")
                else:
                    logger.debug(f"[下载] 适配器 {type(adapter).__name__} 不支持获取真实 hash")
            except Exception as e:
                logger.warning(f"[下载] 获取真实 hash 失败，使用占位符: {e}")

        # 保存到数据库
        task = DownloadTask(
            client_id=client_db.id,
            torrent_name=data.title or data.torrent_url.split("/")[-1][:200],
            torrent_url=data.torrent_url,
            info_hash=torrent_hash,
            save_path=data.save_path or "",
            status="downloading",
            message=download_error,
        )
        self.db.add(task)
        await self.db.commit()  # 显式提交
        await self.db.refresh(task)
        logger.info(f"[下载] 添加任务成功: {task.torrent_name} (id={task.id})")
        return DownloadTaskOut.model_validate(task)

    async def list_tasks(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        from sqlalchemy import func

        query = select(DownloadTask).order_by(DownloadTask.created_at.desc())
        count_query = select(func.count()).select_from(DownloadTask)

        if status:
            query = query.where(DownloadTask.status == status)
            count_query = count_query.where(DownloadTask.status == status)

        total = (await self.db.execute(count_query)).scalar() or 0
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        tasks = [DownloadTaskOut.model_validate(t) for t in result.scalars().all()]

        return {
            "items": tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def sync_task_status(self):
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
        
        # 显式提交事务，确保状态同步持久化
        await self.db.commit()
        logger.debug(f"[同步] 已提交事务，更新了 {len(all_updates)} 个任务状态")


    async def _mark_subscriptions_completed(self, sub_ids: set[int]):
        """将指定订阅标记为 completed 状态"""
        try:
            from app.subscribe.models import Subscription
            for sub_id in sub_ids:
                result = await self.db.execute(
                    select(Subscription).where(Subscription.id == sub_id)
                )
                sub = result.scalar_one_or_none()
                if sub and sub.status == "active":
                    sub.status = "completed"
                    logger.info(f"[下载同步] 订阅 {sub.name}(id={sub_id}) 下载完成，状态更新为 completed")
            # 批量提交订阅状态更新
            await self.db.commit()
        except Exception as e:
            logger.error(f"[下载同步] 更新订阅状态失败: {e}")
            await self.db.rollback()

    async def detect_and_process_completed(self) -> dict:
        """
        检测新完成的下载任务，自动整理入库。
        返回处理结果统计。
        """
        from sqlalchemy import or_
        # 查找状态为 completed 的任务（seeding 已被 _map_state 映射为 completed）
        result = await self.db.execute(
            select(DownloadTask).where(
                DownloadTask.status == "completed"
            )
        )
        completed_tasks = result.scalars().all()

        stats = {
            "total_completed": len(completed_tasks),
            "organized": 0,
            "skipped": 0,
            "errors": 0,
        }

        for task in completed_tasks:
            # 检查是否已整理过（通过 message 字段标记）
            # 使用 begin_nested() 实现单步异常隔离，不破坏整体会话
            try:
                async with self.db.begin_nested():
                    msg = task.message or ""
                    if "[organized]" in msg:
                        stats["skipped"] += 1
                        continue

                    organize_result = await self._organize_task(task)
                    if organize_result.organized > 0:
                        stats["organized"] += 1
                        task.message = f"[organized] 已整理 {organize_result.organized} 个文件"
                        # 触发媒体库扫描（对相关媒体库）
                        await self._trigger_library_scan(task)
                    elif organize_result.skipped > 0:
                        stats["skipped"] += 1
                        task.message = f"[organized] 跳过（文件已存在或无需整理）"
                    else:
                        stats["errors"] += 1
                        task.message = f"[organized] 整理失败: {'; '.join(organize_result.errors)}"
            except Exception as e:
                logger.error(f"Organize task {task.id} failed: {e}")
                stats["errors"] += 1
                try:
                    # 在嵌套事务外记录错误信息
                    task.message = f"[organized] 整理异常: {str(e)[:200]}"
                    await self.db.commit()  # 提交错误信息
                except:
                    pass
        
        # 提交所有整理结果
        try:
            await self.db.commit()
            logger.info(f"[下载] 自动整理完成: {stats['organized']} 个入库, {stats['skipped']} 个跳过, {stats['errors']} 个错误")
        except Exception as e:
            logger.error(f"[下载] 提交整理结果失败: {e}")
            await self.db.rollback()
        
        # 发送 SSE 事件
        if stats["organized"] > 0:
            try:
                from app.system.events import get_event_bus
                get_event_bus().emit("download_complete", {
                    "organized": stats["organized"],
                    "skipped": stats["skipped"],
                    "errors": stats["errors"],
                    "message": f"下载完成整理: {stats['organized']} 个入库, {stats['skipped']} 个跳过",
                })
            except Exception:
                pass

        return stats

    async def _get_organize_setting(self, key: str, default: str = "") -> str:
        """读取整理相关设置"""
        try:
            from app.system.settings_service import SettingsService
            service = SettingsService(self.db)
            return await service.get(f"organize.{key}") or default
        except Exception:
            return default

    async def _organize_task(self, task: DownloadTask):
        """整理单个下载任务的文件"""
        from app.config import get_settings
        from app.media.organizer import FileOrganizer

        settings = get_settings()

        # 检查整理模式
        organize_mode = await self._get_organize_setting("mode") or "move_to_library"
        if organize_mode == "keep_in_place":
            return OrganizeResult()  # 不整理，返回空结果

        # 尝试从媒体库配置获取目录
        movies_dir = ""
        tv_dir = ""
        anime_dir = ""

        try:
            from app.media.repository import MediaRepository
            repo = MediaRepository(self.db)
            libraries = await repo.get_all_libraries()
            for lib in libraries:
                if lib.media_type == "movie" and not movies_dir:
                    movies_dir = lib.path
                elif lib.media_type == "tv" and not tv_dir:
                    tv_dir = lib.path
                elif lib.media_type == "anime" and not anime_dir:
                    anime_dir = lib.path
        except Exception:
            pass

        organizer = FileOrganizer(
            movies_dir=movies_dir,
            tv_dir=tv_dir,
            anime_dir=anime_dir,
            download_dir=str(settings.download_dir),
        )

        return organizer.organize_completed_task(
            save_path=task.save_path,
            torrent_name=task.torrent_name,
        )

    async def _trigger_library_scan(self, task: DownloadTask):
        """触发媒体库扫描"""
        try:
            from app.media.repository import MediaRepository
            from app.media.service import MediaService
            from app.system.events import get_event_bus

            repo = MediaRepository(self.db)
            libraries = await repo.get_all_libraries()
            service = MediaService(repo, get_event_bus())

            # 扫描所有启用的媒体库
            for lib in libraries:
                if lib.enabled:
                    try:
                        await service.scan_library(lib.id)
                    except Exception as e:
                        logger.error(f"Auto-scan library {lib.name} failed: {e}")
        except Exception as e:
            logger.error(f"Trigger library scan failed: {e}")

    async def manual_organize(self, task_id: int) -> dict:
        """手动整理指定下载任务"""
        task = await self._get_task(task_id)
        # 清除已整理标记以允许重新整理
        task.message = None
        await self.db.commit()  # 显式提交
        logger.info(f"[下载] 手动整理任务 {task_id}")
        
        result = await self._organize_task(task)
        if result.organized > 0:
            task.message = f"[organized] 已整理 {result.organized} 个文件"
            await self._trigger_library_scan(task)
            await self.db.commit()  # 提交整理结果
            logger.info(f"[下载] 任务 {task_id} 整理完成，已入库 {result.organized} 个文件")
        elif result.errors:
            task.message = f"[organized] 整理失败: {'; '.join(result.errors)}"
            await self.db.commit()
        else:
            task.message = f"[organized] 无需整理"
            await self.db.commit()
        
        return {
            "organized": result.organized,
            "skipped": result.skipped,
            "errors": result.errors,
        }

    async def pause_task(self, task_id: int):
        """暂停下载任务"""
        task = await self._get_task(task_id)
        if task.client_id:
            try:
                adapter = await self._get_adapter_by_id(task.client_id)
                await adapter.connect()
                await adapter.pause(task.info_hash or "")
                logger.info(f"[下载] 已暂停任务 {task_id} (hash={task.info_hash})")
            except Exception as e:
                logger.warning(f"Pause via client failed (task {task_id}), updating local status anyway: {e}")
        task.status = "paused"
        await self.db.commit()  # 显式提交

    async def resume_task(self, task_id: int):
        """恢复下载任务"""
        task = await self._get_task(task_id)
        if task.client_id:
            try:
                adapter = await self._get_adapter_by_id(task.client_id)
                await adapter.connect()
                await adapter.resume(task.info_hash or "")
                logger.info(f"[下载] 已恢复任务 {task_id} (hash={task.info_hash})")
            except Exception as e:
                logger.warning(f"Resume via client failed (task {task_id}), updating local status anyway: {e}")
        task.status = "downloading"
        await self.db.commit()  # 显式提交

    async def delete_task(self, task_id: int, delete_files: bool = False):
        """删除下载任务
        
        必须先从底层下载客户端物理删除，成功后才清理数据库。
        如果客户端删除失败，则保留数据库记录（防止同步定时器将任务复活）。
        """
        from fastapi import HTTPException
        
        task = await self._get_task(task_id)
        if task.client_id and task.info_hash:
            try:
                adapter = await self._get_adapter_by_id(task.client_id)
                await adapter.connect()
                success = await adapter.delete(task.info_hash, delete_files)
                if not success:
                    raise HTTPException(
                        status_code=502,
                        detail=f"底层下载客户端删除任务失败（hash={task.info_hash}），任务保留在数据库中，请检查下载器状态",
                    )
                logger.info(f"[下载] 已从客户端删除任务 {task_id} (hash={task.info_hash})")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"底层下载客户端通信失败: {e}，任务保留在数据库中",
                )
        await self.db.delete(task)
        await self.db.commit()  # 显式提交事务
        logger.info(f"[下载] 已从数据库删除任务 {task_id}")

    # ── 辅助方法 ──
    async def _get_client(self, client_id: int) -> DownloadClient:
        result = await self.db.execute(
            select(DownloadClient).where(DownloadClient.id == client_id)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise NotFoundError("DownloadClient", client_id)
        return client

    async def _get_task(self, task_id: int) -> DownloadTask:
        result = await self.db.execute(
            select(DownloadTask).where(DownloadTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError("DownloadTask", task_id)
        return task

    async def _get_adapter(self, client: DownloadClient) -> DownloadClientAdapter:
        if client.id not in self._client_cache:
            self._client_cache[client.id] = create_client_adapter(
                client.client_type, client.host, client.port,
                client.username or "", client.password or "",
            )
        return self._client_cache[client.id]

    async def _get_adapter_by_id(self, client_id: int) -> DownloadClientAdapter:
        client = await self._get_client(client_id)
        return await self._get_adapter(client)

    # ── Aria2 扩展 ──
    async def get_aria2_stats(self, client_id: int) -> dict:
        """获取 Aria2 客户端的全局统计信息"""
        from app.download.clients import Aria2Adapter

        client = await self._get_client(client_id)
        if client.client_type != "aria2":
            raise ValueError(f"Client {client_id} is not an Aria2 client (type={client.client_type})")

        adapter = await self._get_adapter(client)
        if not isinstance(adapter, Aria2Adapter):
            raise TypeError("Adapter is not an Aria2Adapter")

        await adapter.connect()
        stats = await adapter.get_global_stats()
        return {
            "numActive": int(stats.get("numActive", 0)),
            "numWaiting": int(stats.get("numWaiting", 0)),
            "numStopped": int(stats.get("numStopped", 0)),
            "numStoppedTotal": int(stats.get("numStoppedTotal", 0)),
            "downloadSpeed": int(stats.get("downloadSpeed", 0)),
            "uploadSpeed": int(stats.get("uploadSpeed", 0)),
        }
