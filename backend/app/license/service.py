"""
授权管理服务层
- 生成授权码
- 激活 / 解绑设备
- 验证系统授权状态（本地 + 在线双模式）
- 吊销授权码
- 配置管理（验证模式、服务器连接、心跳参数）
- 在线刷新、心跳状态查询
"""
from __future__ import annotations

import hashlib
import logging
import random
import string
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.license.models import LicenseActivation, LicenseCache, LicenseKey
from app.license.schemas import (
    LicenseActivateRequest,
    LicenseConfigOut,
    LicenseConfigUpdate,
    LicenseHeartbeatStatus,
    LicenseKeyCreate,
    LicenseKeyOut,
    LicenseStatusOut,
)
from app.user.models import SystemConfig, User

logger = logging.getLogger(__name__)

KEY_PREFIX = "MS"
KEY_GROUP_LEN = 4
KEY_GROUPS = 4

# ── SystemConfig keys ──
CFG_MODE = "license_verification_mode"
CFG_URL = "license_server_url"
CFG_SECRET = "license_server_secret"
CFG_INSTANCE = "license_instance_id"
CFG_HB_INTERVAL = "license_heartbeat_interval_days"
CFG_GRACE_DAYS = "license_grace_period_days"


# ============================================================
# 授权码工具函数
# ============================================================

def generate_key_string() -> str:
    """生成格式 MS-ABCD-EFGH-IJKL-MNOP 的授权码"""
    chars = string.ascii_uppercase + string.digits
    # 移除易混淆字符
    chars = "".join(c for c in chars if c not in "O0I1")
    groups = []
    for _ in range(KEY_GROUPS):
        group = "".join(random.choices(chars, k=KEY_GROUP_LEN))
        groups.append(group)
    return f"{KEY_PREFIX}-" + "-".join(groups)


def compute_key_hash(key: str) -> str:
    """
    计算授权码 SHA-256 哈希
    输入可以是：
    1. raw_key 格式：MS-XXXX-XXXX-XXXX-XXXX（generate_key_string 返回值）
    2. key_display 格式：MSXX-XXXX-XXXX-XXXX-XXXX（format_key_display 返回值）
    统一转换为 raw_key 格式后计算哈希（与数据库存储一致）
    """
    k = key.strip().upper()
    # 去除所有连字符
    no_dash = k.replace("-", "")

    # 如果是以 MS 开头，长度 18（MS + 16位随机字符）
    if no_dash.startswith("MS") and len(no_dash) == 18:
        # 转换为 raw_key 格式：MS-XXXX-XXXX-XXXX-XXXX
        rest = no_dash[2:]  # 去掉 MS
        groups = [rest[i:i+4] for i in range(0, 16, 4)]
        raw_key = "MS-" + "-".join(groups)
        return hashlib.sha256(raw_key.encode()).hexdigest()

    # 否则，假设已经是 raw_key 格式或需要直接使用
    return hashlib.sha256(k.encode()).hexdigest()


def format_key_display(key: str) -> str:
    """格式化显示为 MS-XX..."""
    k = key.strip().upper().replace("-", "")
    if not k.startswith(KEY_PREFIX):
        k = KEY_PREFIX + k
    # 每 4 位加-
    parts = [k[i:i+4] for i in range(0, len(k), 4)]
    return "-".join(parts)


# ============================================================
# 配置管理（SystemConfig 读写）
# ============================================================

async def _get_config(db: AsyncSession, key: str, default: str = "") -> str:
    """读取 SystemConfig 值"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    cfg = result.scalar_one_or_none()
    return cfg.value if cfg else default


async def _set_config(db: AsyncSession, key: str, value: str) -> None:
    """写入或更新 SystemConfig"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.value = value
    else:
        cfg = SystemConfig(key=key, value=value)
        db.add(cfg)
    await db.flush()


async def get_license_config(db: AsyncSession) -> LicenseConfigOut:
    """获取当前授权验证配置"""
    mode = await _get_config(db, CFG_MODE, "local")
    url = await _get_config(db, CFG_URL)
    secret = await _get_config(db, CFG_SECRET)
    instance_id = await _get_config(db, CFG_INSTANCE)
    hb_interval = int(await _get_config(db, CFG_HB_INTERVAL, "7"))
    grace_days = int(await _get_config(db, CFG_GRACE_DAYS, "14"))

    return LicenseConfigOut(
        verification_mode=mode,
        server_url=url or None,
        server_secret_set=bool(secret),
        heartbeat_interval_days=hb_interval,
        grace_period_days=grace_days,
        instance_id=instance_id or None,
    )


