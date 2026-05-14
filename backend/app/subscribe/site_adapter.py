"""
站点适配器 — 支持多种站点类型和认证方式

站点类型:
  nexusphp   - NexusPHP（国内绝大多数PT站）
  gazelle    - Gazelle/Luminance（HDBits/OPS等）
  unit3d     - UNIT3D Laravel（BeyondHD/BluTopia等）
  mteam      - 馒头（M-Team，专用REST API接口）
  discuz     - Discuz论坛型资源站
  custom_rss - 自定义RSS

认证方式:
  cookie         - Cookie（大多数NexusPHP/Gazelle站）
  api_key        - API令牌/Passkey（馒头等）
  authorization  - 请求头 Authorization（Bearer Token）
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.subscribe.models import Site, SiteResource

logger = logging.getLogger(__name__)


class SiteAdapterBase(ABC):
    """站点适配器基类"""

    def __init__(self, site: Site):
        self.site = site
        self.base_url = site.base_url.rstrip("/")
        
        # ====== DEBUG: 记录 base_url ======
        import sys
        print(f"[DEBUG] SiteAdapterBase.__init__: site.id={site.id}, site.name={site.name!r}, base_url={self.base_url!r}", file=sys.stderr, flush=True)
        # ====== DEBUG END ======

    @property
    def headers(self) -> dict[str, str]:
        """根据认证方式构建请求头"""
        auth_type = getattr(self.site, "auth_type", "cookie")
        ua = getattr(self.site, "user_agent", None)
        if not ua:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        ua = ua.strip()
        h: dict[str, str] = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        if auth_type == "cookie":
            cookie = getattr(self.site, "cookie", "") or ""
            if cookie:
                h["Cookie"] = cookie
        elif auth_type == "api_key":
            api_key = getattr(self.site, "api_key", "") or ""
            if api_key:
                h["Authorization"] = f"Bearer {api_key}"
        elif auth_type == "authorization":
            auth_header = getattr(self.site, "auth_header", "") or ""
            if auth_header:
                h["Authorization"] = auth_header

        return h

    @property
    def timeout(self) -> int:
        t = getattr(self.site, "timeout", 15)
        return t if t > 0 else 30

    @abstractmethod
    async def search(self, keyword: str, category: str | None = None) -> list[SiteResource]:
        ...

    @abstractmethod
    async def get_download_url(self, resource: SiteResource) -> str:
        ...

    async def get_rss(self, rss_url: str) -> list[SiteResource]:
        """获取 RSS 资源"""
        resources = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    rss_url, headers=self.headers,
                    timeout=self.timeout, follow_redirects=True
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "xml")
                for item in soup.find_all("item"):
                    title = item.find("title")
                    link = item.find("link")
                    size_tag = item.find("size") or item.find("enclosure")

                    if title and link:
                        size = 0
                        if size_tag:
                            if size_tag.name == "enclosure":
                                size = int(size_tag.get("length", 0) or 0)
                            else:
                                try:
                                    size = int(size_tag.text.strip())
                                except ValueError:
                                    pass

                        resources.append(SiteResource(
                            site_name=self.site.name,
                            site_id=self.site.id,
                            title=title.text.strip(),
                            torrent_url=link.text.strip() if link.text else link.get("href", ""),
                            size=size,
                            download_url=link.text.strip() if link.text else link.get("href", ""),
                        ))
        except Exception as e:
            logger.error(f"RSS fetch failed for {rss_url}: {e}")
        return resources

    async def test_connection(self) -> tuple[bool, str]:
        """测试站点连接"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    self.base_url, headers=self.headers,
                    timeout=self.timeout, follow_redirects=True
                )
                if resp.status_code == 200:
                    return True, "连接成功"
                elif resp.status_code in (301, 302, 303, 307, 308):
                    return True, "重定向成功"
                elif resp.status_code == 403:
                    return False, "认证失败（HTTP 403），请检查 Cookie/API Key"
                elif resp.status_code == 401:
                    return False, "未授权（HTTP 401），请检查认证信息"
                else:
                    return False, f"HTTP {resp.status_code}"
        except httpx.ConnectError:
            return False, "连接失败（无法连接到站点）"
        except httpx.TimeoutException:
            return False, f"连接超时（>{self.timeout}s）"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _parse_size(size_str: str) -> int:
        """解析体积字符串如 '1.5 GB' → bytes"""
        size_str = size_str.strip().upper().replace(",", ".")
        multipliers = {
            "TIB": 1024 ** 4, "GIB": 1024 ** 3, "MIB": 1024 ** 2, "KIB": 1024,
            "TB": 1000 ** 4, "GB": 1000 ** 3, "MB": 1000 ** 2, "KB": 1000, "B": 1,
        }
        for unit, mult in multipliers.items():
            if unit in size_str:
                try:
                    num = float(size_str.replace(unit, "").strip())
                    return int(num * mult)
                except ValueError:
                    return 0
        return 0


