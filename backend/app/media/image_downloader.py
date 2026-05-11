"""
安全图片下载器
解决第三方源防盗链问题（Cloudflare 保护、Referer 检查等）

策略：
1. 伪造 Referer 和 User-Agent 绕过防盗链
2. 下载图片到本地 data_dir/metadata/images/
3. 数据库只保存本地相对路径
4. 使用临时文件 + 原子重命名保证写入完整性（Issue #60）
"""
from __future__ import annotations

import os
import tempfile
import httpx
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 通用浏览器 User-Agent
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def download_image(
    url: str,
    save_path: Path,
    source_domain: str | None = None,
) -> bool:
    """
    附带反防盗链机制的安全图片下载器
    
    Args:
        url: 图片 URL
        save_path: 本地保存路径
        source_domain: 原始网页域名，用于伪造 Referer（如 "https://javdb.com"）
    
    Returns:
        是否下载成功
    """
    if not url or not url.startswith(("http://", "https://")):
        logger.warning(f"Invalid image URL: {url}")
        return False
    
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # 伪造 Referer 绕过防盗链
    if source_domain:
        headers["Referer"] = source_domain
    
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            limits=httpx.Limits(max_connections=10)
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # 验证响应内容是图片
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.warning(f"URL is not an image: {url} (content-type: {content_type})")
                return False
            
            # 确保父目录存在
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 原子写入：先写临时文件，完成后 rename 覆盖目标
            # 防止断电/闪断导致损坏的图片文件残留（Issue #60）
            fd, tmp_path = tempfile.mkstemp(dir=save_path.parent)
            try:
                os.write(fd, response.content)
                os.close(fd)
                fd = -1  # 标记已关闭，避免 finally 中重复关闭
                os.replace(tmp_path, save_path)
            except BaseException:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
            
            logger.debug(f"Image downloaded: {url} -> {save_path}")
            return True
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading image {url}: {e.response.status_code}")
        return False
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
        return False


async def download_image_safe(
    url: str,
    save_dir: Path,
    filename: str,
    source_domain: str | None = None,
) -> Optional[str]:
    """
    安全下载图片并返回本地相对路径
    
    Args:
        url: 图片 URL
        save_dir: 保存目录（如 data_dir/metadata/images）
        filename: 文件名（不含扩展名）
        source_domain: 原始网页域名，用于伪造 Referer
    
    Returns:
        本地相对路径（如 "/api/media/image/xxx.jpg"），失败返回 None
    """
    if not url:
        return None
    
    try:
        # 确定文件扩展名
        suffix = Path(url).suffix or ".jpg"
        if suffix not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            suffix = ".jpg"
        
        # 构建保存路径
        save_path = save_dir / f"{filename}{suffix}"
        
        # 下载图片
        success = await download_image(url, save_path, source_domain)
        
        if success:
            # 返回相对路径（用于前端访问）
            return f"/api/media/image/{filename}{suffix}"
        else:
            return None
    
    except Exception as e:
        logger.error(f"Error in download_image_safe: {e}")
        return None


def get_image_proxy_url(original_url: str) -> str:
    """
    如果无法下载到本地，则返回代理 URL
    后端提供 /api/media/proxy-image?url=xxx 接口
    
    Args:
        original_url: 原始图片 URL
    
    Returns:
        代理 URL 或原始 URL
    """
    # TODO: 实现后端图片代理接口
    # 暂时返回原始 URL
    return original_url
