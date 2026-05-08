"""
本地授权缓存管理器
管理 license_cache 表，提供读/写/验证/宽限期计算等功能。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.license.crypto import verify_server_signature
from app.license.models import LicenseCache

logger = logging.getLogger(__name__)


class LicenseCacheManager:
    """管理本地 license_cache 表"""

    def __init__(self, db: AsyncSession, hmac_secret: str = ""):
        self.db = db
        self.hmac_secret = hmac_secret

    async def get_cache(self) -> LicenseCache | None:
        """读取当前缓存记录"""
        result = await self.db.execute(
            select(LicenseCache).order_by(LicenseCache.updated_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, instance_id: str) -> LicenseCache:
        """获取或创建缓存记录"""
        cache = await self.get_cache()
        if cache:
            return cache

        cache = LicenseCache(
            instance_id=instance_id,
            verification_mode="local",
            license_type="",
            max_devices=0,
            signature="",
            last_verified_at=datetime.now(),
            next_heartbeat_at=datetime.now() + timedelta(days=7),
        )
        self.db.add(cache)
        await self.db.flush()
        return cache

    async def save_online_result(
        self,
        instance_id: str,
        fingerprint: str,
        server_response: dict,
    ) -> LicenseCache:
        """
        保存远程验证结果到本地缓存。
        会先验证服务器签名。
        """
        signature = server_response.get("signature", "")
        if not verify_server_signature(server_response, signature, self.hmac_secret):
            logger.warning("服务器签名验证失败，拒绝缓存此结果")
            raise ValueError("服务器响应签名无效")

        cache = await self.get_or_create(instance_id)

        # 解析服务器响应
        now = datetime.now()
        next_hb = server_response.get("next_heartbeat")
        expiry = server_response.get("expiry_date")

        cache.verification_mode = "online"
        cache.license_type = server_response.get("license_type", "")
        cache.expiry_date = datetime.fromisoformat(expiry) if expiry else None
        cache.device_fingerprint = fingerprint
        cache.device_name = server_response.get("device_name")
        cache.max_devices = server_response.get("max_devices", 3)
        cache.days_remaining = server_response.get("days_remaining")
        cache.signature = signature
        cache.last_verified_at = now
        cache.last_heartbeat_at = now
        cache.next_heartbeat_at = datetime.fromisoformat(next_hb) if next_hb else now + timedelta(days=7)
        cache.grace_period_ends = None  # 成功验证，清除宽限期

        await self.db.flush()
        logger.info("在线验证结果已缓存")
        return cache

    async def record_heartbeat_failure(self, instance_id: str, grace_period_days: int = 14) -> LicenseCache:
        """记录心跳失败，启动或延续宽限期"""
        cache = await self.get_or_create(instance_id)
        now = datetime.now()

        if cache.grace_period_ends is None:
            # 首次失败，启动宽限期
            cache.grace_period_ends = now + timedelta(days=grace_period_days)
            logger.warning(f"心跳失败，启动 {grace_period_days} 天宽限期，到期: {cache.grace_period_ends}")

        await self.db.flush()
        return cache

    def is_in_grace_period(self, cache: LicenseCache) -> bool:
        """检查是否仍在宽限期内"""
        if cache.grace_period_ends is None:
            return True  # 没有启动宽限期 = 一切正常
        return datetime.now() < cache.grace_period_ends

    def get_grace_days_remaining(self, cache: LicenseCache) -> int | None:
        """获取宽限期剩余天数"""
        if cache.grace_period_ends is None:
            return None
        delta = cache.grace_period_ends - datetime.now()
        return max(0, delta.days)

    async def save_local_activation(
        self,
        instance_id: str,
        fingerprint: str,
        device_name: str | None,
        license_type: str,
        expiry_date: datetime | None,
        max_devices: int,
    ) -> LicenseCache:
        """保存本地模式激活结果"""
        cache = await self.get_or_create(instance_id)
        now = datetime.now()

        cache.verification_mode = "local"
        cache.license_type = license_type
        cache.expiry_date = expiry_date
        cache.device_fingerprint = fingerprint
        cache.device_name = device_name
        cache.max_devices = max_devices
        cache.days_remaining = None
        cache.signature = ""
        cache.last_verified_at = now
        cache.next_heartbeat_at = now + timedelta(days=9999)  # 本地模式不需要心跳
        cache.grace_period_ends = None

        await self.db.flush()
        return cache

    async def clear_cache(self, instance_id: str) -> None:
        """清除缓存（用于解绑/降级）"""
        cache = await self.get_cache()
        if cache:
            cache.license_type = ""
            cache.signature = ""
            cache.verification_mode = "local"
            cache.grace_period_ends = None
            await self.db.flush()
