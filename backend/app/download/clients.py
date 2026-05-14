"""
下载客户端适配器
支持 qBittorrent、Transmission 和 Aria2
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import string
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── 下载路径安全校验 ──

def validate_download_path(requested_path: str, base_download_dir: str) -> str:
    """
    验证下载保存路径的安全性，防止路径穿越攻击（RCE漏洞修复）
    
    安全规则：
    1. 拒绝绝对路径（以 / 或盘符开头）
    2. 解析后必须在 base_download_dir 内部
    3. 拒绝包含 .. 的路径组件
    
    Args:
        requested_path: 用户请求的保存路径
        base_download_dir: 系统配置的下载根目录
        
    Returns:
        验证通过后的安全路径
        
    Raises:
        ValueError: 路径不安全
    """
    if not requested_path:
        return base_download_dir
    
    # 1. 拒绝绝对路径
    if Path(requested_path).is_absolute():
        raise ValueError(
            f"非法操作：禁止使用绝对路径 '{requested_path}'。"
            f"必须使用相对于下载目录的相对路径。"
        )
    
    # 2. 拒绝包含 .. 的路径（防止目录穿越）
    path_parts = Path(requested_path).parts
    if ".." in path_parts:
        raise ValueError(
            f"非法操作：路径包含非法组件 '..'。禁止访问下载目录之外的位置。"
        )
    
    # 3. 解析最终路径，确保它在 base_download_dir 内部
    base_path = Path(base_download_dir).resolve()
    target_path = (base_path / requested_path).resolve()
    
    # 4. 核心安全断言：目标路径必须在 base_path 内部
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise ValueError(
            f"非法操作：禁止跨目录下载文件。"
            f"请求的路径解析后为 '{target_path}'，超出了允许的下载目录范围。"
        )
    
    # 5. 拒绝指向系统敏感目录的路径（额外保护层）
    SENSITIVE_DIRS = [
        "/etc", "/root", "/home", "/var", "/usr", "/bin", "/sbin",
        "/boot", "/dev", "/proc", "/sys", "/run", "/snap",
        "C:\\Windows", "C:\\Program Files", "C:\\ProgramData"
    ]
    
    target_str = str(target_path).lower()
    for sensitive in SENSITIVE_DIRS:
        if target_str.startswith(sensitive.lower()):
            raise ValueError(
                f"非法操作：禁止在系统敏感目录 '{sensitive}' 中下载文件。"
            )
    
    logger.info(f"路径校验通过: '{requested_path}' -> '{target_path}'")
    return str(target_path)


@dataclass
class TorrentInfo:
    """种子信息"""
    hash: str
    name: str
    size: int               # bytes
    downloaded: int         # bytes
    progress: float         # 0-100
    speed: int              # bytes/s
    seeders: int
    eta: int                # seconds
    status: str             # downloading / seeding / completed / paused / error
    save_path: str
    category: str = ""


class DownloadClientAdapter(ABC):
    """下载客户端抽象基类"""

    def __init__(self, host: str, port: int, username: str = "", password: str = ""):
        self.host = host.strip().rstrip("/")
        self.port = port
        self.username = username
        self.password = password
        # httpx 要求 base_url 必须有 http:// 或 https:// 协议头
        # 兼容用户填 "localhost:8080"、"http://localhost:8080"、或 "https://example.com:8443"
        if self.host.startswith(("http://", "https://")):
            # 用户填了完整 URL，直接拼接端口
            self.base_url = f"{self.host}:{port}"
        else:
            self.base_url = f"http://{self.host}:{port}"
        self._client: httpx.AsyncClient | None = None
        self._logged_in = False

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            from app.config import get_settings
            settings = get_settings()
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
                follow_redirects=True,
                verify=settings.verify_client_ssl,
            )
        return self._client

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def add_torrent(
        self,
        url: str,
        save_path: str | None = None,
        category: str | None = None,
    ) -> str:  # returns hash/id
        ...

    @abstractmethod
    async def get_torrents(self, status: str | None = None) -> list[TorrentInfo]: ...

    @abstractmethod
    async def pause(self, torrent_hash: str) -> bool: ...

    @abstractmethod
    async def resume(self, torrent_hash: str) -> bool: ...

    @abstractmethod
    async def delete(self, torrent_hash: str, delete_files: bool = False) -> bool: ...

    @abstractmethod
    async def get_client_version(self) -> str: ...

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class QBittorrentAdapter(DownloadClientAdapter):
    """qBittorrent WebUI API 适配器

    qBittorrent v4.1 - v4.6.x WebUI API 认证说明:
      - 认证方式：基于 Cookie 的 SID 会话
      - 登录接口：POST /api/v2/auth/login
      - Referer 头：所有请求必须设置 Referer 为服务端地址，否则 403
      - SID Cookie：登录成功后在响应头 Set-Cookie 中返回，后续请求自动携带

    支持的下载 URL 格式:
      - 磁力链: magnet:?xt=urn:btih:...
      - HTTP/HTTPS 种子下载 URL
      - TORRENT: 前缀 + Base64 编码的种子内容
      - tracker URL (如 M-Team): https://tracker.m-team.cc/announce?credential=...
    """

    API = "/api/v2"

    @property
    def _referer(self) -> str:
        """qBittorrent 要求 Referer 头为服务端地址"""
        return self.base_url

    def _auth_headers(self) -> dict[str, str]:
        """构建认证相关的请求头"""
        return {"Referer": self._referer}

    async def connect(self) -> bool:
        try:
            resp = await self.client.post(
                f"{self.API}/auth/login",
                data={"username": self.username, "password": self.password},
                headers=self._auth_headers(),
            )
            # qBittorrent 永远返回 HTTP 200，区分成功/失败看响应体
            if resp.status_code == 200:
                resp_text = resp.text.strip()
                if resp_text.lower() == "ok.":
                    self._logged_in = True
                    logger.info(f"qBittorrent connected: {self.base_url}")
                else:
                    self._logged_in = False
                    logger.error(f"qBittorrent login failed: {resp_text} (HTTP {resp.status_code})")
            else:
                self._logged_in = False
                logger.error(f"qBittorrent login HTTP error: {resp.status_code}")
            return self._logged_in
        except Exception as e:
            logger.warning(f"qBittorrent connect error ({self.base_url}): {e}")
            return False

    async def _ensure_login(self):
        if not self._logged_in:
            await self.connect()

    @staticmethod
    def _is_valid_torrent(content: bytes) -> bool:
        """验证内容是否为有效的 torrent 文件（Bencode dict 格式）

        合法的 .torrent 文件是 Bencode 编码的 dictionary，
        以字节 b"d" 开头（后续跟任意键长度数字）。
        常见开头: d4:、d6:、d8:、d10:、d13: 等
        """
        return len(content) > 50 and content[:1] == b"d"

    async def _try_download_torrent(self, url: str) -> tuple[bytes | None, str]:
        """尝试下载种子文件

        支持的 URL 类型:
          - HTTP/HTTPS 种子下载 URL
          - tracker URL (如 M-Team)

        Returns:
            (torrent_content, error_message)
        """
        try:
            from app.config import get_settings
            settings = get_settings()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
                follow_redirects=True, verify=settings.verify_client_ssl
            ) as http_client:
                # HEAD 请求检查内容类型（不携带内部认证头，防止 Referer 泄露内网地址）
                try:
                    head_resp = await http_client.head(url)
                    content_type = head_resp.headers.get("content-type", "")
                    final_url = str(head_resp.url) if head_resp.url else url
                except Exception:
                    content_type = ""
                    final_url = url

                # 如果是种子文件，直接下载（不携带内部认证头）
                if (".torrent" in final_url.lower() or
                    ".torrent" in url.lower() or
                    "application/x-bittorrent" in content_type or
                    "application/octet-stream" in content_type):
                    logger.info(f"检测到种子文件 URL，正在下载: {url[:60]}...")
                    dl_resp = await http_client.get(url)
                    if dl_resp.status_code == 200:
                        content = dl_resp.content
                        # 验证是否为有效的种子文件（Bencode dict 以 d 开头）
                        if self._is_valid_torrent(content):
                            logger.info(f"种子文件下载成功 (大小: {len(content)} bytes)")
                            return content, ""
                        else:
                            logger.warning(f"下载的内容不是有效的种子文件 (头部: {content[:20]})")

                # 尝试 GET 请求下载（不携带内部认证头）
                dl_resp = await http_client.get(url)
                content_type = dl_resp.headers.get("content-type", "")
                final_url = str(dl_resp.url) if dl_resp.url else url

                # 检查下载的内容
                if dl_resp.status_code == 200:
                    content = dl_resp.content

                    # 验证种子文件格式（Bencode dict 以 d 开头）
                    if self._is_valid_torrent(content):
                        logger.info(f"GET 下载种子成功 (大小: {len(content)} bytes)")
                        return content, ""

                    # 检查是否返回了 HTML（可能是登录页或错误页）
                    if content[:100].strip().startswith(b"<!") or content[:100].strip().startswith(b"<html"):
                        logger.warning(f"下载返回了 HTML 内容，可能需要认证")
                        return None, "下载返回 HTML，可能需要认证"

                    # 尝试从响应中提取种子 URL
                    import re
                    # 尝试提取 tracker URL 并构建磁力链
                    tracker_match = re.search(
                        r'https://tracker[^\s"\'<>]+\.cc/announce\?[^\s"\'<>]+',
                        content.decode("utf-8", errors="ignore")
                    )
                    if not tracker_match:
                        tracker_match = re.search(
                            r'https://[^\s"\'<>]*m-team[^\s"\'<>]*announce[^\s"\'<>]*',
                            content.decode("utf-8", errors="ignore")
                        )

                    if tracker_match:
                        # 找到了 tracker URL，尝试构建磁力链
                        tracker_url = tracker_match.group(0)
                        logger.info(f"从响应中提取到 tracker URL: {tracker_url[:60]}...")

                        # 尝试从 URL 中提取 credential
                        if "credential=" in tracker_url:
                            # M-Team tracker URL 可以直接作为磁力链的 announce 使用
                            return None, f"MAGNET_NEED_TRACKER:{tracker_url}"

                    # 检查 JSON 响应
                    try:
                        data = dl_resp.json()
                        
                        # 检查 data 字段是否直接是 Base64 编码的种子内容
                        data_field = data.get("data") or data.get("download_url") or data.get("downloadLink")
                        if data_field:
                            data_str = str(data_field)
                            # 如果是 Base64 编码的种子内容（长度大且不是 http 开头）
                            if len(data_str) > 1000 and not data_str.startswith("http"):
                                import base64
                                try:
                                    torrent_bytes = base64.b64decode(data_str)
                                    if self._is_valid_torrent(torrent_bytes):
                                        logger.info(f"JSON data 字段包含 Base64 种子内容 (大小: {len(torrent_bytes)} bytes)")
                                        return torrent_bytes, ""
                                except Exception:
                                    pass  # 不是 Base64，继续作为 URL 处理
                            
                            # 作为下载 URL 处理
                            if data_str.startswith("http"):
                                return await self._try_download_torrent(data_str)
                    except Exception:
                        pass

                    return None, f"无法解析下载响应 (状态码: {dl_resp.status_code}, 头部: {content[:20]})"

        except httpx.HTTPStatusError as e:
            logger.error(f"下载种子文件 HTTP 错误 {e.response.status_code}: {e.response.text[:100]}")
            return None, f"HTTP {e.response.status_code}"
        except Exception as e:
            logger.error(f"下载种子文件失败: {e}")
            return None, str(e)

        return None, "未知错误"

    async def _get_latest_torrent_hash(self, max_wait_seconds: int = 5, category: str | None = None) -> str | None:
        """获取最近添加的任务的 hash

        通过获取 torrent info 列表，按添加时间倒序返回第一个的 hash。
        这用于在添加任务后获取真实的 hash，以便后续匹配和状态同步。

        如果提供了 category，则只返回该 category 的 torrent（用于避免竞态条件）。

        Args:
            max_wait_seconds: 最大等待秒数，用于等待任务出现
            category: 可选，按 category 过滤（推荐使用 UUID 来避免竞态）

        Returns:
            任务的 info hash，如果失败返回 None
        """
        import asyncio
        start_time = asyncio.get_event_loop().time if hasattr(asyncio, 'get_event_loop') else None

        for attempt in range(10):  # 最多尝试 10 次
            try:
                params = {}
                if category:
                    params["category"] = category
                resp = await self.client.get(
                    f"{self.API}/torrents/info",
                    params=params,
                    headers=self._auth_headers(),
                )
                if resp.status_code == 200:
                    torrents = resp.json()
                    if torrents:
                        # 按添加时间倒序，取最新的
                        latest = torrents[0]  # qBittorrent 已按时间倒序
                        info_hash = latest.get("hash", "").lower()
                        if info_hash and len(info_hash) in (32, 40):
                            logger.info(f"获取到任务 hash: {info_hash} ({latest.get('name', '')})")
                            return info_hash
            except Exception as e:
                logger.debug(f"获取任务 hash 失败 (尝试 {attempt + 1}): {e}")

            if attempt < 9:  # 不是最后一次，等待一下
                await asyncio.sleep(0.3)

        logger.warning("无法获取新添加任务的 hash")
        return None

    def _calc_torrent_hash(self, torrent_content: bytes) -> str | None:
        """从种子文件内容计算 info_hash

        使用 SHA1(info_dict) 计算 hash，这是 BitTorrent 协议的标准。

        Args:
            torrent_content: 原始种子文件内容

        Returns:
            40位的 info_hash (hex 字符串)，失败返回 None
        """
        import hashlib

        try:
            # 解析 Bencode 数据
            def bencode_read(data, pos=0):
                if data[pos:pos+1] == b'i':
                    # 整数
                    end = data.index(b'e', pos)
                    return int(data[pos+1:end]), end + 1
                elif data[pos:pos+1] == b'l':
                    # 列表
                    pos += 1
                    items = []
                    while data[pos:pos+1] != b'e':
                        item, pos = bencode_read(data, pos)
                        items.append(item)
                    return items, pos + 1
                elif data[pos:pos+1] == b'd':
                    # 字典
                    pos += 1
                    items = {}
                    while data[pos:pos+1] != b'e':
                        key, pos = bencode_read(data, pos)
                        value, pos = bencode_read(data, pos)
                        items[key] = value
                    return items, pos + 1
                elif data[pos:pos+1].isdigit():
                    # 字节串
                    colon = data.index(b':', pos)
                    length = int(data[pos:colon])
                    value = data[colon+1:colon+1+length]
                    return value, colon + 1 + length
                else:
                    raise ValueError(f"Invalid bencode at position {pos}")

            # 解析种子
            decoded, _ = bencode_read(torrent_content)

            # 提取 info 字典并重新编码
            info_dict = decoded.get(b'info')
            if not info_dict:
                return None

            # 重新编码 info 字典
            def bencode_encode(data):
                if isinstance(data, int):
                    return f"i{data}e".encode()
                elif isinstance(data, bytes):
                    return f"{len(data)}:".encode() + data
                elif isinstance(data, str):
                    return f"{len(data)}:".encode() + data.encode()
                elif isinstance(data, list):
                    return b'l' + b''.join(bencode_encode(item) for item in data) + b'e'
                elif isinstance(data, dict):
                    # 注意：Bencode 字典的键必须是 bytes 且按字典序排列
                    result = b'd'
                    for key in sorted(data.keys(), key=lambda k: (isinstance(k, bytes) and k or k.encode()) if isinstance(k, str) else k):
                        value = data[key]
                        key_bytes = key.encode() if isinstance(key, str) else key
                        result += bencode_encode(key_bytes) + bencode_encode(value)
                    return result + b'e'
                else:
                    raise ValueError(f"Cannot bencode: {type(data)}")

            info_bencoded = bencode_encode(info_dict)
            info_hash = hashlib.sha1(info_bencoded).hexdigest()
            return info_hash.lower()
        except Exception as e:
            logger.debug(f"计算种子 hash 失败: {e}")
            return None

    async def _find_existing_torrent_hash(self, info_hash: str) -> str | None:
        """在 qBittorrent 中查找已存在的种子

        Args:
            info_hash: 要查找的 info hash

        Returns:
            找到的 info hash，失败返回 None
        """
        try:
            resp = await self.client.get(
                f"{self.API}/torrents/info",
                headers=self._auth_headers(),
            )
            if resp.status_code == 200:
                torrents = resp.json()
                for t in torrents:
                    if t.get("hash", "").lower() == info_hash.lower():
                        logger.info(f"找到已存在的种子: {t.get('name', '')} (hash: {info_hash})")
                        return info_hash
            return None
        except Exception as e:
            logger.debug(f"查找已存在种子失败: {e}")
            return None

    async def _construct_magnet(self, tracker_url: str, name: str = "") -> str:
        """从 tracker URL 构造磁力链

        M-Team tracker URL 格式: https://tracker.m-team.cc/announce?credential=xxx
        可以直接作为磁力链的 dn 和 tr 参数使用
        """
        import urllib.parse

        # 提取 credential
        credential = ""
        if "credential=" in tracker_url:
            parts = tracker_url.split("credential=")
            if len(parts) > 1:
                credential = parts[1].split("&")[0]

        if not credential:
            logger.warning(f"无法从 tracker URL 提取 credential: {tracker_url[:60]}")
            return ""

        # 构造磁力链
        # M-Team 的 credential 可以直接作为 passkey 使用
        # 由于没有 info_hash，我们只能使用 tracker URL
        # qBittorrent 可能无法完全处理这种情况
        magnet_parts = [
            "magnet:?",
            f"dn={urllib.parse.quote(name)}" if name else "dn=download",
            f"tr={urllib.parse.quote(tracker_url)}",
        ]

        magnet = "&".join(magnet_parts)
        logger.info(f"构造磁力链: {magnet[:100]}...")
        return magnet

    async def add_torrent(
        self, url: str, save_path: str | None = None, category: str | None = None
    ) -> str:
        """添加种子到 qBittorrent

        支持多种 URL 格式:
          - 磁力链: magnet:?xt=urn:btih:...
          - HTTP/HTTPS 种子下载 URL
          - TORRENT: 前缀 + Base64 编码的种子内容
          - tracker URL (如 M-Team)
        """
        await self._ensure_login()

        # 生成 UUID 用于避免竞态条件（确保获取到正确的 hash）
        import uuid
        temp_category = str(uuid.uuid4())

        data: dict[str, str] = {}
        if save_path:
            # ── Issue #54 修复：路径安全校验 ──
            from app.config import get_settings
            settings = get_settings()
            safe_path = validate_download_path(save_path, settings.download_dir)
            data["savepath"] = safe_path
            logger.info(f"Download path validated: '{save_path}' -> '{safe_path}'")
        
        # 使用临时 category 来识别新添加的种子（避免竞态）
        data["category"] = temp_category
        user_category = category  # 保存用户原始的 category

        # 处理特殊格式
        if url.startswith("TORRENT:"):
            # Base64 编码的种子文件内容
            import base64
            try:
                b64_data = url[8:]
                # 验证 Base64 格式
                if not b64_data or len(b64_data) < 100:
                    raise Exception(f"Base64 数据太短 (长度: {len(b64_data)})，可能不是有效的种子")
                
                torrent_content = base64.b64decode(b64_data)
                
                # 验证种子文件格式（Bencode dict 以 d 开头）
                if not self._is_valid_torrent(torrent_content):
                    preview = torrent_content[:20]
                    raise Exception(f"解码内容不是有效的种子文件格式 (文件头: {preview}，大小: {len(torrent_content)} bytes)")
                
                logger.info(f"添加 Base64 编码的种子文件 (大小: {len(torrent_content)} bytes)")
                resp = await self.client.post(
                    f"{self.API}/torrents/add",
                    data=data,
                    files={"torrents": ("torrent.torrent", torrent_content, "application/x-bittorrent")},
                    headers=self._auth_headers(),
                )
                resp_text = resp.text.strip()
                logger.info(f"qBittorrent 添加种子响应: {resp_text[:100]!r}")
                # qBittorrent 成功时返回 "Ok." 或空字符串
                if resp_text.lower() in ("ok.", "ok", ""):
                    logger.info("种子添加成功 (Base64)，正在获取任务 hash")
                    # 使用临时 category 获取新添加任务的真实 hash（避免竞态）
                    torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                    if torrent_hash:
                        # 如果用户指定了 category，更新它
                        if user_category:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": user_category},
                                headers=self._auth_headers(),
                            )
                        else:
                            # 清除临时 category
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": ""},
                                headers=self._auth_headers(),
                            )
                        return torrent_hash
                    return "torrent-base64"
                elif resp_text.lower() == "fails.":
                    # 种子可能已存在，尝试从现有种子中找到匹配的
                    logger.warning(f"qBittorrent 返回 Fails，可能是种子已存在，尝试查找...")
                    # 验证种子文件格式以获取 hash
                    info_hash = self._calc_torrent_hash(torrent_content)
                    if info_hash:
                        # 尝试获取已存在种子的 hash
                        existing_hash = await self._find_existing_torrent_hash(info_hash)
                        if existing_hash:
                            logger.info(f"找到已存在的种子 hash: {existing_hash}")
                            return existing_hash
                    raise Exception(f"qBittorrent 添加种子失败: {resp_text} (种子可能已存在)")
                else:
                    # 任何非成功响应都视为失败（包括中文错误消息）
                    raise Exception(f"qBittorrent 添加种子失败: {resp_text}")
            except Exception as e:
                logger.error(f"处理 Base64 种子失败: {e}")
                raise

        elif url.startswith("magnet:"):
            # 磁力链
            logger.info(f"添加磁力链: {url[:80]}...")
            data["urls"] = url
            resp = await self.client.post(
                f"{self.API}/torrents/add",
                data=data,
                headers=self._auth_headers(),
            )
            resp_text = resp.text.strip()
            if resp_text.lower() == "fail." or "fail" in resp_text.lower():
                raise Exception(f"添加磁力链失败: {resp_text}")

            # 从磁力链提取 info_hash
            import re as _re
            match = _re.search(r"urn:btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", url)
            if match:
                return match.group(1).lower()
            return "magnet"

        elif url.startswith("MAGNET_NEED_TRACKER:"):
            # 需要从 tracker URL 构造磁力链
            tracker_url = url.replace("MAGNET_NEED_TRACKER:", "")
            magnet = await self._construct_magnet(tracker_url)
            if magnet:
                logger.info(f"从 tracker URL 构造磁力链: {magnet[:100]}...")
                data["urls"] = magnet
                resp = await self.client.post(
                    f"{self.API}/torrents/add",
                    data=data,
                    headers=self._auth_headers(),
                )
                resp_text = resp.text.strip()
                if resp_text.lower() in ("ok.", "", "tracker-magnet"):
                    # 尝试获取 hash
                    torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                    if torrent_hash:
                        # 如果用户指定了 category，更新它
                        if user_category:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": user_category},
                                headers=self._auth_headers(),
                            )
                        return torrent_hash
                    return "tracker-magnet"
                elif "fail" not in resp_text.lower():
                    torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                    if torrent_hash:
                        if user_category:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": user_category},
                                headers=self._auth_headers(),
                            )
                        return torrent_hash
                    return "tracker-magnet"

            # 磁力链构造失败，尝试直接下载种子
            logger.warning(f"构造磁力链失败，尝试直接下载种子...")
            torrent_content, error = await self._try_download_torrent(tracker_url)
            if torrent_content:
                resp = await self.client.post(
                    f"{self.API}/torrents/add",
                    data=data,
                    files={"torrents": ("torrent.torrent", torrent_content, "application/x-bittorrent")},
                    headers=self._auth_headers(),
                )
                resp_text2 = resp.text.strip()
                if resp_text2.lower() == "ok." or resp_text2 == "":
                    logger.info("种子添加成功 (tracker 下载)，正在获取任务 hash")
                    torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                    if torrent_hash:
                        # 如果用户指定了 category，更新它
                        if user_category:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": user_category},
                                headers=self._auth_headers(),
                            )
                        else:
                            # 清除临时 category
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": ""},
                                headers=self._auth_headers(),
                            )
                        return torrent_hash
                    return "tracker-download"
                elif "fail" in resp_text2.lower():
                    raise Exception(f"添加种子失败: {resp_text2}")
                else:
                    # 其他响应也视为成功
                    torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                    if torrent_hash:
                        if user_category:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": user_category},
                                headers=self._auth_headers(),
                            )
                        else:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": ""},
                                headers=self._auth_headers(),
                            )
                        return torrent_hash
                    return "tracker-download"
            raise Exception(f"无法添加: {error or 'tracker URL 不被支持'}")

        elif url.startswith(("http://", "https://")):
            # HTTP/HTTPS URL：可能是种子下载 URL 或 tracker URL
            try:
                # 先尝试直接下载种子
                torrent_content, error = await self._try_download_torrent(url)

                if torrent_content:
                    # 成功下载种子文件，上传
                    logger.info(f"成功下载种子文件，正在添加到 qBittorrent...")
                    resp = await self.client.post(
                        f"{self.API}/torrents/add",
                        data=data,
                        files={"torrents": ("torrent.torrent", torrent_content, "application/x-bittorrent")},
                        headers=self._auth_headers(),
                    )
                    resp_text = resp.text.strip()
                    logger.info(f"qBittorrent HTTP 下载添加响应: {resp_text[:100]!r}")
                    if resp_text.lower() in ("ok.", "ok", ""):
                        logger.info("种子添加成功 (HTTP 下载)，正在获取任务 hash")
                        torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                        if torrent_hash:
                            # 如果用户指定了 category，更新它
                            if user_category:
                                await self.client.post(
                                    f"{self.API}/torrents/setCategory",
                                    data={"hashes": torrent_hash, "category": user_category},
                                    headers=self._auth_headers(),
                                )
                            else:
                                # 清除临时 category
                                await self.client.post(
                                    f"{self.API}/torrents/setCategory",
                                    data={"hashes": torrent_hash, "category": ""},
                                    headers=self._auth_headers(),
                                )
                            return torrent_hash
                        return "http-torrent"
                    else:
                        # 非成功响应，抛出异常以触发 URL 方式兜底
                        logger.warning(f"种子文件添加失败: {resp_text}，尝试 URL 方式")
                        raise Exception(f"qBittorrent 添加种子失败: {resp_text}")

                # 下载失败，尝试作为 URL 添加（仅对可能直接下载的 URL 有效）
                # genDlToken API 地址不适合直接传给 QB
                if "genDlToken" in url or "api/torrent" in url:
                    raise Exception(f"M-Team genDlToken 下载失败 ({error})，请检查 API Key 权限")

                logger.info(f"直接下载失败 ({error})，尝试作为 URL 添加: {url[:80]}...")
                data["urls"] = url
                resp = await self.client.post(
                    f"{self.API}/torrents/add",
                    data=data,
                    headers=self._auth_headers(),
                )
                resp_text = resp.text.strip()
                logger.info(f"qBittorrent URL 添加响应: {resp_text[:100]!r}")

                if resp_text.lower() in ("ok.", "ok", ""):
                    logger.info("URL 添加成功")
                    torrent_hash = await self._get_latest_torrent_hash(category=temp_category)
                    if torrent_hash:
                        # 如果用户指定了 category，更新它
                        if user_category:
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": user_category},
                                headers=self._auth_headers(),
                            )
                        else:
                            # 清除临时 category
                            await self.client.post(
                                f"{self.API}/torrents/setCategory",
                                data={"hashes": torrent_hash, "category": ""},
                                headers=self._auth_headers(),
                            )
                        return torrent_hash
                    return "http-url"

                # URL 方式也失败
                logger.warning(f"URL 方式添加失败: {resp_text}")
                raise Exception(f"添加失败: {resp_text}")

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP {e.response.status_code}: {e.response.text[:100]}")
                raise Exception(f"HTTP {e.response.status_code}")
            except Exception as e:
                logger.error(f"处理下载 URL 时出错: {e}")
                raise

        else:
            # 本地种子文件 - 严格路径校验防止任意文件读取
            from pathlib import Path
            from app.config import get_settings

            file_path = Path(url).resolve()
            settings = get_settings()
            safe_upload_dir = Path(settings.data_dir) / "tmp_uploads"
            safe_upload_dir.mkdir(parents=True, exist_ok=True)

            # 验证路径在安全的上传目录内
            try:
                file_path.relative_to(safe_upload_dir.resolve())
            except ValueError:
                raise Exception(f"安全警告：非法的种子文件路径！路径必须在 {safe_upload_dir} 内")

            if not file_path.exists() or not file_path.is_file():
                raise Exception(f"种子文件不存在：{url}")

            logger.info(f"读取本地种子文件：{file_path}")
            try:
                with open(file_path, "rb") as f:
                    torrent_content = f.read()
            except Exception as e:
                raise Exception(f"读取种子文件失败: {e}")

            resp = await self.client.post(
                f"{self.API}/torrents/add",
                data=data,
                files={"torrents": ("file.torrent", torrent_content, "application/x-bittorrent")},
                headers=self._auth_headers(),
            )

        if resp.status_code != 200:
            raise Exception(f"Failed to add torrent: {resp.text}")

        return "unknown"

    async def get_torrents(self, status: str | None = None) -> list[TorrentInfo]:
        await self._ensure_login()
        params: dict[str, Any] = {}
        if status == "downloading":
            params["filter"] = "downloading"
        elif status == "seeding":
            params["filter"] = "seeding"
        elif status == "completed":
            params["filter"] = "completed"

        try:
            resp = await self.client.get(
                f"{self.API}/torrents/info",
                params=params,
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # 拦截 403 错误，标记为未登录并尝试重新登录
            if e.response.status_code == 403:
                logger.warning("qBittorrent 会话已过期，尝试重新登录...")
                self._logged_in = False
                await self._ensure_login()
                # 重新发送请求
                resp = await self.client.get(
                    f"{self.API}/torrents/info",
                    params=params,
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
            else:
                raise

        torrents = resp.json()

        results = []
        for t in torrents:
            results.append(TorrentInfo(
                hash=t["hash"],
                name=t["name"],
                size=t["size"],
                downloaded=t["downloaded"],
                progress=round(t["progress"] * 100, 1),
                speed=t["dlspeed"],
                seeders=t["num_seeds"],
                eta=t["eta"],
                status=self._map_state(t["state"]),
                save_path=t["save_path"],
                category=t.get("category", ""),
            ))
        return results

    async def pause(self, torrent_hash: str) -> bool:
        await self._ensure_login()
        resp = await self.client.post(
            f"{self.API}/torrents/pause",
            data={"hashes": torrent_hash},
            headers=self._auth_headers(),
        )
        return resp.status_code == 200

    async def resume(self, torrent_hash: str) -> bool:
        await self._ensure_login()
        resp = await self.client.post(
            f"{self.API}/torrents/resume",
            data={"hashes": torrent_hash},
            headers=self._auth_headers(),
        )
        return resp.status_code == 200

    async def delete(self, torrent_hash: str, delete_files: bool = False) -> bool:
        await self._ensure_login()
        resp = await self.client.post(
            f"{self.API}/torrents/delete",
            data={"hashes": torrent_hash, "deleteFiles": str(delete_files).lower()},
            headers=self._auth_headers(),
        )
        return resp.status_code == 200

    async def get_client_version(self) -> str:
        await self._ensure_login()
        resp = await self.client.get(
            f"{self.API}/app/version",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return f"qBittorrent {resp.text}"

    @staticmethod
    def _map_state(state: str) -> str:
        """
        将 qBittorrent 内部状态映射到统一状态。

        qBittorrent 完成下载后进入做种阶段，状态变为 uploading/stalledUP/forcedUP 等。
        这些状态均代表「下载已完成」，统一映射为 "completed"。
        """
        mapping = {
            # 下载中
            "downloading": "downloading",
            "stalledDL": "downloading",
            "queuedDL": "downloading",
            "checkingDL": "downloading",
            "metaDL": "downloading",
            "allocating": "downloading",
            "forcedDL": "downloading",
            # 下载完成/做种中 → 统一视为已完成
            "uploading": "completed",
            "stalledUP": "completed",
            "forcedUP": "completed",
            "checkingUP": "completed",
            "queuedUP": "completed",
            "moving": "completed",
            # 暂停：上传暂停 = 下载已完成；下载暂停 = 还在下载
            "pausedUP": "completed",
            "pausedDL": "paused",
            # 错误
            "error": "error",
            "missingFiles": "error",
            "unknown": "error",
        }
        return mapping.get(state, state)


class TransmissionAdapter(DownloadClientAdapter):
    """Transmission RPC 适配器"""

    _rpc_id = 1

    async def _rpc_call(self, method: str, arguments: dict | None = None) -> dict:
        payload: dict[str, Any] = {"method": method, "tag": self._rpc_id}
        if arguments:
            payload["arguments"] = arguments
        self._rpc_id += 1

        resp = await self.client.post("/transmission/rpc", json=payload)
        if resp.status_code == 409:
            # 需要认证
            csrf_token = resp.headers.get("X-Transmission-Session-Id")
            self._client.headers["X-Transmission-Session-Id"] = csrf_token
            resp = await self.client.post("/transmission/rpc", json=payload)

        resp.raise_for_status()
        return resp.json()

    async def connect(self) -> bool:
        try:
            result = await self._rpc_call("session-get")
            self._logged_in = "arguments" in result
            if self._logged_in:
                logger.info(f"Transmission connected: {self.base_url}")
            return self._logged_in
        except Exception as e:
            logger.warning(f"Transmission connect error ({self.base_url}): {e}")
            return False

    async def add_torrent(
        self, url: str, save_path: str | None = None, category: str | None = None
    ) -> str:
        arguments: dict[str, Any] = {"filename": url}
        if save_path:
            # ── Issue #54 修复：路径安全校验 ──
            from app.config import get_settings
            settings = get_settings()
            safe_path = validate_download_path(save_path, settings.download_dir)
            arguments["download-dir"] = safe_path
            logger.info(f"Transmission download path validated: '{save_path}' -> '{safe_path}'")
        
        result = await self._rpc_call("torrent-add", arguments)
        torrent = result.get("arguments", {}).get("torrent-added", {})
        return str(torrent.get("hashString", ""))

    async def get_torrents(self, status: str | None = None) -> list[TorrentInfo]:
        result = await self._rpc_call("torrent-get", {"fields": [
            "hashString", "name", "totalSize", "downloadedEver", "percentDone",
            "rateDownload", "seeders", "eta", "status", "downloadDir", "labels",
        ]})
        torrents = result.get("arguments", {}).get("torrents", [])

        status_map = {
            4: "downloading",   # TR_STATUS_DOWNLOAD
            6: "seeding",       # TR_STATUS_SEED
            0: "stopped",       # TR_STATUS_STOPPED
            3: "downloading",   # TR_STATUS_DOWNLOAD_WAIT
        }

        results = []
        for t in torrents:
            results.append(TorrentInfo(
                hash=t["hashString"],
                name=t["name"],
                size=t["totalSize"],
                downloaded=t["downloadedEver"],
                progress=round(t["percentDone"] * 100, 1),
                speed=t["rateDownload"],
                seeders=t.get("seeders", 0),
                eta=t["eta"],
                status=status_map.get(t["status"], "downloading"),
                save_path=t["downloadDir"],
                category=", ".join(t.get("labels", [])),
            ))
        return results

    async def pause(self, torrent_hash: str) -> bool:
        await self._rpc_call("torrent-stop", {"ids": [torrent_hash]})
        return True

    async def resume(self, torrent_hash: str) -> bool:
        await self._rpc_call("torrent-start", {"ids": [torrent_hash]})
        return True

    async def delete(self, torrent_hash: str, delete_files: bool = False) -> bool:
        await self._rpc_call(
            "torrent-remove",
            {"ids": [torrent_hash], "delete-local-data": delete_files},
        )
        return True

    async def get_client_version(self) -> str:
        result = await self._rpc_call("session-get")
        version = result.get("arguments", {}).get("version", "unknown")
        return f"Transmission {version}"


class Aria2Adapter(DownloadClientAdapter):
    """Aria2 JSON-RPC 适配器 (via HTTP)

    Aria2 通过 HTTP JSON-RPC 通信，支持 magnet/种子/直链。
    需要配置 host（含 RPC 路径）和可选的 secret token。
    """

    def __init__(self, host: str, port: int, username: str = "", password: str = ""):
        # Aria2 的 "password" 字段复用为 RPC secret token
        super().__init__(host, port, username, password)
        self._secret = password  # aria2.secret
        # Aria2 默认 RPC 端口 6800, 路径 /jsonrpc
        # base_url 已由父类补上了 http://，这里只追加路径
        host_stripped = host.strip().rstrip("/")
        base = host_stripped if host_stripped.startswith(("http://", "https://")) else f"http://{host_stripped}"
        self.base_url = f"{base}:{port}/jsonrpc"
        # 重新初始化 client
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            from app.config import get_settings
            settings = get_settings()
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),   # Aria2 某些操作较慢
                follow_redirects=True,
                verify=settings.verify_client_ssl,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    def _build_params(self, method_name: str, params: list | None = None) -> dict[str, Any]:
        """构建 Aria2 JSON-RPC 请求体

        Aria2 JSON-RPC 规范:
        - jsonrpc: "2.0"
        - id: 自增 ID
        - method: "aria2.{methodName}"
        - params: [token, ...args]  (如果有 secret)
        """
        rpc_params = []
        if self._secret:
            rpc_params.append(f"token:{self._secret}")
        if params:
            rpc_params.extend(params)

        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4())[:8],
            "method": f"aria2.{method_name}",
            "params": rpc_params,
        }

    async def _call(self, method_name: str, params: list | None = None) -> dict:
        """发送 JSON-RPC 请求并返回结果"""
        payload = self._build_params(method_name, params)
        try:
            resp = await self.client.post("", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise Exception(f"Aria2 RPC error: {data['error']}")
            return data
        except httpx.HTTPStatusError as e:
            raise Exception(f"Aria2 HTTP {e.response.status_code}: {e.response.text}")

    async def connect(self) -> bool:
        try:
            result = await self._call("getVersion")
            version_data = result.get("result", {})
            version = version_data.get("version", ["unknown"])[0] if isinstance(version_data.get("version"), list) else version_data.get("version", "unknown")
            enabled_features = version_data.get("enabledFeatures", [])
            logger.info(f"Aria2 connected: v{version} at {self.base_url}, features={enabled_features}")
            self._logged_in = True
            return True
        except Exception as e:
            logger.warning(f"Aria2 connect error ({self.base_url}): {e}")
            return False

    async def add_torrent(
        self, url: str, save_path: str | None = None, category: str | None = None
    ) -> str:
        """添加下载任务（支持 magnet/种子 URL/直链/本地种子文件）"""
        try:
            if url.startswith(("magnet:", "http://", "https://", "ftp://", "ftps://")):
                # URL 类型：magnet 或远程资源
                options = {}
                if save_path:
                    # ── Issue #54 修复：路径安全校验 ──
                    from app.config import get_settings
                    settings = get_settings()
                    safe_path = validate_download_path(save_path, settings.download_dir)
                    options["dir"] = safe_path
                    logger.info(f"Aria2 download path validated: '{save_path}' -> '{safe_path}'")
                
                if category:
                    options["all-subscription"] = category  # 使用 Aria2 的订阅名标记

                result = await self._call("addUri", [[url], options])
                gid = result.get("result", "")
                logger.info(f"Aria2 added URI: {url[:60]}... => GID={gid}")
                return gid

            else:
                # 本地种子文件路径 - 严格路径校验防止任意文件读取（Issue #17 修复）
                from pathlib import Path
                from app.config import get_settings
                
                file_path = Path(url).resolve()
                settings = get_settings()
                safe_upload_dir = Path(settings.data_dir) / "tmp_uploads"
                safe_upload_dir.mkdir(parents=True, exist_ok=True)
                
                # 验证路径在安全的上传目录内
                try:
                    file_path.relative_to(safe_upload_dir.resolve())
                except ValueError:
                    raise ValueError(f"安全警告：非法的种子文件路径！路径必须在 {safe_upload_dir} 内")
                
                logger.info(f"读取本地种子文件：{file_path}")
                import base64
                with open(file_path, "rb") as f:
                    torrent_b64 = base64.b64encode(f.read()).decode()

                    options = {}
                    if save_path:
                        # ── Issue #54 修复：路径安全校验 ──
                        from app.config import get_settings
                        settings = get_settings()
                        safe_path = validate_download_path(save_path, settings.download_dir)
                        options["dir"] = safe_path

                    result = await self._call("addTorrent", [torrent_b64, [], options])
                    gid = result.get("result", "")
                    logger.info(f"Aria2 added torrent file => GID={gid}")
                    return gid

        except Exception as e:
            logger.error(f"Aria2 add_torrent failed: {e}")
            raise

    async def get_torrents(self, status: str | None = None) -> list[TorrentInfo]:
        """获取所有活跃下载任务状态

        注意：Aria2 的 tellActive/tellWaiting/tellStopped 是分开的，
        这里统一合并返回。已完成的任务也会在 stopped 中保留一段时间。
        """
        results: list[TorrentInfo] = []

        # 告诉 Aria2 返回哪些字段
        keys = [
            "gid", "totalLength", "completedLength", "downloadSpeed",
            "numSeeders", "dir", "bittorrent", "status", "errorCode",
            "infoHash", "files", "uploadSpeed",
        ]

        try:
            # 1. 正在下载的任务
            active_result = await self._call("tellActive", [keys])
            for t in active_result.get("result", []):
                info = self._parse_aria2_status(t)
                if status is None or info.status == status:
                    results.append(info)

            # 2. 等待中的任务（最多取 100 个）
            waiting_result = await self._call("tellWaiting", [0, 100, keys])
            for t in waiting_result.get("result", []):
                info = self._parse_aria2_status(t)
                info.status = "downloading"  # waiting → downloading
                if status is None or info.status == status:
                    results.append(info)

            # 3. 已停止/已完成/错误的任务（最近 100 个）
            stopped_result = await self._call("tellStopped", [0, 100, keys])
            for t in stopped_result.get("result", []):
                info = self._parse_aria2_status(t)
                if status is None or info.status == status:
                    results.append(info)

        except Exception as e:
            logger.error(f"Aria2 get_torrents failed: {e}")

        return results

    def _parse_aria2_status(self, t: dict) -> TorrentInfo:
        """将 Aria2 任务状态转换为统一的 TorrentInfo"""
        total = int(t.get("totalLength", 0))
        completed = int(t.get("completedLength", 0))
        speed = int(t.get("downloadSpeed", 0))
        aria2_status = t.get("status", "error")

        # 映射 Aria2 状态到通用状态
        status_map = {
            "active": "downloading",
            "waiting": "downloading",
            "paused": "paused",
            "error": "error",
            "complete": "completed",
            "removed": "completed",
            "seeding": "seeding",
        }
        status = status_map.get(aria2_status, aria2_status)

        # 进度计算
        progress = round((completed / total * 100), 1) if total > 0 else 0.0

        # ETA 计算
        eta = int((total - completed) / speed) if speed > 0 and total > completed else 0

        # 从 bittorrent info 中提取名称和 hash
        bittorrent = t.get("bittorrent") or {}
        bt_info = bittorrent.get("info", {})
        name = bt_info.get("name", "")
        info_hash = t.get("infoHash", "")

        # 如果没有 bittorrent 信息（如直链下载），从 files 中取文件名
        if not name:
            files = t.get("files", [])
            if files:
                # 取第一个文件的 path 的最后一段
                paths = files[0].get("uris", [])
                if paths:
                    name = paths[0].get("uri", "").split("/")[-1]
                else:
                    name = files[0].get("path", "").split("/")[-1]

        if not name:
            name = f"aria2-{t.get('gid', 'unknown')}"

        # 种子数
        seeders = int(t.get("numSeeders", 0))

        return TorrentInfo(
            hash=info_hash or t.get("gid", ""),  # 无 hash 时用 GID
            name=name,
            size=total,
            downloaded=completed,
            progress=progress,
            speed=speed,
            seeders=seeders,
            eta=eta,
            status=status,
            save_path=t.get("dir", ""),
        )

    async def pause(self, torrent_hash: str) -> bool:
        """暂停任务（支持 GID 或 InfoHash）"""
        try:
            # 尝试当 GID 处理（Aria2 主要用 GID）
            await self._call("pause", [torrent_hash])
            return True
        except Exception as e:
            # 可能需要通过 hash 找到 GID
            logger.warning(f"Aria2 pause by hash failed ({e}), trying forcePause")
            try:
                await self._call("forcePause", [torrent_hash])
                return True
            except Exception as e2:
                logger.error(f"Aria2 forcePause failed: {e2}")
                return False

    async def resume(self, torrent_hash: str) -> bool:
        """恢复任务"""
        try:
            await self._call("unpause", [torrent_hash])
            return True
        except Exception as e:
            logger.warning(f"Aria2 unpause failed ({e}), trying forceUnpause")
            try:
                await self._call("forceUnpause", [torrent_hash])
                return True
            except Exception as e2:
                logger.error(f"Aria2 forceUnpause failed: {e2}")
                return False

    async def delete(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除任务"""
        try:
            if delete_files:
                await self._call("removeDownloadResult", [torrent_hash])
                await self._call("forceRemove", [torrent_hash])
            else:
                await self._call("removeDownloadResult", [torrent_hash])
                await self._call("remove", [torrent_hash])
            return True
        except Exception as e:
            logger.error(f"Aria2 delete failed: {e}")
            return False

    async def get_client_version(self) -> str:
        try:
            result = await self._call("getVersion")
            ver = result.get("result", {})
            v = ver.get("version", ["unknown"])[0] if isinstance(ver.get("version"), list) else ver.get("version", "unknown")
            features = ", ".join(ver.get("enabledFeatures", []))
            return f"Aria2 v{v} [{features}]" if features else f"Aria2 v{v}"
        except Exception:
            return "Aria2 (unknown)"

    # ── Aria2 特有功能 ──

    async def get_global_stats(self) -> dict:
        """获取全局统计信息"""
        result = await self._call("getGlobalStat")
        return result.get("result", {})

    async def get_options(self, gid: str) -> dict:
        """获取任务选项"""
        result = await self._call("getOption", [gid])
        return result.get("result", {})

    async def change_option(self, gid: str, options: dict) -> bool:
        """修改运行中任务的选项"""
        await self._call("changeOption", [gid, options])
        return True

    async def list_methods(self) -> list[str]:
        """列出所有可用的 RPC 方法（调试用）"""
        result = await self._call("listMethods")
        methods = result.get("result", [])
        return [m for m in methods if isinstance(m, str)]


def create_client_adapter(client_type: str, host: str, port: int, username: str = "", password: str = "") -> DownloadClientAdapter:
    """工厂方法：根据类型创建下载客户端适配器"""
    if client_type == "qbittorrent":
        return QBittorrentAdapter(host, port, username, password)
    elif client_type == "transmission":
        return TransmissionAdapter(host, port, username, password)
    elif client_type == "aria2":
        return Aria2Adapter(host, port, username, password)
    else:
        raise ValueError(f"Unsupported client type: {client_type}")
