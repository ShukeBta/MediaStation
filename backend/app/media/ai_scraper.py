"""
AI 辅助刮削服务
通过 LLM API（兼容 OpenAI 格式）对媒体元数据进行智能补充和修正。

功能：
- 剧情简介生成/翻译（中文优化）
- 中文标题翻译/优化
- 标签/关键词自动生成
- 模糊匹配纠错（TMDb 匹配到错误结果时 AI 纠正）
- 评分合理性校验

支持：OpenAI / 兼容 API (如 Ollama、vLLM、本地部署的模型)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── AI 刮削操作类型 ──
AI_SCRAPE_OVERVIEW = "overview"        # 生成/优化剧情简介
AI_SCRAPE_TITLE = "title"              # 翻译/优化中文标题
AI_SCRAPE_TAGS = "tags"                # 生成标签
AI_SCRAPE_VALIDATE = "validate"        # 验证刮削结果是否合理
AI_SCRAPE_ALL = "all"                  # 全部操作


@dataclass
class AIScrapeResult:
    """AI 刮削结果"""
    success: bool
    overview: str | None = None       # 优化后的简介
    title: str | None = None          # 优化后的中文标题
    original_title: str | None = None # 修正的原名
    tags: list[str] = field(default_factory=list)
    is_valid: bool | None = None      # 验证结果（刮削是否匹配正确内容）
    confidence: float = 0.0           # AI 置信度 0-1
    error: str | None = None
    model_used: str = ""
    tokens_used: int = 0


@dataclass
class AIMessage:
    """Chat message"""
    role: str  # system / user / assistant
    content: str


class AIScraper:
    """AI 刮削器 — 基于 OpenAI 兼容 API"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        max_tokens: int = 1024,
        temperature: float = 0.3,   # 低温度保证稳定输出
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _chat_completion(self, messages: list[AIMessage]) -> dict:
        """调用 OpenAI Chat Completion API"""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},  # 要求 JSON 输出
        }
        resp = await self.client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def scrape(
        self,
        title: str,
        media_type: str,
        operations: list[str] | None = None,
        current_metadata: dict | None = None,
        file_name: str | None = None,
    ) -> AIScrapeResult:
        """
        执行 AI 刮削

        Args:
            title: 当前媒体标题
            media_type: movie / tv / anime
            operations: 要执行的操作列表，默认全部
            current_metadata: 已有的元数据（供 AI 参考/修正）
            file_name: 原始文件名（辅助识别）

        Returns:
            AIScrapeResult 包含所有操作的结果
        """
        if not self.is_configured():
            return AIScrapeResult(success=False, error="AI scraper not configured (no API key)")

        if operations is None:
            operations = [AI_SCRAPE_OVERVIEW, AI_SCRAPE_TITLE, AI_SCRAPE_TAGS, AI_SCRAPE_VALIDATE]

        result = AIScrapeResult(model_used=self.model)

        try:
            # 构建系统提示
            system_prompt = self._build_system_prompt(media_type, operations)

            # 构建用户消息
            user_content = self._build_user_prompt(
                title=title,
                media_type=media_type,
                current_metadata=current_metadata,
                file_name=file_name,
                operations=operations,
            )

            messages = [
                AIMessage(role="system", content=system_prompt),
                AIMessage(role="user", content=user_content),
            ]

            response = await self._chat_completion(messages)

            # 解析响应
            choice = response.get("choices", [{}])
            if not choice:
                return AIScrapeResult(success=False, error="Empty response from AI")

            text = choice[0].get("message", {}).get("content", "")
            usage = response.get("usage", {})
            result.tokens_used = usage.get("total_tokens", 0)

            # 解析 JSON 结果
            try:
                ai_data = json.loads(text)
            except json.JSONDecodeError:
                # 尝试提取 JSON 块
                import re
                match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if match:
                    ai_data = json.loads(match.group())
                else:
                    logger.warning(f"Failed to parse AI response as JSON: {text[:200]}")
                    return AIScrapeResult(success=False, error="Invalid JSON response", tokens_used=result.tokens_used)

            # 提取各字段
            result.success = True
            result.overview = ai_data.get("overview") if AI_SCRAPE_OVERVIEW in operations else None
            result.title = ai_data.get("title") if AI_SCRAPE_TITLE in operations else None
            result.original_title = ai_data.get("original_title")
            result.tags = ai_data.get("tags", []) if AI_SCRAPE_TAGS in operations else []
            result.is_valid = ai_data.get("is_valid") if AI_SCRAPE_VALIDATE in operations else None
            result.confidence = float(ai_data.get("confidence", 0.8))

            logger.info(f"AI scrape completed for '{title}': confidence={result.confidence}, tokens={result.tokens_used}")

        except httpx.HTTPStatusError as e:
            err_body = e.response.text[:300]
            logger.error(f"AI scrape HTTP error {e.response.status_code}: {err_body}")
            result.error = f"HTTP {e.response.status_code}: {err_body}"
        except Exception as e:
            logger.error(f"AI scrape error: {e}")
            result.error = str(e)

        return result

    def _build_system_prompt(self, media_type: str, operations: list[str]) -> str:
        """构建系统提示词"""
        type_label = {"movie": "电影", "tv": "电视剧", "anime": "动漫"}.get(media_type, media_type)

        prompt_parts = [
            f"你是一个专业的{type_label}元数据助手。你的任务是根据提供的信息，优化和补充媒体元数据。",
            "",
            "要求：",
            "- 所有文本输出使用简体中文",
            "- 保持客观准确，不要编造信息",
            "- 如果信息不足，明确标注'未知'",
            "- 输出必须是有效的 JSON 格式",
        ]

        op_instructions = []
        if AI_SCRAPE_OVERVIEW in operations:
            op_instructions.append("- overview: 生成或优化剧情简介，200-500字，突出故事核心和看点")
        if AI_SCRAPE_TITLE in operations:
            op_instructions.append("- title: 提供最佳中文标题（如果原标题不够好），original_title: 正确的外文原名")
        if AI_SCRAPE_TAGS in operations:
            op_instructions.append('- tags: 生成 3-8 个标签/关键词，如["科幻","动作","悬疑"]')
        if AI_SCRAPE_VALIDATE in operations:
            op_instructions.append("- is_valid: 布尔值，判断当前刮削的媒体信息是否与标题匹配（可能 TMDb 匹配错了）")
            op_instructions.append("- confidence: 0-1 的浮点数，表示整体置信度")

        if op_instructions:
            prompt_parts.append("")
            prompt_parts.append("本次需要完成的任务：")
            prompt_parts.extend(op_instructions)

        prompt_parts.extend([
            "",
            "输出 JSON 格式示例：",
            '{"overview":"...","title":"中文名","original_title":"Original Name","tags":["标签"],"is_valid":true,"confidence":0.95}',
        ])

        return "\n".join(prompt_parts)

    def _build_user_prompt(
        self,
        title: str,
        media_type: str,
        current_metadata: dict | None,
        file_name: str | None,
        operations: list[str],
    ) -> str:
        """构建用户消息"""
        type_label = {"movie": "电影", "tv": "电视剧", "anime": "动漫"}.get(media_type, "媒体")

        parts = [
            f"请为以下{type_label}优化元数据：",
            f"- 标题：{title}",
        ]

        if file_name:
            parts.append(f"- 文件名：{file_name}")

        if current_metadata:
            meta_lines = []
            if current_metadata.get("overview"):
                meta_lines.append(f"  当前简介：{current_metadata['overview'][:300]}...")
            if current_metadata.get("original_title"):
                meta_lines.append(f"  外文名：{current_metadata['original_title']}")
            if current_metadata.get("year"):
                meta_lines.append(f"  年份：{current_metadata['year']}")
            if current_metadata.get("genres"):
                meta_lines.append(f"  类型：{current_metadata['genres']}")
            if current_metadata.get("rating"):
                meta_lines.append(f"  评分：{current_metadata['rating']}")
            if meta_lines:
                parts.append("- 已有元数据：")
                parts.extend(meta_lines)

        parts.append("")
        parts.append(f"请完成以下操作：{', '.join(operations)}")
        parts.append("返回 JSON 格式的结果。")

        return "\n".join(parts)


# ── 全局单例 ─_
_ai_scraper: AIScraper | None = None


def get_ai_scraper() -> AIScraper:
    """获取全局 AI 刮削器实例"""
    global _ai_scraper
    if _ai_scraper is None:
        from app.config import get_settings
        settings = get_settings()
        _ai_scraper = AIScraper(
            api_key=getattr(settings, 'openai_api_key', ''),
            base_url=getattr(settings, 'openai_base_url', 'https://api.openai.com/v1'),
            model=getattr(settings, 'openai_model', 'gpt-4o-mini'),
        )
    return _ai_scraper
