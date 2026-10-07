"""Funnel 三分類（T1.7；規格 §4.2）。

來源：GEO關鍵字研究工具-簡易版規格 v2 §4.2；BOFU/MOFU/TOFU 訊號依據
https://searchengineland.com/guide/bofu-keywords 、
https://searchengineland.com/guide/mofu-keywords 、
https://searchengineland.com/guide/tofu-keywords（規格 §9 基礎組）。

多命中：BOFU > MOFU；其餘一律 TOFU。
"""

from __future__ import annotations

from rules._signals import classify_first_match, compile_english

FUNNELS = ("bofu", "mofu", "tofu")

_BOFU_EN = (
    "price", "cost", "buy", "discount", "coupon", "quote", "book",
    "demo", "free trial",
)
_BOFU_ZH = ("價錢", "幾錢", "優惠", "購買", "預約", "試用")

_MOFU_EN = ("vs", "best", "top", "review", "alternative", "compare")
_MOFU_ZH = ("推薦", "比較", "邊間", "邊款", "點揀")

_LEVELS = (
    ("bofu", compile_english(_BOFU_EN), _BOFU_ZH),
    ("mofu", compile_english(_MOFU_EN), _MOFU_ZH),
)


def classify_funnel(keyword: str) -> str:
    """單一關鍵字 → bofu / mofu / tofu。"""
    return classify_first_match(keyword, _LEVELS, default="tofu")
