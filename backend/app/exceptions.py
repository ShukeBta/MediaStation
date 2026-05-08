"""
统一错误层级
所有业务错误继承 AppError，全局异常处理器统一捕获。
"""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """基础业务异常"""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        detail: Any = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)

    def to_dict(self) -> dict:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "status": self.status_code,
        }
        if self.detail:
            result["detail"] = self.detail
        return result


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str | int):
        super().__init__(
            f"{resource} not found: {resource_id}",
            code="NOT_FOUND",
            status_code=404,
        )


class ValidationError(AppError):
    def __init__(self, errors: list[dict]):
        super().__init__(
            "Validation failed",
            code="VALIDATION_ERROR",
            status_code=422,
            detail=errors,
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code="FORBIDDEN", status_code=403)


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="CONFLICT", status_code=409)


class ExternalServiceError(AppError):
    def __init__(self, service: str, detail: str = ""):
        super().__init__(
            f"External service error: {service}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            detail={"service": service, "detail": detail},
        )


class ScraperError(AppError):
    def __init__(self, title: str, detail: str = ""):
        super().__init__(
            f"Failed to scrape: {title}",
            code="SCRAPER_ERROR",
            status_code=404,
            detail=detail,
        )


class TranscodeError(AppError):
    def __init__(self, message: str = "Transcoding failed"):
        super().__init__(message, code="TRANSCODE_ERROR", status_code=500)


class DownloadClientError(AppError):
    def __init__(self, client: str, detail: str = ""):
        super().__init__(
            f"Download client error: {client}",
            code="DOWNLOAD_CLIENT_ERROR",
            status_code=502,
            detail={"client": client, "reason": detail},
        )


class SiteError(AppError):
    def __init__(self, site: str, detail: str = ""):
        super().__init__(
            f"Site error: {site}",
            code="SITE_ERROR",
            status_code=502,
            detail={"site": site, "reason": detail},
        )
