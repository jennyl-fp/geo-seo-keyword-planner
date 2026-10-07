# TASKS.md — 唯一工作事實來源

驗收條件先於實作寫好。做完 = 更新本表 + 測試綠 + commit 訊息帶任務 ID。

## Phase 0 — 契約文件層（半天）

| ID | 任務 | 驗收條件 | 狀態 |
|---|---|---|---|
| T0.1 | README.md（定位+不做+報告模板） | 模板八節與規格 §6 逐字一致 | ✅ |
| T0.2 | DECISIONS.md（≥5 條 ADR + API 坑表） | 每條架構選擇有編號與理由 | ✅ |
| T0.3 | TASKS.md | 每任務有可測驗收條件 | ✅ |

**閘門**：能用一段話向陌生人講清「這工具回答什麼、輸出什麼、不輸出什麼」。

## Phase 1 — 資料地基 + 規則核心（1.5–2 週；順序不可交換）

| ID | 任務 | 驗收條件 | 狀態 |
|---|---|---|---|
| T1.1 | `rules/cjk_norm.py` 正規化先行 | 「鑽戒 推薦」≡「鑽戒推薦」；純拉丁保留詞界；小寫+trim。中英各 ≥3 案例 | ✅ |
| T1.2 | `config.py` env 讀取 | `has_ahrefs/has_gsc/has_gkp` 布林；缺 env 不 raise | ✅ |
| T1.3 | `ahrefs_client.py` | 缺 key 回 None 永不 raise；§3 坑寫進註解；每 endpoint 一份 fixture；date=昨天；逗號過濾；apex→www | ✅ |
| T1.4 | `gsc_client.py` | `top_queries() → {keyword: position}`；end=today−3；缺憑證回 None | ✅ |
| T1.5 | `gkp_adapter.py` | 子進程 MCP client + markdown 表格 parser；只在 metrics 步驟補量測；缺指令回 None | ✅ |
| T1.6 | `rules/intent.py` 四分類 | EN 詞界 / ZH 子字串；多命中按 transactional→commercial→navigational→informational 順序（§4.1 表序）；3–5 案例×中英 | ✅ |
| T1.7 | `rules/funnel.py` 三分類 | BOFU/MOFU/TOFU 詞表；中英案例 | ✅ |
| T1.8 | `rules/questions.py` 問句偵測 | 裸「點」不觸發（特點/賣點/地點不誤中）；中英案例 | ✅ |
| T1.9 | `rules/cluster.py` 分組 | parent_topic 同組；否則共享 4+ 字英文 / 2+ 字中文子字串；hub=最高量 | ✅ |
| T1.10 | `rules/fanout.py` | 8 類分類詞表；5 原型模板；topic 清洗（剝問句外殼/助動詞/冠詞）；≤13 詞（中文 26 字）——13 與 14 各測一個；branded 標記 | ✅ |
| T1.11 | `scoring.py` | `log1p(vol)/log1p(max)×KD可行率×intent權重×100 + strike(11–30位,+15)`；每行附組件值；無 KD→0.5；KD≥80→0.1 | ✅ |

**閘門**：拔掉所有 key，套件全綠且輸出帶估算標籤；同輸入兩次運行 byte-level 相同（`diff` 為空）。
→ 測試部分 ✅（`env -i` 無任何 key/PATH 下 290 全綠，零網路）；估算標籤與 byte-level diff 屬報告層輸出，隨 T2.3 補驗。

## Phase 2 — 編排 + 驗收（1 週）

| ID | 任務 | 驗收條件 | 狀態 |
|---|---|---|---|
| T2.1 | MCP server（FastMCP stdio）掛 4 tools | 每個 tool 有 schema；`expand_keywords/keyword_metrics/keyword_gap/build_report` 行為符合 README 表（build_report 正文 T2.3 接線 report.py） | ✅ |
| T2.2 | `report.py` 八節渲染 | 逐節對照 README 模板；表格可貼 Excel | ✅ |
| T2.3 | `build_report` 編排全管線 | expand→metrics→分組→評分→問句+fanout→原型→渲染 一鍵完成 | ✅ |

**Phase 1 閘門補驗**：估算標籤 ✅（全源關閉時 §8 三源標「估算（未接）」、§2 標「無量測數據」）；byte-level 確定性 ✅（同輸入兩次運行寫檔 `filecmp` byte 相等）。
| T2.4 | live 真 key 驗證 | Ahrefs+GSC+GKP 各打一次；DECISIONS.md 坑表逐條標「已驗證」 | ✅（三源皆 live；坑表 2026-10-06 全部標註） |
| T2.5 | dogfood 盲測 | 真域名跑一次；SEO 同事不看說明能否直接排下週工作；報告歸檔進 repo 當範例 | 報告歸檔 ✅（`examples/2026-10-06-parklandmusic.md`，896 行全 live）；盲測⏳待人評（見下） |

**閘門**：dogfood 報告歸檔後才算完成。→ ✅ 已歸檔；**盲測（人）待執行**——請交報告給一位 SEO 同事，不看說明能否直接排下週工作？能 → 上線；不能 → 記下卡在哪一節。

