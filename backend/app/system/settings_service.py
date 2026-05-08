"""
整理 & 刮削配置服务
使用 SettingsKV 表存储用户自定义配置
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.system.models import SettingsKV

logger = logging.getLogger(__name__)

# ── 预设配置 Schema ──
# 每个配置项: key, 默认值, 类型, 分组, 描述, 选项(可选)

SETTING_GROUPS = {
    "organize": "整理配置",
    "scrape": "刮削配置",
}

SETTINGS_SCHEMA: dict[str, dict[str, Any]] = {
    # 整理配置
    "organize.movie_rename_format": {
        "default": "{{title}}{% if year %} ({{year}}){% endif %}/{{title}}{% if year %} ({{year}}){% endif %}{% if part %}-{{part}}{% endif %}{% if videoFormat %} - {{videoFormat}}{% endif %}{{fileExt}}",
        "type": "text",
        "group": "organize",
        "label": "电影重命名格式",
        "description": "使用 Jinja2 语法，支持变量: title, year, part, videoFormat, fileExt",
    },
    "organize.tv_rename_format": {
        "default": "{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{% if part %}-{{part}}{% endif %}{% if episode %} - 第 {{episode}} 集{% endif %}{{fileExt}}",
        "type": "text",
        "group": "organize",
        "label": "电视剧重命名格式",
        "description": "使用 Jinja2 语法，支持变量: title, year, season, season_episode, episode, part, videoFormat, fileExt",
    },
    "organize.anime_rename_format": {
        "default": "{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{% if part %}-{{part}}{% endif %}{{fileExt}}",
        "type": "text",
        "group": "organize",
        "label": "动漫重命名格式",
        "description": "使用 Jinja2 语法，支持变量: title, year, season, season_episode, episode, part, fileExt",
    },
    "organize.auto_organize": {
        "default": "true",
        "type": "boolean",
        "group": "organize",
        "label": "下载完成自动整理",
        "description": "下载完成后自动整理文件到媒体库",
    },
    "organize.move_subtitles": {
        "default": "true",
        "type": "boolean",
        "group": "organize",
        "label": "同步移动字幕",
        "description": "整理视频时同步移动关联的字幕文件",
    },
    "organize.cleanup_empty_dirs": {
        "default": "true",
        "type": "boolean",
        "group": "organize",
        "label": "清理空目录",
        "description": "整理完成后删除空文件夹",
    },
    # 刮削配置
    "scrape.providers": {
        "default": "tmdb",
        "type": "text",
        "group": "scrape",
        "label": "刮削数据源",
        "description": "刮削数据源优先级，用逗号分隔: tmdb,douban,bangumi,thetvdb",
    },
    "scrape.language": {
        "default": "zh-CN",
        "type": "select",
        "group": "scrape",
        "label": "刮削语言",
        "options": [
            {"value": "zh-CN", "label": "简体中文"},
            {"value": "zh-TW", "label": "繁体中文"},
            {"value": "en", "label": "English"},
            {"value": "ja", "label": "日本語"},
        ],
        "description": "刮削时优先返回的语言",
    },
    "scrape.poster_size": {
        "default": "w500",
        "type": "select",
        "group": "scrape",
        "label": "海报尺寸",
        "options": [
            {"value": "w185", "label": "小 (185px)"},
            {"value": "w342", "label": "中 (342px)"},
            {"value": "w500", "label": "大 (500px)"},
            {"value": "original", "label": "原始尺寸"},
        ],
        "description": "刮削海报图片的尺寸",
    },
    "scrape.backdrop_size": {
        "default": "original",
        "type": "select",
        "group": "scrape",
        "label": "背景图尺寸",
        "options": [
            {"value": "w300", "label": "小 (300px)"},
            {"value": "w780", "label": "中 (780px)"},
            {"value": "w1280", "label": "大 (1280px)"},
            {"value": "original", "label": "原始尺寸"},
        ],
        "description": "刮削背景图的尺寸",
    },
    "scrape.auto_scrape_on_scan": {
        "default": "true",
        "type": "boolean",
        "group": "scrape",
        "label": "扫描时自动刮削",
        "description": "媒体库扫描时自动刮削缺失的元数据",
    },
    "scrape.auto_scrape_on_add": {
        "default": "true",
        "type": "boolean",
        "group": "scrape",
        "label": "添加时自动刮削",
        "description": "添加新文件时自动刮削元数据",
    },
    "scrape.overwrite_existing": {
        "default": "false",
        "type": "boolean",
        "group": "scrape",
        "label": "覆盖已有元数据",
        "description": "刮削时覆盖已存在的元数据（关闭则只刮削缺失字段）",
    },
}


class SettingsService:
    """配置服务 - 读写 SettingsKV 表"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 基础 CRUD ──

    async def get(self, key: str) -> str | None:
        """获取单个配置值（不存在返回默认值）"""
        result = await self.db.execute(
            select(SettingsKV).where(SettingsKV.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            return row.value
        # 返回 schema 默认值
        if key in SETTINGS_SCHEMA:
            return SETTINGS_SCHEMA[key]["default"]
        return None

    async def get_all(self) -> dict[str, str]:
        """获取所有配置（key -> value，缺失的用默认值填充）"""
        result = await self.db.execute(select(SettingsKV))
        rows = result.scalars().all()

        # 构建 dict，优先用数据库值
        settings: dict[str, str] = {}
        for row in rows:
            settings[row.key] = row.value or ""

        # 填充默认值（只在 key 存在于 schema 时）
        for key, schema in SETTINGS_SCHEMA.items():
            if key not in settings:
                settings[key] = schema["default"]

        return settings

    async def set(self, key: str, value: str) -> bool:
        """设置配置值（upsert）"""
        result = await self.db.execute(
            select(SettingsKV).where(SettingsKV.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            row = SettingsKV(key=key, value=value)
            self.db.add(row)
        await self.db.flush()
        return True

    async def set_many(self, updates: dict[str, str]) -> int:
        """批量设置配置"""
        count = 0
        for key, value in updates.items():
            await self.set(key, value)
            count += 1
        return count

    async def delete(self, key: str) -> bool:
        """删除配置（重置为默认值）"""
        result = await self.db.execute(
            select(SettingsKV).where(SettingsKV.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            await self.db.delete(row)
            await self.db.flush()
            return True
        return False

    async def reset_all(self) -> int:
        """重置所有配置为默认值"""
        count = 0
        for key in SETTINGS_SCHEMA:
            await self.delete(key)
            count += 1
        return count

    # ── Schema ──

    def get_schema(self) -> dict[str, dict[str, Any]]:
        """获取配置 Schema（供前端渲染表单）"""
        return SETTINGS_SCHEMA

    def get_grouped_schema(self) -> dict[str, list[dict[str, Any]]]:
        """获取按分组组织的 Schema"""
        groups: dict[str, list[dict[str, Any]]] = {}
        for key, schema in SETTINGS_SCHEMA.items():
            group = schema.get("group", "other")
            if group not in groups:
                groups[group] = []
            groups[group].append({
                "key": key,
                **schema,
            })
        return groups

    # ── 便捷方法 ──

    async def get_bool(self, key: str) -> bool:
        """获取布尔值配置"""
        val = await self.get(key)
        return val is not None and val.lower() in ("true", "1", "yes", "on")

    async def get_list(self, key: str, sep: str = ",") -> list[str]:
        """获取列表值配置"""
        val = await self.get(key) or ""
        return [v.strip() for v in val.split(sep) if v.strip()]

    # ── 媒体服务专用 ──

    async def get_rename_format(self, media_type: str) -> str:
        """获取指定媒体类型的重命名格式"""
        key_map = {
            "movie": "organize.movie_rename_format",
            "tv": "organize.tv_rename_format",
            "anime": "organize.anime_rename_format",
        }
        key = key_map.get(media_type, "organize.movie_rename_format")
        return await self.get(key) or SETTINGS_SCHEMA[key]["default"]

    async def get_scrape_providers(self) -> list[str]:
        """获取刮削数据源优先级列表"""
        return await self.get_list("scrape.providers")

    async def is_auto_organize_enabled(self) -> bool:
        """是否启用自动整理"""
        return await self.get_bool("organize.auto_organize")

    async def is_auto_scrape_enabled(self) -> bool:
        """是否启用自动刮削"""
        return await self.get_bool("scrape.auto_scrape_on_scan")