# ─────────────────────────────────────────────
# NexusPHP 适配器（国内绝大多数PT站）
# ─────────────────────────────────────────────
class NexusPhpAdapter(SiteAdapterBase):
    """NexusPHP 站点适配器"""

    async def search(self, keyword: str, category: str | None = None) -> list[SiteResource]:
        resources = []
        try:
            params: dict[str, Any] = {
                "search": keyword,
                "inclbookmarked": 0,
                "incldead": 0,
                "spstate": 0,
            }
            if category:
                params["cat"] = category

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/torrents.php",
                    params=params, headers=self.headers,
                    timeout=self.timeout, follow_redirects=True,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                rows = soup.select("table.torrents tr")
                for row in rows:
                    try:
                        title_elem = (
                            row.select_one("a[href*='details.php']")
                            or row.select_one("td.title a")
                        )
                        if not title_elem:
                            continue

                        dl_elem = row.select_one("a[href*='download.php']")
                        dl_url = ""
                        if dl_elem:
                            href = dl_elem.get("href", "")
                            dl_url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('/')}"
                        else:
                            href = title_elem.get("href", "")
                            if "details.php" in href:
                                tid = re.search(r'id=(\d+)', href)
                                if tid:
                                    dl_url = f"{self.base_url}/download.php?id={tid.group(1)}"

                        size = 0
                        size_elem = row.select_one("td:nth-child(5)")
                        if size_elem:
                            size = self._parse_size(size_elem.text.strip())

                        seeders, leechers = 0, 0
                        seed_elem = row.select_one("td:nth-child(7)")
                        leech_elem = row.select_one("td:nth-child(8)")
                        if seed_elem:
                            try: seeders = int(re.sub(r'\D', '', seed_elem.text.strip()) or "0")
                            except: pass
                        if leech_elem:
                            try: leechers = int(re.sub(r'\D', '', leech_elem.text.strip()) or "0")
                            except: pass

                        free = bool(row.select_one("img.pro_free, img.pro_free2up, font.free, .free"))
                        title_text = title_elem.get_text(strip=True)
                        if not title_text:
                            continue

                        resources.append(SiteResource(
                            site_name=self.site.name,
                            site_id=self.site.id,
                            title=title_text,
                            torrent_url=f"{self.base_url}/{title_elem.get('href', '').lstrip('/')}",
                            size=size, seeders=seeders, leechers=leechers,
                            free=free, download_url=dl_url,
                        ))
                    except Exception as e:
                        logger.debug(f"Failed to parse row: {e}")
        except Exception as e:
            logger.error(f"NexusPHP search failed for {self.base_url}: {e}")
        return resources

    async def get_download_url(self, resource: SiteResource) -> tuple[str, str]:
        """解析站点的真实下载链接

        NexusPHP 站点的 download.php 需要有效的 Cookie。
        如果 Cookie 无效（返回登录页），尝试从详情页重新解析。
        如果所有方法都失败，返回原始 URL 让下载客户端尝试（客户端可能有独立 Cookie）。

        Returns:
            (download_url, error_message)
        """
        # 已有直链，直接返回
        if resource.download_url and resource.download_url.startswith("http"):
            # 验证 URL 是否为有效的下载端点
            if "download.php" in resource.download_url or "torrents.php" in resource.download_url:
                # 尝试验证 Cookie 有效性（通过 HEAD 请求快速检查）
                try:
                    async with httpx.AsyncClient() as client:
                        head_resp = await client.head(
                            resource.download_url,
                            headers=self.headers,
                            timeout=10,
                            follow_redirects=True,
                        )
                        # 如果重定向到登录页，说明 Cookie 无效
                        if head_resp.url and "login" in str(head_resp.url).lower():
                            logger.warning(
                                f"NexusPHP Cookie 无效（下载链接重定向到登录页）— "
                                f"请重新获取 Cookie"
                            )
                            return resource.download_url, (
                                "Cookie 已失效（下载链接被重定向到登录页），"
                                "请重新在站点设置中更新 Cookie"
                            )
                except Exception:
                    # 网络问题不影响下载，静默忽略
                    pass
            return resource.download_url, ""

        # 从 torrent_url 构造 download.php?id=xxx
        if "details.php" in resource.torrent_url:
            match = re.search(r'id=(\d+)', resource.torrent_url)
            if match:
                dl_url = f"{self.base_url}/download.php?id={match.group(1)}"
                return dl_url, ""

        return resource.torrent_url, ""


