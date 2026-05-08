"""
系统模块数据模型
"""
from app.base_models import Base
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class SettingsKV(Base):
    """KV 设置表（预留扩展）"""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