async def update_license_config(
    data: LicenseConfigUpdate,
    db: AsyncSession,
) -> LicenseConfigOut:
    """更新授权验证配置（管理员）"""
    # 验证模式值
    if data.verification_mode not in ("local", "online"):
        raise HTTPException(400, "验证模式必须是 'local' 或 'online'")

    # 如果切换到在线模式，必须提供服务器 URL
    if data.verification_mode == "online" and not data.server_url:
        current_url = await _get_config(db, CFG_URL)
        if not current_url:
            raise HTTPException(400, "在线模式必须提供授权服务器 URL")

    # 写入配置
    await _set_config(db, CFG_MODE, data.verification_mode)

    if data.server_url is not None:
        await _set_config(db, CFG_URL, data.server_url.strip())
    if data.server_secret is not None:
        await _set_config(db, CFG_SECRET, data.server_secret.strip())
    if data.heartbeat_interval_days is not None:
        if data.heartbeat_interval_days < 1:
            raise HTTPException(400, "心跳间隔天数不能小于 1")
        await _set_config(db, CFG_HB_INTERVAL, str(data.heartbeat_interval_days))
    if data.grace_period_days is not None:
        if data.grace_period_days < 1:
            raise HTTPException(400, "宽限期天数不能小于 1")
        await _set_config(db, CFG_GRACE_DAYS, str(data.grace_period_days))

    # 首次使用时自动生成 instance_id
    instance_id = await _get_config(db, CFG_INSTANCE)
    if not instance_id:
        instance_id = str(uuid.uuid4())
        await _set_config(db, CFG_INSTANCE, instance_id)

    return await get_license_config(db)


async def test_server_connection(url: str, db: AsyncSession) -> dict:
    """测试与授权服务器的连通性"""
    if not url:
        raise HTTPException(400, "服务器 URL 不能为空")

    try:
        from app.license.remote_client import RemoteLicenseClient
        client = RemoteLicenseClient(url)
        ok = await client.test_connection()
        await client.close()
        return {"success": ok, "message": "连接成功" if ok else "连接失败，请检查 URL 和网络"}
    except ValueError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {e}"}


async def _get_instance_id(db: AsyncSession) -> str:
    """获取或创建 instance_id"""
    instance_id = await _get_config(db, CFG_INSTANCE)
    if not instance_id:
        instance_id = str(uuid.uuid4())
        await _set_config(db, CFG_INSTANCE, instance_id)
    return instance_id


# ============================================================
# 授权码生成 / 激活 / 管理
# ============================================================

async def generate_license(
    data: LicenseKeyCreate,
    created_by: int,
    db: AsyncSession,
) -> LicenseKeyOut:
    """生成新的授权码"""
    # 确保不重复
    max_attempts = 10
    for _ in range(max_attempts):
        raw_key = generate_key_string()
        key_hash = compute_key_hash(raw_key)
        key_display = format_key_display(raw_key)

        # 检查是否已存在
        existing = await db.execute(
            select(LicenseKey).where(LicenseKey.key_hash == key_hash)
        )
        if not existing.scalar_one_or_none():
            break
    else:
        raise HTTPException(500, "无法生成唯一授权码，请重试")

    # 计算过期时间
    expiry = None
    if data.license_type == "subscription" and data.expiry_days:
        expiry = datetime.now() + timedelta(days=data.expiry_days)

    license_key = LicenseKey(
        key_hash=key_hash,
        key_display=key_display,
        license_type=data.license_type,
        max_devices=data.max_devices,
        expiry_date=expiry,
        note=data.note,
        created_by=created_by,
    )
    db.add(license_key)
    await db.flush()

    return LicenseKeyOut(
        id=license_key.id,
        key_display=key_display,   # 仅此时返回明文
        license_type=license_key.license_type,
        max_devices=license_key.max_devices,
        expiry_date=license_key.expiry_date,
        is_revoked=license_key.is_revoked,
        note=license_key.note,
        created_at=license_key.created_at,
        active_device_count=0,
    )


async def activate_license(
    data: LicenseActivateRequest,
    db: AsyncSession,
) -> LicenseStatusOut:
    """
    激活授权码（绑定当前设备）。
    根据当前验证模式分流：
    - local: 走原有本地验证逻辑
    - online: 转发到远程授权服务器
    """
    mode = await _get_config(db, CFG_MODE, "local")

    if mode == "online":
        return await _activate_online(data, db)
    else:
        return await _activate_local(data, db)


