"""規則模組共享的訊號比對機械（私有用）。

英文詞界以 ASCII lookaround 邊界定義（非 \\b——CJK 同屬 \\w，
混合詞如「buy 鑽戒」用 \\b 會漏判）；中文子字串；
多命中按 levels 順序取第一。比對用形 = match_form（保留詞界）。
"""

from __future__ import annotations

import re

from rules.cjk_norm import match_form

Level = tuple[str, tuple[re.Pattern[str], ...], tuple[str, ...]]


def compile_english(terms: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(
        re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")
        for term in terms
    )


def classify_first_match(keyword: str, levels: tuple[Level, ...], default: str) -> str:
    """按 levels 順序首命中；無命中回 default。"""
    text = match_form(keyword)
    if not text:
        return default
    for name, english_patterns, chinese_terms in levels:
        if any(pattern.search(text) for pattern in english_patterns):
            return name
        if any(term in text for term in chinese_terms):
            return name
    return default
