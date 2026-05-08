"""
番号识别引擎 (ParseCode)

从文件名/路径中识别番号，判断是否 18+ 内容。
支持格式：
- FC2-PPV-xxxxxx
- HEY-xxx
- 10MU-xxx
- 3Q-xxx
- ABC-123 等通用格式
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedCode:
    """解析后的番号信息"""
    code: str = ""               # 提取的番号（标准化格式）
    original: str = ""           # 原始匹配文本
    is_adult: bool = False      # 是否 18+ 内容
    code_type: str = ""         # 类别: fc2, hey, general, western
    cleaned_title: str = ""     # 清理后的标题（用于搜索）
    confidence: float = 0.0     # 匹配置信度 (0.0-1.0)


# 番号正则表达式（按优先级排序）
CODE_PATTERNS = [
    # FC2-PPV 系列（最高优先级，格式最固定）
    (re.compile(r"FC2[_\-\.]?(?:PPV[_\-\.]?)?(\d{6,7})", re.IGNORECASE), "fc2"),
    # HEY 系列
    (re.compile(r"HEY[_\-\.]?(\d{3})", re.IGNORECASE), "hey"),
    # 10MU 系列
    (re.compile(r"10MU[_\-\.]?(\d{3})", re.IGNORECASE), "10mu"),
    # 3Q 系列
    (re.compile(r"3Q[_\-\.]?(\d{3})", re.IGNORECASE), "3q"),
    # 1Pondo 系列
    (re.compile(r"1Pondo[_\-\.]?(\d{6})", re.IGNORECASE), "1pondo"),
    # 9KG 系列 (9KGirl 等)
    (re.compile(r"9KG(?:irl)?[_\-\.]?(\d{3,5})", re.IGNORECASE), "9kg"),
    # 通用格式：2-4个大写字母 + 数字（ABC-123, MIDE-xxx）
    (re.compile(r"([A-Z]{2,4})[_\-\.]?(\d{2,5})"), "general"),
    # 数字+字母格式（例如 123ABC-456）
    (re.compile(r"(\d{2,4})([A-Z]{2,4})[_\-\.]?(\d{2,5})", re.IGNORECASE), "mixed"),
]

# 18+ 关键词（用于辅助判断）
ADULT_KEYWORDS = [
    "18+", "adult", "uncensored", "censored", "jav", "av",
    "fc2", "hey", "10mu", "3q", "1pondo",
    "番号", "无码", "有码", "步兵", "骑兵",
    # 9KG 相关关键词
    "9kg", "9kgirl", "9kgirls",
    "snis", "nhdta", "heyzo", "dell", "toha",
]

# 已知 18+ 番号前缀（用于快速判断）
KNOWN_PREFIXES = {
    "FC2", "HEY", "10MU", "3Q", "1PONDO",
    "ABC", "MIDE", "GOPJ", "S-CUTE", "CARIB",
    "MKBD", "MEYD", "JUY", "DANDY", "EBOD",
    "STARS", "WANZ", "MIGD", "IPX", "IPZ",
    "ABP", "ADN", "AFN", "AIG", "ANA", "APN",
    "ATID", "AUKG", "BAC", "BANK", "BBAN",
    "BCP", "BEF", "BF", "BID", "BLK", "BNG",
    # 9KG 相关番号
    "SNIS", "NHDTA", "HEYZO", "TOHA", "LAFBD",
    "MXGS", "HND", "IST", "JBD", "BOKD",
    "MIDE", "ADN", "PPPD", "JUL", "SHKD",
}


class CodeParser:
    """番号解析器"""

    def __init__(self):
        self.patterns = CODE_PATTERNS
        self.adult_keywords = [kw.lower() for kw in ADULT_KEYWORDS]

    def parse(self, filename: str, folder_path: str = "") -> ParsedCode | None:
        """
        从文件名（和文件夹路径）中解析番号

        Args:
            filename: 文件名（不含路径）
            folder_path: 文件夹路径（可选，用于辅助判断）

        Returns:
            ParsedCode 对象，如果不匹配则返回 None
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not filename:
            logger.debug(f"[ParseCode] 文件名为空")
            return None

        # 组合文本用于匹配
        search_text = f"{filename} {os.path.basename(folder_path) if folder_path else ''}"
        logger.debug(f"[ParseCode] 搜索文本: '{search_text}'")

        # 尝试所有正则模式
        for pattern, code_type in self.patterns:
            match = pattern.search(search_text)
            if match:
                code = self._normalize_code(match.group(0), code_type)
                logger.info(f"[ParseCode] ✓ 匹配成功! 模式: {code_type}, 番号: {code}, 原始匹配: {match.group(0)}")
                return ParsedCode(
                    code=code,
                    original=match.group(0),
                    is_adult=True,
                    code_type=code_type,
                    cleaned_title=self._clean_title(filename, code),
                    confidence=0.9 if code_type == "fc2" else 0.7,
                )

        logger.debug(f"[ParseCode] ❌ 正则匹配失败，尝试已知前缀匹配...")

        # 尝试匹配已知前缀
        upper_name = filename.upper()
        for prefix in KNOWN_PREFIXES:
            if prefix in upper_name:
                # 尝试提取完整番号
                idx = upper_name.find(prefix)
                remaining = filename[idx:]
                # 提取番号部分
                code_match = re.search(r"([A-Z]{2,4}[_\-\.]?\d{2,5})", remaining, re.IGNORECASE)
                if code_match:
                    logger.info(f"[ParseCode] ✓ 已知前缀匹配成功! 前缀: {prefix}, 番号: {code_match.group(1)}")
                    return ParsedCode(
                        code=self._normalize_code(code_match.group(1), "general"),
                        original=code_match.group(1),
                        is_adult=True,
                        code_type="general",
                        cleaned_title=self._clean_title(filename, code_match.group(1)),
                        confidence=0.6,
                    )

        logger.debug(f"[ParseCode] ❌ 所有匹配方式均失败，文件 '{filename}' 不符合番号格式")
        return None

    def is_adult_content(self, filename: str, folder_path: str = "") -> bool:
        """
        判断文件是否是 18+ 内容

        Args:
            filename: 文件名
            folder_path: 文件夹路径

        Returns:
            True 如果是 18+ 内容
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 1. 检查是否匹配番号格式
        parsed = self.parse(filename, folder_path)
        if parsed:
            logger.info(f"[is_adult_content] ✓ 文件 '{filename}' 匹配番号格式 {parsed.code}，判定为 18+ 内容")
            return True

        # 2. 检查关键词
        text = f"{filename} {folder_path}".lower()
        matched_keywords = [kw for kw in self.adult_keywords if kw in text]
        if matched_keywords:
            logger.info(f"[is_adult_content] ✓ 文件 '{filename}' 匹配成人关键词 {matched_keywords}，判定为 18+ 内容")
            return True

        logger.info(f"[is_adult_content] ❌ 文件 '{filename}' 不符合 18+ 内容特征")
        return False

    def _normalize_code(self, code: str, code_type: str) -> str:
        """
        标准化番号格式

        Examples:
            FC2-PPV-123456 → FC2-PPV-123456
            HEY_001        → HEY-001
            ABC123         → ABC-123
        """
        if code_type == "fc2":
            # FC2 格式：FC2-PPV-123456
            num = re.search(r"\d{6,7}", code)
            if num:
                return f"FC2-PPV-{num.group(0)}"

        # 通用格式：将分隔符统一为 "-"
        code = re.sub(r"[_\.\s]+", "-", code)

        # 确保字母部分和数字部分之间有 "-"
        if "-" not in code:
            match = re.match(r"([A-Za-z]+)(\d+)", code)
            if match:
                code = f"{match.group(1)}-{match.group(2)}"

        return code.upper()

    def _clean_title(self, filename: str, code: str) -> str:
        """
        从文件名中移除番号，返回清理后的标题
        """
        # 移除番号
        title = filename
        for pattern in [code, code.replace("-", "_"), code.replace("-", ".")]:
            title = title.replace(pattern, "")

        # 移除扩展名
        title = os.path.splitext(title)[0]

        # 移除常见分隔符
        title = re.sub(r"[_\-.\s]+", " ", title)

        # 移除分辨率、编码等后缀（复用 scanner.py 的逻辑）
        title = re.sub(r"2160p?|1080[pi]?|720p?|480p?", "", title, flags=re.IGNORECASE)
        title = re.sub(r"HEVC|H\.?265|H\.?264|AV1", "", title, flags=re.IGNORECASE)
        title = re.sub(r"10bit|8bit", "", title, flags=re.IGNORECASE)

        return title.strip()


def parse_code(filename: str, folder_path: str = "") -> ParsedCode | None:
    """
    便捷函数：解析番号

    Usage:
        result = parse_code("HEY-001.mp4")
        if result:
            print(result.code)  # HEY-001
            print(result.is_adult)  # True
    """
    parser = CodeParser()
    return parser.parse(filename, folder_path)


def is_adult_content(filename: str, folder_path: str = "") -> bool:
    """
    便捷函数：判断是否是 18+ 内容

    Usage:
        if is_adult_content("FC2-PPV-123456.mp4"):
            print("This is adult content")
    """
    parser = CodeParser()
    return parser.is_adult_content(filename, folder_path)


# 导出
__all__ = [
    "ParsedCode",
    "CodeParser",
    "parse_code",
    "is_adult_content",
]
