"""
用户模块数据模型
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.base_models import Base, TimestampMixin


class UserTier(str, Enum):
    FREE = "free"        # 免费版，系统级限制用户数量
    PLUS = "plus"        # 付费版，无用户数量限制


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")  # admin / user
    tier: Mapped[str] = mapped_column(String(20), default=UserTier.FREE)  # free / plus
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关联
    play_history: Mapped[list["PlayHistory"]] = relationship("PlayHistory", back_populates="user", cascade="all, delete-orphan")
    playlists: Mapped[list["Playlist"]] = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")
    permissions: Mapped["UserPermission | None"] = relationship(
        "UserPermission", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_plus(self) -> bool:
        return self.tier == UserTier.PLUS


class UserPermission(TimestampMixin, Base):
    """用户功能权限表 — 管理员可对每个用户精细控制功能访问"""
    __tablename__ = "user_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # ── 基础权限（普通用户默认开启）──
    can_view_dashboard: Mapped[bool] = mapped_column(Boolean, default=True)
    can_play_media: Mapped[bool] = mapped_column(Boolean, default=True)
    can_cast: Mapped[bool] = mapped_column(Boolean, default=True)                # 投屏
    can_external_player: Mapped[bool] = mapped_column(Boolean, default=True)     # 外部播放器
    can_favorite: Mapped[bool] = mapped_column(Boolean, default=True)            # 收藏
    can_view_history: Mapped[bool] = mapped_column(Boolean, default=True)        # 观看历史

    # ── 受限功能（普通用户默认关闭，需管理员开启）──
    can_edit_media: Mapped[bool] = mapped_column(Boolean, default=False)          # 编辑媒体信息
    can_rescrape: Mapped[bool] = mapped_column(Boolean, default=False)            # 重新刮削
    can_use_ai: Mapped[bool] = mapped_column(Boolean, default=False)              # AI 智能功能（AI 优化刮削）
    can_capture_frames: Mapped[bool] = mapped_column(Boolean, default=False)      # 视频截帧
    can_manage_downloads: Mapped[bool] = mapped_column(Boolean, default=False)    # 下载管理
    can_view_discover: Mapped[bool] = mapped_column(Boolean, default=False)       # 发现页
    can_manage_subscriptions: Mapped[bool] = mapped_column(Boolean, default=False) # 订阅管理
    can_manage_sites: Mapped[bool] = mapped_column(Boolean, default=False)        # 站点管理
    can_use_ai_assistant: Mapped[bool] = mapped_column(Boolean, default=False)    # AI 助手
    can_manage_users: Mapped[bool] = mapped_column(Boolean, default=False)        # 用户管理
    can_manage_files: Mapped[bool] = mapped_column(Boolean, default=False)        # 文件管理
    can_manage_strm: Mapped[bool] = mapped_column(Boolean, default=False)         # STRM 管理
    can_access_settings: Mapped[bool] = mapped_column(Boolean, default=False)     # 系统设置

    # ── 关联 ──
    user: Mapped["User"] = relationship("User", back_populates="permissions")

    def to_dict(self) -> dict:
        """导出为字典（排除 id, user_id, 时间戳）"""
        return {
            k: getattr(self, k)
            for k in self.__table__.columns.keys()
            if k not in ("id", "user_id", "created_at", "updated_at")
        }

    def apply_dict(self, data: dict):
        """从字典批量更新权限字段"""
        allowed = {
            k for k in self.__table__.columns.keys()
            if k not in ("id", "user_id", "created_at", "updated_at")
        }
        for k, v in data.items():
            if k in allowed and isinstance(v, bool):
                setattr(self, k, v)


class SystemConfig(TimestampMixin, Base):
    """系统配置表 — 存储 FREE/PLUS 等系统级设置"""
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string / int / bool / json


class WatchHistory(TimestampMixin, Base):
    __tablename__ = "watch_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_item_id: Mapped[int] = mapped_column(nullable=False, index=True)
    episode_id: Mapped[int | None] = mapped_column(nullable=True)
    progress: Mapped[float] = mapped_column(default=0)       # 播放进度（秒）
    duration: Mapped[float] = mapped_column(default=0)        # 总时长（秒）
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_watched: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# 导入 PlayHistory 和 Playlist（避免循环导入，必须在类定义之后）
from app.playback.models import PlayHistory, Playlist
