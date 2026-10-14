"""評分 v3（ADR-019：客戶排名可行性為主要考量）。

score = 100 × (0.60 × feasibility + 0.25 × volume_component + 0.15 × intent_weight)

  feasibility = max(KD可行率, 自家排名分)（自家排名有證據時永遠優先）
  KD可行率   = 1 − 0.9 × (KD / 80)（KD ≥ 80 → 0.1；無 KD → 0.5）
  自家排名分 = 1–3 → 1.00／4–10 → 0.95／11–20 → 0.85／21–30 → 0.70／
              31–50 → 0.55（相鄰詞匹配 × 0.85 折扣）
  intent權重 = transactional 1.0 / commercial 0.8 / informational 0.6 /
              navigational 0.3

自家排名來源：GSC top_queries + Ahrefs site-explorer/organic-keywords
（上層合併，取較佳名次）。相鄰匹配 = 正規化後互為子字串（≥2 字），
例：自家排「魚油」#7 → 候選「魚油功效」記相鄰 #7。

舊公式（v2，規格 §5）：volume × KD × intent × 100 + strike +15（11–30）
——dogfood（Amway 2026-10）證明 volume 主導會推高量低可行詞；
可行性現佔 60%，volume 降為 25% 調節。strike 獨立加分移除
（已內化進自家排名分，避免雙重計數）；STRIKE_* 常數保留供
report §6 自家排名機會節使用。

來源：「無 volume 的問句照樣列出」原則依據
https://www.semrush.com/blog/how-to-choose-long-tail-keywords/
（無量 ≠ 無需求，規格 §9 基礎組）。每行輸出附組件值（可解釋）。

組件顯示值四捨五入（volume 3dp / KD 3dp / feasibility 3dp / 分數 1dp）；
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

# report §6 自家排名機會節沿用（不參與 score，ADR-019）
STRIKE_MIN_POSITION = 11
STRIKE_MAX_POSITION = 30

# 可行性主導權重（合計 1.00，ADR-019）
FEASIBILITY_WEIGHT = 0.60
VOLUME_WEIGHT = 0.25
INTENT_WEIGHT = 0.15

# 自家排名 → 可行性分（上限, 分）；>50 不計（無證據）
OWN_POSITION_BANDS: tuple[tuple[int, float], ...] = (
    (3, 1.00),
    (10, 0.95),
    (20, 0.85),
    (30, 0.70),
    (50, 0.55),
)
# 相鄰詞（子字串）匹配折扣：證據力弱於精確匹配
ADJACENT_DISCOUNT = 0.85
_ADJACENT_MIN_LEN = 2

MATCH_EXACT = "exact"
MATCH_ADJACENT = "adjacent"
MATCH_NONE = "none"


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
    own_rank_component: float
    feasibility: float
    match_type: str
    base_score: float


@dataclass(frozen=True)
class ScoredKeyword:
    keyword: str
    volume: int | None
    difficulty: int | None
    intent: str
    own_position: float | None
    match_type: str
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


def own_rank_component(position: float | None) -> float:
    """自家名次 → 可行性分；>50 或無名次 → 0.0（無證據，回落 KD）。"""
    if position is None or position <= 0:
        return 0.0
    for cap, score in OWN_POSITION_BANDS:
        if position <= cap:
            return score
    return 0.0


def _find_own_position(
    key: str, positions: dict[str, float]
) -> tuple[float | None, str]:
    """精確匹配優先；無則相鄰（互為子字串，≥2 字）取最佳名次。"""
    exact = positions.get(key)
    if exact is not None:
        return exact, MATCH_EXACT
    best: float | None = None
    for own_key, position in positions.items():
        if len(own_key) < _ADJACENT_MIN_LEN or len(key) < _ADJACENT_MIN_LEN:
            continue
        if own_key in key or key in own_key:
            if best is None or position < best:
                best = position
    if best is not None:
        return best, MATCH_ADJACENT
    return None, MATCH_NONE


def score_keywords(
    entries: list[KeywordForScoring],
    own_positions: dict[str, float] | None = None,
) -> list[ScoredKeyword]:
    """批次評分；own_positions（正規化鍵 → 排名，GSC+Ahrefs 合併）可選。"""
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
        position, match_type = _find_own_position(key, positions)
        own_component = own_rank_component(position)
        if match_type == MATCH_ADJACENT:
            own_component = round(own_component * ADJACENT_DISCOUNT, 3)
        volume_part = volume_component(entry.volume, batch_max)
        kd_part = kd_feasibility(entry.difficulty)
        intent_weight = INTENT_WEIGHTS.get(entry.intent, _DEFAULT_INTENT_WEIGHT)
        feasibility = round(max(kd_part, own_component), 3)
        base = round(
            100
            * (
                FEASIBILITY_WEIGHT * feasibility
                + VOLUME_WEIGHT * volume_part
                + INTENT_WEIGHT * intent_weight
            ),
            1,
        )
        results.append(
            ScoredKeyword(
                keyword=entry.keyword,
                volume=entry.volume,
                difficulty=entry.difficulty,
                intent=entry.intent,
                own_position=position,
                match_type=match_type,
                has_volume_data=entry.volume is not None,
                score=base,
                components=ScoreComponents(
                    volume_component=volume_part,
                    kd_feasibility=kd_part,
                    intent_weight=intent_weight,
                    own_rank_component=own_component,
                    feasibility=feasibility,
                    match_type=match_type,
                    base_score=base,
                ),
            )
        )
    results.sort(key=lambda item: (-item.score, normalize_keyword(item.keyword)))
    return results
