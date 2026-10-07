"""評分（T1.11；規格 §5 一條公式 + GSC 加分）。

score = log1p(volume)/log1p(批次最大量) × KD可行率 × intent權重 × 100
        + strike_distance_bonus（僅 GSC 已接時）

  KD可行率  = 1 − 0.9 × (KD / 80)（KD ≥ 80 → 0.1；無 KD → 0.5）
  intent權重 = transactional 1.0 / commercial 0.8 / informational 0.6 /
              navigational 0.3
  strike    = 自家排名 11–30 → +15 分（前 10 名不加——已經贏了）

來源：規格 v2 §5；「無 volume 的問句照樣列出」原則依據
https://www.semrush.com/blog/how-to-choose-long-tail-keywords/
（無量 ≠ 無需求，規格 §9 基礎組）。每行輸出附組件值（可解釋）。

組件顯示值四捨五入（volume 3dp / KD 3dp / 分數 1dp），
score 由捨入後 base + strike 構成（顯示一致性）；
排序：分數降序、關鍵字字典序 tie-break（ADR-009）。
own_positions 鍵為正規化形（GscClient.top_queries 輸出直接可用）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rules.cjk_norm import normalize_keyword

INTENT_WEIGHTS = {
    "transactional": 1.0,
    "commercial": 0.8,
    "informational": 0.6,
    "navigational": 0.3,
}
_DEFAULT_INTENT_WEIGHT = 0.6

KD_HARD_CAP = 80
NO_KD_FEASIBILITY = 0.5

STRIKE_BONUS = 15.0
STRIKE_MIN_POSITION = 11
STRIKE_MAX_POSITION = 30


@dataclass(frozen=True)
class KeywordForScoring:
    keyword: str
    volume: int | None
    difficulty: int | None
    intent: str


@dataclass(frozen=True)
class ScoreComponents:
    volume_component: float
    kd_feasibility: float
    intent_weight: float
    base_score: float
    strike_bonus: float


@dataclass(frozen=True)
class ScoredKeyword:
    keyword: str
    volume: int | None
    difficulty: int | None
    intent: str
    own_position: float | None
    has_volume_data: bool
    score: float
    components: ScoreComponents


def kd_feasibility(difficulty: int | None) -> float:
    if difficulty is None:
        return NO_KD_FEASIBILITY
    if difficulty >= KD_HARD_CAP:
        return 0.1
    return round(1 - 0.9 * (max(difficulty, 0) / KD_HARD_CAP), 3)


def volume_component(volume: int | None, batch_max: int | None) -> float:
    if volume is None or batch_max is None or batch_max <= 0:
        return 0.0
    return round(math.log1p(volume) / math.log1p(batch_max), 3)


def score_keywords(
    entries: list[KeywordForScoring],
    own_positions: dict[str, float] | None = None,
) -> list[ScoredKeyword]:
    """批次評分；own_positions（正規化鍵 → GSC 排名）可選，未接 GSC 就 None。"""
    positions = own_positions or {}
    measured = [
        entry.volume
        for entry in entries
        if entry.volume is not None and entry.volume > 0
    ]
    batch_max = max(measured) if measured else None

    results: list[ScoredKeyword] = []
    for entry in entries:
        key = normalize_keyword(entry.keyword)
        position = positions.get(key)
        strike = (
            STRIKE_BONUS
            if position is not None and STRIKE_MIN_POSITION <= position <= STRIKE_MAX_POSITION
            else 0.0
        )
        volume_part = volume_component(entry.volume, batch_max)
        kd_part = kd_feasibility(entry.difficulty)
        intent_weight = INTENT_WEIGHTS.get(entry.intent, _DEFAULT_INTENT_WEIGHT)
        base = round(volume_part * kd_part * intent_weight * 100, 1)
        results.append(
            ScoredKeyword(
                keyword=entry.keyword,
                volume=entry.volume,
                difficulty=entry.difficulty,
                intent=entry.intent,
                own_position=position,
                has_volume_data=entry.volume is not None,
                score=round(base + strike, 1),
                components=ScoreComponents(
                    volume_component=volume_part,
                    kd_feasibility=kd_part,
                    intent_weight=intent_weight,
                    base_score=base,
                    strike_bonus=strike,
                ),
            )
        )
    results.sort(key=lambda item: (-item.score, normalize_keyword(item.keyword)))
    return results
