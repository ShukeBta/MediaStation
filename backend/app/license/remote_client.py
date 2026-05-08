"""
远程授权客户端
通过 httpx 与 License Server 通信，提供激活、心跳、状态查询等功能。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RemoteLicenseClient:
    """与中心授权服务器通信的 httpx 客户端"""

    def __init__(self, server_url: str):
        """
        Args:
            server_url: 授权服务器地址（必须 HTTPS）
        """
        url = server_url.strip()
        if not url:
            raise ValueError("授权服务器 URL 不能为空")

        # 强制 HTTPS
        if url.startswith("http://") and not url.startswith("http://localhost"):
            raise ValueError("授权服务器必须使用 HTTPS")

        self.base_url = url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """懒初始化 httpx 客户端（连接池复用）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(15.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """关闭客户端连接"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        """统一请求方法（连接错误自动重试 1 次）"""
        client = await self._get_client()
        try:
            resp = await client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError as e:
            # 连接错误重试 1 次
            logger.warning(f"连接失败，重试中: {e}")
            try:
                resp = await client.request(method, path, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except Exception as e2:
                logger.error(f"重试仍然失败: {e2}")
                raise ConnectionError(f"无法连接授权服务器: {self.base_url}") from e2
        except httpx.HTTPStatusError as e:
            # 4xx/5xx 不重试，返回响应体
            logger.warning(f"授权服务器返回错误: {e.response.status_code} {e.response.text}")
            return e.response.json()

    # ── 公开方法 ──

    async def activate(
        self,
        key: str,
        fingerprint: str,
        device_name: str | None = None,
        instance_id: str | None = None,
    ) -> dict:
        """
        激活授权码
        POST /api/v1/activate
        """
        payload = {
            "key": key,
            "fingerprint": fingerprint,
            "device_name": device_name,
            "instance_id": instance_id,
        }
        # 清理 None 值
        payload = {k: v for k, v in payload.items() if v is not None}
        return await self._request("POST", "/api/v1/activate", json=payload)

    async def heartbeat(
        self,
        fingerprint: str,
        instance_id: str | None = None,
        cached_info: dict | None = None,
    ) -> dict:
        """
        心跳验证
        POST /api/v1/heartbeat
        """
        payload: dict[str, Any] = {
            "fingerprint": fingerprint,
            "instance_id": instance_id,
        }
        if cached_info:
            payload["license_type"] = cached_info.get("license_type")
            payload["activated_at"] = cached_info.get("activated_at")
        payload = {k: v for k, v in payload.items() if v is not None}
        return await self._request("POST", "/api/v1/heartbeat", json=payload)

    async def check_status(
        self,
        fingerprint: str,
        instance_id: str | None = None,
    ) -> dict:
        """
        查询设备授权状态
        GET /api/v1/status/{fingerprint}
        """
        params = {}
        if instance_id:
            params["instance_id"] = instance_id
        return await self._request("GET", f"/api/v1/status/{fingerprint}", params=params)

    async def deactivate(
        self,
        fingerprint: str,
        instance_id: str | None = None,
    ) -> dict:
        """
        注销设备
        POST /api/v1/deactivate
        """
        payload = {"fingerprint": fingerprint, "instance_id": instance_id}
        payload = {k: v for k, v in payload.items() if v is not None}
        return await self._request("POST", "/api/v1/deactivate", json=payload)

    async def test_connection(self) -> bool:
        """
        测试与授权服务器的连通性
        GET /health
        """
        try:
            result = await self._request("GET", "/health")
            return result.get("status") == "ok"
        except Exception:
            return False
