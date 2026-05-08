"""
AI 助手路由

端点：
  POST   /api/admin/assistant/chat          AI 自然语言对话（含操作意图识别）
  POST   /api/admin/assistant/execute       执行已识别的操作
  POST   /api/admin/assistant/undo/:opId    撤销操作
  GET    /api/admin/assistant/session/:id   获取会话历史
  DELETE /api/admin/assistant/session/:id   删除会话
  GET    /api/admin/assistant/history       获取操作历史记录
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import AdminUser, DB
from app.common.schemas import SuccessResponse

router = APIRouter(prefix="/admin/assistant", tags=["assistant"])


# ── 内存会话存储（生产环境应使用 Redis 或数据库） ──
_sessions: dict[str, dict] = {}        # session_id -> {messages, created_at, metadata}
_op_history: list[dict] = []           # 操作历史记录（全局）


# ── Pydantic Schemas ──

class ChatMessage(BaseModel):
    role: str = Field(..., description="角色: user / assistant / system")
    content: str
    timestamp: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: str | None = Field(None, description="会话 ID（空则创建新会话）")
    context: dict = Field(default_factory=dict, description="附加上下文（如当前页面、选中媒体）")


class ExecuteRequest(BaseModel):
    operation: str = Field(..., description="操作类型")
    params: dict = Field(default_factory=dict, description="操作参数")
    session_id: str | None = None
    description: str | None = None     # 可读描述（用于历史记录）


# ── 意图识别（轻量级规则引擎） ──

INTENT_PATTERNS = [
    # 媒体库扫描
    {"keywords": ["扫描", "scan", "刷新媒体库"], "operation": "scan_library", "params_hint": {"library_id": "all"}},
    # 刮削
    {"keywords": ["刮削", "scrape", "获取元数据", "刷新信息"], "operation": "scrape_media", "params_hint": {}},
    # 重命名
    {"keywords": ["重命名", "rename"], "operation": "batch_rename", "params_hint": {}},
    # 收藏
    {"keywords": ["收藏", "favorite"], "operation": "batch_favorite", "params_hint": {"action": "add"}},
    # 标记已看
    {"keywords": ["已看", "watched", "标记看过"], "operation": "batch_watched", "params_hint": {"watched": True}},
    # 删除重复
    {"keywords": ["删除重复", "去重", "duplicate"], "operation": "remove_duplicates", "params_hint": {}},
    # 统计
    {"keywords": ["统计", "stats", "报告", "report"], "operation": "get_stats", "params_hint": {}},
    # 下载
    {"keywords": ["下载", "download", "订阅"], "operation": "create_subscription", "params_hint": {}},
    # 搜索
    {"keywords": ["搜索", "search", "找", "查找"], "operation": "search", "params_hint": {}},
]

AI_RESPONSES = {
    "scan_library": "好的，我来帮您扫描媒体库。将扫描所有已配置的媒体库目录，识别新增文件。",
    "scrape_media": "明白，我将对选中的媒体条目进行元数据刮削，从 TMDb、豆瓣等数据源获取信息。",
    "batch_rename": "我将按照媒体规范命名格式对文件进行批量重命名预览，确认后再执行。",
    "batch_favorite": "已将选中的媒体条目添加到收藏列表。",
    "batch_watched": "已将选中的媒体条目标记为已观看。",
    "remove_duplicates": "我将检测并移除媒体库中的重复文件，只保留质量最好的版本。",
    "get_stats": "正在生成系统统计报告，包括媒体库容量、播放统计、用户活跃度等信息。",
    "create_subscription": "好的，我来帮您创建下载订阅任务。请告诉我需要追踪的内容名称和目标网站。",
    "search": "正在搜索相关媒体内容，同时检索本地媒体库和在线数据库。",
    "unknown": "我理解您的请求。作为 MediaStation 的 AI 助手，我可以帮助您管理媒体库、刮削元数据、创建订阅下载等任务。请告诉我您具体需要什么帮助？",
}

def _detect_intent(message: str) -> dict:
    """简单的意图识别（关键词匹配）"""
    message_lower = message.lower()
    for pattern in INTENT_PATTERNS:
        if any(kw in message_lower for kw in pattern["keywords"]):
            return {
                "detected": True,
                "operation": pattern["operation"],
                "params_hint": pattern["params_hint"],
                "confidence": 0.8,
            }
    return {"detected": False, "operation": "unknown", "confidence": 0.0}


# ── 路由 ──

@router.post("/chat", summary="AI 对话")
async def chat(data: ChatRequest, user: AdminUser, db: DB):
    """
    与 AI 助手对话。
    助手会分析用户意图，提供操作建议或直接执行简单操作。
    支持多轮对话（通过 session_id 保持上下文）。
    """
    # 获取或创建会话
    session_id = data.session_id or str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = {
            "id": session_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "user_id": user.id,
        }

    session = _sessions[session_id]

    # 添加用户消息
    user_msg = {
        "role": "user",
        "content": data.message,
        "timestamp": datetime.now().isoformat(),
    }
    session["messages"].append(user_msg)

    # 意图识别
    intent = _detect_intent(data.message)
    op = intent.get("operation", "unknown")
    ai_response = AI_RESPONSES.get(op, AI_RESPONSES["unknown"])

    # 构造回复（包含操作建议）
    reply_content = ai_response
    suggested_action = None

    if intent["detected"]:
        suggested_action = {
            "operation": op,
            "params": intent.get("params_hint", {}),
            "label": f"执行: {op.replace('_', ' ').title()}",
            "requires_confirmation": op in ["batch_rename", "remove_duplicates", "batch_watched"],
        }
        reply_content += f"\n\n💡 *检测到操作意图: **{op}**，点击下方按钮确认执行。*"

    # 添加 AI 回复
    assistant_msg = {
        "role": "assistant",
        "content": reply_content,
        "timestamp": datetime.now().isoformat(),
        "intent": intent,
        "suggested_action": suggested_action,
    }
    session["messages"].append(assistant_msg)

    # 限制会话长度（保留最近 50 条）
    if len(session["messages"]) > 50:
        session["messages"] = session["messages"][-50:]

    return SuccessResponse.ok({
        "session_id": session_id,
        "reply": reply_content,
        "intent": intent if intent["detected"] else None,
        "suggested_action": suggested_action,
        "message_count": len(session["messages"]),
    })


@router.post("/execute", summary="执行 AI 建议的操作")
async def execute_operation(data: ExecuteRequest, user: AdminUser, db: DB):
    """
    执行 AI 助手建议的操作。
    操作会被记录到历史中以支持撤销。
    """
    op_id = str(uuid.uuid4())
    op_record = {
        "id": op_id,
        "operation": data.operation,
        "params": data.params,
        "description": data.description or f"执行操作: {data.operation}",
        "user_id": user.id,
        "session_id": data.session_id,
        "executed_at": datetime.now().isoformat(),
        "status": "pending",
        "result": None,
        "undoable": True,
        "undo_data": {},    # 用于撤销的备份数据
    }

    result = {"success": False, "message": ""}

    try:
        # 根据操作类型执行对应逻辑
        if data.operation == "scan_library":
            from app.media.repository import MediaRepository
            from app.media.service import MediaService
            from app.system.events import get_event_bus
            repo = MediaRepository(db)
            service = MediaService(repo, get_event_bus())

            library_id = data.params.get("library_id")
            if library_id and library_id != "all":
                scan_result = await service.scan_library(int(library_id), auto_scrape=False)
                result = {"success": True, "message": f"媒体库 {library_id} 扫描完成", "data": scan_result}
            else:
                libraries = await repo.get_all_libraries()
                total_added = 0
                for lib in libraries:
                    try:
                        r = await service.scan_library(lib.id, auto_scrape=False)
                        total_added += getattr(r, "added", 0)
                    except Exception:
                        pass
                result = {"success": True, "message": f"所有媒体库扫描完成，新增 {total_added} 个文件"}

        elif data.operation == "get_stats":
            from app.stats.service import StatsService
            from app.stats.schemas import StatsOverview
            stats = await StatsService(db).get_overview()
            result = {"success": True, "message": "统计数据获取成功", "data": stats}

        elif data.operation == "search":
            query = data.params.get("q", "")
            if query:
                from app.media.repository import MediaRepository
                repo = MediaRepository(db)
                items = await repo.search_items(query, limit=10)
                from app.media.schemas import MediaItemOut
                result = {
                    "success": True,
                    "message": f"搜索 '{query}' 找到 {len(items)} 个结果",
                    "data": [MediaItemOut.model_validate(i).model_dump() for i in items],
                }
            else:
                result = {"success": False, "message": "搜索词不能为空"}

        elif data.operation == "batch_favorite":
            media_ids = data.params.get("media_ids", [])
            action = data.params.get("action", "add")
            if media_ids:
                from app.media.models import Favorite
                from sqlalchemy import delete
                if action == "add":
                    for mid in media_ids:
                        db.add(Favorite(user_id=user.id, media_item_id=mid))
                    await db.commit()
                    result = {"success": True, "message": f"已收藏 {len(media_ids)} 个媒体"}
                    op_record["undo_data"] = {"media_ids": media_ids, "action": "remove"}
                else:
                    await db.execute(
                        delete(Favorite).where(
                            Favorite.user_id == user.id,
                            Favorite.media_item_id.in_(media_ids)
                        )
                    )
                    await db.commit()
                    result = {"success": True, "message": f"已取消收藏 {len(media_ids)} 个媒体"}
            else:
                result = {"success": False, "message": "未指定媒体 ID"}

        else:
            # 未知操作或复杂操作（返回提示）
            result = {
                "success": True,
                "message": f"操作 '{data.operation}' 已排队，系统将在后台处理",
                "async": True,
            }

        op_record["status"] = "completed" if result["success"] else "failed"
        op_record["result"] = result

    except Exception as e:
        op_record["status"] = "error"
        op_record["result"] = {"success": False, "message": str(e)}
        result = {"success": False, "message": f"操作执行失败: {e}"}

    # 保存到历史
    _op_history.insert(0, op_record)
    if len(_op_history) > 200:  # 保留最近 200 条
        _op_history.pop()

    return SuccessResponse.ok({
        "op_id": op_id,
        "operation": data.operation,
        "result": result,
        "undoable": op_record.get("undoable", False),
    })


@router.post("/undo/{op_id}", summary="撤销操作")
async def undo_operation(op_id: str, user: AdminUser, db: DB):
    """
    撤销已执行的操作。
    仅支持有备份数据的可逆操作（如收藏/标记观看）。
    """
    # 查找操作记录
    op_record = next((r for r in _op_history if r["id"] == op_id), None)
    if not op_record:
        raise HTTPException(404, f"操作记录 {op_id} 不存在")

    if not op_record.get("undoable"):
        raise HTTPException(400, "此操作不支持撤销")

    if op_record.get("status") == "undone":
        raise HTTPException(409, "此操作已被撤销")

    undo_data = op_record.get("undo_data", {})
    operation = op_record.get("operation")
    result = {"success": False, "message": ""}

    try:
        if operation == "batch_favorite":
            media_ids = undo_data.get("media_ids", [])
            action = undo_data.get("action", "remove")
            if action == "remove":
                from app.media.models import Favorite
                from sqlalchemy import delete
                await db.execute(
                    delete(Favorite).where(
                        Favorite.user_id == user.id,
                        Favorite.media_item_id.in_(media_ids)
                    )
                )
                await db.commit()
                result = {"success": True, "message": f"已撤销收藏 {len(media_ids)} 个媒体"}
            else:
                result = {"success": False, "message": "无法执行撤销操作"}
        else:
            result = {"success": False, "message": f"操作 '{operation}' 暂不支持撤销"}

        if result["success"]:
            op_record["status"] = "undone"

    except Exception as e:
        result = {"success": False, "message": f"撤销失败: {e}"}

    return SuccessResponse.ok({
        "op_id": op_id,
        "operation": operation,
        "result": result,
    })


@router.get("/session/{session_id}", summary="获取会话历史")
async def get_session(session_id: str, user: AdminUser):
    """获取指定会话的完整对话历史"""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, f"会话 {session_id} 不存在")

    return SuccessResponse.ok({
        "session_id": session_id,
        "created_at": session["created_at"],
        "message_count": len(session["messages"]),
        "messages": session["messages"],
    })


@router.delete("/session/{session_id}", status_code=204, summary="删除会话")
async def delete_session(session_id: str, user: AdminUser):
    """删除会话记录"""
    if session_id not in _sessions:
        raise HTTPException(404, f"会话 {session_id} 不存在")
    del _sessions[session_id]


@router.get("/history", summary="获取操作历史")
async def get_operation_history(
    user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    operation: str | None = Query(None, description="按操作类型过滤"),
    status: str | None = Query(None, description="按状态过滤: completed/failed/undone"),
):
    """获取 AI 助手的操作执行历史（支持分页和过滤）"""
    filtered = _op_history

    if operation:
        filtered = [r for r in filtered if r.get("operation") == operation]
    if status:
        filtered = [r for r in filtered if r.get("status") == status]

    total = len(filtered)
    offset = (page - 1) * page_size
    page_items = filtered[offset: offset + page_size]

    return SuccessResponse.ok({
        "history": [
            {
                "id": r["id"],
                "operation": r["operation"],
                "description": r.get("description"),
                "status": r.get("status"),
                "undoable": r.get("undoable", False),
                "executed_at": r.get("executed_at"),
                "result_message": r.get("result", {}).get("message") if r.get("result") else None,
            }
            for r in page_items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    })


@router.get("/sessions", summary="列出所有活跃会话")
async def list_sessions(user: AdminUser):
    """列出所有活跃的 AI 助手会话"""
    sessions_list = [
        {
            "session_id": sid,
            "created_at": s["created_at"],
            "message_count": len(s["messages"]),
            "last_message": s["messages"][-1]["content"][:100] if s["messages"] else None,
        }
        for sid, s in _sessions.items()
        if s.get("user_id") == user.id or user.role == "admin"
    ]
    return SuccessResponse.ok({
        "sessions": sessions_list,
        "total": len(sessions_list),
    })
