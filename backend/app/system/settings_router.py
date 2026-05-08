"""
整理 & 刮削配置 API
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.deps import DB, require_admin
from app.system.settings_service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_admin)],
)


class SettingUpdate(BaseModel):
    value: str


class SettingBatchUpdate(BaseModel):
    settings: dict[str, str]


# ── API 端点 ──

@router.get("")
async def get_all_settings(
    db: DB,
) -> dict[str, str]:
    """获取所有配置"""
    service = SettingsService(db)
    return await service.get_all()


@router.get("/schema")
async def get_settings_schema() -> dict[str, Any]:
    """获取配置 Schema（用于前端渲染表单）"""
    service = SettingsService(None)  # schema 不需要 db
    return {
        "groups": service.get_grouped_schema(),
        "schema": service.get_schema(),
    }


@router.get("/{key}")
async def get_setting(
    key: str,
    db: DB,
) -> dict[str, str | None]:
    """获取单个配置"""
    service = SettingsService(db)
    value = await service.get(key)
    return {"key": key, "value": value}


@router.put("/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    db: DB,
) -> dict[str, Any]:
    """更新单个配置"""
    service = SettingsService(db)
    await service.set(key, body.value)
    return {"key": key, "value": body.value, "success": True}


@router.patch("")
async def batch_update_settings(
    body: SettingBatchUpdate,
    db: DB,
) -> dict[str, Any]:
    """批量更新配置"""
    service = SettingsService(db)
    count = await service.set_many(body.settings)
    return {"updated": count, "success": True}


@router.delete("/{key}")
async def reset_setting(
    key: str,
    db: DB,
) -> dict[str, Any]:
    """重置单个配置为默认值（删除记录）"""
    service = SettingsService(db)
    deleted = await service.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": key, "success": True, "message": "已重置为默认值"}


@router.delete("")
async def reset_all_settings(
    db: DB,
) -> dict[str, Any]:
    """重置所有配置为默认值"""
    service = SettingsService(db)
    count = await service.reset_all()
    return {"reset": count, "success": True, "message": "所有配置已重置"}
