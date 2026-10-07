"""Title tag 建議 + ≤580px 像素檢查（日常需求 #2；ADR-015）。

像素估算：字元類寬度表（約 16px Roboto 桌面 SERP 標題近似）——
CJK／全形 16、ASCII 窄字（i l j t f . , : ; ' | ! 空格）4、
小寫／數字 8、大寫 10（W/M 12）、其他 ASCII 8。
580px 上限出處：Google SERP 桌面標題截斷實務
（https://moz.com/learn/seo/title-tag）。
估算為近似值（±10%），供檢查與建議用，非排版精確測量。
建議模板 = primary keyword +「 | 品牌」；超限先棄品牌後綴。
"""

from __future__ import annotations

from dataclasses import dataclass

from rules.cjk_norm import contains_cjk

TITLE_MAX_PIXELS = 580

_NARROW_ASCII = set("iljtf.,:;'|! ")
_WIDE_LATIN = set("WM")


def _char_pixels(char: str) -> int:
    if contains_cjk(char) or ord(char) >= 0x3000:
        return 16
    if char in _NARROW_ASCII:
        return 4
    if char in _WIDE_LATIN:
        return 12
    if char.isascii() and char.isupper():
        return 10
    return 8


def estimate_title_pixels(title: str) -> int:
    """字元類寬度表加總（近似值；ADR-015）。"""
    return sum(_char_pixels(char) for char in title)


def check_title(title: str) -> tuple[int, bool]:
    """（像素估算, 是否符合 ≤580px）。"""
    pixels = estimate_title_pixels(title)
    return pixels, pixels <= TITLE_MAX_PIXELS


@dataclass(frozen=True)
class TitleSuggestion:
    title: str
    pixels: int
    fits: bool
    dropped_brand: bool


def suggest_title(primary: str, brand: str | None = None) -> TitleSuggestion:
    """primary keyword + 品牌後綴模板；超限先棄品牌。品牌仍在 → 標 fits=False
    讓使用者自行縮短 primary（工具不改寫關鍵字本身）。"""
    primary = primary.strip()
    if brand and brand.strip():
        title = f"{primary} | {brand.strip()}"
        pixels = estimate_title_pixels(title)
        if pixels <= TITLE_MAX_PIXELS:
            return TitleSuggestion(title=title, pixels=pixels, fits=True, dropped_brand=False)
    pixels = estimate_title_pixels(primary)
    return TitleSuggestion(
        title=primary,
        pixels=pixels,
        fits=pixels <= TITLE_MAX_PIXELS,
        dropped_brand=bool(brand and brand.strip()),
    )
