# GEO Keyword Research Tool — MCP

A keyword-research pipeline composed of multiple studies: keyword expansion study (Ahrefs 3-path + GKP ideas), market-volume study (GKP > Ahrefs volume priority), own-ranking study (GSC grounding), competitive-gap study (1–3 competitors, brand/is_branded filtered), topic clustering study, and blog-topic packaging study (1 primary + 2–4 secondaries with intent, register, and ≤580px title checks).

Feed in seed keywords — get back an execution-ready content plan: ranked keyword list, topic clusters with hub→spokes roadmap, GEO prompt suggestions (fan-out classification + 5 templates per cluster), competitor keyword gaps, and ready-to-publish blog topic packs.

## Tools (4 data tools + 2 data adapters)

```
seeds ──► expand_keywords ──► keyword_metrics ──► （internal clustering + scoring）
              ▲ GKP (volume coverage)     ▲ GSC (own rankings)
                                          │
              keyword_gap (1–3 competitors, GSC excludes own keywords)
                                          ▼
              build_report (pipeline: clustering → scoring → question mining
                          → fan-out classification → 5 templates → markdown report)
```

| Tool | Behavior |
|---|---|
| `expand_keywords` | Ahrefs 3-way expansion + dedupe; GKP `generate_keyword_ideas` supplements volumes when available |
| `keyword_metrics` | Batches ≤100; volume priority GKP > Ahrefs; intent / KD / CPC |
| `keyword_gap` | 1–3 competitors' organic keywords, minus own ranked keywords (Ahrefs + GSC) and competitor brand terms (incl. `is_branded`) |
| `build_report` | One-click pipeline → markdown report (incl. GEO prompt section) |
| `plan_blog_topics` | Day-to-day blog topic research (ADR-014~017): packages 1 primary + 2–4 secondary keywords (vol>0, intent matching `page_type`, optional written/Cantonese register filter), with title suggestion and ≤580px pixel check |

Adapters (not standalone tools; sit in the data layer): GKP (local Keyword Planner MCP server subprocess), GSC (**preferred**: First Page agency MCP `FIRSTPAGE_MCP_TOKEN`; fallback: Search Console API service account; ADR-010). Both optional: when unconfigured the feature is skipped and noted in the report — nothing breaks.

## Acceptance standard: report template (§6, fixed 8 sections)

The report output language is Traditional Chinese (spec §6). The template below mirrors the actual rendered output:

```markdown
# 內容計劃 — <domain>（<date>）

## 1. 摘要        → keyword count, cluster count, data sources (Ahrefs/GKP/GSC live or estimated)
## 2. 關鍵字清單   → keyword / volume / KD / intent / funnel / score (Excel-pasteable)
## 3. 主題分組     → cluster name, hub suggestion, members, total volume
## 4. 內容路線     → hub → spokes order (highest-volume clusters first)
## 5. GEO prompt 建議 → per cluster: mined questions (funnel + fanout_type labels)
                        + 5 template prompts (tagged; branded flagged)
                        + guidance: answer in the first sentence under H3 (40–50 char BLUF),
                          then expand into a 134–167 char self-contained paragraph (AI citation band)
## 6. 自家排名機會 → (GSC connected only): keywords ranked 11–30 (strike-distance list)
## 7. 競爭對手差距  → top 20: keyword / volume / KD / which competitors rank
## 8. 資料聲明      → one line: live/estimated status per source
```

## Engineering principles (three, non-negotiable)

1. Fully green test suite with no keys and no network (all APIs mocked; GKP subprocess and GSC mocked too)
2. Same input run twice → byte-identical output (dates injected as parameters)
3. API fields verified with a real key before going live (verified pitfalls recorded in DECISIONS.md)

## Setup & run

```bash
pip install -e ".[dev]"      # or: uv sync --extra dev
cp .env.example .env         # fill in AHREFS_API_TOKEN / FIRSTPAGE_MCP_TOKEN / KEYWORD_PLANNER_MCP_COMMAND (+ its Google Ads env vars)
geo-keyword-planner          # stdio MCP server (auto-loads .env; existing env vars are not overridden)
```

Tests: `pytest` (green offline, no keys); lint: `ruff check src tests`.
GKP subprocess debugging: `GKP_MCP_DEBUG=1` forwards stderr.

## Full specification

See the Chinese spec document (v2) in `../geo-seo-keyword-planner-lite/`. This README is the scope anchor — any requirement beyond the "does NOT do" list requires a new ADR first.