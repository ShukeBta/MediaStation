#!/usr/bin/env python3
"""修复 _is_title_relevant 函数"""
import re

with open('app/subscribe/service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 使用正则表达式找到并替换函数
pattern = r'def _is_title_relevant\(keyword: str, title: str\) -> bool:.*?return False'

replacement = '''def _is_title_relevant(keyword: str, title: str) -> bool:
    """检查搜索结果标题是否与关键词真正相关
    
    避免 "hoppers" 误匹配 "grasshoppers" 这类子串误判。
    中文关键词：标题包含关键词即认为相关（允许部分匹配）
    """
    if not keyword or not title:
        return False
    keyword_lower = keyword.lower().strip()
    title_lower = title.lower()
    
    # 中文关键词（包含中文字符）
    if re.search(r"[\\u4e00-\\u9fff]", keyword_lower):
        is_match = keyword_lower in title_lower
        logger.debug(f"[_is_title_relevant] 中文关键词 '{keyword}' vs '{title[:50]}': {is_match}")
        return is_match
    
    # 英文关键词：使用 \\b 词边界匹配（避免 hoppers 匹配 grasshoppers）
    try:
        escaped_kw = re.escape(keyword_lower)
        # 允许常见分隔符（- _ . 空格）
        pattern = r"(?:^|\\s|\\-|_|\\.)" + escaped_kw + r"(?:\\s|\\-|_|\\.|$)"
        if re.search(pattern, title_lower):
            return True
    except re.error:
        pass
    
    # 降级：如果词边界匹配失败，使用简单的包含判断
    if keyword_lower in title_lower:
        logger.debug(f"[_is_title_relevant] 英文关键词降级匹配: '{keyword}' in '{title[:50]}'")
        return True
    
    return False'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content == content:
    print("ERROR: Pattern not found!")
else:
    with open('app/subscribe/service.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully updated _is_title_relevant function")
