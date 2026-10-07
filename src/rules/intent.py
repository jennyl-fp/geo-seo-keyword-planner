"""Intent 四分類（T1.6；規格 §4.1 簡版詞表）。

來源：GEO關鍵字研究工具規格書（v2）§4.1；
詞表總表依據 https://searchengineland.com/guide/search-intent-seo（規格 §9 基礎組）。

比對規則：
  - 比對用形 = match_form（保留詞界；normalize_keyword 的 CJK 去空白
    會破壞英文詞界）
  - 英文訊號：詞界比對——邊界以 ASCII 字母/數字定義（見 _signals.py）
  - 中文訊號：子字串
  - 多命中：按 §4.1 表序取第一（transactional → commercial →
    navigational → informational）
  - 無命中：預設 informational
  - 已知接受的誤差（規格 §4.1）：「best X to buy」判 transactional
"""

from __future__ import annotations

from rules._signals import classify_first_match, compile_english

INTENTS = ("transactional", "commercial", "navigational", "informational")

_TRANSACTIONAL_EN = (
    "buy", "price", "cost", "deal", "discount", "sale", "order",
    "shop", "cheap", "coupon", "free trial", "quote", "book",
)
_TRANSACTIONAL_ZH = ("報價", "價錢", "幾錢", "優惠", "購買", "訂購", "預約", "試用")

_COMMERCIAL_EN = (
    "best", "top", "review", "vs", "compare", "alternative", "pros and cons",
)
_COMMERCIAL_ZH = ("推薦", "比較", "評價", "評測", "開箱", "邊間", "邊款")

_NAVIGATIONAL_EN = ("login", "sign in", "official", "website")
_NAVIGATIONAL_ZH = ("登入", "官網")

_INFORMATIONAL_EN = ("how", "what", "why", "when", "guide", "tutorial", "tips", "ideas")
_INFORMATIONAL_ZH = ("如何", "什麼", "為何", "點樣", "點解", "教學", "入門", "懶人包")

_LEVELS = (
    ("transactional", compile_english(_TRANSACTIONAL_EN), _TRANSACTIONAL_ZH),
    ("commercial", compile_english(_COMMERCIAL_EN), _COMMERCIAL_ZH),
    ("navigational", compile_english(_NAVIGATIONAL_EN), _NAVIGATIONAL_ZH),
    ("informational", compile_english(_INFORMATIONAL_EN), _INFORMATIONAL_ZH),
)


def classify_intent(keyword: str) -> str:
    """單一關鍵字 → transactional / commercial / navigational / informational。"""
    return classify_first_match(keyword, _LEVELS, default="informational")
