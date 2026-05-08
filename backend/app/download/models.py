"""
下载数据模型
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.base_models import Base, TimestampMixin


class DownloadClient(TimestampMixin, Base):
    """下载客户端配置"""
    __tablename__ = "download_clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    client_type: Mapped[str] = mapped_column(String(30), nullable=False)  # qbittorrent / transmission
    host: Mapped[str] = mapped_column(String(500), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=8080)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(50), default="MediaStation")


class DownloadTask(TimestampMixin, Base):
    """下载任务"""
    __tablename__ = "download_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("download_clients.id"), nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    torrent_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    torrent_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    info_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    save_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="downloading")
    progress: Mapped[float] = mapped_column(Float, default=0)       # 0-100
    total_size: Mapped[int] = mapped_column(Integer, default=0)     # bytes
    downloaded: Mapped[int] = mapped_column(Integer, default=0)     # bytes
    speed: Mapped[int] = mapped_column(Integer, default=0)          # bytes/s
    seeders: Mapped[int] = mapped_column(Integer, default=0)
    eta: Mapped[int] = mapped_column(Integer, default=0)           # seconds
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
