"""
依赖注入 — DB session, current_user, settings, permissions
所有路由通过 Depends() 注入依赖，不在 handler 中直接创建。
"""
from __future__ import annotations

from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import async_session_factory
from app.exceptions import UnauthorizedError
from app.user.auth import ALGORITHM
from app.user.models import User, UserPermission, SystemConfig
from app.user.repository import UserRepository
from app.user.schemas import UserOut, UserPermissionOut
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话依赖"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserOut:
    """当前认证用户依赖（返回 Pydantic 模型，避免 SQLAlchemy **kwargs 问题）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.app_secret_key, algorithms=[ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if user is None:
        raise credentials_exception
    # 检查用户是否处于激活状态（防止已封禁用户继续使用 token）
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号已被封禁",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserOut.model_validate(user)


async def get_current_active_user(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    """当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def require_admin(
    current_user: Annotated[UserOut, Depends(get_current_active_user)],
) -> UserOut:
    """管理员权限依赖"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_user_permissions(
    current_user: Annotated[UserOut, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserPermissionOut:
    """获取当前用户的功能权限
    
    使用数据库锁（with_for_update）避免竞态条件。
    如果权限记录不存在，自动创建默认权限。
    """
    from sqlalchemy.exc import IntegrityError

    # 使用 with_for_update 锁避免竞态条件
    # 如果记录不存在，锁会持续到事务结束
    result = await db.execute(
        select(UserPermission)
        .where(UserPermission.user_id == current_user.id)
        .with_for_update()
    )
    perms = result.scalar_one_or_none()

    if not perms:
        # 自动创建默认权限
        is_admin = current_user.role == "admin"
        perms = UserPermission(user_id=current_user.id)
        if is_admin:
            # 管理员默认开启所有权限
            for col in UserPermission.__table__.columns:
                if col.name not in ("id", "user_id", "created_at", "updated_at"):
                    setattr(perms, col.name, True)
        try:
            db.add(perms)
            await db.flush()
        except IntegrityError:
            # 竞态条件：另一个请求已经创建了记录，重新查询
            await db.rollback()
            result = await db.execute(
                select(UserPermission).where(UserPermission.user_id == current_user.id)
            )
            perms = result.scalar_one()

    return UserPermissionOut.model_validate(perms)


def require_permission(permission_field: str):
    """
    权限检查依赖工厂 — 用于路由级权限控制。

    用法：
        @router.get("/discover")
        async def discover(
            perms: Annotated[UserPermissionOut, Depends(require_permission("can_view_discover"))],
        ):
            ...
    """
    async def checker(
        current_user: Annotated[UserOut, Depends(get_current_active_user)],
        perms: Annotated[UserPermissionOut, Depends(get_user_permissions)],
        db: DB,
    ) -> UserPermissionOut:
        # 管理员默认拥有所有权限
        if current_user.role == "admin":
            return perms
        # Plus 用户（个人 tier）默认拥有所有权限
        if current_user.tier == "plus":
            return perms
        # 系统级 Plus 授权（检查 SystemConfig）
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "user_tier")
        )
        config = result.scalar_one_or_none()
        if config and config.value == "plus":
            return perms
        # 普通用户：检查具体权限
        if not getattr(perms, permission_field, False):
            raise HTTPException(
                status_code=403,
                detail=f"权限不足：当前用户无权访问此功能，请联系管理员申请。",
            )
        return perms
    return checker


# 类型别名，简化路由签名
DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserOut, Depends(get_current_active_user)]
AdminUser = Annotated[UserOut, Depends(require_admin)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserPerms = Annotated[UserPermissionOut, Depends(get_user_permissions)]