## Phase 3 — 日常工作需求（2026-10-07；ADR-014~017）

| ID | 任務 | 驗收條件 | 狀態 |
|---|---|---|---|
| T3.1 | `rules/page_intent.py` | blog/service/home→允許 intent 對照；未知 page_type 報錯 | ✅ |
| T3.2 | `rules/register.py` | 口語/書面語/中性；「關係」不誤中口語（係 不入表） | ✅ |
| T3.3 | `rules/title.py` | 580px 邊界（36 CJK=576 ✓ / 37 CJK=592 ✗）；品牌後綴超限棄用 | ✅ |
| T3.4 | `rules/topics.py` 打包 | vol>0 硬過濾；intent 匹配；1 primary + ≤4 secondary；<2 標 needs_more；確定性（亂序同輸出） | ✅ |
| T3.5 | `plan_blog_topics` MCP tool | schema 註冊（共 5 tools）；impl 含 title 建議；live 冒煙（112 topics，結他/學唱歌包正確） | ✅ |

需求對應：#1 intent 對照（T3.1）、#2 title ≤580px（T3.3）、#3 vol>0（T3.4 硬過濾）、#4 region/語域（country 參數 + T3.2）、#5/#6 打包（T3.4）、#7 GEO prompts 不限量（build_report 不變）。

## 債務清理（2026-10-07）

| ID | 事項 | 狀態 |
|---|---|---|
| T3.6 | 修真問題×5：volume_source short-circuit 脆弱點重構為 `_volume_source()`；合併政策統一（首見 display、None 量可升級，server/report 同政策）；死 import×2；metrics 死 lookup | ✅ |
| T3.7 | 測試 fakes 抽 `tests/fakes.py`（5 檔去重）；fastmcp 工具列舉改公開 API 優先、私有後備、模組屬性兜底 | ✅ |
| T3.8 | 打包：`pip install -e ".[dev]"` + console script + py-modules；`.env` 零依賴載入；GKP_MCP_DEBUG stderr 直通；ruff 閘門（全 clean） | ✅ |
| T3.9 | GSC service account 後備未 live 驗證——無憑證可驗；DECISIONS 坑表標 ⚠️ 待驗證，使用前須真憑證打一次 | ⚠️ 已標註（無法修，缺憑證） |
| T4.0 | **上線（2026-10-07）**：stdio 協定開機驗證 ✅（initialize/tools-list/plan_blog_topics 真 E2E）；註冊 `~/.config/opencode/opencode.jsonc` `mcp.geo-keyword-planner`（local console script + 9 env）✅；JSONC 語法驗證 ✅；⚠️ 需重啟 opencode 生效；⚠️ repo 未 commit（上線後強烈建議封存） | ⬜ 待 commit |

### T2.5 dogfood 發現（升級路徑候選，§9）
1. 過度合併：結他 hub 吸了 373 spokes（歌詞/影子老師/dcard 雜訊）——§4.5 簡版已知誤差，真實資料下放大
2. 雜訊組（冰結、任我行chord、威威唱片）各產生 5 原型——雜訊放大
3. 對手品牌別名漏網：tut（tutmusic.com.hk）、mc music（mcmusic.hk）仍出現在 §7 gap
4. live byte-level 確定性：上游 API 於擴展清單 limit 邊界（vol 10 附近）偶發一詞之差的波動；我方處理層確定性已由 mock 測試 + 兩次 live 連續運行 byte 相同證明

### 升級修正（T2.6，ADR-011/012/013）→ v2 報告 `examples/2026-10-06-parklandmusic-v2.md`
| 發現 | 修法 | v1→v2 實測 |
|---|---|---|
| #3 品牌別名 | organic select 加 `is_branded`，gap 過濾 | §7 的 tut/mc music 已消失（蔡曉彤殘留：Ahrefs 未標 branded，接受） |
| #1 泛詞鏈式合併 | 策展泛詞簽章停用表（16 詞，不採 DF——會誤殺正主題） | 37→51 組；歌詞類/影子老師已拆出成單例；結他 hub 373→361（殘餘為分散 2 字泛詞長尾鏈條——§4.5 單鏈結構上限，屬完全版演算法改動） |
| #2 雜訊組原型 | 原型總量下限 50（§3 照列、§5 標低優先略過） | 32 組標「低優先，略過原型」 |
| #4 live 波動 | 接受（已文件化） | — |

## 時程

| 週 | 內容 |
|---|---|
| W1 | T1.1–T1.5（正規化→三個資料源）+ T1.6–T1.8 起步 |
| W2 | T1.9–T1.11 + Phase 1 閘門（離線全綠 + 確定性 diff） |
| W3 | T2.1–T2.5 + dogfood 盲測 → 上線 |

## 貫穿紀律

1. 出處標籤：非實測標「估算」；詞表 docstring 註來源文章
2. 確定性：日期注入、tie-break 明確
3. 降級優雅：降級路徑本身有測試
4. 任務閉環：TASKS.md + 測試綠 + commit 帶 ID
5. 測試即離線契約：flaky 必查（常見：測試洩漏真網路）
6. 工具失敗是發現：記錄、降級、標籤；絕不手動填數字