# ─────────────────────────────────────────────
# Gazelle 适配器（HDBits/OPS/Redacted等）
# ─────────────────────────────────────────────
class GazelleAdapter(SiteAdapterBase):
    """Gazelle/Luminance 站点适配器"""

    async def search(self, keyword: str, category: str | None = None) -> list[SiteResource]:
        """Gazelle 提供 JSON API"""
        resources = []
        try:
            # Gazelle 提供 /ajax.php?action=browse 接口
            api_headers = {**self.headers, "Accept": "application/json"}
            auth_type = getattr(self.site, "auth_type", "cookie")
            if auth_type == "api_key":
                api_key = getattr(self.site, "api_key", "") or ""
                api_headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/ajax.php",
                    params={"action": "browse", "searchstr": keyword},
                    headers=api_headers,
                    timeout=self.timeout, follow_redirects=True,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") != "success":
                    return []

                for group in data.get("response", {}).get("results", []):
                    for torrent in group.get("torrents", []):
                        tid = torrent.get("torrentId") or torrent.get("id")
                        title = (
                            f"{group.get('artist', '')} - {group.get('groupName', '')} "
                            f"[{torrent.get('format', '')} / {torrent.get('encoding', '')}]"
                        ).strip(" -")
                        resources.append(SiteResource(
                            site_name=self.site.name,
                            site_id=self.site.id,
                            title=title or group.get("groupName", ""),
                            size=torrent.get("size", 0),
                            seeders=torrent.get("seeders", 0),
                            leechers=torrent.get("leechers", 0),
                            free=torrent.get("isFreeleech", False),
                            download_url=f"{self.base_url}/torrents.php?action=download&id={tid}",
                            torrent_url=f"{self.base_url}/torrents.php?id={group.get('groupId')}&torrentid={tid}",
                        ))
        except Exception as e:
            logger.error(f"Gazelle search failed for {self.base_url}: {e}")
        return resources

    async def get_download_url(self, resource: SiteResource) -> tuple[str, str]:
        return resource.download_url or resource.torrent_url, ""


# ─────────────────────────────────────────────
# UNIT3D 适配器（BeyondHD/BluTopia/JPTV等）
# ─────────────────────────────────────────────
class Unit3dAdapter(SiteAdapterBase):
    """UNIT3D Laravel 站点适配器（支持 API Token 认证）"""

    async def search(self, keyword: str, category: str | None = None) -> list[SiteResource]:
        resources = []
        try:
            auth_type = getattr(self.site, "auth_type", "cookie")
            api_key = getattr(self.site, "api_key", "") or ""

            # UNIT3D REST API
            api_url = f"{self.base_url}/api/torrents/filter"
            params: dict[str, Any] = {"name": keyword, "perPage": 50}
            if api_key and auth_type == "api_key":
                params["api_token"] = api_key

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    api_url, params=params, headers=self.headers,
                    timeout=self.timeout, follow_redirects=True,
                )
                resp.raise_for_status()
                data = resp.json()

                for torrent in data.get("data", []):
                    attrs = torrent.get("attributes", torrent)
                    tid = torrent.get("id") or attrs.get("id")
                    resources.append(SiteResource(
                        site_name=self.site.name,
                        site_id=self.site.id,
                        title=attrs.get("name", ""),
                        size=attrs.get("size", 0),
                        seeders=attrs.get("seeders", 0),
                        leechers=attrs.get("leechers", 0),
                        free=attrs.get("freeleech", 0) > 0 if isinstance(attrs.get("freeleech"), (int, float)) else bool(attrs.get("freeleech")),
                        download_url=attrs.get("download_link") or f"{self.base_url}/torrents/{tid}/download",
                        torrent_url=f"{self.base_url}/torrents/{tid}",
                    ))
        except Exception as e:
            logger.error(f"UNIT3D search failed for {self.base_url}: {e}")
        return resources

    async def get_download_url(self, resource: SiteResource) -> tuple[str, str]:
        return resource.download_url or resource.torrent_url, ""


