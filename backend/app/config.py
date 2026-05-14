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

    # ── 媒体库路径（整理目标目录）──
    # Docker 部署时通过环境变量挂载，非 Docker 部署可直接填写绝对路径
    # 留空则使用 {data_dir}/media/{movies|tv|anime}
    movies_dir: str = ""
    tv_dir: str = ""
    anime_dir: str = ""

    # ── 授权服务器（在线验证模式，已废弃） ──
    # 保留空壳以兼容旧 .env 配置，不再被代码读取。
    # 如需在线授权验证请通过独立服务实现。

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
        """同步数据库 URL，供 Alembic 使用（支持多种数据库）"""
        if self.database_url:
            url = self.database_url
            # 映射多种主流异步驱动到同步驱动 (Issue #24 修复)
            import re
            replacements = {
                r"\+asyncpg": "+psycopg2",
                r"\+aiomysql": "+pymysql",
                r"\+aiosqlite": "",
            }
            for pattern, repl in replacements.items():
                url = re.sub(pattern, repl, url)
            return url
        
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
        """默认媒体目录（用于兼容旧代码）"""
        base = Path(self.data_dir) / "media"
        return [base / "movies", base / "tv", base / "anime"]

    @property
    def movies_dir_path(self) -> Path:
        """电影库绝对路径（优先级：环境变量 > UI设置 > 数据库 > 默认）"""
        if self.movies_dir:
            p = Path(self.movies_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return Path(self.data_dir) / "media" / "movies"

    @property
    def tv_dir_path(self) -> Path:
        """剧集库绝对路径"""
        if self.tv_dir:
            p = Path(self.tv_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return Path(self.data_dir) / "media" / "tv"

    @property
    def anime_dir_path(self) -> Path:
        """动漫库绝对路径"""
        if self.anime_dir:
            p = Path(self.anime_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return Path(self.data_dir) / "media" / "anime"

    @property
    def download_dir(self) -> Path:
        p = Path(self.data_dir) / "downloads"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
