"""關鍵字 CJK 正規化 — 所有跨源比對的地基（T1.1，正規化先行）。

規則（GEO關鍵字研究工具-簡易版規格 v2 §4.4，跨源比對前必做）：
  1. 小寫 + 去首尾空白
  2. 含 CJK 字元 → 移除所有內部空白（「鑽戒 推薦」=「鑽戒推薦」）
  3. 純拉丁 → 保留詞界（連續空白摺疊為單一空格）

CJK 判定範圍：CJK Unified Ideographs 及 Extension A
（U+3400–U+4DBF、U+4E00–U+9FFF）、Compatibility Ideographs
（U+F900–U+FAFF）、Extension B–H 補充平面（U+20000–U+3134A）。
"""

from __future__ import annotations

import re

CJK_CLASS = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003134a"

_CJK_RE = re.compile(f"[{CJK_CLASS}]")


def contains_cjk(text: str) -> bool:
    """True 若字串含任一 CJK 表意字元。"""
    return _CJK_RE.search(text) is not None


def normalize_keyword(raw: str) -> str:
    """正規化單一關鍵字，供跨源（Ahrefs/GKP/GSC）比對與去重使用。

    純函數、無日期或隨機成分 → 同輸入必同輸出（ADR-009 確定性）。
    冪等：normalize(normalize(x)) == normalize(x)。
    """
    text = raw.strip().lower()
    if not text:
        return ""
    if _CJK_RE.search(text):
        return "".join(text.split())
    return " ".join(text.split())


def match_form(raw: str) -> str:
    """規則比對用形（T1.6+）：小寫 + trim + 連續空白摺疊為單一空格，
    一律保留內部空白。

    與 normalize_keyword 的分工：normalize_keyword 是跨源比對「鍵」，
    會刪含 CJK 字串的所有內部空白——這會破壞英文詞界
    （「google ads login教學」→「googleadslogin教學」，login 漏判）。
    詞表訊號比對一律用本函數；英文詞界另以 ASCII 邊界定義（見 intent.py）。
    """
    text = raw.strip().lower()
    if not text:
        return ""
    return " ".join(text.split())
