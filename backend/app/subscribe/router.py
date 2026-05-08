"""
订阅模块路由
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.deps import AdminUser, CurrentUser, DB
from app.subscribe.service import SubscribeService
from app.subscribe.schemas import (
    NotifyChannelCreate,
    NotifyChannelOut,
    NotifyChannelUpdate,
    ResourceOut,
    SiteCreate,
    SiteOut,
    SiteUpdate,
    SubscriptionCreate,
    SubscriptionOut,
    SubscriptionUpdate,
)

router = APIRouter(prefix="", tags=["subscribe"])


# ── 站点管理 ──
@router.get("/sites", response_model=list[SiteOut])
async def list_sites(user: CurrentUser, db: DB):
    service = SubscribeService(db)
    return await service.list_sites()


@router.post("/sites", response_model=SiteOut)
async def create_site(data: SiteCreate, user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.create_site(data)


@router.put("/sites/{site_id}", response_model=SiteOut)
async def update_site(site_id: int, data: SiteUpdate, user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.update_site(site_id, data)


@router.delete("/sites/{site_id}", status_code=204)
async def delete_site(site_id: int, user: AdminUser, db: DB):
    service = SubscribeService(db)
    await service.delete_site(site_id)


@router.post("/sites/{site_id}/test")
async def test_site(site_id: int, user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.test_site(site_id)


@router.get("/sites/{site_id}/resource")
async def browse_site_resource(
    site_id: int,
    user: CurrentUser,
    db: DB,
    keyword: str | None = None,
    cat: str | None = Query(None, alias="cat", description="分类"),
    page: int = Query(0, ge=0, description="页码（从0开始）"),
):
    """浏览站点资源（MoviePilot API 参考）

    按关键字/分类分页浏览站点资源列表。
    """
    service = SubscribeService(db)
    return await service.browse_site_resource(site_id, keyword, cat, page)


@router.get("/sites/{site_id}/userdata")
async def refresh_site_userdata(site_id: int, user: AdminUser, db: DB):
    """刷新站点用户数据（MoviePilot API 参考）

    获取用户在站点的上传/下载量、做种数等统计信息。
    """
    service = SubscribeService(db)
    return await service.refresh_site_userdata(site_id)


# ── 资源搜索 ──
@router.get("/search/sites", response_model=list[ResourceOut])
async def search_sites(
    user: CurrentUser,
    db: DB,
    keyword: str = Query(..., min_length=1),
    site_ids: str | None = Query(None, description="逗号分隔的站点ID"),
):
    service = SubscribeService(db)
    ids = [int(i) for i in site_ids.split(",")] if site_ids else None
    return await service.search_sites(keyword, ids)


# ── 订阅管理 ──
@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def list_subscriptions(
    user: CurrentUser, db: DB, status: str | None = None,
):
    service = SubscribeService(db)
    return await service.list_subscriptions(status)


@router.post("/subscriptions", response_model=SubscriptionOut)
async def create_subscription(data: SubscriptionCreate, user: CurrentUser, db: DB):
    service = SubscribeService(db)
    return await service.create_subscription(data)


@router.put("/subscriptions/{sub_id}", response_model=SubscriptionOut)
async def update_subscription(sub_id: int, data: SubscriptionUpdate, user: CurrentUser, db: DB):
    service = SubscribeService(db)
    return await service.update_subscription(sub_id, data)


@router.delete("/subscriptions/{sub_id}", status_code=204)
async def delete_subscription(sub_id: int, user: AdminUser, db: DB):
    service = SubscribeService(db)
    await service.delete_subscription(sub_id)


@router.get("/subscriptions/media/{mediaid}")
async def get_subscription_by_media(
    mediaid: str,
    user: CurrentUser,
    db: DB,
    season: int | None = None,
    title: str | None = None,
):
    """按媒体ID查询订阅（MoviePilot API 参考）

    支持 tmdb:/douban:/bangumi: 前缀格式。
    """
    service = SubscribeService(db)
    return await service.get_subscription_by_media(mediaid, season, title)


@router.post("/subscriptions/{sub_id}/search")
async def trigger_subscription_search(sub_id: int, user: CurrentUser, db: DB):
    service = SubscribeService(db)
    return await service.process_subscription(sub_id)


@router.post("/subscriptions/{sub_id}/share")
async def share_subscription(
    sub_id: int,
    user: CurrentUser,
    db: DB,
    note: str | None = None,
):
    """分享订阅（MoviePilot API 参考）

    创建订阅分享记录。
    """
    service = SubscribeService(db)
    return await service.share_subscription(sub_id, note)


@router.post("/subscriptions/{sub_id}/fork")
async def fork_subscription(sub_id: int, user: CurrentUser, db: DB):
    """复制订阅（MoviePilot API 参考）

    从分享链接复制订阅到本地。
    """
    service = SubscribeService(db)
    return await service.fork_subscription(sub_id)


# ── 通知渠道 ──
@router.get("/notify/channels", response_model=list[NotifyChannelOut])
async def list_notify_channels(user: CurrentUser, db: DB):
    service = SubscribeService(db)
    return await service.list_notify_channels()


@router.post("/notify/channels", response_model=NotifyChannelOut)
async def create_notify_channel(data: NotifyChannelCreate, user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.create_notify_channel(data)


@router.put("/notify/channels/{channel_id}", response_model=NotifyChannelOut)
async def update_notify_channel(channel_id: int, data: NotifyChannelUpdate, user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.update_notify_channel(channel_id, data)


@router.delete("/notify/channels/{channel_id}", status_code=204)
async def delete_notify_channel(channel_id: int, user: AdminUser, db: DB):
    service = SubscribeService(db)
    await service.delete_notify_channel(channel_id)


@router.post("/notify/channels/{channel_id}/test")
async def test_notify_channel(channel_id: int, user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.test_notify_channel(channel_id)


# ── RSS 拉取 ──
@router.post("/rss/pull")
async def pull_rss(user: AdminUser, db: DB):
    service = SubscribeService(db)
    return await service.pull_rss()
