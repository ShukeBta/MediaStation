"""
播放回放模块数据模型
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_models import Base, TimestampMixin


class PlayHistory(Base):
    """播放历史记录"""
    __tablename__ = "play_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False, index=True)
    played_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now(),
        index=True
    )
    duration: Mapped[int] = mapped_column(Integer, default=0)  # 播放时长（秒）
    device_type: Mapped[str] = mapped_column(String(20), default="web")  # web, mobile, tv, cast
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    
    # 关联
    user: Mapped["User"] = relationship("User", back_populates="play_history")
    media: Mapped["MediaItem"] = relationship("MediaItem", back_populates="play_history")


class Playlist(Base):
    """播放列表"""
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # 关联
    user: Mapped["User"] = relationship("User", back_populates="playlists")
    items: Mapped[list["PlaylistItem"]] = relationship(
        "PlaylistItem", 
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistItem.position"
    )


class PlaylistItem(Base):
    """播放列表项"""
    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    
    # 关联
    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="items")
    media: Mapped["MediaItem"] = relationship("MediaItem", back_populates="playlist_items")


# 导入 User 和 MediaItem（避免循环导入）
from app.user.models import User
from app.media.models import MediaItem
