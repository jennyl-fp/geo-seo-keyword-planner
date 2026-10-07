"""MCP server — 4 個工具（T2.1；FastMCP stdio；ADR-001）。

  expand_keywords  種子 → Ahrefs 三路擴展（matching/related/suggestions）
                  + 去重；GKP 有接時以 generate_keyword_ideas 補量測
  keyword_metrics  批次 ≤100；volume 取 GKP > Ahrefs 優先序（ADR-008）；
                  intent / KD / CPC 來自 Ahrefs overview
  keyword_gap      1–3 對手 organic keywords，減去自家已排名詞
                  （自家 Ahrefs organic + GSC）與對手品牌詞
  build_report     一鍵編排 → markdown 報告（report.py，T2.3 接線完成）

缺任何資料源 → 該源跳過、sources 標 false，永不崩（ADR-004）。
執行：PYTHONPATH=src python -m server（stdio transport）。
純邏輯放 *_impl 函式（不經 FastMCP），測試直接打 impl；
建置/安裝打包到 T2.4 dogfood 時再議。
"""

from __future__ import annotations

import re
from typing import Any

from fastmcp import FastMCP

from ahrefs_client import AhrefsClient
from config import Config, load_config
from firstpage_client import FirstpageGscClient
from gkp_adapter import GkpAdapter
from gsc_client import GscClient
from rules.cjk_norm import normalize_keyword
from rules.intent import classify_intent
from rules.register import classify_register
from rules.title import suggest_title
from rules.topics import TopicKeyword, pack_topics
from scoring import KeywordForScoring, score_keywords

mcp = FastMCP("geo-keyword-planner")

Clients = tuple[AhrefsClient, GscClient | FirstpageGscClient, GkpAdapter]


def _build_clients(today: str | None = None) -> Clients:
    """GSC 優先走 firstpage MCP（ADR-010），無 token 才退 service account。"""
    config: Config = load_config()
    if config.has_firstpage:
        gsc: GscClient | FirstpageGscClient = FirstpageGscClient(config, today=today)
    else:
        gsc = GscClient(config, today=today)
    return AhrefsClient(config, today=today), gsc, GkpAdapter(config)


def main() -> None:
    from config import load_dotenv

    load_dotenv()
    mcp.run()


def _merge_expansion(
    expansion_lists: list[list[tuple[str, int | None]] | None],
) -> dict[str, tuple[str, int | None]]:
    """多路結果合併（統一政策，report.build_report 同此）：
    同鍵保序——display 形首見為準；量為 None 時可被後路升級。"""
    merged: dict[str, tuple[str, int | None]] = {}
    for rows in expansion_lists:
        if not rows:
            continue
        for keyword, volume in rows:
            key = normalize_keyword(keyword)
            if not key:
                continue
            if key not in merged:
                merged[key] = (keyword, volume)
            elif merged[key][1] is None and volume is not None:
                merged[key] = (merged[key][0], volume)
    return merged


def _volume_source(
    key: str, volume: int | None, gkp_live: bool, ideas: dict[str, int | None] | None
) -> str:
    if gkp_live and ideas is not None and ideas.get(key) is not None:
        return "gkp"
    if volume is not None:
        return "ahrefs"
    return "none"


def expand_keywords_impl(
    seeds: list[str], country: str, clients: Clients
) -> dict[str, Any]:
    ahrefs, _, gkp = clients
    paths = [
        ahrefs.matching_terms(seeds, country=country),
        ahrefs.related_terms(seeds, country=country),
        ahrefs.search_suggestions(seeds, country=country),
    ]
    ahrefs_live = any(path is not None for path in paths)
    pool = _merge_expansion(
        [
            [(row.keyword, row.volume) for row in path] if path else None
            for path in paths
        ]
    )
    ideas: dict[str, int | None] | None = None
    gkp_live = False
    if gkp is not None:
        ideas = gkp.generate_ideas(seeds, country=country)
        if ideas is not None:
            gkp_live = True
            for key, volume in ideas.items():
                if key not in pool or (pool[key][1] is None and volume is not None):
                    pool[key] = (key, volume)
    keywords = [
        {
            "keyword": display,
            "volume": volume,
            "volume_source": _volume_source(key, volume, gkp_live, ideas),
        }
        for key, (display, volume) in pool.items()
    ]
    keywords.sort(key=lambda row: (-(row["volume"] or 0), row["keyword"]))
    return {
        "keywords": keywords,
        "sources": {"ahrefs": ahrefs_live, "gkp": gkp_live},
    }


