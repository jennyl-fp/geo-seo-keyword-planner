"""報告渲染 + build_report 編排（T2.2 渲染層；T2.3 編排層）。

八節模板 = README.md §6（驗收標準，逐節對照）。渲染是純函數：
資料全由 ReportData 攜帶、日期由參數注入 → 同輸入 byte-level 相同
（ADR-009）。BLUF 40–50 字 / 134–167 字指引出處：
https://searchengineland.com/guide/people-also-ask（規格 §9）。

build_report 管線：expand（三路+GKP 補量測）→ metrics（GKP > Ahrefs）
→ GSC 自家排名 → 分組 → 評分 → 問句+fanout → 原型 → 渲染。
量測優先序 ADR-008；缺源降級 ADR-004。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rules.cjk_norm import normalize_keyword


@dataclass(frozen=True)
class ReportKeywordRow:
    keyword: str
    volume: int | None
    difficulty: int | None
    intent: str
    funnel: str
    score: float


@dataclass(frozen=True)
class ReportCluster:
    name: str
    hub: str
    members: tuple[str, ...]
    total_volume: int


@dataclass(frozen=True)
class ReportQuestion:
    keyword: str
    funnel: str
    fanout_type: str


@dataclass(frozen=True)
class ReportPrototype:
    template: str
    prompt: str
    branded: bool


@dataclass(frozen=True)
class ReportGeoCluster:
    cluster_name: str
    questions: tuple[ReportQuestion, ...] = ()
    prototypes: tuple[ReportPrototype, ...] = ()
    prototypes_skipped: bool = False


@dataclass(frozen=True)
class ReportStrikeRow:
    keyword: str
    position: float
    volume: int | None


@dataclass(frozen=True)
class ReportGapRow:
    keyword: str
    volume: int | None
    difficulty: int | None
    competitors: tuple[str, ...]


@dataclass(frozen=True)
class ReportData:
    domain: str
    date: str
    keywords: tuple[ReportKeywordRow, ...] = ()
    clusters: tuple[ReportCluster, ...] = ()
    geo: tuple[ReportGeoCluster, ...] = ()
    strike: tuple[ReportStrikeRow, ...] = ()
    gap: tuple[ReportGapRow, ...] = ()
    sources: dict[str, bool] = field(default_factory=dict)


GAP_TOP_N = 20

MIN_PROTOTYPE_CLUSTER_VOLUME = 50

BLUF_GUIDANCE = (
    "> 指引：答案在 H3 下首句直給（40–50 字 BLUF），"
    "再展開成 134–167 字自足段落（AI 引用帶）。"
)


def _fmt_volume(volume: int | None) -> str:
    return "無量測數據" if volume is None else str(volume)


def _fmt_difficulty(difficulty: int | None) -> str:
    return "—" if difficulty is None else str(difficulty)


def _fmt_source(live: bool | None) -> str:
    return "live" if live else "估算（未接）"


def render_report(data: ReportData) -> str:
    """ReportData → 八節 markdown（模板逐節對照 README §6）。"""
    lines: list[str] = []
    add = lines.append

    add(f"# 內容計劃 — {data.domain}（{data.date}）")
    add("")
    add("## 1. 摘要")
    add("")
    add(f"- 關鍵字：{len(data.keywords)} 個；主題分組：{len(data.clusters)} 組")
    add(
        f"- 資料來源：Ahrefs={_fmt_source(data.sources.get('ahrefs'))}；"
        f"GKP={_fmt_source(data.sources.get('gkp'))}；"
        f"GSC={_fmt_source(data.sources.get('gsc'))}"
    )
    add("")
    add("## 2. 關鍵字清單")
    add("")
    add("| keyword | volume | KD | intent | funnel | score |")
    add("|---|---|---|---|---|---|")
    for row in data.keywords:
        add(
            f"| {row.keyword} | {_fmt_volume(row.volume)} | "
            f"{_fmt_difficulty(row.difficulty)} | {row.intent} | {row.funnel} | "
            f"{row.score:.1f} |"
        )
    add("")
    add("## 3. 主題分組")
    add("")
    add("| 組名 | hub 建議 | 成員數 | 總量 |")
    add("|---|---|---|---|")
    for cluster in data.clusters:
        add(
            f"| {cluster.name} | {cluster.hub} | {len(cluster.members)} | "
            f"{cluster.total_volume} |"
        )
    add("")
    add("## 4. 內容路線")
    add("")
    for index, cluster in enumerate(data.clusters, start=1):
        spokes = "、".join(m for m in cluster.members if m != cluster.hub) or "（無 spoke）"
        add(f"{index}. hub：{cluster.hub}（總量 {cluster.total_volume}）→ spokes：{spokes}")
    add("")
    add("## 5. GEO prompt 建議")
    add("")
    for geo in data.geo:
        add(f"### {geo.cluster_name}")
        if geo.questions:
            for question in geo.questions:
                add(
                    f"- 問句：「{question.keyword}」"
                    f"（funnel={question.funnel}，fanout={question.fanout_type}）"
                )
        else:
            add("- （本組未挖到問句）")
        if geo.prototypes_skipped:
            add(f"- （組量低於 {MIN_PROTOTYPE_CLUSTER_VOLUME}，低優先，略過原型——ADR-013）")
        for prototype in geo.prototypes:
            tag = f"[{prototype.template}]" + ("[branded]" if prototype.branded else "")
            add(f"- 原型 {tag} {prototype.prompt}")
        add("")
    add(BLUF_GUIDANCE)
    add("")
    add("## 6. 自家排名機會")
    add("")
    if data.sources.get("gsc"):
        if data.strike:
            add("| keyword | 自家排名 | volume |")
            add("|---|---|---|")
            for row in data.strike:
                add(f"| {row.keyword} | {row.position:.0f} | {_fmt_volume(row.volume)} |")
        else:
            add("（近 90 天無排名 11–30 的詞）")
    else:
        add("GSC 未接，本節略（規格 §6：自家排名機會僅 GSC 已接時輸出）。")
    add("")
    add("## 7. 競爭對手差距")
    add("")
    if data.gap:
        add("| keyword | volume | KD | 哪些對手在排 |")
        add("|---|---|---|---|")
        for row in data.gap[:GAP_TOP_N]:
            add(
                f"| {row.keyword} | {_fmt_volume(row.volume)} | "
                f"{_fmt_difficulty(row.difficulty)} | {'、'.join(row.competitors)} |"
            )
    else:
        add("（無差距資料：未提供對手或來源不可用）")
    add("")
    add("## 8. 資料聲明")
    add("")
    add(
        f"Ahrefs：{_fmt_source(data.sources.get('ahrefs'))}；"
        f"GKP：{_fmt_source(data.sources.get('gkp'))}；"
        f"GSC：{_fmt_source(data.sources.get('gsc'))}。"
        "未 live 的來源，其對應欄位為估算值或該節略過。"
    )
    add("")
    return "\n".join(lines)


def build_report(
    seeds: list[str],
    domain: str,
    competitors: list[str] | None = None,
    country: str = "hk",
    brands: tuple[str, ...] = (),
    today: str | None = None,
    clients: tuple | None = None,
    output_path: str | Path | None = None,
) -> str:
    """一鍵編排全管線 → 八節 markdown（ADR-005：輸出 = 單一報告檔）。

    clients 可注入（測試）；today 注入則報告日期與資料日期一致（ADR-009）。
    output_path 有值時另存檔（dogfood 歸檔用）。
    """
    from datetime import date as _date

    from rules.cluster import ClusterEntry, cluster_keywords
    from rules.fanout import build_prototypes, classify_fanout
    from rules.funnel import classify_funnel
    from rules.intent import classify_intent
    from rules.questions import is_question
    from scoring import (
        STRIKE_MAX_POSITION,
        STRIKE_MIN_POSITION,
        KeywordForScoring,
        score_keywords,
    )

    if clients is None:
        from server import _build_clients

        clients = _build_clients(today)
    ahrefs, gsc, gkp = clients
    resolved_today = today or _date.today().isoformat()
    competitor_list = [c for c in (c.strip() for c in competitors or []) if c]

    seed_list = [s for s in (s.strip() for s in seeds) if s]
    pool: dict[str, tuple[str, int | None]] = {}
    for seed in seed_list:
        key = normalize_keyword(seed)
        if key and key not in pool:
            pool[key] = (seed, None)

    from server import _merge_expansion

    paths = [
        ahrefs.matching_terms(seed_list, country=country),
        ahrefs.related_terms(seed_list, country=country),
        ahrefs.search_suggestions(seed_list, country=country),
    ]
    ahrefs_live = any(path is not None for path in paths)
    for keyword, volume in _merge_expansion(
        [[(row.keyword, row.volume) for row in path] for path in paths if path]
    ).values():
        key = normalize_keyword(keyword)
        if not key:
            continue
        if key not in pool:
            pool[key] = (keyword, volume)
        elif pool[key][1] is None and volume is not None:
            pool[key] = (pool[key][0], volume)

    ideas = gkp.generate_ideas(seed_list, country=country) if gkp else None
    gkp_ideas_live = ideas is not None
    if ideas:
        for key, volume in ideas.items():
            if key not in pool or (pool[key][1] is None and volume is not None):
                pool[key] = (key, volume)

    keys = list(pool)
    overview = ahrefs.keyword_overview(keys, country=country)
    ahrefs_live = ahrefs_live or overview is not None
    gkp_volumes = gkp.historical_metrics(keys, country=country) if gkp else None
    gkp_live = gkp_ideas_live or gkp_volumes is not None

    details: dict[str, dict] = {}
    for key, (display, expansion_volume) in pool.items():
        metric = (overview or {}).get(key)
        if gkp_volumes and gkp_volumes.get(key) is not None:
            volume = gkp_volumes[key]
        elif metric is not None and metric.volume is not None:
            volume = metric.volume
        else:
            volume = expansion_volume
        details[key] = {
            "display": display,
            "volume": volume,
            "difficulty": metric.difficulty if metric else None,
            "parent_topic": metric.parent_topic if metric else None,
        }

    positions = gsc.top_queries(domain=domain) if gsc else None
    gsc_live = positions is not None

    scored = score_keywords(
        [
            KeywordForScoring(
                keyword=info["display"],
                volume=info["volume"],
                difficulty=info["difficulty"],
                intent=classify_intent(key),
            )
            for key, info in details.items()
        ],
        own_positions=positions,
    )

    clusters = cluster_keywords(
        [
            ClusterEntry(
                keyword=info["display"],
                volume=info["volume"],
                parent_topic=info["parent_topic"],
            )
            for info in details.values()
        ]
    )

    geo_clusters = []
    for cluster in clusters:
        small_cluster = cluster.total_volume < MIN_PROTOTYPE_CLUSTER_VOLUME
        geo_clusters.append(
            ReportGeoCluster(
                cluster_name=cluster.name,
                questions=tuple(
                    ReportQuestion(
                        keyword=member.keyword,
                        funnel=classify_funnel(member.keyword),
                        fanout_type=classify_fanout(member.keyword),
                    )
                    for member in cluster.members
                    if is_question(member.keyword)
                ),
                prototypes=(
                    ()
                    if small_cluster
                    else tuple(
                        build_prototypes(
                            cluster.hub,
                            brands=brands,
                            competitors=tuple(competitor_list),
                        )
                    )
                ),
                prototypes_skipped=small_cluster,
            )
        )

    strike_rows = sorted(
        (
            ReportStrikeRow(
                keyword=row.keyword, position=row.own_position, volume=row.volume
            )
            for row in scored
            if row.own_position is not None
            and STRIKE_MIN_POSITION <= row.own_position <= STRIKE_MAX_POSITION
        ),
        key=lambda row: (row.position, row.keyword),
    )

    gap_rows: tuple[ReportGapRow, ...] = ()
    if competitor_list:
        from server import keyword_gap_impl

        gap = keyword_gap_impl(domain, competitor_list, country, clients)
        gap_rows = tuple(
            ReportGapRow(
                keyword=row["keyword"],
                volume=row["volume"],
                difficulty=row["difficulty"],
                competitors=tuple(row["competitors"]),
            )
            for row in gap["keywords"]
        )

    data = ReportData(
        domain=domain,
        date=resolved_today,
        keywords=tuple(
            ReportKeywordRow(
                keyword=row.keyword,
                volume=row.volume,
                difficulty=row.difficulty,
                intent=row.intent,
                funnel=classify_funnel(row.keyword),
                score=row.score,
            )
            for row in scored
        ),
        clusters=tuple(
            ReportCluster(
                name=cluster.name,
                hub=cluster.hub,
                members=tuple(member.keyword for member in cluster.members),
                total_volume=cluster.total_volume,
            )
            for cluster in clusters
        ),
        geo=tuple(geo_clusters),
        strike=tuple(strike_rows),
        gap=gap_rows,
        sources={"ahrefs": ahrefs_live, "gkp": gkp_live, "gsc": gsc_live},
    )
    markdown = render_report(data)
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    return markdown
