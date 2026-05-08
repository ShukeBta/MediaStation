"""
授权管理路由
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AdminUser, CurrentUser, DB
from app.license.schemas import (
    LicenseActivateRequest,
    LicenseConfigOut,
    LicenseConfigUpdate,
    LicenseHeartbeatStatus,
    LicenseKeyCreate,
    LicenseKeyOut,
    LicenseStatusOut,
)
from app.license.service import (
    activate_license,
    generate_license,
    get_activations,
    get_heartbeat_status,
    get_license_config,
    get_license_status,
    list_licenses,
    refresh_online_license,
    revoke_license,
    test_server_connection,
    unbind_current_device,
    unbind_device,
    update_license_config,
)

router = APIRouter(prefix="/license", tags=["license"])


# ── 配置管理（管理员） ──

@router.get("/config", response_model=LicenseConfigOut)
async def get_config(user: AdminUser, db: DB):
    """获取授权验证配置"""
    return await get_license_config(db)


@router.post("/config", response_model=LicenseConfigOut)
async def set_config(data: LicenseConfigUpdate, user: AdminUser, db: DB):
    """更新授权验证配置"""
    return await update_license_config(data, db)


@router.post("/config/test")
async def test_connection(url: str, user: AdminUser, db: DB):
    """测试授权服务器连通性"""
    return await test_server_connection(url, db)


# ── 在线验证操作 ──

@router.post("/refresh", response_model=LicenseStatusOut)
async def refresh(user: CurrentUser, db: DB):
    """手动刷新在线授权（立即发送心跳）"""
    return await refresh_online_license(db)


@router.get("/heartbeat-status", response_model=LicenseHeartbeatStatus)
async def heartbeat_status(user: CurrentUser, db: DB):
    """获取心跳状态详情"""
    return await get_heartbeat_status(db)


# ── 管理员接口 ──

@router.post("/generate", response_model=LicenseKeyOut)
async def generate(data: LicenseKeyCreate, user: AdminUser, db: DB):
    """生成新的授权码"""
    return await generate_license(data, user.id, db)


@router.get("/list", response_model=list[LicenseKeyOut])
async def list_all(user: AdminUser, db: DB):
    """列出所有授权码"""
    return await list_licenses(db)


@router.get("/{key_id}/activations")
async def get_device_activations(key_id: int, user: AdminUser, db: DB):
    """查看某授权码的设备激活列表"""
    return await get_activations(key_id, db)


@router.post("/{key_id}/revoke")
async def revoke(key_id: int, user: AdminUser, db: DB):
    """吊销授权码"""
    await revoke_license(key_id, db)
    return {"success": True, "message": "授权码已吊销"}


@router.post("/activation/{activation_id}/unbind")
async def unbind(activation_id: int, user: AdminUser, db: DB):
    """管理员解绑某设备"""
    await unbind_device(activation_id, db)
    return {"success": True, "message": "设备已解绑"}


# ── 所有认证用户接口 ──

@router.post("/activate")
async def activate(
    data: LicenseActivateRequest, user: CurrentUser, db: DB
):
    """激活授权码（绑定当前设备）"""
    return await activate_license(data, db)


@router.get("/status", response_model=LicenseStatusOut)
async def status(db: DB):
    """查看当前系统授权状态"""
    return await get_license_status(db)


@router.post("/unbind")
async def unbind_current(user: CurrentUser, db: DB):
    """解绑当前设备"""
    await unbind_current_device(db)
    return {"success": True, "message": "当前设备已解绑"}
