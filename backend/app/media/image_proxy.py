"""
图片代理与本地图片服务
提供本地图片访问接口，避免第三方防盗链问题
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}


@router.get("/image/{filename}")
async def get_local_image(filename: str):
    """
    提供本地图片访问
    图片保存在 data_dir/metadata/images/ 目录下
    """
    settings = get_settings()
    images_dir = Path(settings.data_dir) / "metadata" / "images"
    
    # 安全校验：防止路径遍历攻击
    file_path = (images_dir / filename).resolve()
    if not str(file_path).startswith(str(images_dir.resolve())):
        raise HTTPException(403, "Access denied")
    
    if not file_path.exists():
        raise HTTPException(404, "Image not found")
    
    # 检查文件扩展名
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(403, "File type not allowed")
    
    return FileResponse(file_path)


@router.get("/proxy-image")
async def proxy_image(
    url: str = Query(..., description="原始图片 URL"),
    referer: str | None = Query(None, description="Referer 头（用于绕过防盗链）"),
):
    """
    图片代理接口（备用方案）
    当本地图片不存在时，通过后端代理访问第三方图片
    
    注意：此接口应添加频率限制，防止被滥用
    """
    import httpx
    
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    
    if referer:
        headers["Referer"] = referer
    
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # 验证响应内容是图片
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise HTTPException(502, "URL is not an image")
            
            # 返回图片内容
            from fastapi.responses import Response
            
            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  # 缓存 24 小时
                },
            )
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Failed to fetch image: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        raise HTTPException(500, "Internal server error")
