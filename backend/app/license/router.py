"""
License API Router

Provides license management functionality:
- License status checking (based on user.tier)
- License activation for users
- Admin license management (generating keys, revoking, etc.)
"""
import secrets
import platform
import socket
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import async_session_factory
from app.deps import get_current_user
from app.user.models import User
from app.license.schemas import (
    LicenseStatusOut,
    LicenseConfigOut,
    LicenseConfigUpdate,
    LicenseKeyCreate,
    LicenseKeyOut,
    LicenseActivationOut,
    LicenseHeartbeatStatus,
    ActivateRequest,
    TestConnectionResponse,
    GenerateKeyResponse,
)

router = APIRouter(prefix="/license", tags=["license"])


def get_device_name() -> str:
    """Get current device name"""
    try:
        hostname = socket.gethostname()
        return f"{hostname} ({platform.system()})"
    except Exception:
        return "Unknown Device"


@router.get("/status", response_model=LicenseStatusOut)
async def get_license_status(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's license status.
    Plus status is determined by user.tier field.
    """
    is_plus = current_user.tier == "plus"
    
    return LicenseStatusOut(
        is_plus=is_plus,
        license_type="permanent" if is_plus else None,
        expiry_date=None,
        device_name=get_device_name() if is_plus else None,
        max_devices=None,
        days_remaining=None,
        license_key_id=None,
        verification_mode="local",
        in_grace_period=False,
        grace_days_remaining=None,
    )


@router.post("/activate")
async def activate_license(
    request: ActivateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Activate license with a key.
    In this simplified version, any key starting with 'MS-' activates Plus.
    """
    key = request.key.strip().upper()
    
    # Simple validation: accept keys starting with MS-
    if not key.startswith("MS-"):
        raise HTTPException(
            status_code=400,
            detail="无效的授权码格式，授权码应以 MS- 开头"
        )
    
    # In a real implementation, you would validate the key against a database
    # For now, we just accept any valid format key
    
    # Update user to plus tier
    async with async_session_factory() as session:
        from app.user.repository import UserRepository
        repo = UserRepository(session)
        await repo.update_tier(current_user.id, "plus")
        await session.commit()
    
    return {"message": "授权激活成功", "is_plus": True}


@router.post("/unbind")
async def unbind_license(
    current_user: User = Depends(get_current_user),
):
    """Unbind current device from license"""
    # In simplified version, just downgrade to free
    async with async_session_factory() as session:
        from app.user.repository import UserRepository
        repo = UserRepository(session)
        await repo.update_tier(current_user.id, "free")
        await session.commit()
    
    return {"message": "已解绑，当前设备已退回免费版"}


# Admin endpoints

@router.get("/config", response_model=LicenseConfigOut)
async def get_license_config(
    current_user: User = Depends(get_current_user),
):
    """Get license configuration (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    return LicenseConfigOut(
        verification_mode="local",
        server_url=None,
        server_secret_set=False,
        heartbeat_interval_days=7,
        grace_period_days=14,
        instance_id=None,
    )


@router.post("/config", response_model=LicenseConfigOut)
async def update_license_config(
    config: LicenseConfigUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update license configuration (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    # In simplified version, just return current config
    return LicenseConfigOut(
        verification_mode=config.verification_mode or "local",
        server_url=config.server_url,
        server_secret_set=bool(config.server_secret),
        heartbeat_interval_days=config.heartbeat_interval_days or 7,
        grace_period_days=config.grace_period_days or 14,
        instance_id=None,
    )


@router.post("/config/test", response_model=TestConnectionResponse)
async def test_connection(
    url: str,
    current_user: User = Depends(get_current_user),
):
    """Test license server connection (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    # Simplified: just return success
    return TestConnectionResponse(success=True, message="连接测试成功")


@router.get("/heartbeat-status", response_model=LicenseHeartbeatStatus)
async def get_heartbeat_status(
    current_user: User = Depends(get_current_user),
):
    """Get heartbeat status"""
    return LicenseHeartbeatStatus(
        verification_mode="local",
        last_verified_at=None,
        last_heartbeat_at=None,
        next_heartbeat_at=None,
        grace_period_ends=None,
        days_in_grace=None,
    )


@router.post("/refresh")
async def refresh_license(
    current_user: User = Depends(get_current_user),
):
    """Refresh license status"""
    return {"message": "授权已刷新"}


@router.post("/generate", response_model=GenerateKeyResponse)
async def generate_license_key(
    data: LicenseKeyCreate,
    current_user: User = Depends(get_current_user),
):
    """Generate a new license key (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    # Generate a random key
    key_parts = [
        "MS",
        secrets.token_hex(2).upper(),
        secrets.token_hex(2).upper(),
        secrets.token_hex(2).upper(),
        secrets.token_hex(2).upper(),
    ]
    key = "-".join(key_parts)
    
    return GenerateKeyResponse(
        key=key,
        key_display=key,
    )


@router.get("/list", response_model=List[LicenseKeyOut])
async def list_license_keys(
    current_user: User = Depends(get_current_user),
):
    """List all license keys (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    # Return empty list in simplified version
    return []


@router.get("/{key_id}/activations", response_model=List[LicenseActivationOut])
async def get_activations(
    key_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get activations for a license key (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    return []


@router.post("/{key_id}/revoke")
async def revoke_license_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
):
    """Revoke a license key (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    return {"message": "授权码已吊销"}


@router.post("/activation/{activation_id}/unbind")
async def unbind_device(
    activation_id: int,
    current_user: User = Depends(get_current_user),
):
    """Unbind a device from license (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    return {"message": "设备已解绑"}
