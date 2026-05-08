"""
DLNA 模块 — 媒体投屏到 DLNA 设备（TV/音箱/游戏机）

基于 SSDP 协议发现设备，通过 UPnP AVTransport 服务控制播放。
核心组件：
- DeviceDiscovery: SSDP 设备发现
- MediaRenderer: 设备控制和媒体推送
"""
from __future__ import annotations

import asyncio
import logging
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# SSDP 配置
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 2  # 最大等待秒数
SSDP_SEARCH_TARGET = "urn:schemas-upnp-org:device:MediaRenderer:1"

# 搜索消息模板
SSDP_SEARCH = f"M-SEARCH * HTTP/1.1\r\n" \
    f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n" \
    f'MAN: "ssdp:discover"\r\n' \
    f"MX: {SSDP_MX}\r\n" \
    f"ST: {SSDP_SEARCH_TARGET}\r\n\r\n"


@dataclass
class DlnaDevice:
    """DLNA/UPnP 设备信息"""
    uuid: str                    # 设备唯一标识
    name: str                    # 友好名称 (如 "Living Room TV")
    location: str                # 设备描述 URL (HTTP)
    manufacturer: str = ""       # 制造商 (如 "Samsung", "LG")
    model_name: str = ""         # 型号
    device_type: str = ""        # UPnP 设备类型
    control_url: str = ""        # AVTransport 控制 URL
    event_sub_url: str = ""      # 事件订阅 URL
    is_video: bool = True        # 是否支持视频
    is_audio: bool = True        # 是否支持音频
    ip: str = ""
    port: int = 0

    @property
    def display_name(self) -> str:
        if self.manufacturer and self.model_name:
            return f"{self.name} ({self.manufacturer} {self.model_name})"
        return self.name


class DeviceDiscovery:
    """SSDP 设备发现器

    通过多播搜索网络中的 DLNA MediaRenderer 设备。
    """

    def __init__(self, search_timeout: float = 3.0):
        self.search_timeout = search_timeout
        self._devices: dict[str, DlnaDevice] = {}

    async def discover(self) -> list[DlnaDevice]:
        """发现网络中的 DLNA 设备，返回设备列表"""
        self._devices = {}

        try:
            # 创建 UDP socket 用于 SSDP
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _SsdpProtocol(self),
                local_addr=("0.0.0.0", 0),
            )

            # 发送 M-SEARCH
            sock = transport.get_extra_info("socket")
            sock.sendto(SSDP_SEARCH.encode(), (SSDP_ADDR, SSDP_PORT))

            # 等待响应
            await asyncio.sleep(self.search_timeout)

            transport.close()

        except Exception as e:
            logger.error(f"SSDP discovery error: {e}")

        return list(self._devices.values())

    def _add_device(self, location: str, usn: str):
        """添加发现的设备（由协议回调）"""
        if location in [d.location for d in self._devices.values()]:
            return
        # 用 UUID 作 key
        uuid = usn.split("::")[0] if "::" in usn else usn
        if uuid not in self._devices:
            self._devices[uuid] = DlnaDevice(uuid=uuid, name="Unknown Device", location=location)
            # 异步获取设备详细信息
            asyncio.create_task(self._fetch_device_details(uuid))

    async def _fetch_device_details(self, uuid: str):
        """获取设备完整描述信息"""
        device = self._devices.get(uuid)
        if not device or not device.location:
            return

        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(device.location)
                resp.raise_for_status()

                root = ET.fromstring(resp.text)
                ns = {"ns": "urn:schemas-upnp-org:device-1-0"}

                # 基本信息
                device_elem = root.find(".//ns:device", ns)
                if device_elem is not None:
                    name_el = device_elem.find("ns:friendlyName", ns)
                    if name_el is not None and name_el.text:
                        device.name = name_el.text.strip()

                    mf_el = device_elem.find("ns:manufacturer", ns)
                    if mf_el is not None and mf_el.text:
                        device.manufacturer = mf_el.text.strip()

                    model_el = device_elem.find("ns:modelName", ns)
                    if model_el is not None and model_el.text:
                        device.model_name = model_el.text.strip()

                    type_el = device_elem.find("ns:deviceType", ns)
                    if type_el is not None and type_el.text:
                        device.device_type = type_el.text.strip()

                # 解析控制 URL（AVTransport service）
                for svc in root.iter("{urn:schemas-upnp-org:device-1-0}service"):
                    svc_type = svc.find("{urn:schemas-upnp-org:device-1-0}serviceType")
                    if svc_type is not None and "AVTransport" in (svc_type.text or ""):
                        ctrl_url = svc.find("{urn:schemas-upnp-org:device-1-0}controlURL")
                        if ctrl_url is not None and ctrl_url.text:
                            base = device.location.rsplit("/", 1)[0]
                            device.control_url = base + ctrl_url.text.strip()

                        evt_url = svc.find("{urn:schemas-upnp-org:device-1-0}eventSubURL")
                        if evt_url is not None and evt_url.text:
                            base = device.location.rsplit("/", 1)[0]
                            device.event_sub_url = base + evt_url.text.strip()
                        break

                # 提取 IP 和端口
                from urllib.parse import urlparse
                parsed = urlparse(device.location)
                device.ip = parsed.hostname or ""
                device.port = parsed.port or 0

                logger.info(f"DLNA device found: {device.display_name}")

        except Exception as e:
            logger.warning(f"Failed to fetch details for device {uuid}: {e}")