async def _activate_local(
    data: LicenseActivateRequest,
    db: AsyncSession,
) -> LicenseStatusOut:
    """本地模式激活（原有逻辑）"""
    key_input = data.key.strip().upper()

    # 使用统一的哈希计算函数
    key_hash = compute_key_hash(key_input)

    # 查找授权码（通过哈希）
    result = await db.execute(
        select(LicenseKey).where(
            LicenseKey.key_hash == key_hash,
            LicenseKey.is_revoked == False,
        )
    )
    license_key = result.scalar_one_or_none()

    # 如果哈希不匹配，尝试根据 key_display 查找
    if not license_key:
        # 规范化用户输入（去除所有非字母数字字符）
        search_key = "".join(c for c in key_input if c.isalnum())
        result = await db.execute(
            select(LicenseKey).where(
                func.replace(LicenseKey.key_display, "-", "") == search_key,
                LicenseKey.is_revoked == False,
            )
        )
        license_key = result.scalar_one_or_none()

    if not license_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "授权码无效或已被吊销")

    # 检查是否过期
    if license_key.expiry_date and license_key.expiry_date < datetime.now():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "授权码已过期")

    # 获取设备指纹
    from app.license.fingerprint import get_device_fingerprint, get_device_name
    fingerprint = get_device_fingerprint()
    device_name = data.device_name or get_device_name()
    now = datetime.now()

    # 检查该设备是否已激活此授权
    existing_act = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.license_key_id == license_key.id,
            LicenseActivation.device_fingerprint == fingerprint,
        )
    )
    activation = existing_act.scalar_one_or_none()

    if activation:
        # 已激活：更新最后活跃时间
        activation.last_seen_at = now
        if not activation.is_active:
            activation.is_active = True
            activation.unbound_at = None
        await db.flush()
        return _build_status_out(license_key, activation, "local")
    # 检查设备数量限制
    active_count_result = await db.execute(
        select(func.count(LicenseActivation.id)).where(
            LicenseActivation.license_key_id == license_key.id,
            LicenseActivation.is_active == True,
        )
    )
    active_count = active_count_result.scalar() or 0

    if active_count >= license_key.max_devices:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"该授权码已达最大绑定设备数（{license_key.max_devices}）"
            f"，请先在已绑定设备中解绑本设备，或联系管理员增加设备限额。",
        )

    # 创建新激活记录
    activation = LicenseActivation(
        license_key_id=license_key.id,
        device_fingerprint=fingerprint,
        device_name=device_name,
        first_activated_at=now,
        last_seen_at=now,
        is_active=True,
    )
    db.add(activation)
    await db.flush()

    # 同时更新本地缓存（标记为 local 模式）
    from app.license.cache import LicenseCacheManager
    instance_id = await _get_instance_id(db)
    secret = await _get_config(db, CFG_SECRET)
    cache_mgr = LicenseCacheManager(db, hmac_secret=secret)
    await cache_mgr.save_local_activation(
        instance_id=instance_id,
        fingerprint=fingerprint,
        device_name=device_name,
        license_type=license_key.license_type,
        expiry_date=license_key.expiry_date,
        max_devices=license_key.max_devices,
    )

    return _build_status_out(license_key, activation, "local")


async def _activate_online(
    data: LicenseActivateRequest,
    db: AsyncSession,
) -> LicenseStatusOut:
    """在线模式激活 — 转发到远程授权服务器"""
    server_url = await _get_config(db, CFG_URL)
    secret = await _get_config(db, CFG_SECRET)
    instance_id = await _get_instance_id(db)

    if not server_url:
        raise HTTPException(500, "在线模式未配置授权服务器 URL")

    from app.license.fingerprint import get_device_fingerprint, get_device_name
    from app.license.remote_client import RemoteLicenseClient
    from app.license.cache import LicenseCacheManager

    fingerprint = get_device_fingerprint()
    device_name = data.device_name or get_device_name()

    client = RemoteLicenseClient(server_url)
    try:
        result = await client.activate(
            key=data.key,
            fingerprint=fingerprint,
            device_name=device_name,
            instance_id=instance_id,
        )
    except ConnectionError as e:
        raise HTTPException(502, f"无法连接授权服务器: {e}")
    except Exception as e:
        raise HTTPException(502, f"授权服务器通信失败: {e}")
    finally:
        await client.close()

    # 检查远程服务器响应
    if not result.get("valid"):
        error_msg = result.get("message", result.get("error", "激活失败"))
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"远程激活失败: {error_msg}",
        )

    # 验证签名并缓存
    cache_mgr = LicenseCacheManager(db, hmac_secret=secret)
    try:
        cache = await cache_mgr.save_online_result(
            instance_id=instance_id,
            fingerprint=fingerprint,
            server_response=result,
        )
    except ValueError as e:
        raise HTTPException(502, f"服务器响应签名验证失败: {e}")

    return LicenseStatusOut(
        is_plus=True,
        license_type=result.get("license_type"),
        expiry_date=datetime.fromisoformat(result["expiry_date"]) if result.get("expiry_date") else None,
        device_name=device_name,
        max_devices=result.get("max_devices", 3),
        days_remaining=result.get("days_remaining"),
        license_key_id=None,
        verification_mode="online",
        in_grace_period=False,
        grace_days_remaining=None,
    )


