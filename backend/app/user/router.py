"""
用户模块路由
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func

from app.deps import AdminUser, CurrentUser, DB, UserPerms, get_user_permissions
from app.user.repository import UserRepository
from app.user.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SystemConfigOut,
    SystemConfigUpdate,
    UpdateProfileRequest,
    UserCreate,
    UserOut,
    UserPermissionOut,
    UserPermissionUpdate,
    UserUpdate,
    WatchHistoryOut,
)
from app.user.service import UserService
from app.user.models import UserPermission, SystemConfig, User, UserTier

router = APIRouter(prefix="", tags=["user"])


# ── 认证 ──
@router.post("/auth/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: DB):
    service = UserService(UserRepository(db))
    return await service.login(data)


@router.post("/auth/refresh", response_model=LoginResponse)
async def refresh_token(data: RefreshRequest, db: DB):
    service = UserService(UserRepository(db))
    return await service.refresh(data.refresh_token)


@router.get("/auth/me", response_model=UserOut)
async def get_me(user: CurrentUser):
    return UserOut.model_validate(user)


@router.post("/auth/change-password")
async def change_password(data: ChangePasswordRequest, user: CurrentUser, db: DB):
    """当前用户修改自己的密码"""
    service = UserService(UserRepository(db))
    await service.change_password(user.id, data)
    return {"success": True, "message": "密码已修改"}


@router.patch("/auth/profile", response_model=UserOut)
async def update_profile(data: UpdateProfileRequest, user: CurrentUser, db: DB):
    """当前用户更新自己的资料（头像等）"""
    service = UserService(UserRepository(db))
    return await service.update_profile(user.id, data)


# ── 当前用户权限 ──
@router.get("/auth/permissions", response_model=UserPermissionOut)
async def get_my_permissions(perms: UserPerms):
    """获取当前用户的功能权限"""
    return perms


# ── 管理员用户管理 ──
@router.get("/users", response_model=list[UserOut])
async def list_users(user: AdminUser, db: DB):
    service = UserService(UserRepository(db))
    return await service.list_users()


@router.post("/users", response_model=UserOut)
async def create_user(data: UserCreate, user: AdminUser, db: DB):
    """创建用户（免费版限制最多30人，Plus 版无限制）"""
    # 检查系统用户数量限制（仅免费版）
    from sqlalchemy import select, func
    from app.user.models import SystemConfig

    tier_result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "user_tier")
    )
    tier_config = tier_result.scalar_one_or_none()
    system_tier = tier_config.value if tier_config else UserTier.FREE

    if system_tier == UserTier.FREE:
        max_result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "max_free_users")
        )
        max_config = max_result.scalar_one_or_none()
        max_users = int(max_config.value) if max_config else 30

        count_result = await db.execute(select(func.count(User.id)))
        current_count = count_result.scalar() or 0

        if current_count >= max_users:
            raise HTTPException(
                status_code=403,
                detail=f"免费版最多支持 {max_users} 个用户。当前已有 {current_count} 个用户。"
                       f"请升级至 PLUS 版以解除限制。",
            )

    service = UserService(UserRepository(db))
    return await service.create_user(data)


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate, user: AdminUser, db: DB):
    service = UserService(UserRepository(db))
    return await service.update_user(user_id, data)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, user: AdminUser, db: DB):
    service = UserService(UserRepository(db))
    await service.delete_user(user_id)


# ── 管理员：用户权限管理 ──
@router.get("/users/{user_id}/permissions", response_model=UserPermissionOut)
async def get_user_permissions_admin(user_id: int, admin: AdminUser, db: DB):
    """获取指定用户的功能权限"""
    # 检查目标用户存在
    repo = UserRepository(db)
    target_user = await repo.get_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    perms = result.scalar_one_or_none()

    if not perms:
        # 自动创建默认权限
        is_admin = target_user.role == "admin"
        perms = UserPermission(user_id=user_id)
        if is_admin:
            for col in UserPermission.__table__.columns:
                if col.name not in ("id", "user_id", "created_at", "updated_at"):
                    setattr(perms, col.name, True)
        db.add(perms)
        await db.flush()

    return UserPermissionOut.model_validate(perms)


@router.put("/users/{user_id}/permissions", response_model=UserPermissionOut)
async def update_user_permissions_admin(
    user_id: int, data: UserPermissionUpdate, admin: AdminUser, db: DB
):
    """更新指定用户的功能权限"""
    repo = UserRepository(db)
    target_user = await repo.get_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    perms = result.scalar_one_or_none()

    if not perms:
        perms = UserPermission(user_id=user_id)
        db.add(perms)

    # 只更新非 None 的字段
    update_data = data.model_dump(exclude_none=True)
    for k, v in update_data.items():
        if hasattr(perms, k):
            setattr(perms, k, v)

    await db.flush()
    return UserPermissionOut.model_validate(perms)


@router.post("/users/{user_id}/permissions/reset", response_model=UserPermissionOut)
async def reset_user_permissions(user_id: int, admin: AdminUser, db: DB):
    """重置用户权限为默认值"""
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    perms = result.scalar_one_or_none()

    if perms:
        await db.delete(perms)
        await db.flush()

    # 创建新的默认权限
    repo = UserRepository(db)
    target_user = await repo.get_by_id(user_id)
    is_admin = target_user.role == "admin" if target_user else False

    perms = UserPermission(user_id=user_id)
    if is_admin:
        for col in UserPermission.__table__.columns:
            if col.name not in ("id", "user_id", "created_at", "updated_at"):
                setattr(perms, col.name, True)
    db.add(perms)
    await db.flush()

    return UserPermissionOut.model_validate(perms)


# ── 系统配置管理 ──
@router.get("/system/config", response_model=SystemConfigOut)
async def get_system_config(user: AdminUser, db: DB):
    """获取系统配置（管理员）"""
    # user_tier
    tier_result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "user_tier")
    )
    tier_config = tier_result.scalar_one_or_none()
    user_tier = tier_config.value if tier_config else UserTier.FREE

    # max_free_users
    max_result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "max_free_users")
    )
    max_config = max_result.scalar_one_or_none()
    max_free_users = int(max_config.value) if max_config else 30

    # current_user_count
    count_result = await db.execute(select(func.count(User.id)))
    current_user_count = count_result.scalar() or 0

    return SystemConfigOut(
        user_tier=user_tier,
        max_free_users=max_free_users,
        current_user_count=current_user_count,
    )


@router.put("/system/config", response_model=SystemConfigOut)
async def update_system_config(data: SystemConfigUpdate, user: AdminUser, db: DB):
    """更新系统配置（管理员）"""
    for key, value in [("user_tier", data.user_tier), ("max_free_users", data.max_free_users)]:
        if value is None:
            continue
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        config = result.scalar_one_or_none()
        str_value = str(value)
        if config:
            config.value = str_value
        else:
            db.add(SystemConfig(key=key, value=str_value))

    await db.flush()

    # 重新查询返回
    return await get_system_config(user, db)


# ── 观看历史 ──
@router.get("/watch-history/stats")
async def get_watch_history_stats(user: CurrentUser, db: DB):
    """获取当前用户观看历史统计（总条数）"""
    from app.user.models import WatchHistory
    from sqlalchemy import func
    from app.database import async_session_factory

    async with async_session_factory() as session:
        count_stmt = select(func.count(WatchHistory.id)).where(
            WatchHistory.user_id == user.id
        )
        result = await session.execute(count_stmt)
        total = result.scalar() or 0

        completed_stmt = select(func.count(WatchHistory.id)).where(
            WatchHistory.user_id == user.id,
            WatchHistory.completed == True,
        )
        result = await session.execute(completed_stmt)
        completed = result.scalar() or 0

    return {"total": total, "completed": completed}


@router.get("/watch-history", response_model=list[WatchHistoryOut])
async def get_watch_history(
    user: CurrentUser,
    db: DB,
    limit: int = Query(20, ge=1, le=1000),
    completed: bool | None = None,
):
    """获取当前用户的观看历史"""
    from app.user.models import WatchHistory
    from app.media.models import MediaItem
    from sqlalchemy import select
    from app.database import async_session_factory

    async with async_session_factory() as session:
        stmt = (
            select(WatchHistory, MediaItem)
            .join(MediaItem, WatchHistory.media_item_id == MediaItem.id)
            .where(WatchHistory.user_id == user.id)
            .order_by(WatchHistory.last_watched.desc())
            .limit(limit)
        )
        if completed is not None:
            stmt = stmt.where(WatchHistory.completed == completed)

        result = await session.execute(stmt)
        rows = result.all()

        history_list = []
        for wh, mi in rows:
            out = WatchHistoryOut(
                id=wh.id,
                user_id=wh.user_id,
                media_item_id=wh.media_item_id,
                episode_id=wh.episode_id,
                progress=wh.progress,
                duration=wh.duration,
                completed=wh.completed,
                last_watched=wh.last_watched,
                media_title=mi.title,
                media_type=mi.media_type,
                poster_url=mi.poster_url,
            )
            history_list.append(out)

        return history_list


@router.get("/watch-history/continue", response_model=list[WatchHistoryOut])
async def get_continue_watching(
    user: CurrentUser,
    db: DB,
    limit: int = Query(10, ge=1, le=50),
):
    """获取继续观看列表（未完成、有进度、有有效时长）"""
    from app.user.models import WatchHistory
    from app.media.models import MediaItem
    from sqlalchemy import select
    from app.database import async_session_factory

    async with async_session_factory() as session:
        stmt = (
            select(WatchHistory, MediaItem)
            .join(MediaItem, WatchHistory.media_item_id == MediaItem.id)
            .where(
                WatchHistory.user_id == user.id,
                WatchHistory.completed == False,
                WatchHistory.progress > 0,
                WatchHistory.duration > 0,
            )
            .order_by(WatchHistory.last_watched.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = result.all()

        history_list = []
        for wh, mi in rows:
            out = WatchHistoryOut(
                id=wh.id,
                user_id=wh.user_id,
                media_item_id=wh.media_item_id,
                episode_id=wh.episode_id,
                progress=wh.progress,
                duration=wh.duration,
                completed=wh.completed,
                last_watched=wh.last_watched,
                media_title=mi.title,
                media_type=mi.media_type,
                poster_url=mi.poster_url,
            )
            history_list.append(out)

        return history_list


@router.delete("/watch-history/{history_id}")
async def delete_watch_history(history_id: int, user: CurrentUser, db: DB):
    """删除观看历史记录"""
    from app.user.models import WatchHistory
    from sqlalchemy import select, delete as sa_delete
    from app.database import async_session_factory

    async with async_session_factory() as session:
        stmt = select(WatchHistory).where(WatchHistory.id == history_id)
        result = await session.execute(stmt)
        history = result.scalar_one_or_none()

        if not history:
            from fastapi import HTTPException
            raise HTTPException(404, "History record not found")

        # 只能删除自己的历史（管理员可删任何人的）
        if history.user_id != user.id and user.role != "admin":
            from fastapi import HTTPException
            raise HTTPException(403, "Cannot delete other user's history")

        await session.delete(history)
        await session.commit()

    return {"success": True}


@router.delete("/watch-history")
async def clear_watch_history(
    user: CurrentUser,
    db: DB,
    media_item_id: int | None = None,
):
    """清空观看历史（可指定某个媒体）"""
    from app.user.models import WatchHistory
    from sqlalchemy import delete as sa_delete
    from app.database import async_session_factory

    async with async_session_factory() as session:
        stmt = sa_delete(WatchHistory).where(WatchHistory.user_id == user.id)
        if media_item_id:
            stmt = stmt.where(WatchHistory.media_item_id == media_item_id)
        await session.execute(stmt)
        await session.commit()

    return {"success": True}
