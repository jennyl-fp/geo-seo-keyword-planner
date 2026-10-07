# DECISIONS.md — ADR 表

不經新 ADR 不翻案。

| # | 決策 | 理由 | 日期 |
|---|------|------|------|
| ADR-001 | 語言框架：Python 3.11+ / uv / FastMCP（stdio transport） | 規格 repo 結構為 Python；MCP 官方 SDK 成熟；團隊 Junior SEO 可維護 | 2026-09-30 |
| ADR-002 | Ahrefs 為唯一付費資料源（REST API v3，`AHREFS_API_TOKEN`） | 本版不做多付費源；GKP/GSC 免費補量測與自家 grounding | 2026-09-30 |
| ADR-003 | 無 LLM：所有輸出（分組、fan-out、原型 prompt）皆規則驅動 | 可測、確定性、離線可跑；升級路徑才考慮 LLM | 2026-09-30 |
| ADR-004 | Offline-first：缺 key / 斷網永不 raise，client 回 None，輸出標「估算」 | 測試全套綠 + 降級路徑本身有測試 | 2026-09-30 |
| ADR-005 | 輸出 = 單一 markdown 報告檔（reports/，gitignore） | 產品身分：一鍵內容計劃，不是資料管道 | 2026-09-30 |
| ADR-006 | GKP adapter = 子進程 spawn 本地 Keyword Planner MCP server（stdio MCP client），回傳 markdown 表格自寫 parser | GKP 量比 Ahrefs 準且支援地區/語言；`KEYWORD_PLANNER_MCP_COMMAND` 可選 | 2026-09-30 |
| ADR-007 | GSC adapter = service account（`GOOGLE_APPLICATION_CREDENTIALS` + `GSC_SITE_URL`），end date 一律 today−3 | GSC finalization lag，否則尾部天數是 0 假值 | 2026-09-30 |
| ADR-008 | 量測優先序 GKP > Ahrefs > 無資料（標估算）；無 volume 的問句照列（標「無量測數據」） | 信譽原則：猜測永不偽裝成實測；無量 ≠ 無需求 | 2026-09-30 |
| ADR-009 | 確定性：日期以參數注入；排序 tie-break = keyword 字典序 | 同輸入兩次運行 byte-level 相同 | 2026-09-30 |
| ADR-010 | GSC 優先經 First Page agency MCP（remote，`FIRSTPAGE_MCP_TOKEN` + `FIRSTPAGE_MCP_URL`），無 token 才退 service account（ADR-007 路徑保留） | agency 已有 838 個 GSC properties 的 MCP 存取；免去逐客戶 service account；GA4 工具同 server 亦有（升級路徑，本版未用） | 2026-10-06 |
| ADR-011 | §7 gap 排除 Ahrefs organic `is_branded=true` 的列（另保留品牌 pattern 過濾作雙保險） | dogfood 發現對手品牌別名（tut/mc music/人名）漏網；is_branded 是 Ahrefs 自帶欄位，資料驅動免維護別名表；品牌流量難搶，排除不損失機會 | 2026-10-06 |
| ADR-012 | 分組簽章加策展泛詞停用表（老師/歌曲/歌詞/課程/教學/推薦/收費/價錢/好唔好/dcard/lihkg/ptt/chord/hong/kong/best），泛詞不作合併依據。**不**採 DF 門檻：單一主題池中正主題詞出現率天然超標，DF 會誤殺主分組（dogfood 實證） | dogfood：結他 hub 吸 373 spokes 的根因是泛詞簽章鏈式合併；停用表與 §4.1 詞表哲學一致，來源=2026-10-06 dogfood 觀察 | 2026-10-06 |
| ADR-013 | 原型產生設總量下限：cluster 總量 <50 的組在 §3/§4 照列，§5 標「低優先，略過原型」 | dogfood 雜訊小組各產 5 原型屬雜訊放大；閾值 50 為單一數據點啟發式，註明待調；高量離題雜訊（冰結 720）仍需完全版相關性過濾——本 ADR 不處理 | 2026-10-06 |
| ADR-014 | 頁面類型 → 允許 intent 對照（blog→informational+commercial；service→transactional+commercial；home→navigational+transactional） | 日常需求 #1：topic keyword 必須符合 target page intent；啟發式對照表，調整須立 ADR | 2026-10-07 |
| ADR-015 | title tag 像素估算用字元類寬度表（CJK/全形 16px、窄字 4px、小寫/數字 8px、大寫 10px、W/M 12px），上限 580px；建議模板 = primary keyword +「 \| 品牌」，超限先棄品牌後綴 | 日常需求 #2；580px 為 Google SERP 桌面截斷實務（moz.com/learn/seo/title-tag）；估算是近似值（±10%）非精確排版 | 2026-10-07 |
| ADR-016 | 語域分類器：口語（廣東話標記 邊度/邊間/點樣/唔/嘅/咩/咁/冇/咗/嚟…）／書面語（如何/什麼/收費/價格/比較…）／中性；口語優先；「係」不入表（關係/體係誤中），改用係咩/係咪 | 日常需求 #4：HK 內容需配合書面語或口語語域 | 2026-10-07 |
| ADR-017 | blog topic 打包：score 降序貪婪——primary + 同簽章/同 parent_topic 的 2–4 個 secondary；硬性過濾 volume>0（#3）與 intent 匹配（#1）；secondary <2 標 needs_more_keywords；GEO prompts 不受限（#7，規格 §5 無量照列原則不變） | 日常需求 #5/#6；打包獨立於 build_report 八節模板（新 tool `plan_blog_topics`，不改 §6 驗收標準） | 2026-10-07 |
| ADR-018 | 開發工具鏈：`pip install -e ".[dev]"`（setuptools + console script `geo-keyword-planner`）、零依賴 `.env` 載入（config.load_dotenv，已存在 env 不覆蓋）、ruff 為 lint 閘門（BLE001/DTZ011 為 ADR-004/009 刻意豁免；RUF001-003 中文全形標點豁免）、GKP_MCP_DEBUG=1 時子進程 stderr 直通 | 債務清理 2026-10-07：打包/runbook/lint 補齊 | 2026-10-07 |

