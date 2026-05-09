"""
MediaStation 配置中心
所有配置通过环境变量注入，启动时校验，缺失关键配置立即失败。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 应用 ──
    app_name: str = "MediaStation"
    app_port: int = 3001
    app_debug: bool = False
    app_secret_key: str = "AUTO_GENERATE"  # 将在 model_validator 中自动生成随机密钥
    data_dir: str = "./data"

    # ── 服务器地址（用于 external-url / DLNA 投屏等场景） ──
    server_url: str = ""

    # ── 数据库 ──
    database_url: str = ""  # 留空则使用 SQLite

    # ── TMDb ──
    tmdb_api_key: str = ""
    tmdb_language: str = "zh-CN"
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base: str = "https://image.tmdb.org/t/p"

    # ── 豆瓣 ──
    douban_cookie: str = ""

    # ── Bangumi ──
    bangumi_token: str = ""

    # ── qBittorrent ──
    qb_host: str = ""
    qb_username: str = "admin"
    qb_password: str = "adminadmin"

    # ── Transmission ──
    tr_host: str = ""
    tr_username: str = ""
    tr_password: str = ""

    # ── Telegram ──
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── 微信 (Server酱) ──
    wechat_sendkey: str = ""

    # ── Bark (iOS) ──
    bark_server: str = ""
    bark_key: str = ""

    # ── AI 刮削 (OpenAI 兼容 API) ──
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # ── FFmpeg ──
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    hw_accel: Literal["auto", "qsv", "vaapi", "nvenc", "videotoolbox", "none"] = "auto"
    max_transcode_jobs: int = 2
    transcode_enabled: bool = False  # 默认关闭转码，仅 Direct Play

    # ── 授权服务器（在线验证模式） ──
    license_server_url: str = ""                   # 留空 = 本地模式（向后兼容）
    license_server_secret: str = ""                 # HMAC 签名密钥（与服务端一致）
    license_heartbeat_interval_days: int = 7        # 心跳间隔天数
    license_grace_period_days: int = 14             # 离线宽限期天数

    # ── JWT ──
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    # ── 下载客户端 SSL 校验 ──
    verify_client_ssl: bool = True  # 改为 False 可允许自签证书（仅限内网）

    @field_validator("data_dir")
    @classmethod
    def ensure_data_dir(cls, v: str) -> str:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return str(p.resolve())

    @model_validator(mode='after')
    def validate_secret_key(self) -> 'Settings':
        """检测弱密钥或未配置，自动生成随机密钥并警告"""
        import secrets
        import logging
        logger = logging.getLogger(__name__)

        # 检测是否使用默认值或未配置
        if self.app_secret_key in ("AUTO_GENERATE", "change-me-to-a-random-string", ""):
            random_key = secrets.token_hex(32)
            logger.warning(
                f"⚠️  APP_SECRET_KEY not properly configured! "
                f"Auto-generated random key: {random_key[:16]}... "
                f"Users will be logged out on restart. "
                f"Please set a fixed APP_SECRET_KEY in .env file."
            )
            self.app_secret_key = random_key
        return self

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = Path(self.data_dir) / "mediastation.db"
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def sync_db_url(self) -> str:
        """同步数据库 URL，供 Alembic 使用"""
        if self.database_url:
            return self.database_url.replace("+asyncpg", "+psycopg2")
        db_path = Path(self.data_dir) / "mediastation.db"
        return f"sqlite:///{db_path}"

    @property
    def cache_dir(self) -> Path:
        p = Path(self.data_dir) / "cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def transcode_cache_dir(self) -> Path:
        p = Path(self.data_dir) / "transcode"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def media_dirs(self) -> list[Path]:
        """默认媒体目录"""
        base = Path(self.data_dir) / "media"
        return [base / "movies", base / "tv", base / "anime"]

    @property
    def download_dir(self) -> Path:
        p = Path(self.data_dir) / "downloads"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
