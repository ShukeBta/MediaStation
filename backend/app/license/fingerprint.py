"""
设备指纹识别 — 跨平台获取唯一设备标识
Windows: CPU ProcessorId + 主板 SerialNumber + 磁盘 SerialNumber
Linux: /etc/machine-id 或 /sys/class/dmi/id/product_uuid
macOS: platform UUID (IOPlatformExpertDevice)
"""
from __future__ import annotations

import hashlib
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def get_device_fingerprint() -> str:
    """
    获取设备指纹（SHA-256 哈希的前 32 位十六进制字符串）
    失败时使用 hostname + MAC 作为后备
    """
    raw = _collect_raw_identifiers()
    if not raw:
        # 后备方案：hostname + 第一个 MAC 地址
        import socket, uuid
        mac = uuid.getnode()
        raw = f"{socket.gethostname()}-{mac}"
        logger.warning("Using fallback device fingerprint (hostname+MAC)")

    fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return fp


def get_device_name() -> str:
    """获取可读设备名称"""
    try:
        import socket
        name = socket.gethostname()
        if name:
            return name
    except Exception:
        pass
    return platform.node() or "Unknown Device"


def _collect_raw_identifiers() -> str:
    """收集原始硬件标识符"""
    system = platform.system()
    parts: list[str] = []

    try:
        if system == "Windows":
            parts = _windows_identifiers()
        elif system == "Linux":
            parts = _linux_identifiers()
        elif system == "Darwin":
            parts = _macos_identifiers()
    except Exception as e:
        logger.warning(f"Failed to collect {system} identifiers: {e}")

    return "|".join(filter(None, parts))


def _windows_identifiers() -> list[str]:
    """Windows: CPU ProcessorId + 主板 SerialNumber + 第一块硬盘 SerialNumber"""
    parts: list[str] = []

    try:
        # CPU ProcessorId
        out = subprocess.check_output(
            "wmic cpu get ProcessorId /value",
            shell=True, stderr=subprocess.DEVNULL
        ).decode("gbk", errors="ignore")
        for line in out.splitlines():
            if "ProcessorId=" in line:
                parts.append(line.split("=", 1)[1].strip())
                break

        # 主板 SerialNumber
        out = subprocess.check_output(
            "wmic baseboard get SerialNumber /value",
            shell=True, stderr=subprocess.DEVNULL
        ).decode("gbk", errors="ignore")
        for line in out.splitlines():
            if "SerialNumber=" in line:
                val = line.split("=", 1)[1].strip()
                if val and val != "To be filled by O.E.M.":
                    parts.append(val)
                break

        # 第一块硬盘 SerialNumber
        out = subprocess.check_output(
            "wmic diskdrive get SerialNumber /value",
            shell=True, stderr=subprocess.DEVNULL
        ).decode("gbk", errors="ignore")
        for line in out.splitlines():
            if "SerialNumber=" in line:
                val = line.split("=", 1)[1].strip()
                if val:
                    parts.append(val)
                break
    except Exception as e:
        logger.debug(f"WMIC query failed: {e}")

    return parts


def _linux_identifiers() -> list[str]:
    """Linux: /etc/machine-id 或 /sys/class/dmi/id/product_uuid"""
    parts: list[str] = []

    # /etc/machine-id (systemd 标准)
    try:
        with open("/etc/machine-id", "r") as f:
            mid = f.read().strip()
            if mid:
                parts.append(mid)
    except Exception:
        pass

    # 如果 machine-id 不存在，尝试 product_uuid
    if not parts:
        try:
            with open("/sys/class/dmi/id/product_uuid", "r") as f:
                uid = f.read().strip()
                if uid and uid != "00000000-0000-0000-0000-000000000000":
                    parts.append(uid)
        except Exception:
            pass

    # 后备：/var/lib/dbus/machine-id
    if not parts:
        try:
            with open("/var/lib/dbus/machine-id", "r") as f:
                mid = f.read().strip()
                if mid:
                    parts.append(mid)
        except Exception:
            pass

    return parts


def _macos_identifiers() -> list[str]:
    """macOS: system_profiler 获取 Platform UUID"""
    parts: list[str] = []

    try:
        out = subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore")

        for line in out.splitlines():
            if "Platform UUID" in line or "IOPlatformUUID" in line:
                uid = line.split(":", 1)[1].strip()
                if uid:
                    parts.append(uid)
                break
    except Exception:
        pass

    return parts
