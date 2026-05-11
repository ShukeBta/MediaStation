"""
数据库备份服务
使用 aiosqlite 的 backup() API 实现安全的在线热备份
避免直接复制 SQLite 文件导致的数据库损坏
"""
from __future__ import annotations

import aiosqlite
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def create_database_backup(db_path: str, backup_dir: str) -> str:
    """
    创建数据库热备份（使用 SQLite 原生 backup API）
    
    Args:
        db_path: 源数据库路径（如 mediastation.db）
        backup_dir: 备份文件保存目录
    
    Returns:
        备份文件的完整路径
    
    Raises:
        Exception: 备份失败时抛出异常
    """
    # 确保备份目录存在
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # 生成备份文件名（带时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"mediastation_{timestamp}.db"
    
    try:
        # 使用 aiosqlite 的 backup() API 进行安全的在线备份
        async with aiosqlite.connect(db_path) as src:
            async with aiosqlite.connect(str(backup_file)) as dst:
                await src.backup(dst)
        
        logger.info(f"Database backup created: {backup_file}")
        return str(backup_file)
    
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        # 清理可能生成的半残文件
        if backup_file.exists():
            try:
                backup_file.unlink()
            except Exception:
                pass
        raise Exception(f"备份失败: {str(e)}")


async def list_backups(backup_dir: str) -> list[dict]:
    """
    列出所有可用的备份文件
    
    Args:
        backup_dir: 备份文件保存目录
    
    Returns:
        备份文件信息列表（按时间倒序）
    """
    backup_path = Path(backup_dir)
    
    if not backup_path.exists():
        return []
    
    backups = []
    for file in backup_path.glob("mediastation_*.db"):
        stat = file.stat()
        backups.append({
            "filename": file.name,
            "path": str(file),
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        })
    
    # 按创建时间倒序（最新的在前面）
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    
    return backups


async def restore_database(backup_path: str, db_path: str) -> bool:
    """
    从备份文件恢复数据库
    
    Args:
        backup_path: 备份文件路径
        db_path: 目标数据库路径
    
    Returns:
        是否恢复成功
    """
    backup_file = Path(backup_path)
    
    if not backup_file.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return False
    
    try:
        # 先备份当前数据库（防止恢复失败）
        temp_backup = db_path + ".before_restore"
        if Path(db_path).exists():
            async with aiosqlite.connect(db_path) as src:
                async with aiosqlite.connect(temp_backup) as dst:
                    await src.backup(dst)
        
        # 从备份文件恢复
        async with aiosqlite.connect(backup_path) as src:
            async with aiosqlite.connect(db_path) as dst:
                await src.backup(dst)
        
        # 删除临时备份
        if Path(temp_backup).exists():
            Path(temp_backup).unlink()
        
        logger.info(f"Database restored from: {backup_path}")
        return True
    
    except Exception as e:
        logger.error(f"Database restore failed: {e}")
        return False


async def delete_backup(backup_path: str) -> bool:
    """
    删除指定的备份文件
    
    Args:
        backup_path: 备份文件路径
    
    Returns:
        是否删除成功
    """
    try:
        file = Path(backup_path)
        if file.exists():
            file.unlink()
            logger.info(f"Backup deleted: {backup_path}")
            return True
        else:
            logger.warning(f"Backup file not found: {backup_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete backup: {e}")
        return False
