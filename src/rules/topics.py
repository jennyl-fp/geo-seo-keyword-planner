"""Blog topic 打包（日常需求 #3/#5/#6；ADR-017）。

規則：
  - 硬性過濾：volume > 0（#3；無量測／0 量的詞不進 topic 包——
    注意 GEO prompts 不受此限，規格 §5「無量≠無需求」只適用問句層）
  - intent 匹配：page_type 對照表過濾（#1；page_intent.py，ADR-014）
  - register 偏好：any/written/colloquial（#4；register.py，ADR-016）
  - 打包：score 降序貪婪（#5/#6）——取最高分未分配詞做 primary，
    拉共享簽章（cluster.py _signatures，泛詞停用表已剔除）或
    同 parent_topic 的未分配詞，按 score 填滿最多 4 個 secondary
  - secondary < 2 → needs_more_keywords=True（不丟棄，交使用者擴充）
  - 確定性：排序 tie-break = 正規化關鍵字字典序（ADR-009）
"""

from __future__ import annotations

from dataclasses import dataclass

from rules.cjk_norm import normalize_keyword
from rules.cluster import _signatures
from rules.page_intent import intent_allowed
from rules.register import classify_register

MAX_SECONDARIES = 4
MIN_SECONDARIES = 2


@dataclass(frozen=True)
class TopicKeyword:
    keyword: str
    volume: int | None
    difficulty: int | None
    intent: str
    score: float = 0.0
    parent_topic: str | None = None


@dataclass(frozen=True)
class TopicPackage:
    primary: TopicKeyword
    secondaries: tuple[TopicKeyword, ...]
    total_volume: int
    register: str
    needs_more_keywords: bool


def _matches(primary: TopicKeyword, candidate: TopicKeyword) -> bool:
    primary_topic = (
        normalize_keyword(primary.parent_topic) if primary.parent_topic else ""
    )
    if (
        primary_topic
        and candidate.parent_topic
        and normalize_keyword(candidate.parent_topic) == primary_topic
    ):
        return True
    return bool(_signatures(primary.keyword) & _signatures(candidate.keyword))


def pack_topics(
    keywords: list[TopicKeyword],
    page_type: str = "blog",
    register: str = "any",
) -> list[TopicPackage]:
    """關鍵字（需帶 score）→ topic 包列（primary score 降序）。"""
    if register not in ("any", "written", "colloquial"):
        raise ValueError(f"未知 register：{register}（any/written/colloquial）")
    pool = [
        kw
        for kw in keywords
        if kw.volume
        and kw.volume > 0
        and intent_allowed(kw.intent, page_type)
        and (register == "any" or classify_register(kw.keyword) == register)
    ]
    pool.sort(key=lambda kw: (-kw.score, normalize_keyword(kw.keyword)))
    assigned: set[str] = set()
    topics: list[TopicPackage] = []
    for primary in pool:
        primary_key = normalize_keyword(primary.keyword)
        if primary_key in assigned:
            continue
        candidates = [
            candidate
            for candidate in pool
            if normalize_keyword(candidate.keyword) not in assigned
            and normalize_keyword(candidate.keyword) != primary_key
            and _matches(primary, candidate)
        ]
        secondaries = tuple(candidates[:MAX_SECONDARIES])
        assigned.add(primary_key)
        assigned.update(normalize_keyword(candidate.keyword) for candidate in secondaries)
        topics.append(
            TopicPackage(
                primary=primary,
                secondaries=secondaries,
                total_volume=(primary.volume or 0)
                + sum(candidate.volume or 0 for candidate in secondaries),
                register=classify_register(primary.keyword),
                needs_more_keywords=len(secondaries) < MIN_SECONDARIES,
            )
        )
    return topics
