"""
轻量级加解密工具
使用 Fernet (AES-128-CBC) 对敏感字段（API Key、Passkey 等）进行加密存储。
基于 APP_SECRET_KEY 派生加密密钥，读取时自动解密。
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# 加密数据前缀标识，用于区分加密数据和旧版明文数据
_ENCRYPTED_PREFIX = "enc:v1:"


def _get_cipher() -> Fernet:
    """基于 APP_SECRET_KEY 派生 32 字节 Fernet 密钥"""
    from app.config import get_settings
    secret = get_settings().app_secret_key.encode("utf-8")
    # SHA-256 确保密钥长度固定为 32 字节，再 base64url 编码为 Fernet 要求的 44 字符密钥
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_secret(plain_text: str | None) -> str | None:
    """
    加密敏感字段，返回带前缀的密文字符串。
    
    - 空值或 None 直接返回，不加密
    - 已加密的数据（带前缀）不重复加密
    """
    if not plain_text:
        return plain_text
    # 避免重复加密
    if plain_text.startswith(_ENCRYPTED_PREFIX):
        return plain_text
    try:
        cipher = _get_cipher()
        encrypted = cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        return _ENCRYPTED_PREFIX + encrypted
    except Exception as e:
        logger.error(f"加密失败: {e}")
        return plain_text


def decrypt_secret(encrypted_text: str | None) -> str | None:
    """
    解密敏感字段。
    
    - 空值或 None 直接返回
    - 非加密数据（旧版明文）直接返回，兼容平滑迁移
    - 解密失败（密钥变更等）返回原文并记录警告
    """
    if not encrypted_text:
        return encrypted_text
    # 非加密数据，直接返回（旧版明文兼容）
    if not encrypted_text.startswith(_ENCRYPTED_PREFIX):
        return encrypted_text
    try:
        cipher = _get_cipher()
        raw = encrypted_text[len(_ENCRYPTED_PREFIX):]
        return cipher.decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("解密失败：密钥可能已变更，返回密文原文")
        return encrypted_text
    except Exception as e:
        logger.error(f"解密异常: {e}")
        return encrypted_text


def is_encrypted(value: str | None) -> bool:
    """检查值是否已加密"""
    return bool(value and value.startswith(_ENCRYPTED_PREFIX))
