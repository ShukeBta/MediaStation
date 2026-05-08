"""
HMAC-SHA256 签名验证（客户端）
与 License Server 的 crypto.py 保持一致的签名逻辑。
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def verify_server_signature(payload: dict[str, Any], signature: str, secret: str) -> bool:
    """
    验证 License Server 返回的 HMAC-SHA256 签名。

    签名算法：
    1. 排除 payload 中的 'signature' 字段
    2. 按 key 排序后 JSON 序列化（紧凑格式）
    3. HMAC-SHA256(secret, serialized_data)

    Args:
        payload: 服务器返回的完整响应体（含 signature 字段）
        signature: 服务器返回的 signature 值
        secret: 配置的 LICENSE_SERVER_SECRET（必须与服务端一致）

    Returns:
        签名是否有效
    """
    if not secret or not signature:
        return False

    data = {k: v for k, v in sorted(payload.items()) if k != "signature"}
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