# ─────────────────────────────────────────────
# 馒头 M-Team 适配器（官方 REST API v3）
# ─────────────────────────────────────────────
class MTeamAdapter(SiteAdapterBase):
    """馒头 M-Team 专用适配器

    基于官方 M-Team v3 API：

    ✅ API 基础地址: 使用用户配置的 base_url（支持测试/正式环境）
        - 测试环境: {self.base_url}/api
        - 正式环境: https://api.m-team.cc/api

    认证方式: x-api-key 请求头
    API Key 永久有效（除非用户在【控制台→实验室→存取令牌】中主动删除）

    搜索接口:
        POST /torrent/search
        Body: {"pageNumber": 1, "pageSize": 50, "keyword": "..."}
        响应: {"code": "0", "message": "SUCCESS", "data": {"data": [...]}}

    ⚠️ 注意参数格式使用 camelCase (pageNumber, pageSize) 不是 snake_case

    下载流程:
        POST /torrent/genDlToken?id={id}
        → 响应 {"code": "0", "data": "https://api.m-team.cc/api/rss/dlv2?sign=..."}
        → 用该 URL 下载 .torrent 文件
    """

    @property
    def api_base(self) -> str:
        """API 基础地址，使用用户配置的 base_url"""
        return f"{self.base_url}/api"

    @property
    def headers(self) -> dict[str, str]:
        api_key = getattr(self.site, "api_key", "") or ""
        ua = getattr(self.site, "user_agent", None)
        if not ua:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        ua = ua.strip()
        h: dict[str, str] = {
            "User-Agent": ua,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if api_key:
            h["x-api-key"] = api_key
        return h

    def _parse_response(self, data: dict) -> tuple[bool, str]:
        """解析 M-Team API 响应

        返回: (success: bool, message: str)

        M-Team API 响应格式: {"code": "0", "message": "SUCCESS", "data": ...}
        code="0" 表示成功，其他值表示失败。

        ⚠️ 注意：API 可能返回字符串类型的 code（如 "0", "1", "401"），
           需要统一转换为字符串比较。
        """
        code_raw = data.get("code")
        message = data.get("message", "")

        # code 为字符串 "0" 表示成功
        code_str = str(code_raw) if code_raw is not None else ""

        if code_str == "0":
            return True, message or "SUCCESS"

        # 认证失败
        if code_str == "401":
            return False, "未授权（401），请检查 API Key 是否正确"

        # 其他错误
        return False, f"API 错误: {message} (code={code_raw})"

    async def search(self, keyword: str, category: str | None = None) -> list[SiteResource]:
        """馒头 API 搜索

        请求: POST /torrent/search
        Body: {"pageNumber": 1, "pageSize": 50, "keyword": "..."}
        响应: {"code": 0, "message": "SUCCESS", "data": {"data": [...]}}

        ⚠️ 必须使用 camelCase 参数名 (pageNumber, pageSize)
        """
        resources = []
        try:
            # ⚠️ 必须使用 camelCase 参数名 (pageNumber, pageSize)
            payload: dict[str, Any] = {
                "pageNumber": 1,
                "pageSize": 50,
                "keyword": keyword,
            }
            if category:
                payload["categories"] = [category]

            api_key = getattr(self.site, "api_key", "") or ""
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            if api_key:
                headers["x-api-key"] = api_key

            async with httpx.AsyncClient(follow_redirects=False, verify=False) as client:
                # Debug: 打印请求信息
                import sys
                print(f"[MTeamAdapter.search] 开始搜索", file=sys.stderr, flush=True)
                print(f"  site.id={self.site.id}, site.name={self.site.name!r}", file=sys.stderr, flush=True)
                print(f"  api_base={self.api_base!r}", file=sys.stderr, flush=True)
                print(f"  payload={json.dumps(payload, ensure_ascii=False)[:200]}", file=sys.stderr, flush=True)
                print(f"  headers.x-api-key={'已设置' if 'x-api-key' in headers else '未设置'}", file=sys.stderr, flush=True)
                
                resp = await client.post(
                    f"{self.api_base}/torrent/search",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                
                # Debug: 打印响应信息
                print(f"[MTeamAdapter.search] API 响应", file=sys.stderr, flush=True)
                print(f"  HTTP status: {resp.status_code}", file=sys.stderr, flush=True)
                print(f"  Response body: {resp.text[:300]}", file=sys.stderr, flush=True)

                # 如果返回重定向（301/302），说明 API Key 无效或未登录
                if resp.status_code in (301, 302, 303, 307, 308):
                    logger.warning(f"M-Team search 认证失败: HTTP {resp.status_code} 重定向")
                    logger.warning(f"M-Team search 请检查 API Key 是否正确，或是否已登录 {self.base_url}")
                    return []

                resp.raise_for_status()
                data = resp.json()

                # 解析响应: code=0 表示成功，code=1 或其他表示失败
                # ⚠️ 注意：M-Team v3 API 中 code=1 不是成功，是失败（如 key 無效）
                code_raw = data.get("code")
                code_str = str(code_raw) if code_raw is not None else ""

                if code_str == "0":
                    pass  # 成功，继续处理
                elif code_str == "1":
                    # code=1 是明确的失败响应
                    msg = data.get("message", "未知错误")
                    # 特殊处理 key 无效
                    if "key" in msg.lower() or "無效" in msg or "invalid" in msg.lower():
                        logger.error(
                            f"⚠️ M-Team API Key 无效！响应: {msg}。"
                            f"请前往【{self.base_url} 控制台→实验室→存取令牌】重新生成 API Key"
                        )
                    else:
                        logger.warning(f"M-Team search 返回错误: {msg}")
                    return []
                elif code_str == "401":
                    logger.error(
                        f"⚠️ M-Team API Key 认证失败（401）！"
                        f"请前往【{self.base_url} 控制台→实验室→存取令牌】重新生成 API Key"
                    )
                    return []
                else:
                    msg = data.get("message", f"未知错误 (code={code_raw})")
                    logger.warning(f"M-Team search 失败: {msg}")
                    return []

                # 提取种子列表: data.data.data = list[dict]
                result_data = data.get("data") or {}
                items = result_data.get("data") if isinstance(result_data, dict) else []
                if not isinstance(items, list):
                    items = []

                logger.info(f"M-Team search '{keyword}' 返回 {len(items)} 个结果")
                # Debug: print first 3 items
                for i, item in enumerate(items[:3]):
                    logger.info(f"  Item {i}: title={item.get('name', '')[:60]}, id={item.get('id')}")

                for item in items:
                    tid_str = str(item.get("id") or "")
                    if not tid_str:
                        continue

                    title = item.get("name") or item.get("title") or ""
                    if not title:
                        continue

                    # 解析做种/吸血信息
                    status_info = item.get("status") or {}
                    seeders = 0
                    leechers = 0
                    if isinstance(status_info, dict):
                        try:
                            seeders = int(status_info.get("seeders") or 0)
                            leechers = int(status_info.get("leechers") or 0)
                        except (ValueError, TypeError):
                            pass

                    # 解析文件大小
                    size_str = str(item.get("size") or "0")
                    try:
                        size = int(size_str)
                    except ValueError:
                        size = 0

                    # 解析是否免费
                    free = False
                    if isinstance(status_info, dict):
                        discount = status_info.get("discount") or ""
                        if discount and discount != "FREE" and discount != "normal":
                            free = True
                        # toppingLevel > 0 也表示免费
                        topping = status_info.get("toppingLevel") or "0"
                        if str(topping) != "0":
                            free = True
                    # 也检查顶层字段
                    if item.get("discount") or item.get("isFreeleech"):
                        free = True

                    resources.append(SiteResource(
                        site_name=self.site.name,
                        site_id=self.site.id,
                        title=title,
                        size=size,
                        seeders=seeders,
                        leechers=leechers,
                        free=free,
                        download_url=f"{self.api_base}/torrent/genDlToken?id={tid_str}",
                        torrent_url=f"{self.base_url}/detail/{tid_str}",
                    ))
        except httpx.HTTPStatusError as e:
            logger.error(f"M-Team search HTTP error {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"M-Team search failed: {e}")
        return resources

    @staticmethod
    def _is_valid_torrent(content: bytes) -> bool:
        """验证内容是否为有效的 torrent 文件（Bencode dict 以 d 开头）"""
        return len(content) > 50 and content[:1] == b"d"

    async def _download_torrent_file(self, tid: int) -> tuple[bytes | None, str]:
        """从 M-Team 下载种子文件

        流程:
        1. POST /torrent/genDlToken?id={tid}  → 获取下载 URL
        2. 用下载 URL 请求获取 .torrent 二进制内容

        ⚠️ genDlToken 端点要求：
        - 不能有 Content-Type 请求头
        - 只需要 User-Agent 和 x-api-key
        - 不能有 Referer/Origin（会导致 CORS 错误）

        Returns:
            (torrent_content, error_message)
        """
        try:
            api_key = getattr(self.site, "api_key", "") or ""
            if not api_key:
                return None, "API Key 为空，请检查站点配置"

            # ⚠️ genDlToken 端点不接受 Content-Type/Referer/Origin，
            # 只接受 User-Agent 和 x-api-key
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "x-api-key": api_key,
            }

            logger.info(f"[M-Team] 准备调用 genDlToken, tid={tid}")

            async with httpx.AsyncClient(follow_redirects=False, verify=False, timeout=self.timeout) as client:
                # 步骤1: 获取下载 URL
                resp = await client.post(
                    f"{self.api_base}/torrent/genDlToken",
                    params={"id": tid},
                    headers=headers,
                )

                logger.info(f"[M-Team] genDlToken 响应: HTTP {resp.status_code}, body: {resp.text[:200]}")

                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location", "unknown")
                    logger.warning(f"[M-Team] genDlToken 被重定向到: {location}")
                    return None, f"HTTP {resp.status_code} 重定向到 {location}（认证可能失败）"

                resp.raise_for_status()
                data = resp.json()

                code_raw = data.get("code")
                code_str = str(code_raw) if code_raw is not None else ""
                msg = data.get("message", "")

                # 检查是否有有效的下载 URL（即使 code 不为 "0"）
                dl_url = data.get("data", "")
                if not dl_url or not isinstance(dl_url, str):
                    error_hint = f"请检查: 1) API Key 是否正确 2) 是否已登录 {self.base_url}"
                    return None, f"genDlToken 失败 (code={code_raw}, message={msg})。{error_hint}"

                logger.info(f"[M-Team] genDlToken 获取下载 URL: {dl_url[:80]}...")

                # 步骤2: 下载 .torrent 文件
                dl_resp = await client.get(
                    dl_url,
                    headers=headers,
                    follow_redirects=True,
                    timeout=self.timeout,
                )
                dl_resp.raise_for_status()

                content = dl_resp.content
                if self._is_valid_torrent(content):
                    logger.info(f"[M-Team] 种子下载成功 (大小: {len(content)} bytes)")
                    return content, ""

                return None, f"下载内容无效 (大小: {len(content)}, 头部: {content[:10]})"

        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}: {str(e.response.text)[:100]}"
        except Exception as e:
            logger.error(f"[M-Team] 种子下载异常: {e}")
            return None, str(e)

    async def get_download_url(self, resource: SiteResource) -> tuple[str, str]:
        """解析站点的真实下载链接

        M-Team 使用两步下载流程：
        1. genDlToken → 获取下载 URL
        2. 下载 URL → 获取 .torrent 二进制

        Returns:
            (download_url, error_message)
            download_url 可能为 "TORRENT:" + base64(种子内容)，或普通 URL。
        """
        url_str = resource.download_url or ""
        if "/genDlToken" in url_str:
            # 解析 torrent ID
            tid = None
            if "id=" in url_str:
                try:
                    tid = int(url_str.split("id=")[-1].split("&")[0])
                except (ValueError, IndexError):
                    tid = None

            if tid is None:
                return "", "无法解析种子 ID"

            # 下载种子文件
            torrent_content, error = await self._download_torrent_file(tid)
            if torrent_content:
                import base64
                b64_content = base64.b64encode(torrent_content).decode("ascii")
                return f"TORRENT:{b64_content}", ""

            return "", f"无法获取种子文件: {error}"

        # 原始 URL 直接返回
        return url_str, ""

    async def test_connection(self) -> tuple[bool, str]:
        """测试馒头站点连接

        通过调用搜索接口验证 API Key 是否有效。
        使用用户配置的 base_url 的 v3 API。
        即使搜索返回 0 结果（test 关键词无匹配），只要不重定向就表示认证通过。
        """
        # ====== RUNTIME DEBUG ======
        import sys
        _ru_site_id = getattr(self.site, 'id', '?')
        _ru_base_url = getattr(self.site, 'base_url', '?')
        print(f"[RUNTIME DEBUG] MTeamAdapter.test_connection: site.id={_ru_site_id}, site.base_url={_ru_base_url!r}", file=sys.stderr, flush=True)
        print(f"[RUNTIME DEBUG] self.base_url={self.base_url!r}, self.api_base={self.api_base!r}", file=sys.stderr, flush=True)
        # ====== RUNTIME DEBUG END ======
        try:
            api_key = getattr(self.site, "api_key", "") or ""
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if api_key:
                headers["x-api-key"] = api_key

            async with httpx.AsyncClient(follow_redirects=False) as client:
                resp = await client.post(
                    f"{self.api_base}/torrent/search",
                    json={"pageNumber": 1, "pageSize": 1, "keyword": "test"},
                    headers=headers,
                    timeout=self.timeout,
                )

                # 如果返回重定向（301/302），说明 API Key 无效或未登录
                if resp.status_code in (301, 302, 303, 307, 308):
                    logger.warning(f"M-Team test_connection 认证失败: HTTP {resp.status_code}")
                    return False, f"API Key 无效或未登录 {self.base_url}，请检查【控制台→实验室→存取令牌】"

                resp.raise_for_status()
                data = resp.json()

                code_raw = data.get("code")
                code_str = str(code_raw) if code_raw is not None else ""

                if code_str == "0":
                    total = (data.get("data") or {}).get("total", "0")
                    logger.info(f"M-Team test_connection 成功，总资源数: {total}")
                    return True, "连接成功"
                elif code_str == "1":
                    msg = data.get("message", "未知错误")
                    if "key" in msg.lower() or "無效" in msg or "invalid" in msg.lower():
                        hint = f"请前往【{self.base_url} 控制台→实验室→存取令牌】重新生成 API Key"
                        logger.error(f"M-Team test_connection 失败: {msg}。{hint}")
                        return False, f"API Key 无效（{msg}）。{hint}"
                    logger.warning(f"M-Team test_connection 失败: {msg}")
                    return False, msg
                elif code_str == "401":
                    hint = f"请前往【{self.base_url} 控制台→实验室→存取令牌】重新生成 API Key"
                    logger.error(f"M-Team test_connection 认证失败（401）。{hint}")
                    return False, f"API Key 认证失败（401）。{hint}"
                else:
                    msg = data.get("message", f"未知错误 (code={code_raw})")
                    logger.warning(f"M-Team test_connection 失败: {msg}")
                    return False, msg

        except httpx.HTTPStatusError as e:
            return False, f"HTTP {e.response.status_code}: {str(e.response.text)[:100]}"
        except httpx.ConnectError:
            return False, f"连接失败（无法连接到 {self.api_base}），请检查网络"
        except httpx.TimeoutException:
            return False, f"连接超时（>{self.timeout}s）"
        except Exception as e:
            return False, f"连接错误: {str(e)[:100]}"


# ─────────────────────────────────────────────
# 自定义 RSS 适配器
# ─────────────────────────────────────────────
class CustomRssAdapter(SiteAdapterBase):
    """自定义 RSS 站点适配器"""

    async def search(self, keyword: str, category: str | None = None) -> list[SiteResource]:
        if self.site.rss_url:
            all_resources = await self.get_rss(self.site.rss_url)
            if keyword:
                all_resources = [r for r in all_resources if keyword.lower() in r.title.lower()]
            return all_resources
        return []

    async def get_download_url(self, resource: SiteResource) -> tuple[str, str]:
        return resource.download_url or resource.torrent_url, ""


# ─────────────────────────────────────────────
# 工厂方法
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 站点资源浏览增强
# ─────────────────────────────────────────────
class SiteResourceBrowser:
    """站点资源浏览器（MoviePilot API 参考实现）

    支持按分类浏览站点资源，兼容多种站点类型。
    """

    def __init__(self, site: Site):
        self.site = site
        self.base_url = site.base_url.rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        ua = getattr(self.site, "user_agent", None)
        if not ua:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        ua = ua.strip()
        h: dict[str, str] = {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        auth_type = getattr(self.site, "auth_type", "cookie")
        if auth_type == "cookie":
            cookie = getattr(self.site, "cookie", "") or ""
            if cookie:
                h["Cookie"] = cookie
        elif auth_type == "api_key":
            api_key = getattr(self.site, "api_key", "") or ""
            if api_key:
                h["Authorization"] = f"Bearer {api_key}"
        return h

    async def browse(
        self,
        keyword: str | None = None,
        category: str | None = None,
        page: int = 0,
    ) -> tuple[list[SiteResource], int]:
        """浏览站点资源（支持分页）

        Returns:
            (resources, total_count) - 资源列表和总数
        """
        site_type = getattr(self.site, "site_type", "nexusphp")

        if site_type == "nexusphp":
            return await self._browse_nexusphp(keyword, category, page)
        elif site_type == "mteam":
            return await self._browse_mteam(keyword, category, page)
        elif site_type == "unit3d":
            return await self._browse_unit3d(keyword, category, page)
        else:
            # 通用搜索模式
            if keyword:
                adapter = create_site_adapter(self.site)
                resources = await adapter.search(keyword, category)
                return resources, len(resources)
            return [], 0

    async def _browse_nexusphp(
        self, keyword: str | None, category: str | None, page: int
    ) -> tuple[list[SiteResource], int]:
        """NexusPHP 站点浏览"""
        resources = []
        total = 0
        try:
            params: dict[str, Any] = {
                "search": keyword or "",
                "inclbookmarked": 0,
                "incldead": 0,
                "spstate": 0,
                "page": page,
            }
            if category:
                params["cat"] = category

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/torrents.php",
                    params=params, headers=self.headers,
                    timeout=30, follow_redirects=True,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                # 计算总数（从分页信息中提取）
                total = 0
                pagination = soup.select_one("span.medium")
                if pagination:
                    match = re.search(r"(\d+)\s*-\s*(\d+)\s*/\s*(\d+)", pagination.text)
                    if match:
                        total = int(match.group(3))

                # 解析列表
                rows = soup.select("table.torrents tr")
                for row in rows:
                    try:
                        title_elem = row.select_one("a[href*='details.php']")
                        if not title_elem:
                            continue

                        dl_elem = row.select_one("a[href*='download.php']")
                        dl_url = ""
                        if dl_elem:
                            href = dl_elem.get("href", "")
                            dl_url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('/')}"

                        size = 0
                        size_elem = row.select_one("td:nth-child(5)")
                        if size_elem:
                            size = SiteAdapterBase._parse_size(size_elem.text.strip())

                        seeders, leechers = 0, 0
                        seed_elem = row.select_one("td:nth-child(7)")
                        leech_elem = row.select_one("td:nth-child(8)")
                        if seed_elem:
                            try: seeders = int(re.sub(r'\D', '', seed_elem.text.strip()) or "0")
                            except: pass
                        if leech_elem:
                            try: leechers = int(re.sub(r'\D', '', leech_elem.text.strip()) or "0")
                            except: pass

                        free = bool(row.select_one("img.pro_free, img.pro_free2up, .free"))
                        title_text = title_elem.get_text(strip=True)

                        resources.append(SiteResource(
                            site_name=self.site.name,
                            site_id=self.site.id,
                            title=title_text,
                            torrent_url=f"{self.base_url}/{title_elem.get('href', '').lstrip('/')}",
                            size=size, seeders=seeders, leechers=leechers,
                            free=free, download_url=dl_url,
                        ))
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"NexusPHP browse failed for {self.base_url}: {e}")

        return resources, total

    async def _browse_mteam(
        self, keyword: str | None, category: str | None, page: int
    ) -> tuple[list[SiteResource], int]:
        """M-Team 站点浏览（使用 v3 API）

        API 端点: POST /torrent/search
        参数格式: camelCase (pageNumber, pageSize, keyword)
        """
        # M-Team v3 API 基础地址（使用站点配置的 base_url）
        api_base = f"{self.base_url}/api"
        resources = []
        try:
            payload: dict[str, Any] = {
                "keyword": keyword or "",
                "pageNumber": page + 1,
                "pageSize": 30,
            }
            if category:
                payload["categories"] = [category]

            api_key = getattr(self.site, "api_key", "") or ""
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if api_key:
                headers["x-api-key"] = api_key

            async with httpx.AsyncClient(follow_redirects=False) as client:
                resp = await client.post(
                    f"{api_base}/torrent/search",
                    json=payload, headers=headers, timeout=30,
                )
                if resp.status_code in (301, 302):
                    logger.warning(f"M-Team browse 认证失败: HTTP {resp.status_code}")
                    return [], 0
                resp.raise_for_status()
                data = resp.json()

                # ⚠️ code=1 在 M-Team v3 API 中表示失败，不是成功
                code_raw = data.get("code")
                code_str = str(code_raw) if code_raw is not None else ""
                if code_str not in ("0", "200"):
                    msg = data.get("message", f"code={code_raw}")
                    if code_str == "1" and ("key" in msg.lower() or "無效" in msg):
                        logger.error(
                            f"⚠️ M-Team browse API Key 无效: {msg}。"
                            f"请前往【{self.base_url} 控制台→实验室→存取令牌】重新生成 API Key"
                        )
                    else:
                        logger.warning(f"M-Team browse 失败: {msg}")
                    return [], 0

                raw_data = data.get("data") or data
                items = raw_data.get("data") if isinstance(raw_data, dict) else []
                total = raw_data.get("total", len(items)) if isinstance(raw_data, dict) else len(items)

                for item in items:
                    tid = item.get("id")
                    name = item.get("name") or item.get("smallDescr", "")

                    status_info = item.get("status", {})
                    seeders = leechers = 0
                    if isinstance(status_info, dict):
                        seeders = int(status_info.get("seeders", 0) or 0)
                        leechers = int(status_info.get("leechers", 0) or 0)

                    free = bool(item.get("discount") or item.get("isFreeleech"))

                    resources.append(SiteResource(
                        site_name=self.site.name,
                        site_id=self.site.id,
                        title=name,
                        size=int(item.get("size", 0) or 0),
                        seeders=seeders,
                        leechers=leechers,
                        free=free,
                        download_url=f"{api_base}/torrent/genDlToken?id={tid}",
                        torrent_url=f"{self.base_url}/detail/{tid}",
                    ))

                return resources, total

        except Exception as e:
            logger.error(f"M-Team browse failed for {self.base_url}: {e}")

        return resources, 0

    async def _browse_unit3d(
        self, keyword: str | None, category: str | None, page: int
    ) -> tuple[list[SiteResource], int]:
        """UNIT3D 站点浏览"""
        resources = []
        try:
            api_key = getattr(self.site, "api_key", "") or ""
            params: dict[str, Any] = {
                "page": page + 1,
                "perPage": 30,
            }
            if keyword:
                params["name"] = keyword
            if category:
                params["category_id"] = category
            if api_key:
                params["api_token"] = api_key

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/api/torrents/filter",
                    params=params, headers=self.headers, timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                total = data.get("total", len(data.get("data", [])))

                for torrent in data.get("data", []):
                    attrs = torrent.get("attributes", torrent)
                    tid = torrent.get("id")
                    resources.append(SiteResource(
                        site_name=self.site.name,
                        site_id=self.site.id,
                        title=attrs.get("name", ""),
                        size=attrs.get("size", 0),
                        seeders=attrs.get("seeders", 0),
                        leechers=attrs.get("leechers", 0),
                        free=attrs.get("freeleech", 0) > 0,
                        download_url=attrs.get("download_link") or f"{self.base_url}/torrents/{tid}/download",
                        torrent_url=f"{self.base_url}/torrents/{tid}",
                    ))

                return resources, total

        except Exception as e:
            logger.error(f"UNIT3D browse failed for {self.base_url}: {e}")

        return resources, 0


def create_site_adapter(site: Site) -> SiteAdapterBase:
    """根据站点类型创建对应适配器"""
    site_type = getattr(site, "site_type", "nexusphp")
    
    _adapters = {
        "nexusphp": NexusPhpAdapter,
        "nexus_php": NexusPhpAdapter,   # 兼容旧数据
        "gazelle": GazelleAdapter,
        "unit3d": Unit3dAdapter,
        "mteam": MTeamAdapter,
        "discuz": NexusPhpAdapter,      # Discuz 类站暂用 NexusPHP 解析
        "custom_rss": CustomRssAdapter,
    }
    
    adapter_cls = _adapters.get(site_type, NexusPhpAdapter)
    
    # ====== DEBUG: 记录适配器创建 ======
    import sys
    print(f"[DEBUG] create_site_adapter: site.id={site.id}, site.name={site.name!r}, site_type={site_type!r}, adapter={adapter_cls.__name__}", file=sys.stderr, flush=True)
    # ====== DEBUG END ======
    
    return adapter_cls(site)
