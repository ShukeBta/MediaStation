"""
精细化权限管理 — Admin API 路由

端点：
  GET    /api/admin/profiles              列出用户的所有 Profile
  POST   /api/admin/profiles              创建新 Profile
  GET    /api/admin/profiles/:id          获取 Profile 详情
  PUT    /api/admin/profiles/:id          更新 Profile
  DELETE /api/admin/profiles/:id          删除 Profile
  POST   /api/admin/profiles/:id/switch   切换当前活跃 Profile
  GET    /api/admin/profiles/:id/watch-logs  获取观看日志
  GET    /api/admin/profiles/:id/usage    获取使用统计
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import AdminUser, CurrentUser, DB
from app.common.schemas import SuccessResponse

router = APIRouter(prefix="/admin/profiles", tags=["profiles"])


# ── Pydantic Schemas ──

class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Profile 名称")
    user_id: int = Field(..., ge=1, description="所属用户 ID")
    avatar: str | None = None
    is_default: bool = False
    content_rating_limit: str | None = Field(None, description="内容分级上限：G/PG/PG-13/R/NC-17")
    allow_adult: bool = False
    require_pin: bool = False
    pin: str | None = Field(None, min_length=4, max_length=8, description="切换 PIN 码")
    allowed_library_ids: list[int] = Field(default_factory=list, description="允许访问的媒体库 ID 列表（空=全部）")
    preferred_subtitle_lang: str | None = None
    preferred_audio_lang: str | None = None
    autoplay_next: bool = True
    skip_intro: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    avatar: str | None = None
    is_default: bool | None = None
    content_rating_limit: str | None = None
    allow_adult: bool | None = None
    require_pin: bool | None = None
    pin: str | None = None
    allowed_library_ids: list[int] | None = None
    preferred_subtitle_lang: str | None = None
    preferred_audio_lang: str | None = None
    autoplay_next: bool | None = None
    skip_intro: bool | None = None


# ── 辅助函数 ──

def _profile_to_dict(p) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "name": p.name,
        "avatar": p.avatar,
        "is_default": p.is_default,
        "is_active": p.is_active,
        "content_rating_limit": p.content_rating_limit,
        "allow_adult": p.allow_adult,
        "require_pin": p.require_pin,
        "allowed_library_ids": json.loads(p.allowed_library_ids) if p.allowed_library_ids else [],
        "preferred_subtitle_lang": p.preferred_subtitle_lang,
        "preferred_audio_lang": p.preferred_audio_lang,
        "autoplay_next": p.autoplay_next,
        "skip_intro": p.skip_intro,
        "total_watch_time": p.total_watch_time,
        "last_active": p.last_active.isoformat() if p.last_active else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


async def _get_profile_or_404(profile_id: int, db):
    from app.profiles.models import UserProfile
    from sqlalchemy import select
    result = await db.execute(select(UserProfile).where(UserProfile.id == profile_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, f"Profile {profile_id} 不存在")
    return p


# ── 路由 ──

@router.get("", summary="列出所有 Profile")
async def list_profiles(
    user: AdminUser,
    db: DB,
    user_id: int | None = Query(None, description="按用户 ID 过滤"),
):
    """列出所有用户配置文件（管理员可查看所有用户，普通用户只能查看自己的）"""
    from app.profiles.models import UserProfile
    from sqlalchemy import select

    query = select(UserProfile).where(UserProfile.is_active == True)
    if user_id:
        query = query.where(UserProfile.user_id == user_id)
    query = query.order_by(UserProfile.user_id, UserProfile.is_default.desc(), UserProfile.created_at)

    result = await db.execute(query)
    profiles = result.scalars().all()

    return SuccessResponse.ok([_profile_to_dict(p) for p in profiles])


@router.post("", summary="创建 Profile", status_code=201)
async def create_profile(data: ProfileCreate, user: AdminUser, db: DB):
    """为指定用户创建新的配置文件"""
    from app.profiles.models import UserProfile
    from app.user.auth import hash_password
    from sqlalchemy import select

    # 如果设为默认，先清除该用户的其他默认 Profile
    if data.is_default:
        from sqlalchemy import update
        await db.execute(
            update(UserProfile)
            .where(UserProfile.user_id == data.user_id)
            .values(is_default=False)
        )

    profile = UserProfile(
        user_id=data.user_id,
        name=data.name,
        avatar=data.avatar,
        is_default=data.is_default,
        content_rating_limit=data.content_rating_limit,
        allow_adult=data.allow_adult,
        require_pin=data.require_pin,
        pin_hash=hash_password(data.pin) if data.pin else None,
        allowed_library_ids=json.dumps(data.allowed_library_ids) if data.allowed_library_ids else None,
        preferred_subtitle_lang=data.preferred_subtitle_lang,
        preferred_audio_lang=data.preferred_audio_lang,
        autoplay_next=data.autoplay_next,
        skip_intro=data.skip_intro,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return SuccessResponse.ok(_profile_to_dict(profile))


@router.get("/{profile_id}", summary="获取 Profile 详情")
async def get_profile(profile_id: int, user: AdminUser, db: DB):
    """获取指定 Profile 的详情"""
    profile = await _get_profile_or_404(profile_id, db)
    return SuccessResponse.ok(_profile_to_dict(profile))


@router.put("/{profile_id}", summary="更新 Profile")
async def update_profile(profile_id: int, data: ProfileUpdate, user: AdminUser, db: DB):
    """更新 Profile 设置"""
    from app.user.auth import hash_password

    profile = await _get_profile_or_404(profile_id, db)

    if data.name is not None:
        profile.name = data.name
    if data.avatar is not None:
        profile.avatar = data.avatar
    if data.is_default is not None:
        if data.is_default:
            # 清除同用户其他默认 Profile
            from sqlalchemy import update
            from app.profiles.models import UserProfile
            await db.execute(
                update(UserProfile)
                .where(UserProfile.user_id == profile.user_id)
                .values(is_default=False)
            )
        profile.is_default = data.is_default
    if data.content_rating_limit is not None:
        profile.content_rating_limit = data.content_rating_limit
    if data.allow_adult is not None:
        profile.allow_adult = data.allow_adult
    if data.require_pin is not None:
        profile.require_pin = data.require_pin
    if data.pin is not None:
        profile.pin_hash = hash_password(data.pin)
    if data.allowed_library_ids is not None:
        profile.allowed_library_ids = json.dumps(data.allowed_library_ids)
    if data.preferred_subtitle_lang is not None:
        profile.preferred_subtitle_lang = data.preferred_subtitle_lang
    if data.preferred_audio_lang is not None:
        profile.preferred_audio_lang = data.preferred_audio_lang
    if data.autoplay_next is not None:
        profile.autoplay_next = data.autoplay_next
    if data.skip_intro is not None:
        profile.skip_intro = data.skip_intro

    await db.commit()
    await db.refresh(profile)

    return SuccessResponse.ok(_profile_to_dict(profile))


@router.delete("/{profile_id}", status_code=204, summary="删除 Profile")
async def delete_profile(profile_id: int, user: AdminUser, db: DB):
    """软删除 Profile（标记为不活跃）"""
    profile = await _get_profile_or_404(profile_id, db)
    profile.is_active = False
    await db.commit()


@router.post("/{profile_id}/switch", summary="切换活跃 Profile")
async def switch_profile(
    profile_id: int,
    user: CurrentUser,
    db: DB,
    pin: str | None = None,
):
    """
    切换当前用户的活跃 Profile。
    如果 Profile 需要 PIN 保护，必须提供正确的 PIN。
    """
    from app.profiles.models import UserProfile
    from app.user.auth import verify_password
    from sqlalchemy import select, update
    from datetime import datetime

    # 检查 Profile 是否属于当前用户（或管理员可切换任意）
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.id == profile_id,
            UserProfile.is_active == True,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile 不存在")

    if profile.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "无权访问此 Profile")

    # PIN 验证
    if profile.require_pin and profile.pin_hash:
        if not pin:
            raise HTTPException(422, "此 Profile 需要 PIN 码")
        if not verify_password(pin, profile.pin_hash):
            raise HTTPException(401, "PIN 码错误")

    # 更新最后活跃时间
    profile.last_active = datetime.now()
    await db.commit()

    return SuccessResponse.ok({
        "active_profile_id": profile_id,
        "profile": _profile_to_dict(profile),
        "message": f"已切换到 Profile: {profile.name}",
    })


@router.get("/{profile_id}/watch-logs", summary="获取观看日志")
async def get_watch_logs(
    profile_id: int,
    user: AdminUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    completed_only: bool = False,
):
    """获取 Profile 的详细观看日志（按观看时间倒序）"""
    from app.profiles.models import ProfileWatchLog
    from sqlalchemy import select, func

    await _get_profile_or_404(profile_id, db)

    base = select(ProfileWatchLog).where(ProfileWatchLog.profile_id == profile_id)
    count_q = select(func.count(ProfileWatchLog.id)).where(ProfileWatchLog.profile_id == profile_id)

    if completed_only:
        base = base.where(ProfileWatchLog.completed == True)
        count_q = count_q.where(ProfileWatchLog.completed == True)

    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(ProfileWatchLog.watched_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()

    return SuccessResponse.ok({
        "profile_id": profile_id,
        "logs": [
            {
                "id": log.id,
                "media_item_id": log.media_item_id,
                "media_title": log.media_title,
                "episode_id": log.episode_id,
                "progress": log.progress,
                "duration": log.duration,
                "progress_pct": round(log.progress / log.duration * 100, 1) if log.duration > 0 else 0,
                "completed": log.completed,
                "watched_at": log.watched_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    })


@router.get("/{profile_id}/usage", summary="获取 Profile 使用统计")
async def get_profile_usage(profile_id: int, user: AdminUser, db: DB):
    """获取 Profile 的使用统计（观看时长、完成数、最爱类型等）"""
    from app.profiles.models import ProfileWatchLog, UserProfile
    from sqlalchemy import select, func

    profile = await _get_profile_or_404(profile_id, db)

    # 基础统计
    total_count = (await db.execute(
        select(func.count(ProfileWatchLog.id)).where(ProfileWatchLog.profile_id == profile_id)
    )).scalar() or 0

    completed_count = (await db.execute(
        select(func.count(ProfileWatchLog.id)).where(
            ProfileWatchLog.profile_id == profile_id,
            ProfileWatchLog.completed == True
        )
    )).scalar() or 0

    total_watch_seconds = (await db.execute(
        select(func.sum(ProfileWatchLog.progress)).where(ProfileWatchLog.profile_id == profile_id)
    )).scalar() or 0

    # 最近观看记录（TOP 5）
    recent_result = await db.execute(
        select(ProfileWatchLog)
        .where(ProfileWatchLog.profile_id == profile_id)
        .order_by(ProfileWatchLog.watched_at.desc())
        .limit(5)
    )
    recent_logs = recent_result.scalars().all()

    hours = int(total_watch_seconds // 3600)
    minutes = int((total_watch_seconds % 3600) // 60)

    return SuccessResponse.ok({
        "profile_id": profile_id,
        "profile_name": profile.name,
        "statistics": {
            "total_watch_sessions": total_count,
            "completed_count": completed_count,
            "completion_rate": round(completed_count / total_count * 100, 1) if total_count > 0 else 0,
            "total_watch_seconds": int(total_watch_seconds),
            "total_watch_formatted": f"{hours}h {minutes}m",
            "last_active": profile.last_active.isoformat() if profile.last_active else None,
        },
        "recent_watches": [
            {
                "media_item_id": log.media_item_id,
                "media_title": log.media_title,
                "progress_pct": round(log.progress / log.duration * 100, 1) if log.duration > 0 else 0,
                "completed": log.completed,
                "watched_at": log.watched_at.isoformat(),
            }
            for log in recent_logs
        ],
    })
