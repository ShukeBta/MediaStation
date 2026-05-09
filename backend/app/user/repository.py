"""
用户数据访问层
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[User]:
        result = await self.db.execute(select(User).order_by(User.id))
        return list(result.scalars().all())

    async def check_admin_exists(self) -> bool:
        """检查系统中是否存在任何 admin 角色的用户"""
        result = await self.db.execute(select(User).where(User.role == "admin").limit(1))
        return result.scalar_one_or_none() is not None

    async def create(self, username: str, password_hash: str, role: str = "user", tier: str = "free") -> User:
        user = User(username=username, password_hash=password_hash, role=role, tier=tier)
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user_id: int):
        user = await self.get_by_id(user_id)
        if user:
            from datetime import datetime, timezone
            user.last_login = datetime.now(timezone.utc)
            await self.db.flush()

    async def update(self, user_id: int, **kwargs) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        for k, v in kwargs.items():
            if hasattr(user, k):
                setattr(user, k, v)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: int):
        user = await self.get_by_id(user_id)
        if user:
            await self.db.delete(user)
            await self.db.flush()

    async def update_tier(self, user_id: int, tier: str) -> User | None:
        """Update user tier (free/plus)"""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.tier = tier
        await self.db.flush()
        await self.db.refresh(user)
        return user
