"""
媒体库数据模型
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_models import Base, TimestampMixin


class MediaLibrary(TimestampMixin, Base):
    __tablename__ = "media_libraries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(20), default="movie")  # movie / tv / anime
    scan_interval: Mapped[int] = mapped_column(Integer, default=60)       # 分钟
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 高级设置
    min_file_size: Mapped[int] = mapped_column(Integer, default=0)            # 最小文件大小（字节），0表示不限
    metadata_language: Mapped[str] = mapped_column(String(10), default="zh-CN")  # 元数据语言
    adult_content: Mapped[bool] = mapped_column(Boolean, default=False)        # 允许成人内容
    prefer_nfo: Mapped[bool] = mapped_column(Boolean, default=True)          # 优先使用NFO元数据
    enable_watch: Mapped[bool] = mapped_column(Boolean, default=True)        # 启用实时监控

    # 关系
    items: Mapped[list[MediaItem]] = relationship(back_populates="library", lazy="selectin")


class MediaItem(TimestampMixin, Base):
    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("media_libraries.id"), nullable=False, index=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    douban_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bangumi_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rating: Mapped[float] = mapped_column(Float, default=0)
    douban_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    bangumi_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON array string
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=0)           # 秒
    video_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    container: Mapped[str | None] = mapped_column(String(10), nullable=True)
    date_added: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_scanned: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scraped: Mapped[bool] = mapped_column(Boolean, default=False)

    # STRM 文件支持（虚拟文件，实际播放远程 URL）
    strm_url: Mapped[str | None] = mapped_column(String(2000), nullable=True, index=True)

    # 视频增强元数据（FFprobe 提取）
    hdr_format: Mapped[str | None] = mapped_column(String(20), nullable=True)       # HDR10, HDR10+, Dolby Vision, HLG
    audio_channels: Mapped[str | None] = mapped_column(String(10), nullable=True)    # 7.1, 5.1, 2.0, stereo, mono
    frame_rate: Mapped[float | None] = mapped_column(Float, nullable=True)           # 23.976, 24, 60
    color_space: Mapped[str | None] = mapped_column(String(20), nullable=True)       # BT.709, BT.2020, DCI-P3
    bit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)            # 8, 10, 12

    # 重复检测
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 指向主条目的ID
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)   # 文件哈希（用于重复检测）

    # 关系
    library: Mapped[MediaLibrary] = relationship(back_populates="items")
    seasons: Mapped[list[MediaSeason]] = relationship(back_populates="media_item", lazy="selectin")
    subtitles: Mapped[list[Subtitle]] = relationship(back_populates="media_item", lazy="selectin")
    play_history: Mapped[list["PlayHistory"]] = relationship("PlayHistory", back_populates="media", cascade="all, delete-orphan")
    playlist_items: Mapped[list["PlaylistItem"]] = relationship("PlaylistItem", back_populates="media", cascade="all, delete-orphan")


class MediaSeason(TimestampMixin, Base):
    __tablename__ = "media_seasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), nullable=False, index=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # 关系
    media_item: Mapped[MediaItem] = relationship(back_populates="seasons")
    episodes: Mapped[list[MediaEpisode]] = relationship(back_populates="season", lazy="selectin")


class MediaEpisode(TimestampMixin, Base):
    __tablename__ = "media_episodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("media_seasons.id"), nullable=False, index=True)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    video_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 关系
    season: Mapped[MediaSeason] = relationship(back_populates="episodes")


class Subtitle(TimestampMixin, Base):
    __tablename__ = "subtitles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), nullable=False, index=True)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False)    # zh, en, zh-CN
    language_name: Mapped[str] = mapped_column(String(50), nullable=False) # 中文, English
    path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="external")   # embedded / external

    # 关系
    media_item: Mapped[MediaItem] = relationship(back_populates="subtitles")


class Favorite(TimestampMixin, Base):
    """用户收藏"""
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False, index=True)

    # 关系
    media_item: Mapped[MediaItem] = relationship()
    
    __table_args__ = (
        UniqueConstraint("user_id", "media_item_id", name="uq_favorites_user_media"),
    )
