"""License API Pydantic schemas"""
from typing import Optional
from pydantic import BaseModel


class LicenseStatusOut(BaseModel):
    """License status response"""
    is_plus: bool
    license_type: Optional[str] = None
    expiry_date: Optional[str] = None
    device_name: Optional[str] = None
    max_devices: Optional[int] = None
    days_remaining: Optional[int] = None
    license_key_id: Optional[int] = None
    verification_mode: str = "local"
    in_grace_period: bool = False
    grace_days_remaining: Optional[int] = None


class LicenseConfigOut(BaseModel):
    """License configuration response"""
    verification_mode: str = "local"
    server_url: Optional[str] = None
    server_secret_set: bool = False
    heartbeat_interval_days: int = 7
    grace_period_days: int = 14
    instance_id: Optional[str] = None


class LicenseConfigUpdate(BaseModel):
    """License configuration update request"""
    verification_mode: Optional[str] = None
    server_url: Optional[str] = None
    server_secret: Optional[str] = None
    heartbeat_interval_days: Optional[int] = None
    grace_period_days: Optional[int] = None


class LicenseKeyCreate(BaseModel):
    """License key generation request"""
    license_type: str = "permanent"
    max_devices: int = 3
    expiry_days: Optional[int] = None
    note: Optional[str] = None


class LicenseKeyOut(BaseModel):
    """License key response"""
    id: int
    key_display: str
    license_type: str
    max_devices: int
    expiry_date: Optional[str] = None
    is_revoked: bool = False
    note: Optional[str] = None
    created_at: str
    active_device_count: int = 0


class LicenseActivationOut(BaseModel):
    """License activation response"""
    id: int
    device_name: Optional[str] = None
    device_fingerprint_short: str
    first_activated_at: str
    last_seen_at: str
    is_active: bool = True
    unbound_at: Optional[str] = None


class LicenseHeartbeatStatus(BaseModel):
    """License heartbeat status"""
    verification_mode: str = "local"
    last_verified_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    next_heartbeat_at: Optional[str] = None
    grace_period_ends: Optional[str] = None
    days_in_grace: Optional[int] = None


class ActivateRequest(BaseModel):
    """License activation request"""
    key: str


class TestConnectionResponse(BaseModel):
    """Test connection response"""
    success: bool
    message: str


class GenerateKeyResponse(BaseModel):
    """Generate key response"""
    key: str
    key_display: str