# ============================================================
# 授权状态查询（增强双模式）
# ============================================================

async def get_license_status(db: AsyncSession) -> LicenseStatusOut:
    """
    获取当前系统授权状态。
    优先检查在线缓存，再回退到本地验证。
    """
    mode = await _get_config(db, CFG_MODE, "local")

    if mode == "online":
        return await _get_online_status(db)
    else:
        return await _get_local_status(db)


async def _get_local_status(db: AsyncSession) -> LicenseStatusOut:
    """本地模式授权状态查询"""
    now = datetime.now()
    result = await db.execute(
        select(LicenseKey, LicenseActivation)
        .join(LicenseActivation, LicenseActivation.license_key_id == LicenseKey.id)
        .where(
            LicenseKey.is_revoked == False,
            LicenseActivation.is_active == True,
        )
        .order_by(LicenseKey.created_at.desc())
    )
    rows = result.all()

    # 优先级：订阅（有期限）> 永久
    selected_lic = None
    selected_act = None

    for lic, act in rows:
        if lic.expiry_date and lic.expiry_date < now:
            continue  # 已过期的订阅，跳过
        if selected_lic is None:
            selected_lic = lic
            selected_act = act
        elif lic.license_type == "subscription" and selected_lic.license_type == "permanent":
            selected_lic = lic
            selected_act = act

    if not selected_lic:
        return LicenseStatusOut(
            is_plus=False,
            license_type=None,
            expiry_date=None,
            device_name=None,
            max_devices=None,
            days_remaining=None,
            license_key_id=None,
            verification_mode="local",
        )

    days_remaining = None
    if selected_lic.expiry_date:
        delta = selected_lic.expiry_date - now
        days_remaining = max(0, delta.days)

    return LicenseStatusOut(
        is_plus=True,
        license_type=selected_lic.license_type,
        expiry_date=selected_lic.expiry_date,
        device_name=selected_act.device_name if selected_act else None,
        max_devices=selected_lic.max_devices,
        days_remaining=days_remaining,
        license_key_id=selected_lic.id,
        verification_mode="local",
    )


async def _get_online_status(db: AsyncSession) -> LicenseStatusOut:
    """
    在线模式授权状态查询。
    优先读取 license_cache 缓存，判断是否在宽限期内。
    """
    from app.license.cache import LicenseCacheManager

    secret = await _get_config(db, CFG_SECRET)
    cache_mgr = LicenseCacheManager(db, hmac_secret=secret)
    cache = await cache_mgr.get_cache()

    if not cache or not cache.license_type:
        # 无缓存记录，等同未授权
        return LicenseStatusOut(
            is_plus=False,
            license_type=None,
            expiry_date=None,
            device_name=None,
            max_devices=None,
            days_remaining=None,
            license_key_id=None,
            verification_mode="online",
            in_grace_period=False,
            grace_days_remaining=None,
        )

    # 检查宽限期
    in_grace = cache.grace_period_ends is not None and datetime.now() < cache.grace_period_ends
    grace_expired = cache.grace_period_ends is not None and datetime.now() >= cache.grace_period_ends

    if grace_expired:
        # 宽限期已过，降级为免费版
        logger.warning("在线授权宽限期已过期，降级为免费版")
        return LicenseStatusOut(
            is_plus=False,
            license_type=cache.license_type,
            expiry_date=cache.expiry_date,
            device_name=cache.device_name,
            max_devices=cache.max_devices,
            days_remaining=cache.days_remaining,
            license_key_id=None,
            verification_mode="online",
            in_grace_period=False,
            grace_days_remaining=0,
        )

    # 检查订阅过期
    if cache.expiry_date and cache.expiry_date < datetime.now():
        return LicenseStatusOut(
            is_plus=False,
            license_type=cache.license_type,
            expiry_date=cache.expiry_date,
            device_name=cache.device_name,
            max_devices=cache.max_devices,
            days_remaining=0,
            license_key_id=None,
            verification_mode="online",
            in_grace_period=False,
            grace_days_remaining=None,
        )

    grace_days = cache_mgr.get_grace_days_remaining(cache)

    return LicenseStatusOut(
        is_plus=True,
        license_type=cache.license_type,
        expiry_date=cache.expiry_date,
        device_name=cache.device_name,
        max_devices=cache.max_devices,
        days_remaining=cache.days_remaining,
        license_key_id=None,
        verification_mode="online",
        in_grace_period=in_grace,
        grace_days_remaining=grace_days,
    )


