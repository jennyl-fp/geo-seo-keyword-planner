"""頁面類型 → 允許的 search intent（日常需求 #1；ADR-014）。

來源：需求方日常工作流程（2026-10-07）；intent 定義依據
https://searchengineland.com/guide/search-intent-seo（規格 §9 基礎組）。
對照表為啟發式，調整須立 ADR：
  blog    → informational + commercial（指南／比較內容）
  service → transactional + commercial（服務／產品頁）
  home    → navigational + transactional（品牌主頁）
  any     → 不過濾
"""

from __future__ import annotations

PAGE_INTENTS = {
    "blog": ("informational", "commercial"),
    "service": ("transactional", "commercial"),
    "home": ("navigational", "transactional"),
    "any": ("transactional", "commercial", "navigational", "informational"),
}


def intent_allowed(intent: str, page_type: str = "blog") -> bool:
    allowed = PAGE_INTENTS.get(page_type)
    if allowed is None:
        raise ValueError(f"未知 page_type：{page_type}（可用：{sorted(PAGE_INTENTS)}）")
    return intent in allowed
