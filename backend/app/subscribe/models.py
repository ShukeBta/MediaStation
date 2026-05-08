"""
订阅数据模型
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.base_models import Base, TimestampMixin


class Site(TimestampMixin, Base):
    """站点配置
    
    支持站点类型:
      nexusphp   - NexusPHP（国内绝大多数PT站，如馒头早期/观众/家园等）
      gazelle    - Gazelle/Luminance（HDBits/OPS等）
      unit3d     - UNIT3D（BeyondHD/BluTopia等）
      discuz     - Discuz（部分论坛型资源站）
      mteam      - 馒头（M-Team，专用API接口）
      custom_rss - 自定义RSS

    认证方式:
      cookie         - Cookie（大多数NexusPHP/Gazelle站）
      api_key        - API令牌（馒头等）
      authorization  - 请求头 Authorization（Bearer Token）
    """
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    site_type: Mapped[str] = mapped_column(
        String(30), default="nexusphp"
    )  # nexusphp / gazelle / unit3d / discuz / mteam / custom_rss
    
    # ── 认证信息 ──
    auth_type: Mapped[str] = mapped_column(
        String(20), default="cookie"
    )  # cookie / api_key / authorization
    cookie: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)   # API令牌 / Passkey
    auth_header: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Authorization 头内容
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)   # 自定义 User-Agent
    
    # ── 订阅/RSS ──
    rss_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    
    # ── 高级设置 ──
    timeout: Mapped[int] = mapped_column(Integer, default=15)        # 请求超时(秒)，0=不限制
    priority: Mapped[int] = mapped_column(Integer, default=50)       # 越小越优先
    use_proxy: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否使用代理
    rate_limit: Mapped[bool] = mapped_column(Boolean, default=False) # 是否限制访问频率
    browser_emulation: Mapped[bool] = mapped_column(Boolean, default=False)  # 浏览器仿真（防爬）
    
    # ── 状态 ──
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    login_status: Mapped[str] = mapped_column(String(20), default="unknown")  # unknown/ok/fail
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # ── 流量统计 ──
    upload_bytes: Mapped[int] = mapped_column(Integer, default=0)    # 上传字节数
    download_bytes: Mapped[int] = mapped_column(Integer, default=0)  # 下载字节数
    
    # ── 关联下载器 ──
    downloader: Mapped[str | None] = mapped_column(String(50), nullable=True)  # qbittorrent/transmission/aria2


class SiteResource:
    """站点搜索结果（不持久化）"""
    def __init__(
        self,
        site_name: str = "",
        site_id: int = 0,
        title: str = "",
        torrent_url: str = "",
        size: int = 0,
        seeders: int = 0,
        leechers: int = 0,
        upload_time: str = "",
        category: str = "",
        free: bool = False,
        download_url: str = "",
    ):
        self.site_name = site_name
        self.site_id = site_id
        self.title = title
        self.torrent_url = torrent_url
        self.size = size
        self.seeders = seeders
        self.leechers = leechers
        self.upload_time = upload_time
        self.category = category
        self.free = free
        self.download_url = download_url


class Subscription(TimestampMixin, Base):
    """订阅"""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(500), nullable=True)  # TMDB 英文原名（用于站点搜索）
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)  # movie / tv / anime
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_filter: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: 优先画质列表
    min_size: Mapped[int] = mapped_column(Integer, default=0)     # MB
    max_size: Mapped[int] = mapped_column(Integer, default=0)     # MB (0=不限)
    exclude_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: 排除关键词
    include_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: 包含关键词
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / paused / completed
    last_search: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_downloaded: Mapped[int] = mapped_column(Integer, default=0)


class SubscriptionLog(TimestampMixin, Base):
    """订阅日志"""
    __tablename__ = "subscription_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20))  # search / download / skip / error
    resource_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotifyChannel(TimestampMixin, Base):
    """通知渠道"""
    __tablename__ = "notify_channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)  # telegram / wechat / bark / webhook / email
    config: Mapped[str] = mapped_column(Text, nullable=False)               # JSON 配置
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    events: Mapped[str] = mapped_column(Text, default="[]")                # JSON: 订阅的事件类型
