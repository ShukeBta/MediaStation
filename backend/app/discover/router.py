"""
Discover 路由 - 发现/推荐 API
"""
from __future__ import annotations

import base64
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.deps import DB
from app.discover.service import DiscoverService, SectionOption

router = APIRouter(prefix="/discover", tags=["discover"])


# ── 响应模型 ──


class SectionsResponse(BaseModel):
    sections: List[SectionOption]


class FeedItem(BaseModel):
    id: Optional[Any] = None
    title: Optional[str] = None
    poster_url: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_url: Optional[str] = None
    backdrop_path: Optional[str] = None
    rating: Optional[float] = 0.0
    year: Optional[int] = None
    media_type: Optional[str] = None
    overview: Optional[str] = None
    external: Optional[bool] = False
    source: Optional[str] = None


class FeedSection(BaseModel):
    items: List[FeedItem]


# ── 路由 ──


@router.get("/sections", response_model=SectionsResponse)
async def get_sections(db: DB):
    """获取可用的发现区块配置"""
    service = DiscoverService(db)
    sections = service.get_sections()
    return {"sections": sections}


@router.get("/feed")
async def get_feed(sections: str = Query(..., description="逗号分隔的区块 key"), db: DB):
    """获取多个区块的推荐数据"""
    keys = [k.strip() for k in sections.split(",") if k.strip()]
    service = DiscoverService(db)
    result = await service.get_feed(keys)
    return result


@router.get("/image-proxy")
async def proxy_image(url: str = Query(..., description="图片 URL")):
    """代理外部图片，绕过防盗链"""
    try:
        import httpx

        # 基础64 解码（前端可能编码了 URL）
        try:
            url = base64.b64decode(url).decode("utf-8")
        except Exception:
            # 如果不是 base64，假设是普通 URL
            if not url.startswith("http"):
                raise HTTPException(status_code=400, detail="Invalid URL")

        service = DiscoverService()
        content = await service.proxy_image(url)

        # 根据 URL 判断 content-type
        content_type = "image/jpeg"
        if url.endswith(".png"):
            content_type = "image/png"
        elif url.endswith(".gif"):
            content_type = "image/gif"
        elif url.endswith(".webp"):
            content_type = "image/webp"

        return Response(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Image proxy failed: {str(e)}")
