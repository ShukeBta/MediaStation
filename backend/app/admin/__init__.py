"""
管理后台模块

提供系统管理、批量操作、文件浏览等管理功能。
"""
from app.admin.router import router as admin_router

__all__ = ["admin_router"]
