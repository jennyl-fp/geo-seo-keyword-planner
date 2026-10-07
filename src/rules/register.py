"""語域分類：口語（廣東話）／書面語／中性（日常需求 #4；ADR-016）。

詞表來源：2026-10-06 dogfood 觀察 + HK 廣東話書面慣用。
口語標記：邊度 邊間 邊款 邊個 點樣 點解 唔 嘅 咩 咁 㗎 喎 嚟 冇 咗 緊 喇 係咩 係咪
  （「係」不入表——「關係」「體係」誤中風險，改用係咩/係咪兩詞）
書面語標記：如何 什麼 為何 何時 購買 收費 價格 比較 推薦 評價 是否 以及
多命中口語優先；皆無 → neutral。純函數、確定性（ADR-009）。
"""

from __future__ import annotations

from rules.cjk_norm import match_form

REGISTERS = ("colloquial", "written", "neutral")

_COLLOQUIAL_ZH = (
    "邊度", "邊間", "邊款", "邊個", "點樣", "點解", "唔", "嘅", "咩",
    "咁", "㗎", "喎", "嚟", "冇", "咗", "緊", "喇", "係咩", "係咪",
)
_WRITTEN_ZH = (
    "如何", "什麼", "為何", "何時", "購買", "收費", "價格", "比較",
    "推薦", "評價", "是否", "以及",
)


def classify_register(keyword: str) -> str:
    """單一關鍵字 → colloquial / written / neutral。"""
    text = match_form(keyword)
    if not text:
        return "neutral"
    if any(marker in text for marker in _COLLOQUIAL_ZH):
        return "colloquial"
    if any(marker in text for marker in _WRITTEN_ZH):
        return "written"
    return "neutral"
