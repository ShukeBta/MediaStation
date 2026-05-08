"""
DLNA 路由 — 设备发现和媒体投屏控制
"""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.deps import AdminUser, CurrentUser, DB
from app.dlna import DeviceDiscovery, MediaRenderer

router = APIRouter(prefix="/dlna", tags=["dlna"])

# 设备缓存（减少频繁搜索）
_device_cache: list[dict] = []
_cache_time: float = 0
CACHE_TTL = 30.0  # 秒


class CastRequest(BaseModel):
    """投屏请求"""
    device_uuid: str           # 目标设备 UUID
    media_url: str             # 媒体 URL
    title: str | None = None   # 媒体标题（用于显示）


class DeviceControlRequest(BaseModel):
    """设备控制请求"""
    device_uuid: str


@router.get("/devices")
async def discover_devices(user: CurrentUser, force: bool = Query(False)):
    """发现网络中的 DLNA 设备

    默认使用缓存（30秒 TTL），force=true 强制重新搜索。
    """
    global _device_cache, _cache_time

    import time
    now = time.time()

    if not force and _device_cache and (now - _cache_time) < CACHE_TTL:
        return {"devices": _device_cache, "cached": True}

    discovery = DeviceDiscovery()
    devices = await discovery.discover()

    # 缓存结果
    _device_cache = [_device_to_dict(d) for d in devices]
    _cache_time = now

    return {"devices": _device_cache, "cached": False}


@router.post("/cast")
async def cast_media(request: CastRequest, user: CurrentUser):
    """推送媒体到 DLNA 设备播放"""
    from app.dlna import get_dlna_discovery

    discovery = get_dlna_discovery()
    devices = await discovery.discover()

    # 查找目标设备
    target = next((d for d in devices if d.uuid == request.device_uuid), None)
    if not target:
        return {"ok": False, "error": f"Device not found: {request.device_uuid}"}

    if not target.control_url:
        return {"ok": False, "error": f"Device '{target.name}' has no control URL (not a MediaRenderer)"}

    renderer = MediaRenderer(target)

    try:
        # 构建元数据
        metadata = ""
        if request.title:
            metadata = f'''<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
<item id="0" parentID="-1" restricted="1">
  <res protocolInfo="http-get:*:video/mp4:*">{request.media_url}</res>
  <dc:title>{request.title}</dc:title>
  <upnp:class>object.item.videoItem</upnp:class>
</item>
</DIDL-Lite>'''

        # 设置 URI → Play
        ok = await renderer.set_av_transport_uri(request.media_url, metadata)
        if not ok:
            return {"ok": False, "error": "Failed to set media URI on device"}

        await asyncio.sleep(0.3)  # 短暂等待
        ok = await renderer.play()
        if not ok:
            return {"ok": False, "error": "Failed to start playback"}

        return {
            "ok": True,
            "device_name": target.name,
            "message": f"已推送到 {target.name}",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await renderer.close()


@router.post("/{uuid}/play")
async def device_play(uuid: str, user: CurrentUser):
    """恢复设备播放"""
    result = await _control_device(uuid, lambda r: r.play())
    return result


@router.post("/{uuid}/pause")
async def device_pause(uuid: str, user: CurrentUser):
    """暂停设备播放"""
    result = await _control_device(uuid, lambda r: r.pause())
    return result


@router.post("/{uuid}/stop")
async def device_stop(uuid: str, user: CurrentUser):
    """停止设备播放"""
    result = await _control_device(uuid, lambda r: r.stop())
    return result


@router.get("/{uuid}/status")
async def device_status(uuid: str, user: CurrentUser):
    """获取设备播放状态"""
    transport_info = {}
    position_info = {}

    async def get_status(r: MediaRenderer):
        nonlocal transport_info, position_info
        transport_info = await r.get_transport_info()
        position_info = await r.get_position_info()

    await _control_device(uuid, get_status)

    return {
        **transport_info,
        "position": position_info,
    }


# ── 辅助函数 ──

def _device_to_dict(device) -> dict:
    """将 DlnaDevice 对象转为字典"""
    return {
        "uuid": device.uuid,
        "name": device.name,
        "display_name": device.display_name,
        "manufacturer": device.manufacturer,
        "model_name": device.model_name,
        "ip": device.ip,
        "port": device.port,
        "has_control": bool(device.control_url),
        "is_video": device.is_video,
        "is_audio": device.is_audio,
    }


async def _control_device(uuid: str, action):
    """通用设备操作：发现 → 匹配 → 执行操作"""
    from app.dlna import get_dlna_discovery

    discovery = get_dlna_discovery()
    devices = await discovery.discover()
    target = next((d for d in devices if d.uuid == uuid), None)

    if not target:
        return {"ok": False, "error": "Device not found"}

    if not target.control_url:
        return {"ok": False, "error": "Device does not support AVTransport control"}

    renderer = MediaRenderer(target)
    try:
        await action(renderer)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await renderer.close()
