"""
STRM 文件支持路由

STRM 文件是一种特殊文件（.strm 扩展名），内容是一个 URL。
当播放器打开 .strm 文件时，实际上播放的是文件内的 URL。
这常用于将外部存储（WebDAV/Alist/S3/HTTP 直链）以"文件"形式加入媒体库。

API 端点：
  GET   /api/admin/strm/config          获取 STRM 配置
  PUT   /api/admin/strm/config          更新 STRM 配置
  GET   /api/admin/media/:id/strm     获取媒体的 STRM URL
  PUT   /api/admin/media/:id/strm     设置媒体的 STRM URL
"""
from __future__ import annotations

import json
from typing import Annotated, Any, Dict

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select

from app.deps import AdminUser, DB
from app.media.models import MediaItem
from app.common.schemas import SuccessResponse
from app.strm.schemas import (
    StrmConfigUpdate,
    StrmConfigResponse,
    MediaStrmUpdate,
)
from app.system.models import SettingsKV

router = APIRouter(prefix="/admin/strm", tags=["strm"])


# ── STRM 配置数据库存储辅助函数 ──

async def _get_strm_config(db: DB) -> Dict[str, Any]:
    """从数据库获取 STRM 配置（不存在则返回默认配置）"""
    result = await db.execute(
        select(SettingsKV).where(SettingsKV.key == "strm.config")
    )
    row = result.scalar_one_or_none()
    if row and row.value:
        return json.loads(row.value)
    # 返回默认配置
    return {
        "enabled": False,
        "allowed_protocols": ["http", "https"],
        "max_file_size": 1048576,
    }


async def _save_strm_config(db: DB, config: Dict[str, Any]) -> None:
    """保存 STRM 配置到数据库"""
    result = await db.execute(
        select(SettingsKV).where(SettingsKV.key == "strm.config")
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = json.dumps(config)
    else:
        row = SettingsKV(key="strm.config", value=json.dumps(config))
        db.add(row)
    await db.flush()


@router.get("/config", summary="获取 STRM 配置")
async def get_strm_config(user: AdminUser, db: DB):
    """
    获取 STRM 文件支持配置。
    enabled: 是否启用 STRM 支持
    allowed_protocols: 允许的 URL 协议列表
    max_file_size: 最大 STRM 文件大小（字节）
    """
    config = await _get_strm_config(db)
    return SuccessResponse.ok(StrmConfigResponse(**config).model_dump())


@router.put("/config", summary="更新 STRM 配置")
async def update_strm_config(data: StrmConfigUpdate, user: AdminUser, db: DB):
    """
    更新 STRM 文件支持配置。
    可以部分更新（只传需要修改的字段）。
    """
    # 获取当前配置
    config = await _get_strm_config(db)
    # 更新传入的字段
    update_data = data.model_dump(exclude_none=True)
    config.update(update_data)
    # 保存到数据库
    await _save_strm_config(db, config)
    
    return SuccessResponse.ok({
        "message": "STRM 配置已更新",
        **StrmConfigResponse(**config).model_dump(),
    })


@router.get("/media/{media_id}", summary="获取媒体的 STRM URL")
async def get_media_strm(
    db: DB,
    user: AdminUser,
    media_id: Annotated[int, Path(ge=1, description="媒体 ID")],
):
    """
    获取指定媒体的 STRM 引用 URL。
    如果媒体没有设置 STRM URL，返回 null。
    """
    item = (await db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(404, "媒体条目不存在")

    return SuccessResponse.ok({
        "media_id": item.id,
        "title": item.title,
        "strm_url": item.strm_url,
        "has_strm": item.strm_url is not None,
    })


@router.put("/media/{media_id}", summary="设置媒体的 STRM URL")
async def set_media_strm(
    db: DB,
    user: AdminUser,
    media_id: Annotated[int, Path(ge=1, description="媒体 ID")],
    data: MediaStrmUpdate,
):
    """
    设置媒体的 STRM 引用 URL。
    设置后，该媒体的播放将直接访问该 URL，而不是本地文件。

    如果清空 strm_url（传入空字符串或 null），则取消 STRM 引用。
    """
    item = (await db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(404, "媒体条目不存在")

    # 从数据库获取 STRM 配置
    config = await _get_strm_config(db)
    
    # 检查 STRM 是否启用
    if not config["enabled"]:
        raise HTTPException(400, "STRM 支持未启用，请先在配置中启用")

    # 验证 URL 协议
    url = data.strm_url.strip()
    allowed = config["allowed_protocols"]
    if not any(url.lower().startswith(p + "://") or url.lower().startswith(p + ":") for p in allowed):
        raise HTTPException(
            400,
            f"URL 协议不被允许。允许的协议: {allowed}",
        )

    item.strm_url = url
    await db.commit()

    return SuccessResponse.ok({
        "message": "STRM URL 已设置",
        "media_id": item.id,
        "title": item.title,
        "strm_url": item.strm_url,
    })


@router.delete("/media/{media_id}", summary="清除媒体的 STRM URL")
async def clear_media_strm(
    db: DB,
    user: AdminUser,
    media_id: Annotated[int, Path(ge=1, description="媒体 ID")],
):
    """
    清除指定媒体的 STRM 引用 URL。
    清除后，该媒体将恢复正常本地文件播放。
    """
    item = (await db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(404, "媒体条目不存在")

    item.strm_url = None
    await db.commit()

    return SuccessResponse.ok({
        "message": "STRM URL 已清除",
        "media_id": item.id,
    })


# ── Emby 兼容层 STRM 支持 ──

@router.get("/emby/Items/{item_id}/PlaybackInfo", summary="Emby 兼容: STRM 播放信息")
async def emby_strm_playback_info(
    db: DB,
    item_id: Annotated[int, Path(description="Emby 媒体 ID")],
):
    """
    Emby 兼容端点：获取 STRM 媒体的播放信息。
    如果媒体有 strm_url，直接返回该 URL 作为播放地址。
    """
    item = (await db.execute(
        select(MediaItem).where(MediaItem.id == item_id)
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(404, "媒体不存在")

    if not item.strm_url:
        # 非 STRM 媒体，返回正常播放信息（由 Emby 路由处理）
        return SuccessResponse.ok({"strm": None, "message": "非 STRM 媒体"})

    # 返回 STRM URL 作为播放地址
    return SuccessResponse.ok({
        "strm_url": item.strm_url,
        "media_id": item.id,
        "title": item.title,
        "media_type": item.media_type,
    })
