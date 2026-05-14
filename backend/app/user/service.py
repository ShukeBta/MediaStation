"""
用户模块业务逻辑
"""
from __future__ import annotations

from app.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.user.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.user.models import User, UserPermission
from app.user.repository import UserRepository
from app.user.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UpdateProfileRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def login(self, data: LoginRequest) -> LoginResponse:
        user = await self.repo.get_by_username(data.username)
        if not user or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid username or password")
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")

        await self.repo.update_last_login(user.id)
        access_token = create_access_token(user.id, user.username, user.role)
        refresh_token = create_refresh_token(user.id)
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserOut.model_validate(user),
        )

    async def refresh(self, refresh_token: str) -> LoginResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid refresh token")
            user_id = int(payload["sub"])
        except Exception:
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or disabled")

        access_token = create_access_token(user.id, user.username, user.role)
        new_refresh = create_refresh_token(user.id)
        return LoginResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            user=UserOut.model_validate(user),
        )

    async def create_user(self, data: UserCreate) -> UserOut:
        existing = await self.repo.get_by_username(data.username)
        if existing:
            raise ConflictError(f"Username '{data.username}' already exists")
        hashed = hash_password(data.password)
        tier = getattr(data, "tier", "free")
        user = await self.repo.create(data.username, hashed, data.role, tier=tier)

        # 自动创建默认权限记录（使用同一个 session，避免 database locked）
        perms = UserPermission(user_id=user.id)
        if data.role == "admin":
            # 管理员默认开启所有权限
            for col in UserPermission.__table__.columns:
                if col.name not in ("id", "user_id", "created_at", "updated_at"):
                    setattr(perms, col.name, True)
        self.repo.db.add(perms)
        await self.repo.db.commit()
        await self.repo.db.refresh(perms)

        return UserOut.model_validate(user)

    async def get_user(self, user_id: int) -> UserOut:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return UserOut.model_validate(user)

    async def list_users(self) -> list[UserOut]:
        users = await self.repo.get_all()
        return [UserOut.model_validate(u) for u in users]

    async def update_user(self, user_id: int, data: UserUpdate) -> UserOut:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        updates: dict = {}
        if data.password:
            updates["password_hash"] = hash_password(data.password)
        if data.role:
            updates["role"] = data.role
        if data.tier:
            updates["tier"] = data.tier
        if data.avatar is not None:
            updates["avatar"] = data.avatar
        if data.is_active is not None:
            updates["is_active"] = data.is_active
        user = await self.repo.update(user_id, **updates)
        return UserOut.model_validate(user)

    async def delete_user(self, user_id: int):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        await self.repo.delete(user_id)

    async def change_password(self, user_id: int, data: ChangePasswordRequest):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        if not verify_password(data.old_password, user.password_hash):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="旧密码不正确")
        new_hash = hash_password(data.new_password)
        await self.repo.update(user_id, password_hash=new_hash)

    async def update_profile(self, user_id: int, data: UpdateProfileRequest) -> UserOut:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        updates: dict = {}
        if data.avatar is not None:
            updates["avatar"] = data.avatar
        user = await self.repo.update(user_id, **updates)
        return UserOut.model_validate(user)