## 已驗證 API 坑（上線前真 key 打一次逐條複核）

| 坑 | 正解 | 驗證狀態 |
|---|------|---------|
| Ahrefs organic-keywords `date` 必填 | 缺了 400；一律帶昨天 | ✅ live 2026-10-06（date=2026-10-05 成功） |
| Ahrefs 當日日期被拒 | 一律用昨天 | ✅ live 2026-10-06 |
| 排名欄位 `best_position`；KD 兩 endpoint 不同名（organic=`keyword_difficulty`、overview=`difficulty`） | 照抄 | ✅ live 2026-10-06（兩欄位皆有值） |
| Ahrefs overview 意圖欄位 `intents`（複數布林物件） | 不是 `intent` | ✅ live 2026-10-06 |
| 關鍵字含逗號拆壞批次 | 送出前過濾 | ✅（單元測試；live 無需覆） |
| apex 域名查不到 | target 用 www 變體 | ✅ live 2026-10-06（parklandmusic.com.hk→www 有資料） |
| **Ahrefs v3 只收 GET** | POST 回 405 `{"error": "POST"}`；一律 GET+query | ✅ live 2026-10-06（debug 時發現，transport 已改 GET） |
| **macOS python.org Python 無 root 憑證** | SSL CERTIFICATE_VERIFY_FAILED → 跑 `Install Certificates.command` | ✅ live 2026-10-06 |
| GSC finalization lag | end date = today−3 | ✅ live（firstpage MCP，2026-10-06） |
| GKP 經 MCP 回傳 markdown 表格 | 表格 parser（去外框管線符號） | ⚠️ 修訂：現行 kwp-mcp-hk.js 回 **JSON envelope**（historical=`keywords`、ideas=`ideas`，行內 `text`+`avgMonthlySearches`）；JSON 解析為主、markdown parser 保留 fallback。✅ live 2026-10-06 |
| firstpage MCP 工具名帶前綴 | 後綴比對找工具（同 gkp_adapter 模式） | ✅ live（2026-10-06） |
| firstpage gsc site 同域多 property（http/https/www） | 精確匹配中優先 https 再 www | ✅ live（parklandmusic：6,603 查詢） |
| **GSC service account 後備路徑（ADR-007）未經 live 驗證** | 無測試憑證可打；firstpage 為主路徑已驗證。使用後備前須真憑證打一次（規格工程底線 #3），否則考慮移除 | ⚠️ 待驗證（2026-10-07 標註） |

> 註（2026-10-06 dogfood）：live 來源在擴展清單 limit 邊界有上游資料波動（同秒級兩次運行一詞之差），屬 API 側行為，我方處理層確定性已由 mock 測試與連續 live 運行 byte 相同證明。不重試原則（規格 §3）不變。
| GKP 經 MCP 回傳 markdown 表格 | 表格 parser（去外框管線符號） | 待 live 驗證 |
