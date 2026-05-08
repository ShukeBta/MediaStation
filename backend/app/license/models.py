"""
授权管理数据模型
LicenseKey: 授权码主表
LicenseActivation: 设备激活记录表
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_models import Base, TimestampMixin


class LicenseKey(TimestampMixin, Base):
    """授权码表 — 存储激活密钥及授权信息"""
    __tablename__ = "license_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_display: Mapped[str] = mapped_column(String(32), nullable=False)
    license_type: Mapped[str] = mapped_column(String(20), default="permanent")
    max_devices: Mapped[int] = mapped_column(default=3)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # 关联
    activated_devices: Mapped[list["LicenseActivation"]] = relationship(
        "LicenseActivation", back_populates="license_key", cascade="all, delete-orphan"
    )


class LicenseCache(TimestampMixin, Base):
    """本地缓存 — 远程在线验证结果"""
    __tablename__ = "license_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instance_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    license_type: Mapped[str] = mapped_column(String(20), default="")
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    device_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_devices: Mapped[int] = mapped_column(default=0)
    days_remaining: Mapped[int | None] = mapped_column(nullable=True)
    signature: Mapped[str] = mapped_column(String(128), default="")
    last_verified_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_mode: Mapped[str] = mapped_column(String(20), default="local")
    grace_period_ends: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LicenseActivation(TimestampMixin, Base):
    """设备激活记录表 — 记录每个授权码绑定的设备"""
    __tablename__ = "license_activations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    license_key_id: Mapped[int] = mapped_column(
        ForeignKey("license_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_activated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关联
    license_key: Mapped["LicenseKey"] = relationship(back_populates="activated_devices")
