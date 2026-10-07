"""問句偵測（T1.8；規格 §4.3）。

來源：GEO關鍵字研究工具-簡易版規格 v2 §4.3；問句挖掘概念依據
https://searchengineland.com/guide/people-also-ask（規格 §9 基礎組，
亦是 §6 報告 40–50 字 BLUF 指引出處）。

比對規則：
  - 英文：開頭詞 who/what/when/where/why/how/which/can/is/are，
    其後必須非 ASCII 字母/數字（詞界）——「whatsapp」「island」「canva」
    不得誤中
  - 中文：標記子字串 點樣/點解/如何/邊個/邊間/幾時/幾多/幾錢/咩/嗎/呢
  - 裸「點」不用（誤中 特點/賣點/地點——規格 §4.3 明示）
  - 比對用形 = match_form（保留詞界）
"""

from __future__ import annotations

import re

from rules.cjk_norm import match_form

_START_WORDS_EN = (
    "who", "what", "when", "where", "why", "how", "which", "can", "is", "are",
)
_MARKERS_ZH = (
    "點樣", "點解", "如何", "邊個", "邊間", "幾時", "幾多", "幾錢", "咩", "嗎", "呢",
)

_START_RE = re.compile(
    "(?:"
    + "|".join(re.escape(word) for word in _START_WORDS_EN)
    + ")(?![a-z0-9])"
)


def is_question(keyword: str) -> bool:
    """True 若關鍵字是問句（英文開頭詞或中文問句標記）。"""
    text = match_form(keyword)
    if not text:
        return False
    if _START_RE.match(text):
        return True
    return any(marker in text for marker in _MARKERS_ZH)
