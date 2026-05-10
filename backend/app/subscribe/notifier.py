"""
多渠道通知推送
支持 Telegram / 微信(Server酱) / Bark / Webhook / Email
"""
from __future__ import annotations

import html
import ipaddress
import json
import logging
import socket
import urllib.parse
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NotifyType(str, Enum):
    DOWNLOAD_COMPLETE = "download_complete"
    SUBSCRIPTION_FOUND = "subscription_found"
    SUBSCRIPTION_DOWNLOADED = "subscription_downloaded"
    MEDIA_SCRAPED = "media_scraped"
    SCAN_COMPLETE = "scan_complete"
    TRANSCODE_COMPLETE = "transcode_complete"
    SYSTEM_ERROR = "system_error"


# ── SSRF 防护：私有/保留 IP 段 ──
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),        # private A
    ipaddress.ip_network("172.16.0.0/12"),     # private B
    ipaddress.ip_network("192.168.0.0/16"),    # private C
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / 云元数据
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 private
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
    ipaddress.ip_network("0.0.0.0/8"),         # unspecified
    ipaddress.ip_network("100.64.0.0/10"),     # CGNAT
]


def _is_ssrf_safe_url(url: str) -> tuple[bool, str]:
    """
    校验 URL 是否安全（不指向内网地址）。
    返回 (is_safe, reason)。
    """
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"不允许的协议: {scheme}"

        host = parsed.hostname
        if not host:
            return False, "URL 缺少主机名"

        # 拒绝明显的内网主机名
        if host.lower() in ("localhost", "ip6-localhost", "ip6-loopback"):
            return False, f"拒绝访问内网主机: {host}"

        # 解析 IP（同时处理域名解析）
        try:
            addr_infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False, f"无法解析主机名: {host}"

        for addr_info in addr_infos:
            ip_str = addr_info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            for net in _PRIVATE_NETWORKS:
                if ip_obj in net:
                    return False, f"拒绝访问私有/保留 IP 地址: {ip_str} ({net})"

        return True, ""
    except Exception as e:
        return False, f"URL 校验异常: {e}"


class NotifyChannelBase(ABC):
    name: str = "base"

    @abstractmethod
    async def send(self, title: str, content: str, notify_type: str = "") -> bool:
        ...


class TelegramNotify(NotifyChannelBase):
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, title: str, content: str, notify_type: str = "") -> bool:
        # Issue #35: 使用 HTML 模式并对标题/内容进行 html.escape 转义
        # 防止影视剧标题中的 Markdown 特殊字符（_ * [ ] 等）导致 Telegram API 400 错误
        safe_title = html.escape(title)
        safe_content = html.escape(content)
        text = f"📢 <b>{safe_title}</b>\n\n{safe_content}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",  # 切换为 HTML 模式，容错率更高
                    },
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram notify failed: {e}")
            return False


class WechatNotify(NotifyChannelBase):
    name = "wechat"

    def __init__(self, sendkey: str):
        self.sendkey = sendkey

    async def send(self, title: str, content: str, notify_type: str = "") -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://sctapi.ftqq.com/{self.sendkey}.send",
                    data={"title": title, "desp": content},
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Wechat notify failed: {e}")
            return False


class BarkNotify(NotifyChannelBase):
    name = "bark"

    def __init__(self, server: str, key: str):
        self.server = server.rstrip("/")
        self.key = key

    async def send(self, title: str, content: str, notify_type: str = "") -> bool:
        # Issue #30: 使用 urllib.parse.quote 对 title 和 content 进行 URL 安全编码
        # 防止标题含空格、斜杠、中文等特殊字符时 URL 路径被破坏导致推送失败
        safe_title = urllib.parse.quote(title, safe="")
        safe_content = urllib.parse.quote(content, safe="")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.server}/{self.key}/{safe_title}/{safe_content}",
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Bark notify failed: {e}")
            return False


class WebhookNotify(NotifyChannelBase):
    name = "webhook"

    def __init__(self, url: str, method: str = "POST", headers: dict | None = None):
        self.url = url
        self.method = method
        self.headers = headers or {}

    async def send(self, title: str, content: str, notify_type: str = "") -> bool:
        # Issue #29: SSRF 防护 — 在发起请求前校验 URL 不指向内网地址
        is_safe, reason = _is_ssrf_safe_url(self.url)
        if not is_safe:
            logger.error(f"Webhook SSRF 防护拦截请求: {self.url} — {reason}")
            return False

        payload = {"title": title, "content": content, "type": notify_type}
        try:
            async with httpx.AsyncClient() as client:
                if self.method.upper() == "GET":
                    resp = await client.get(
                        self.url, params=payload, headers=self.headers, timeout=10
                    )
                else:
                    resp = await client.post(
                        self.url, json=payload, headers=self.headers, timeout=10
                    )
                return resp.status_code < 400
        except Exception as e:
            logger.error(f"Webhook notify failed: {e}")
            return False


class NotifierService:
    """通知推送服务（聚合多渠道）"""

    def __init__(self):
        self._channels: list[NotifyChannelBase] = []

    def add_channel(self, channel: NotifyChannelBase):
        self._channels.append(channel)

    async def notify(self, title: str, content: str, notify_type: str = ""):
        """向所有启用的渠道发送通知"""
        for channel in self._channels:
            try:
                await channel.send(title, content, notify_type)
            except Exception as e:
                logger.error(f"Notify via {channel.name} failed: {e}")


def create_channel_from_config(channel_type: str, config: dict) -> NotifyChannelBase:
    """根据配置创建通道实例"""
    if channel_type == "telegram":
        return TelegramNotify(
            bot_token=config.get("bot_token", ""),
            chat_id=config.get("chat_id", ""),
        )
    elif channel_type == "wechat":
        return WechatNotify(sendkey=config.get("sendkey", ""))
    elif channel_type == "bark":
        return BarkNotify(
            server=config.get("server", "https://api.day.app"),
            key=config.get("key", ""),
        )
    elif channel_type == "webhook":
        return WebhookNotify(
            url=config.get("url", ""),
            method=config.get("method", "POST"),
            headers=config.get("headers"),
        )
    else:
        raise ValueError(f"Unsupported notify channel: {channel_type}")
