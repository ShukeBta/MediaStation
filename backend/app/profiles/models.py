"""
精细化权限管理 — 数据模型

Profile 是一个轻量级的"子账户"或"使用场景"概念：
- 一个用户可以有多个 Profile（如"儿童模式"、"影院模式"）
- 每个 Profile 可以有不同的内容分级过滤、媒体库访问权限
- 支持观看日志和使用统计
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_models import Base, TimestampMixin


class UserProfile(TimestampMixin, Base):
    """用户配置文件（子账户 / 使用场景）"""
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)       # 默认 Profile
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 内容控制
    content_rating_limit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # G / PG / PG-13 / R / NC-17
    allow_adult: Mapped[bool] = mapped_column(Boolean, default=False)
    require_pin: Mapped[bool] = mapped_column(Boolean, default=False)      # 切换时是否需要 PIN
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 媒体库访问（JSON list of library_ids，为空则允许全部）
    allowed_library_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: [1, 2, 3]

    # 播放设置
    preferred_subtitle_lang: Mapped[str | None] = mapped_column(String(10), nullable=True)  # zh / en
    preferred_audio_lang: Mapped[str | None] = mapped_column(String(10), nullable=True)
    autoplay_next: Mapped[bool] = mapped_column(Boolean, default=True)
    skip_intro: Mapped[bool] = mapped_column(Boolean, default=False)

    # 统计
    total_watch_time: Mapped[int] = mapped_column(Integer, default=0)      # 秒
    last_active: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    watch_logs: Mapped[list["ProfileWatchLog"]] = relationship(
        "ProfileWatchLog", back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileWatchLog(Base):
    """Profile 观看日志"""
    __tablename__ = "profile_watch_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    media_item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    media_title: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 冗余标题，方便查询
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0)      # 播放进度（秒）
    duration: Mapped[float] = mapped_column(Float, default=0)       # 总时长（秒）
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    watched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关系
    profile: Mapped[UserProfile] = relationship("UserProfile", back_populates="watch_logs")