def keyword_metrics_impl(
    keywords: list[str], country: str, clients: Clients
) -> dict[str, Any]:
    ahrefs, _, gkp = clients
    overview = ahrefs.keyword_overview(keywords, country=country)
    ahrefs_live = overview is not None
    gkp_volumes = gkp.historical_metrics(keywords, country=country) if gkp else None
    gkp_live = gkp_volumes is not None
    rows: dict[str, dict[str, Any]] = {}
    for keyword in keywords:
        key = normalize_keyword(keyword)
        if not key or key in rows:
            continue
        metric = (overview or {}).get(key)
        gkp_volume = (gkp_volumes or {}).get(key)
        if gkp_volume is not None:
            volume, source = gkp_volume, "gkp"
        elif metric is not None and metric.volume is not None:
            volume, source = metric.volume, "ahrefs"
        else:
            volume, source = None, "none"
        rows[key] = {
            "keyword": keyword,
            "volume": volume,
            "volume_source": source,
            "difficulty": metric.difficulty if metric else None,
            "cpc": metric.cpc if metric else None,
            "intents": list(metric.intents) if metric else [],
            "parent_topic": metric.parent_topic if metric else None,
        }
    ordered = sorted(rows.values(), key=lambda row: (-(row["volume"] or 0), row["keyword"]))
    return {"keywords": ordered, "sources": {"ahrefs": ahrefs_live, "gkp": gkp_live}}


def _brand_pattern(domain: str) -> re.Pattern[str]:
    host = domain.lower().strip()
    for scheme in ("https://", "http://"):
        host = host.removeprefix(scheme)
    host = host.split("/")[0]
    labels = [part for part in host.split(".") if part and part != "www"]
    brand = labels[0] if labels else host
    if re.fullmatch(r"[a-z0-9]+", brand):
        return re.compile(rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])")
    return re.compile(re.escape(brand))


def keyword_gap_impl(
    domain: str, competitors: list[str], country: str, clients: Clients
) -> dict[str, Any]:
    if not 1 <= len(competitors) <= 3:
        raise ValueError("competitors 必須 1–3 個（規格 §2）")
    ahrefs, gsc, _ = clients
    own_keywords = ahrefs.organic_keywords(domain, country=country)
    ahrefs_live = own_keywords is not None
    own_ranked = {normalize_keyword(row.keyword) for row in own_keywords or []}
    gsc_positions = gsc.top_queries(domain=domain) if gsc else None
    gsc_live = gsc_positions is not None
    own_ranked |= set(gsc_positions or {})

    gap: dict[str, dict[str, Any]] = {}
    brand_patterns = [(_brand_pattern(comp), comp) for comp in competitors]
    for competitor in competitors:
        rows = ahrefs.organic_keywords(competitor, country=country)
        for row in rows or []:
            if row.is_branded:
                continue
            key = normalize_keyword(row.keyword)
            if not key or key in own_ranked:
                continue
            if any(pattern.search(key) for pattern, _ in brand_patterns):
                continue
            entry = gap.get(key)
            if entry is None:
                gap[key] = {
                    "keyword": row.keyword,
                    "volume": row.volume,
                    "difficulty": row.keyword_difficulty,
                    "best_position": row.best_position,
                    "competitors": [competitor],
                }
            else:
                entry["volume"] = (
                    max(entry["volume"], row.volume)
                    if entry["volume"] is not None and row.volume is not None
                    else (entry["volume"] if entry["volume"] is not None else row.volume)
                )
                if row.best_position is not None and (
                    entry["best_position"] is None
                    or row.best_position < entry["best_position"]
                ):
                    entry["best_position"] = row.best_position
                if competitor not in entry["competitors"]:
                    entry["competitors"].append(competitor)
    ordered = sorted(
        gap.values(),
        key=lambda row: (-(row["volume"] or 0), normalize_keyword(row["keyword"])),
    )
    return {
        "keywords": ordered,
        "sources": {"ahrefs": ahrefs_live, "gsc": gsc_live},
    }


