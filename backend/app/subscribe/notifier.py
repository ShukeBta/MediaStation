"""
多渠道通知推送
支持 Telegram / 微信(Server酱) / Bark / Webhook / Email
"""
from __future__ import annotations

import json
import logging
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
        text = f"📢 *{title}*\n\n{content}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
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
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.server}/{self.key}/{title}/{content}",
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
