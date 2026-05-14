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
    """文件路径白名单验证器
    
    Issue #57 修复：使用 pathlib.is_relative_to() 进行严格路径校验，
    防止目录穿越攻击（Path Traversal）。
    """
    
    # 阻止的系统目录（这些目录绝对不能访问）
    BLOCKED_PATHS: list[str] = [
        "/proc", "/sys", "/dev", "/boot", "/etc",
        "/run", "/snap", "/bin", "/sbin", "/lib",
        "/.git", "/.ssh", "/.docker",
    ]
    # Windows 阻止目录
    WINDOWS_BLOCKED: list[str] = [
        "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
        "C:\\Windows\\System32", "C:\\Windows\\SystemData",
    ]
    
    def __init__(self, media_dirs: list[str] | None = None, data_dir: str | None = None):
        """初始化路径验证器
        
        Args:
            media_dirs: 媒体库配置目录列表
            data_dir: 数据目录
        """
        # 构建允许的根目录列表（使用 pathlib.Path.resolve() 确保绝对路径）
        self.allowed_roots: list[pathlib.Path] = []
        
        if data_dir:
            self.allowed_roots.append(pathlib.Path(data_dir).resolve())
        else:
            self.allowed_roots.append(pathlib.Path("/data").resolve())
        
        # 添加常见媒体目录
        for root in ["/mnt", "/media", "/home"]:
            try:
                p = pathlib.Path(root).resolve()
                if p.exists():
                    self.allowed_roots.append(p)
            except Exception:
                pass
        
        # 添加用户配置的媒体库目录
        if media_dirs:
            for d in media_dirs:
                try:
                    p = pathlib.Path(d).resolve()
                    if p.exists():
                        self.allowed_roots.append(p)
                except Exception:
                    pass
    
    def _is_in_blocked_path(self, resolved_path: pathlib.Path) -> tuple[bool, str | None]:
        """
        检查路径是否在阻止的系统目录下（Issue #57 修复）
        
        使用 is_relative_to() 进行精确匹配，防止误判。
        """
        path_str = str(resolved_path)
        path_lower = path_str.lower()
        
        # 检查阻止的系统目录
        for blocked in self.BLOCKED_PATHS:
            blocked_lower = blocked.lower()
            # 使用 startswith 确保精确匹配目录，而不是子字符串
            if path_lower == blocked_lower or path_lower.startswith(blocked_lower + "/") or path_lower.startswith(blocked_lower + "\\"):
                return True, f"禁止访问系统目录: {blocked}"
        
        # Windows 特殊检查
        import os
        if os.name == 'nt':
            for blocked in self.WINDOWS_BLOCKED:
                blocked_lower = blocked.lower()
                if path_lower == blocked_lower or path_lower.startswith(blocked_lower + "\\"):
                    return True, f"禁止访问系统目录: {blocked}"
        
        return False, None
    
    def _is_in_allowed_path(self, resolved_path: pathlib.Path) -> tuple[bool, str | None]:
        """
        检查路径是否在允许的目录下（Issue #57 修复）
        
        使用 is_relative_to() 确保路径在允许目录内部，而不是仅检查前缀。
        """
        for root in self.allowed_roots:
            try:
                # 核心安全断言：resolved_path 必须在 root 内部
                if resolved_path.is_relative_to(root):
                    return True, None
            except Exception:
                # is_relative_to() 如果路径不相对会抛出 ValueError
                pass
        
        # 允许用户主目录（如果不在允许列表中）
        import os
        home = pathlib.Path(os.path.expanduser("~")).resolve()
        try:
            if resolved_path.is_relative_to(home):
                return True, None
        except Exception:
            pass
        
        return False, f"路径不在允许的目录内: {self.allowed_roots[:3]}..."
    
    def is_safe(self, path: str) -> tuple[bool, str | None]:
        """
        验证路径是否安全（Issue #57 核心修复）

        安全检查流程：
        1. 用 pathlib.Path.resolve() 解析路径（自动处理 Windows/Unix 绝对/相对路径）
        2. 检查是否在阻止的系统目录下
        3. 检查是否在允许的目录下

        Args:
            path: 待验证的路径

        Returns:
            (是否安全, 错误信息或 None)
        """
        try:
            # Step 1: 解析路径
            abs_path = pathlib.Path(path).resolve()

            # Step 2: 检查阻止的系统目录
            blocked, error = self._is_in_blocked_path(abs_path)
            if blocked:
                return False, error

            # Step 3: 检查是否在允许的目录下
            allowed, error = self._is_in_allowed_path(abs_path)
            if allowed:
                return True, None

            return False, error or "路径不在允许的目录内"

        except Exception as e:
            return False, f"路径验证失败: {e}"
    
    def validate_or_raise(self, path: str) -> str:
        """
        验证路径，失败则抛出 ValueError
        
        Issue #57 修复：提供明确的错误信息，帮助调试。
        """
        safe, error = self.is_safe(path)
        if not safe:
            raise ValueError(f"禁止访问: {error}")
        return path


# ── 类型别名 ──

Response200 = SuccessResponse
Response400 = ErrorResponse
Response401 = ErrorResponse
Response403 = ErrorResponse
Response404 = ErrorResponse