def plan_blog_topics_impl(
    seeds: list[str],
    page_type: str,
    register: str,
    brand: str | None,
    country: str,
    limit: int,
    clients: Clients,
) -> dict[str, Any]:
    """日常 blog topic research（需求 #1–#7）：expand+metrics →
    vol>0／intent（page_type）／register 過濾 → 1 primary + 2–4 secondary
    打包 → 每包附 title 建議 + ≤580px 檢查。"""
    expansion = expand_keywords_impl(seeds, country, clients)
    keywords = [row["keyword"] for row in expansion["keywords"]]
    metrics = keyword_metrics_impl(keywords, country, clients)
    expansion_volume = {
        normalize_keyword(row["keyword"]): row["volume"]
        for row in expansion["keywords"]
    }
    topic_keywords = [
        TopicKeyword(
            keyword=row["keyword"],
            volume=(
                row["volume"]
                if row["volume"] is not None
                else expansion_volume.get(normalize_keyword(row["keyword"]))
            ),
            difficulty=row["difficulty"],
            intent=classify_intent(row["keyword"]),
            parent_topic=row["parent_topic"],
        )
        for row in metrics["keywords"]
    ]
    scored = score_keywords(
        [
            KeywordForScoring(kw.keyword, kw.volume, kw.difficulty, kw.intent)
            for kw in topic_keywords
        ]
    )
    score_by_key = {
        normalize_keyword(row.keyword): row.score for row in scored
    }
    topic_keywords = [
        TopicKeyword(
            keyword=kw.keyword,
            volume=kw.volume,
            difficulty=kw.difficulty,
            intent=kw.intent,
            score=score_by_key.get(normalize_keyword(kw.keyword), 0.0),
            parent_topic=kw.parent_topic,
        )
        for kw in topic_keywords
    ]
    topics = pack_topics(topic_keywords, page_type=page_type, register=register)

    def keyword_payload(kw: TopicKeyword) -> dict[str, Any]:
        return {
            "keyword": kw.keyword,
            "volume": kw.volume,
            "difficulty": kw.difficulty,
            "intent": kw.intent,
            "register": classify_register(kw.keyword),
            "score": kw.score,
        }

    packed = []
    for topic in topics[:limit]:
        title = suggest_title(topic.primary.keyword, brand=brand)
        packed.append(
            {
                "primary": keyword_payload(topic.primary),
                "secondaries": [keyword_payload(kw) for kw in topic.secondaries],
                "total_volume": topic.total_volume,
                "register": topic.register,
                "needs_more_keywords": topic.needs_more_keywords,
                "title": {
                    "text": title.title,
                    "pixels": title.pixels,
                    "fits": title.fits,
                    "dropped_brand": title.dropped_brand,
                },
            }
        )
    return {
        "topics": packed,
        "topic_count": len(topics),
        "sources": {
            "ahrefs": expansion["sources"]["ahrefs"] or metrics["sources"]["ahrefs"],
            "gkp": expansion["sources"]["gkp"] or metrics["sources"]["gkp"],
        },
    }


@mcp.tool
def expand_keywords(seeds: list[str], country: str = "hk") -> dict:
    """種子關鍵字 → 擴展清單（Ahrefs 三路 + GKP 補量測；volume GKP > Ahrefs）。"""
    return expand_keywords_impl(seeds, country, _build_clients())


@mcp.tool
def keyword_metrics(keywords: list[str], country: str = "hk") -> dict:
    """關鍵字量測（volume 來源 GKP > Ahrefs > 無；KD/CPC/intents 來自 Ahrefs）。"""
    return keyword_metrics_impl(keywords, country, _build_clients())


@mcp.tool
def keyword_gap(domain: str, competitors: list[str], country: str = "hk") -> dict:
    """競爭對手差距詞（1–3 對手；排除自家已排名詞與對手品牌詞）。"""
    return keyword_gap_impl(domain, competitors, country, _build_clients())


@mcp.tool
def build_report(
    seeds: list[str],
    domain: str,
    competitors: list[str] | None = None,
    country: str = "hk",
    brands: list[str] | None = None,
    today: str | None = None,
) -> str:
    """一鍵編排 → 八節 markdown 內容計劃。today（YYYY-MM-DD）可注入以重現相同報告。"""
    from report import build_report as run_pipeline

    return run_pipeline(
        seeds=seeds,
        domain=domain,
        competitors=competitors or [],
        country=country,
        brands=tuple(brands or ()),
        today=today,
        clients=_build_clients(today),
    )


@mcp.tool
def plan_blog_topics(
    seeds: list[str],
    page_type: str = "blog",
    register: str = "any",
    brand: str | None = None,
    country: str = "hk",
    limit: int = 20,
) -> dict:
    """Blog topic 打包：1 primary + 2–4 secondary（vol>0、intent 符合
    page_type、register 可選），附 title 建議與 ≤580px 像素檢查。"""
    return plan_blog_topics_impl(
        seeds, page_type, register, brand, country, limit, _build_clients()
    )


if __name__ == "__main__":
    main()
