"""
统一响应模型 - 标准化 API 响应格式
所有 API 统一使用以下响应格式：
- Success: {data: ...}
- Error: {error: ..., detail: ...}
- Batch: {message: ..., started: [...], errors: [...]}
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar, Annotated
from datetime import datetime

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── 统一响应模型 ──

class SuccessResponse(BaseModel, Generic[T]):
    """成功响应 - {data: ...}"""
    data: T
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def ok(cls, data: T) -> "SuccessResponse[T]":
        return cls(data=data)


class ErrorResponse(BaseModel):
    """错误响应 - {error: ..., detail: ...}"""
    error: str
    detail: str | None = None
    code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def fail(cls, error: str, detail: str | None = None, code: str | None = None) -> "ErrorResponse":
        return cls(error=error, detail=detail, code=code)
    
    @classmethod
    def not_found(cls, resource: str = "Resource") -> "ErrorResponse":
        return cls(error=f"{resource} not found", code="NOT_FOUND")
    
    @classmethod
    def unauthorized(cls, message: str = "Authentication required") -> "ErrorResponse":
        return cls(error=message, code="UNAUTHORIZED")
    
    @classmethod
    def forbidden(cls, message: str = "Admin access required") -> "ErrorResponse":
        return cls(error=message, code="FORBIDDEN")
    
    @classmethod
    def validation_error(cls, detail: str) -> "ErrorResponse":
        return cls(error="Validation error", detail=detail, code="VALIDATION_ERROR")


class BatchResponse(BaseModel):
    """批量操作响应 - {message, started, errors}"""
    message: str
    started: list[int] = Field(default_factory=list, description="成功处理的 ID 列表")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="失败项详情")
    total: int = 0
    success_count: int = 0
    error_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def completed(
        cls, 
        message: str, 
        started: list[int], 
        errors: list[dict[str, Any]],
        total: int
    ) -> "BatchResponse":
        return cls(
            message=message,
            started=started,
            errors=errors,
            total=total,
            success_count=len(started),
            error_count=len(errors),
        )


class MessageResponse(BaseModel):
    """简单消息响应 - {message: ...}"""
    message: str
    data: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def ok(cls, message: str, data: dict[str, Any] | None = None) -> "MessageResponse":
        return cls(message=message, data=data)


class ListResponse(BaseModel, Generic[T]):
    """列表响应 - {data: {items, total, page, page_size}}"""
    items: list[T]
    total: int = 0
    page: int = 1
    page_size: int = 20
    
    @classmethod
    def of(cls, items: list[T], total: int = 0, page: int = 1, page_size: int = 20) -> "ListResponse[T]":
        return cls(items=items, total=total or len(items), page=page, page_size=page_size)


# ── 路径安全验证 ──

class PathValidator:
    """文件路径白名单验证器"""
    
    # 允许的根目录
    ALLOWED_ROOTS: list[str] = []
    # 阻止的系统目录
    BLOCKED_PATHS: list[str] = [
        "/proc", "/sys", "/dev", "/boot", "/etc",
        "/run", "/snap", "/bin", "/sbin", "/lib",
        "/.git", "/.ssh",
    ]
    # Windows 阻止目录
    WINDOWS_BLOCKED: list[str] = [
        "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
        "C:\\Windows\\System32",
    ]
    
    def __init__(self, media_dirs: list[str] | None = None, data_dir: str | None = None):
        self.allowed_roots = [
            data_dir or "/data",
            "/mnt", "/media", "/home",
        ]
        if media_dirs:
            self.allowed_roots.extend(media_dirs)
    
    def is_safe(self, path: str) -> tuple[bool, str | None]:
        """
        验证路径是否安全
        返回: (是否安全, 错误信息)
        """
        import os
        import pathlib
        
        try:
            abs_path = pathlib.Path(path).resolve()
            path_str = str(abs_path)
            
            # 检查是否在阻止的目录下
            for blocked in self.BLOCKED_PATHS:
                if path_str.startswith(blocked):
                    return False, f"Path is in blocked directory: {blocked}"
            
            # Windows 特殊检查
            if os.name == 'nt':
                for blocked in self.WINDOWS_BLOCKED:
                    if path_str.startswith(blocked):
                        return False, f"Path is in blocked directory: {blocked}"
            
            # 检查是否在允许的目录下
            for root in self.allowed_roots:
                if path_str.startswith(root):
                    return True, None
            
            # 允许用户主目录
            home = os.path.expanduser("~")
            if path_str.startswith(home):
                return True, None
            
            return False, "Path is not in allowed directories"
            
        except Exception as e:
            return False, f"Invalid path: {e}"
    
    def validate_or_raise(self, path: str) -> str:
        """验证路径，失败则抛出 ValueError"""
        safe, error = self.is_safe(path)
        if not safe:
            raise ValueError(f"Path not allowed: {error}")
        return path


# ── 类型别名 ──

Response200 = SuccessResponse
Response400 = ErrorResponse
Response401 = ErrorResponse
Response403 = ErrorResponse
Response404 = ErrorResponse
