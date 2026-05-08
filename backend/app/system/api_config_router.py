"""
API 配置路由
提供 API Key 在线配置接口
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.exceptions import NotFoundError
from .api_config_service import ApiConfigService

router = APIRouter(prefix="/api-config", tags=["API 配置"])


class UpdateConfigRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    enabled: Optional[bool] = None
    extra: Optional[dict] = None


def get_service(db: AsyncSession = Depends(get_db)) -> ApiConfigService:
    return ApiConfigService(db)


@router.get("", summary="获取所有 API 配置")
async def list_configs(service: ApiConfigService = Depends(get_service)) -> list[dict]:
    return await service.list_configs()


@router.get("/{provider}", summary="获取指定 Provider 配置")
async def get_config(
    provider: str,
    service: ApiConfigService = Depends(get_service),
) -> dict:
    config = await service.get_config(provider)
    if not config:
        raise NotFoundError("ApiConfig", provider)
    return config


@router.get("/{provider}/effective", summary="获取生效配置")
async def get_effective_config(
    provider: str,
    service: ApiConfigService = Depends(get_service),
) -> dict:
    return await service.get_effective_config(provider)


@router.post("/{provider}", summary="更新 API 配置")
async def update_config(
    provider: str,
    body: UpdateConfigRequest,
    service: ApiConfigService = Depends(get_service),
) -> dict:
    return await service.update_config(
        provider=provider,
        api_key=body.api_key,
        base_url=body.base_url,
        enabled=body.enabled,
        extra=body.extra,
    )


@router.delete("/{provider}", summary="清除 API Key")
async def delete_config(
    provider: str,
    service: ApiConfigService = Depends(get_service),
) -> dict:
    success = await service.delete_config(provider)
    if not success:
        raise NotFoundError("ApiConfig", provider)
    return {"success": True, "message": f"{provider} API Key 已清除"}


@router.post("/{provider}/test", summary="测试 API 连接")
async def test_connection(
    provider: str,
    service: ApiConfigService = Depends(get_service),
) -> dict:
    return await service.test_connection(provider)


@router.get("/providers/list", summary="获取支持的 Provider 列表")
async def list_providers() -> list[dict]:
    from .api_config_models import DEFAULT_PROVIDERS
    return [
        {
            "provider": p["provider"],
            "description": p["description"],
            "base_url": p["base_url"],
        }
        for p in DEFAULT_PROVIDERS
    ]
