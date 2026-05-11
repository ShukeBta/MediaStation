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
    
    支持 Linux 绝对路径和 Windows 盘符路径。
    使用 pathlib.is_relative_to() 进行严格路径校验，防止目录穿越攻击。
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
            media_dirs: 媒体库配置目录列表（用户自定义，支持任意绝对路径）
            data_dir: 数据目录
        """
        import os
        self.allowed_roots: list[pathlib.Path] = []
        
        # 1. 数据目录始终允许
        if data_dir:
            self.allowed_roots.append(pathlib.Path(data_dir).resolve())
        else:
            self.allowed_roots.append(pathlib.Path("/data").resolve())
        
        # 2. 添加常见 Linux 媒体挂载目录（仅在存在时加入，Windows 不适用）
        if os.name != 'nt':
            for root in ["/mnt", "/media", "/home", "/nas", "/storage"]:
                try:
                    p = pathlib.Path(root).resolve()
                    if p.exists():
                        self.allowed_roots.append(p)
                except Exception:
                    pass
        
        # 3. Windows：允许所有驱动器根目录（D:\, E:\, 等）
        if os.name == 'nt':
            import string
            for drive in string.ascii_uppercase:
                drive_path = pathlib.Path(f"{drive}:\\")
                try:
                    if drive_path.exists():
                        self.allowed_roots.append(drive_path)
                except Exception:
                    pass
        
        # 4. 用户通过 MEDIA_DIRS 或数据库媒体库配置的目录（最高优先级，无需存在检查）
        if media_dirs:
            for d in media_dirs:
                try:
                    p = pathlib.Path(d).resolve()
                    # 即使目录尚未创建也加入白名单（支持挂载点场景）
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
        检查路径是否在允许的目录下。
        使用 is_relative_to() 确保路径严格在允许目录内部。
        """
        for root in self.allowed_roots:
            try:
                # 路径与根目录相同，或是其子路径，均允许
                if resolved_path == root or resolved_path.is_relative_to(root):
                    return True, None
            except Exception:
                pass
        
        roots_display = [str(r) for r in self.allowed_roots[:5]]
        return False, f"路径不在允许的目录内，已配置根目录: {roots_display}"
    
    def is_safe(self, path: str) -> tuple[bool, str | None]:
        """
        验证路径是否安全（Issue #57 核心修复）
        
        安全检查流程：
        1. 解析为绝对路径（直接使用原始路径，不剥离斜杠）
        2. 检查是否包含 .. 穿越组件
        3. 检查是否在阻止的系统目录下
        4. 检查是否在允许的目录下
        
        Args:
            path: 待验证的路径（支持 Linux 绝对路径、Windows 盘符路径）
            
        Returns:
            (是否安全, 错误信息或 None)
        """
        import os
        
        try:
            # Step 1: 直接解析为绝对路径，不剥离首斜杠
            # 原实现错误地 lstrip("/\\") 导致 /media/movies → media/movies
            # 再拼接 "/" → /media/movies（表面看没问题）
            # 但对于 Windows 路径 D:\Movies → D:\Movies（lstrip 无影响，
            # 而后 Path("/") / "D:\\Movies" → 错误拼接）
            abs_path = pathlib.Path(path).resolve()
            
            # Step 2: 检查是否包含 .. 穿越组件（双重检查）
            # resolve() 已消解 ..，若解析后路径与规范路径不同说明有问题
            try:
                # 确保路径是绝对路径（resolve() 总是返回绝对路径）
                if not abs_path.is_absolute():
                    return False, "非法路径：无法解析为绝对路径"
            except ValueError:
                return False, "非法路径"
            
            # Step 3: 检查阻止的系统目录
            blocked, error = self._is_in_blocked_path(abs_path)
            if blocked:
                return False, error
            
            # Step 4: 检查是否在允许的目录下
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
