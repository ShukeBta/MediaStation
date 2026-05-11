"""
重复检测模块
识别和标记媒体库中的重复文件。

检测策略：
1. 文件大小 + 稀疏采样哈希（头部、中部、尾部各1MB）
2. 对于小文件（<3MB）使用全量哈希

标记策略：
- 保留第一个文件作为主文件
- 将后续重复文件标记为 is_duplicate=True, duplicate_of=主文件 ID
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import select, and_, or_

from app.media.models import MediaItem

logger = logging.getLogger(__name__)

# 采样大小（每个采样点 1MB）
SAMPLE_SIZE = 1024 * 1024  # 1MB


async def calculate_file_hash(file_path: str | Path, algorithm: str = "md5") -> Optional[str]:
    """
    计算文件哈希值（使用稀疏采样，避免读取大文件）
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (md5, sha1, sha256)
    
    Returns:
        十六进制哈希字符串（包含文件大小以防止碰撞），失败返回 None
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return None
        
        file_size = path.stat().st_size
        
        # 对于小于 3MB 的小文件，直接全量 Hash
        if file_size <= SAMPLE_SIZE * 3:
            return hashlib.md5(path.read_bytes()).hexdigest()
        
        # 对于大文件，使用稀疏采样 Hash（头、中、尾各 1MB）
        hasher = hashlib.md5()
        
        with open(path, 'rb') as f:
            # 1. 采样头部 1MB
            hasher.update(f.read(SAMPLE_SIZE))
            
            # 2. 采样中部 1MB
            f.seek(file_size // 2 - (SAMPLE_SIZE // 2))
            hasher.update(f.read(SAMPLE_SIZE))
            
            # 3. 采样尾部 1MB
            f.seek(file_size - SAMPLE_SIZE)
            hasher.update(f.read(SAMPLE_SIZE))
        
        # 将文件大小混入 Hash，确保即使哈希碰撞，大小不同也视为不同
        return f"{hasher.hexdigest()}-{file_size}"
    
    except Exception as e:
        logger.error(f"Hash calculation failed for {file_path}: {e}")
        return None


async def detect_duplicates(
    db: AsyncSession,
    library_id: Optional[int] = None,
) -> dict:
    """
    检测媒体库中的重复文件
    
    Args:
        db: 数据库会话
        library_id: 指定媒体库 ID，None 表示所有库
    
    Returns:
        {
            "total_items": 总条目数,
            "duplicates_found": 发现的重复组数,
            "items_marked": 标记为重复的条目数,
            "groups": [  # 重复组列表
                {
                    "primary_id": 主条目 ID,
                    "primary_title": 主条目标题,
                    "primary_path": 主条目路径,
                    "duplicates": [  # 重复条目列表
                        {"id": 重复条目 ID, "title": 标题, "path": 路径, "file_size": 文件大小}
                    ],
                }
            ],
        }
    """
    # 查询所有条目
    stmt = select(MediaItem).where(MediaItem.file_hash.isnot(None))
    if library_id:
        stmt = stmt.where(MediaItem.library_id == library_id)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    # 按 file_hash 分组
    hash_groups: dict[str, list[MediaItem]] = {}
    for item in items:
        if item.file_hash:
            if item.file_hash not in hash_groups:
                hash_groups[item.file_hash] = []
            hash_groups[item.file_hash].append(item)
    
    # 找出重复组（同 hash 有多个条目）
    duplicate_groups = []
    items_marked = 0
    
    for file_hash, group in hash_groups.items():
        if len(group) < 2:
            continue  # 没有重复
        
        # 选择主条目（按 ID 最小或优先级）
        # 策略：选择第一个刮削过的，或文件最大的
        primary = _select_primary_item(group)
        
        # 标记其他条目为重复
        duplicates = []
        for item in group:
            if item.id == primary.id:
                continue  # 跳过主条目
            
            # 标记为重复
            item.is_duplicate = True
            item.duplicate_of = primary.id
            items_marked += 1
            
            duplicates.append({
                "id": item.id,
                "title": item.title,
                "path": item.file_path,
                "file_size": item.file_size,
            })
        
        duplicate_groups.append({
            "primary_id": primary.id,
            "primary_title": primary.title,
            "primary_path": primary.file_path,
            "duplicates": duplicates,
        })
    
    # 提交更改
    if items_marked > 0:
        await db.commit()
        logger.info(f"Marked {items_marked} items as duplicates")
    
    return {
        "total_items": len(items),
        "duplicates_found": len(duplicate_groups),
        "items_marked": items_marked,
        "groups": duplicate_groups,
    }


def _select_primary_item(group: list[MediaItem]) -> MediaItem:
    """
    从重复组中选择主条目
    
    策略：
    1. 优先选择已刮削的
    2. 其次选择文件最大的
    3. 最后选择 ID 最小的
    """
    # 策略 1：已刮削的
    scraped = [item for item in group if item.scraped]
    if scraped:
        # 选择文件最大的
        return max(scraped, key=lambda x: x.file_size or 0)
    
    # 策略 2：文件最大的
    return max(group, key=lambda x: (x.file_size or 0, -x.id))


async def scan_and_hash_files(
    db: AsyncSession,
    library_id: int,
    file_paths: list[str],
    algorithm: str = "md5",
) -> int:
    """
    扫描文件并计算哈希，更新到数据库
    
    Args:
        db: 数据库会话
        library_id: 媒体库 ID
        file_paths: 文件路径列表
        algorithm: 哈希算法
    
    Returns:
        成功计算哈希的文件数
    """
    hashed_count = 0
    
    for file_path in file_paths:
        # 查找数据库中的条目
        stmt = select(MediaItem).where(
            and_(
                MediaItem.library_id == library_id,
                MediaItem.file_path == file_path,
            )
        )
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item:
            logger.warning(f"Item not found for path: {file_path}")
            continue
        
        # 计算哈希（使用稀疏采样）
        file_hash = await calculate_file_hash(file_path, algorithm=algorithm)
        if not file_hash:
            continue
        
        # 更新数据库
        item.file_hash = file_hash
        hashed_count += 1
        
        # 每 10 个文件提交一次
        if hashed_count % 10 == 0:
            await db.commit()
            logger.debug(f"Hashed {hashed_count} files so far...")
    
    # 最终提交
    await db.commit()
    logger.info(f"Hashed {hashed_count} files for library {library_id}")
    
    return hashed_count


async def unmark_duplicates(
    db: AsyncSession,
    library_id: Optional[int] = None,
) -> int:
    """
    取消重复标记
    
    Args:
        db: 数据库会话
        library_id: 指定媒体库 ID，None 表示所有库
    
    Returns:
        取消标记的条目数
    """
    stmt = select(MediaItem).where(MediaItem.is_duplicate == True)
    if library_id:
        stmt = stmt.where(MediaItem.library_id == library_id)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    count = 0
    for item in items:
        item.is_duplicate = False
        item.duplicate_of = None
        count += 1
    
    if count > 0:
        await db.commit()
        logger.info(f"Unmarked {count} duplicate items")
    
    return count


def get_duplicate_info(item: MediaItem, db: AsyncSession) -> Optional[dict]:
    """
    获取条目的重复信息
    
    Args:
        item: 媒体条目
        db: 数据库会话（可选，用于查询主条目信息）
    
    Returns:
        {
            "is_duplicate": 是否是重复项,
            "duplicate_of": 主条目 ID（如果是重复项）,
            "primary_item": {  # 主条目信息（如果提供 db）
                "id": 主条目 ID,
                "title": 标题,
                "path": 路径,
            }
        }
    """
    if not item.is_duplicate:
        return {
            "is_duplicate": False,
            "duplicate_of": None,
            "primary_item": None,
        }
    
    info = {
        "is_duplicate": True,
        "duplicate_of": item.duplicate_of,
        "primary_item": None,
    }
    
    # 如果提供了 db，查询主条目信息
    if db and item.duplicate_of:
        # 注意：这个函数需要在异步上下文中调用
        # 这里只返回基本信息，详细查询由调用者完成
        pass
    
    return info