class _SsdpProtocol(asyncio.DatagramProtocol):
    """SSDP 响应接收协议"""

    def __init__(self, discovery: DeviceDiscovery):
        self.discovery = discovery

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            text = data.decode("utf-8", errors="ignore")
            lines = text.split("\r\n")

            # 解析 HTTP NOTIFY 或 SEARCH RESPONSE
            if lines[0].startswith("HTTP/") or lines[0].startswith("NOTIFY"):
                location = ""
                usn = ""

                for line in lines[1:]:
                    if line.upper().startswith("LOCATION:"):
                        location = line.split(":", 1)[1].strip()
                    elif line.upper().startswith("USN:") or line.upper().startswith("UUID:"):
                        usn = line.split(":", 1)[1].strip()

                if location and usn:
                    self.discovery._add_device(location, usn)

        except Exception:
            pass


class MediaRenderer:
    """DLNA MediaRenderer 控制器

    通过 UPnP AVTransport 服务向设备发送媒体播放指令。
    """

    # UPnP SOAP Action 模板
    SOAP_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
 s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
 <s:Body>{body}</s:Body>
</s:Envelope>'''

    def __init__(self, device: DlnaDevice, timeout: float = 10.0):
        self.device = device
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Content-Type": 'text/xml; charset="utf-8"'},
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def set_av_transport_uri(self, media_url: str, metadata: str = "") -> bool:
        """设置播放 URI

        Args:
            media_url: 媒体 URL（必须是设备可访问的地址）
            metadata: DIDL-Lite 元数据 XML
        """
        body = f'''<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
  <CurrentURI>{_escape_xml(media_url)}</CurrentURI>
  <CurrentURIMetaData>{_escape_xml(metadata)}</CurrentURIMetaData>
</u:SetAVTransportURI>'''
        return await self._soap_call("SetAVTransportURI", body)

    async def play(self) -> bool:
        """开始/恢复播放"""
        body = '<u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play>'
        return await self._soap_call("Play", body)

    async def pause(self) -> bool:
        """暂停"""
        body = '<u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:Pause>'
        return await self._soap_call("Pause", body)

    async def stop(self) -> bool:
        """停止"""
        body = '<u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:Stop>'
        return await self._soap_call("Stop", body)

    async def seek(self, target: str, unit: string = "REL_TIME") -> bool:
        """跳转位置

        Args:
            target: 目标时间，格式 "HH:MM:SS" 或 "00:00:30"
            unit: 时间单位 (REL_TIME / ABS_TIME / TRACK_NR)
        """
        body = f'''<u:Seek xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
  <InstanceID>0</InstanceID>
  <Unit>{unit}</Unit>
  <Target>{target}</Target>
</u:Seek>'''
        return await self._soap_call("Seek", body)

    async def get_position_info(self) -> dict:
        """获取当前播放位置"""
        body = '<u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetPositionInfo>'

        try:
            resp_text = await self._soap_call_raw("GetPositionInfo", body)
            # 解析响应
            root = ET.fromstring(resp_text)
            ns = {"u": "urn:schemas-upnp-org:service:AVTransport:1"}
            result = {}
            for tag in ["TrackDuration", "AbsTime", "RelTime"]:
                el = root.find(f".//u:{tag}", ns)
                if el is not None and el.text:
                    result[tag.lower()] = el.text.strip()
            return result
        except Exception as e:
            logger.warning(f"Get position info failed: {e}")
            return {}

    async def get_transport_info(self) -> dict:
        """获取传输状态（PLAYING/PAUSED/STOPPED）"""
        body = '<u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetTransportInfo>'

        try:
            resp_text = await self._soap_call_raw("GetTransportInfo", body)
            root = ET.fromstring(resp_text)
            ns = {"u": "urn:schemas-upnp-org:service:AVTransport:1"}
            state_el = root.find(".//u:CurrentTransportState", ns)
            return {
                "state": state_el.text.strip() if state_el is not None else "UNKNOWN",
            }
        except Exception as e:
            logger.warning(f"Get transport info failed: {e}")
            return {"state": "UNKNOWN"}

    async def set_volume(self, volume: int) -> bool:
        """设置音量 (0-100)"""
        volume = max(0, min(100, volume))
        body = f'<u:SetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</Instance><Channel>Master</Channel><DesiredVolume>{volume}</DesiredVolume></u:SetVolume>'

        # RenderingControl 的 control URL 可能不同
        ctrl_url = self.device.control_url.replace("AVTransport", "RenderingControl") if "AVTransport" in self.device.control_url else self.device.control_url
        return await self._soap_call_raw("SetVolume", body, ctrl_url=ctrl_url, parse_result=False)

    async def _soap_call(self, action: str, body: str) -> bool:
        """执行 SOAP 调用并返回是否成功"""
        try:
            await self._soap_call_raw(action, body)
            return True
        except Exception as e:
            logger.error(f"SOAP {action} failed: {e}")
            return False

    async def _soap_call_raw(self, action: str, body: str, ctrl_url: str | None = None, parse_result: bool = True) -> str:
        """执行原始 SOAP 调用，返回响应文本"""
        url = ctrl_url or self.device.control_url
        if not url:
            raise Exception("No control URL available for this device")

        envelope = self.SOAP_TEMPLATE.format(body=body)
        headers = {
            "SOAPAction": f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"',
            "Content-Type": 'text/xml; charset="utf-8"',
            "Connection": "close",
        }

        resp = await self.client.post(url, content=envelope, headers=headers)
        resp.raise_for_status()
        return resp.text


def _escape_xml(text: str) -> str:
    """转义 XML 特殊字符"""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;"))


# ── 全局单例 ──
_discovery: DeviceDiscovery | None = None


def get_dlna_discovery() -> DeviceDiscovery:
    global _discovery
    if _discovery is None:
        _discovery = DeviceDiscovery()
    return _discovery
