"""
授权管理 Schema 定义
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LicenseKeyCreate(BaseModel):
    """创建授权码请求"""
    license_type: str = "permanent"   # permanent / subscription
    max_devices: int = 3
    expiry_days: int | None = None   # 订阅制：有效期天数；永久授权留空
    note: str | None = None


class LicenseKeyOut(BaseModel):
    """授权码输出（列表/详情）"""
    id: int
    key_display: str            # 明文 key（仅创建时返回一次）
    license_type: str
    max_devices: int
    expiry_date: datetime | None
    is_revoked: bool
    note: str | None
    created_at: datetime
    active_device_count: int = 0


class LicenseActivationOut(BaseModel):
    """激活记录输出"""
    id: int
    device_name: str | None
    device_fingerprint_short: str   # 短格式显示（前 8 位）
    first_activated_at: datetime
    last_seen_at: datetime
    is_active: bool
    unbound_at: datetime | None


class LicenseActivateRequest(BaseModel):
    """激活授权请求"""
    key: str                      # 明文 key，格式如 MS-XXXX-XXXX-XXXX-XXXX
    device_name: str | None = None


class LicenseStatusOut(BaseModel):
    """当前系统授权状态（所有用户可见）"""
    is_plus: bool
    license_type: str | None      # permanent / subscription / None
    expiry_date: datetime | None
    device_name: str | None
    max_devices: int | None
    days_remaining: int | None    # 订阅剩余天数
    license_key_id: int | None    # 当前激活的授权码 ID（管理员用）
    verification_mode: str = "local"  # "local" / "online"
    in_grace_period: bool = False
    grace_days_remaining: int | None = None


class LicenseConfigUpdate(BaseModel):
    """更新授权验证配置（管理员）"""
    verification_mode: str = "local"  # "local" / "online"
    server_url: str | None = None
    server_secret: str | None = None
    heartbeat_interval_days: int | None = None
    grace_period_days: int | None = None


class LicenseConfigOut(BaseModel):
    """授权验证配置输出"""
    verification_mode: str
    server_url: str | None
    server_secret_set: bool      # 是否已配置密钥（不返回明文）
    heartbeat_interval_days: int
    grace_period_days: int
    instance_id: str | None


class LicenseHeartbeatStatus(BaseModel):
    """心跳状态输出"""
    verification_mode: str
    last_verified_at: datetime | None
    last_heartbeat_at: datetime | None
    next_heartbeat_at: datetime | None
    grace_period_ends: datetime | None
    days_in_grace: int | None
