"""主題分組（T1.9；規格 §4.5 簡版）。

來源：GEO關鍵字研究工具規格書（v2）§4.5；hub→spokes 內容路線欄位
依據 https://www.semrush.com/blog/keyword-mapping/（規格 §9 基礎組）。

分組規則：
  1. parent_topic 相同（正規化後）→ 同組
  2. 否則共享子字串 → 同組（§4.5：4+ 英文字／2+ 中文字）：
     等價轉換——共享 ≥k 長子字串 ⟺ 共享「恰好 k 長」子字串，
     故簽章 = 各段（ASCII 字母段／CJK 段）內所有恰 k 長子字串
     （EN k=4：smart→smar/mart；ZH k=2：智能辦公室→智能/能辦/辦公/公室）
     泛詞簽章先剔除（GENERIC_SIGNATURE_STOP，ADR-012）——
     否則「老師」「歌曲」等泛詞會把無關主題鏈式合併
     （dogfood 2026-10-06：結他 hub 吸 373 spokes 的根因）
     已知過度合併風險（company/compare 共享 comp）為簡版接受的誤差
  3. 兩遍皆走 union-find，結果 = 連通分量（等價閉包，與處理順序無關）

GENERIC_SIGNATURE_STOP 詞表來源：2026-10-06 dogfood 觀察
（啟發式初版；不採 DF 門檻——單一主題池正主題詞出現率天然超標會被誤殺）。

組名與 hub = 量最高的成員（None 視為 0；同量取關鍵字字典序——ADR-009
tie-break）。輸出排序：總量降序、組名字典序 tie-break。
同鍵（正規化後）重複輸入先去重（量高者勝）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rules.cjk_norm import CJK_CLASS, match_form, normalize_keyword

_ASCII_RUN_RE = re.compile(r"[a-z]{4,}")
_CJK_RUN_RE = re.compile(f"[{CJK_CLASS}]{{2,}}")

GENERIC_SIGNATURE_STOP = frozenset(
    {
        "老師", "歌曲", "歌詞", "課程", "教學", "推薦", "收費", "價錢",
        "好唔好", "dcard", "lihkg", "ptt", "chord", "hong", "kong", "best",
    }
)


@dataclass(frozen=True)
class ClusterEntry:
    keyword: str
    volume: int | None
    parent_topic: str | None = None


@dataclass(frozen=True)
class Cluster:
    name: str
    hub: str
    members: tuple[ClusterEntry, ...]
    total_volume: int


def _volume(entry: ClusterEntry) -> int:
    return entry.volume or 0


def _signatures(keyword: str) -> set[str]:
    text = match_form(keyword)
    signatures: set[str] = set()
    for run in _ASCII_RUN_RE.findall(text):
        signatures.update(run[i : i + 4] for i in range(len(run) - 3))
    for run in _CJK_RUN_RE.findall(text):
        signatures.update(run[i : i + 2] for i in range(len(run) - 1))
    return signatures - GENERIC_SIGNATURE_STOP


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_b] = root_a


def _dedupe(entries: list[ClusterEntry]) -> list[ClusterEntry]:
    best: dict[str, ClusterEntry] = {}
    for entry in entries:
        key = normalize_keyword(entry.keyword)
        if not key:
            continue
        if key not in best or _volume(entry) > _volume(best[key]):
            best[key] = entry
    return list(best.values())


def cluster_keywords(entries: list[ClusterEntry]) -> list[Cluster]:
    """關鍵字清單 → cluster 列（總量降序；同量組名字典序）。"""
    deduped = _dedupe(entries)
    ordered = sorted(deduped, key=lambda entry: normalize_keyword(entry.keyword))
    union_find = _UnionFind(len(ordered))

    by_topic: dict[str, int] = {}
    for index, entry in enumerate(ordered):
        if not entry.parent_topic:
            continue
        topic_key = normalize_keyword(entry.parent_topic)
        if topic_key in by_topic:
            union_find.union(index, by_topic[topic_key])
        else:
            by_topic[topic_key] = index

    by_signature: dict[str, int] = {}
    for index, entry in enumerate(ordered):
        for signature in sorted(_signatures(entry.keyword)):
            if signature in by_signature:
                union_find.union(index, by_signature[signature])
            else:
                by_signature[signature] = index

    groups: dict[int, list[ClusterEntry]] = {}
    for index, entry in enumerate(ordered):
        groups.setdefault(union_find.find(index), []).append(entry)

    clusters: list[Cluster] = []
    for members in groups.values():
        sorted_members = sorted(
            members, key=lambda entry: (-_volume(entry), normalize_keyword(entry.keyword))
        )
        hub = sorted_members[0]
        clusters.append(
            Cluster(
                name=hub.keyword,
                hub=hub.keyword,
                members=tuple(sorted_members),
                total_volume=sum(_volume(entry) for entry in members),
            )
        )
    clusters.sort(key=lambda cluster: (-cluster.total_volume, normalize_keyword(cluster.name)))
    return clusters
