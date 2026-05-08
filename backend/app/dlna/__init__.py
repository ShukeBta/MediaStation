# -*- coding: utf-8 -*-
"""
DLNA/投屏 API - 本地模式（stub）
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/dlna", tags=["投屏"])


@router.get("/devices")
async def discover_devices(force: bool = False):
    """发现 DLNA 设备 - 本地模式返回空列表"""
    return {"devices": []}


@router.get("/devices/{device_id}")
async def get_device(device_id: str):
    """获取设备信息"""
    raise HTTPException(status_code=404, detail="DLNA not available in local mode")


@router.post("/cast")
async def cast_media():
    """投屏媒体"""
    raise HTTPException(status_code=404, detail="DLNA not available in local mode")