# ============================================================
# 在线刷新 & 心跳状态
# ============================================================

async def refresh_online_license(db: AsyncSession) -> LicenseStatusOut:
    """
    手动刷新在线授权（立即发送心跳，不等待定时器）。
    用户点击「立即刷新」按钮时调用。
    """
    mode = await _get_config(db, CFG_MODE, "local")
    if mode != "online":
        raise HTTPException(400, "当前为本地验证模式，无需刷新在线授权")

    server_url = await _get_config(db, CFG_URL)
    secret = await _get_config(db, CFG_SECRET)
    instance_id = await _get_instance_id(db)

    if not server_url:
        raise HTTPException(500, "未配置授权服务器 URL")

    from app.license.fingerprint import get_device_fingerprint
    from app.license.remote_client import RemoteLicenseClient
    from app.license.cache import LicenseCacheManager

    fingerprint = get_device_fingerprint()
    cache_mgr = LicenseCacheManager(db, hmac_secret=secret)
    cache = await cache_mgr.get_cache()

    # 构造缓存信息（用于心跳请求）
    cached_info = None
    if cache:
        cached_info = {
            "license_type": cache.license_type,
            "activated_at": cache.last_verified_at.isoformat() if cache.last_verified_at else None,
        }

    client = RemoteLicenseClient(server_url)
    try:
        result = await client.heartbeat(
            fingerprint=fingerprint,
            instance_id=instance_id,
            cached_info=cached_info,
        )
    except ConnectionError as e:
        # 网络失败，记录宽限期但不降级
        await cache_mgr.record_heartbeat_failure(
            instance_id,
            grace_period_days=int(await _get_config(db, CFG_GRACE_DAYS, "14")),
        )
        raise HTTPException(502, f"无法连接授权服务器，已进入宽限期: {e}")
    except Exception as e:
        raise HTTPException(502, f"授权服务器通信失败: {e}")
    finally:
        await client.close()

    # 检查服务器是否仍然认可此授权
    if not result.get("valid"):
        error_msg = result.get("message", result.get("error", "授权已失效"))
        # 清除缓存
        await cache_mgr.clear_cache(instance_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"授权已失效: {error_msg}")

    # 验证签名并更新缓存
    try:
        await cache_mgr.save_online_result(
            instance_id=instance_id,
            fingerprint=fingerprint,
            server_response=result,
        )
    except ValueError as e:
        raise HTTPException(502, f"服务器响应签名验证失败: {e}")

    return await _get_online_status(db)


async def get_heartbeat_status(db: AsyncSession) -> LicenseHeartbeatStatus:
    """获取心跳状态详情"""
    mode = await _get_config(db, CFG_MODE, "local")

    if mode != "online":
        return LicenseHeartbeatStatus(
            verification_mode="local",
            last_verified_at=None,
            last_heartbeat_at=None,
            next_heartbeat_at=None,
            grace_period_ends=None,
            days_in_grace=None,
        )

    from app.license.cache import LicenseCacheManager

    secret = await _get_config(db, CFG_SECRET)
    cache_mgr = LicenseCacheManager(db, hmac_secret=secret)
    cache = await cache_mgr.get_cache()

    if not cache:
        return LicenseHeartbeatStatus(
            verification_mode="online",
            last_verified_at=None,
            last_heartbeat_at=None,
            next_heartbeat_at=None,
            grace_period_ends=None,
            days_in_grace=None,
        )

    grace_days = cache_mgr.get_grace_days_remaining(cache)

    return LicenseHeartbeatStatus(
        verification_mode="online",
        last_verified_at=cache.last_verified_at,
        last_heartbeat_at=cache.last_heartbeat_at,
        next_heartbeat_at=cache.next_heartbeat_at,
        grace_period_ends=cache.grace_period_ends,
        days_in_grace=grace_days,
    )


