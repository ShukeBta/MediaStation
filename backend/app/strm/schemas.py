"""
STRM 配置 Schema 定义
"""
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Optional


class StrmConfigUpdate(BaseModel):
    """更新 STRM 配置"""
    enabled: Optional[bool] = Field(None, description="是否启用 STRM 支持")
    allowed_protocols: Optional[List[str]] = Field(
        None,
        description="允许的协议列表",
        examples=[["http", "https", "webdav", "alist", "s3"]]
    )
    max_file_size: Optional[int] = Field(None, ge=1024, le=10485760, description="最大 STRM 文件大小（字节），1KB ~ 10MB")

    @field_validator("allowed_protocols")
    @classmethod
    def validate_protocols(cls, v):
        if v is None:
            return v
        allowed = {"http", "https", "webdav", "alist", "s3", "ftp"}
        for p in v:
            if p.lower() not in allowed:
                raise ValueError(f"不支持的协议: {p}，允许: {allowed}")
        return [p.lower() for p in v]


class StrmConfigResponse(BaseModel):
    """STRM 配置响应"""
    enabled: bool = False
    allowed_protocols: List[str] = ["http", "https"]
    max_file_size: int = 1048576  # 1MB


class MediaStrmUpdate(BaseModel):
    """设置媒体 STRM URL"""
    strm_url: str = Field(..., min_length=10, max_length=2000, description="STRM 引用的远程 URL")

    @field_validator("strm_url")
    @classmethod
    def validate_url(cls, v):
        v = v.strip()
        allowed_prefixes = ("http://", "https://", "webdav://", "alist://", "s3://")
        if not v.startswith(allowed_prefixes):
            raise ValueError(f"URL 必须以以下协议开头: {allowed_prefixes}")
        return v
