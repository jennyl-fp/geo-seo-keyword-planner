# GEO 關鍵字研究工具 MCP（簡易版）

輸入種子關鍵字，輸出一份可直接執行的內容計劃：關鍵字清單（含評分）、主題分組、內容路線、GEO prompt 建議（含 fan-out 分類與 5 原型）、競爭對手差距。

## 不做清單（產品身分）

- ❌ 內容草稿
- ❌ 排名追蹤
- ❌ 技術審計
- ❌ LLM 生成（所有輸出皆規則驅動，無 LLM 呼叫）

## 工具面（4 個 MCP tools + 2 個資料 adapter）

```
seeds ──► expand_keywords ──► keyword_metrics ──► （內部分組+評分）
              ▲ GKP（量測覆蓋）         ▲ GSC（自家排名）
                                      │
              keyword_gap（1–3 對手，GSC 排除自家詞）
                                      ▼
              build_report（編排：分組 → 評分 → 問句挖掘 → fan-out 分類
                          → 5 原型 → markdown 報告）
```

| 工具 | 行為 |
|---|---|
| `expand_keywords` | Ahrefs 三路擴展 + 去重；GKP 有接時以 generate_keyword_ideas 補量測 |
| `keyword_metrics` | 批次 ≤100；volume 取 GKP > Ahrefs 優先序；intent / KD / CPC |
| `keyword_gap` | 1–3 對手 organic keywords，減去自家已排名詞（Ahrefs + GSC）與對手品牌詞（含 is_branded） |
| `build_report` | 一鍵編排 → markdown 報告（含 GEO prompt 節） |
| `plan_blog_topics` | 日常 blog topic research（ADR-014~017）：1 primary + 2–4 secondary 打包（vol>0、intent 符合 page_type、register 書面/口語可選），附 title 建議與 ≤580px 像素檢查 |

Adapter（非獨立工具，掛在資料層）：GKP（本地 Keyword Planner MCP server 子進程）、GSC（**優先** First Page agency MCP `FIRSTPAGE_MCP_TOKEN`，後備 Search Console API service account；ADR-010）。兩者皆可選：沒配置 → 跳過並在報告聲明，功能不崩。

## 驗收標準：報告模板（§6，八節固定）

```markdown
# 內容計劃 — <域名>（<日期>）

## 1. 摘要
→ 詞數、cluster 數、資料來源（Ahrefs/GKP/GSC live 或估算）

## 2. 關鍵字清單
→ keyword / volume / KD / intent / funnel / score（可貼 Excel）

## 3. 主題分組
→ 組名、hub 建議、成員、總量

## 4. 內容路線
→ hub → spokes 順序（量大組先做）

## 5. GEO prompt 建議
→ 每組：挖到的問句（含 funnel + fanout_type 標籤）
    + 5 條原型（標 template；branded 的另標）
    + 指引：答案在 H3 下首句直給（40–50 字 BLUF），
      再展開成 134–167 字自足段落（AI 引用帶）

## 6. 自家排名機會
→ GSC 已接時：排名 11–30 的詞（strike-distance 清單）

## 7. 競爭對手差距
→ top 20：keyword / volume / KD / 哪些對手在排

## 8. 資料聲明
→ 一行：各來源 live/估算狀態
```

## 工程底線（三條不變）

1. 無 key 無網路，測試全套綠（API 全 mock；GKP 子進程與 GSC 也 mock）
2. 同輸入兩次運行 byte-level 相同（日期參數注入）
3. API 欄位上線前真 key 打一次驗證（DECISIONS.md 記錄已驗證坑）

## 執行

```bash
pip install -e ".[dev]"      # 或 uv sync --extra dev
cp .env.example .env         # 填入 AHREFS_API_TOKEN / FIRSTPAGE_MCP_TOKEN / KEYWORD_PLANNER_MCP_COMMAND（+其 Google Ads env）
geo-keyword-planner          # stdio MCP server（.env 自動載入，已存在的 env 不覆蓋）
```

測試：`pytest`（無 key 無網路全綠）；lint：`ruff check src tests`。
GKP 子進程除錯：`GKP_MCP_DEBUG=1` 時 stderr 直通。

## 完整規格

見 `../geo-seo-keyword-planner-lite/GEO關鍵字研究工具-簡易版規格.docx`（v2）。本 README 即範圍錨——任何超出「不做清單」的需求須先立 ADR。