# ============================================================
# 管理员操作
# ============================================================

async def list_licenses(db: AsyncSession) -> list[LicenseKeyOut]:
    """列出所有授权码（管理员）"""
    result = await db.execute(
        select(LicenseKey).order_by(LicenseKey.created_at.desc())
    )
    keys = result.scalars().all()

    out = []
    for key in keys:
        # 统计活跃设备数
        count_result = await db.execute(
            select(func.count(LicenseActivation.id)).where(
                LicenseActivation.license_key_id == key.id,
                LicenseActivation.is_active == True,
            )
        )
        active_count = count_result.scalar() or 0

        out.append(LicenseKeyOut(
            id=key.id,
            key_display=key.key_display,
            license_type=key.license_type,
            max_devices=key.max_devices,
            expiry_date=key.expiry_date,
            is_revoked=key.is_revoked,
            note=key.note,
            created_at=key.created_at,
            active_device_count=active_count,
        ))
    return out


async def get_activations(key_id: int, db: AsyncSession) -> list[dict]:
    """获取某授权码的设备激活列表"""
    result = await db.execute(
        select(LicenseActivation)
        .where(LicenseActivation.license_key_id == key_id)
        .order_by(LicenseActivation.last_seen_at.desc())
    )
    activations = result.scalars().all()

    return [
        {
            "id": a.id,
            "device_name": a.device_name,
            "device_fingerprint_short": a.device_fingerprint[:8] + "..." if len(a.device_fingerprint) > 8 else a.device_fingerprint,
            "first_activated_at": a.first_activated_at,
            "last_seen_at": a.last_seen_at,
            "is_active": a.is_active,
            "unbound_at": a.unbound_at,
        }
        for a in activations
    ]


async def revoke_license(key_id: int, db: AsyncSession):
    """吊销授权码"""
    result = await db.execute(
        select(LicenseKey).where(LicenseKey.id == key_id)
    )
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "授权码不存在")

    lic.is_revoked = True

    # 停用所有活跃设备
    await db.execute(
        LicenseActivation.__table__.update()
        .where(LicenseActivation.license_key_id == key_id)
        .values(is_active=False, unbound_at=datetime.now())
    )


async def unbind_device(activation_id: int, db: AsyncSession):
    """解绑设备（管理员）"""
    result = await db.execute(
        select(LicenseActivation).where(LicenseActivation.id == activation_id)
    )
    activation = result.scalar_one_or_none()
    if not activation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "激活记录不存在")

    activation.is_active = False
    activation.unbound_at = datetime.now()


async def unbind_current_device(db: AsyncSession):
    """解绑当前设备"""
    from app.license.fingerprint import get_device_fingerprint
    fingerprint = get_device_fingerprint()

    result = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.device_fingerprint == fingerprint,
            LicenseActivation.is_active == True,
        )
    )
    activation = result.scalar_one_or_none()
    if not activation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "当前设备未绑定任何授权")

    activation.is_active = False
    activation.unbound_at = datetime.now()

    # 同时清除在线缓存
    from app.license.cache import LicenseCacheManager
    instance_id = await _get_instance_id(db)
    secret = await _get_config(db, CFG_SECRET)
    cache_mgr = LicenseCacheManager(db, hmac_secret=secret)
    await cache_mgr.clear_cache(instance_id)


# ============================================================
# 内部工具
# ============================================================

def _build_status_out(
    lic: LicenseKey,
    act: LicenseActivation | None,
    verification_mode: str = "local",
) -> LicenseStatusOut:
    """从 LicenseKey + Activation 构造 LicenseStatusOut"""
    now = datetime.now()
    days_remaining = None
    if lic.expiry_date:
        delta = lic.expiry_date - now
        days_remaining = max(0, delta.days)

    return LicenseStatusOut(
        is_plus=True,
        license_type=lic.license_type,
        expiry_date=lic.expiry_date,
        device_name=act.device_name if act else None,
        max_devices=lic.max_devices,
        days_remaining=days_remaining,
        license_key_id=lic.id,
        verification_mode=verification_mode,
    )


async def check_system_license(db: AsyncSession) -> bool:
    """检查系统是否有有效授权（用于启动时设置 tier）"""
    status = await get_license_status(db)
    return status.is_plus
