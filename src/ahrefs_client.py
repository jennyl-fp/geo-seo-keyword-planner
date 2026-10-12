"""Ahrefs API v3 client — 唯一付費資料源（ADR-002）。

規格 §3 已驗證的坑（本檔案照抄正解，上線前 T2.4 真 key 複核）：
  - organic-keywords 的 `date` 必填 → 缺了 400；一律帶上
  - 當日日期被拒（"bad date"）→ 一律用昨天（today 可注入，ADR-009）
  - organic 排名欄位 = `best_position`（不是 position）
  - KD 兩 endpoint 不同名：organic=`keyword_difficulty`、overview=`difficulty`
  - overview 意圖欄位 = `intents`（複數布林物件），不是 `intent`
  - 關鍵字含逗號會拆壞 `keywords` 逗號批次 → 送出前過濾
  - apex 域名查不到 → target 用 www 變體

缺 key（ADR-004 offline-first）與任何傳輸/解析錯誤：回 None、永不 raise、
不重試（規格 §3：錯誤直接降級）。None =「來源不可用」，下游標估算。
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from config import Config

Transport = Callable[[str, dict[str, str]], dict]

_BATCH_SIZE = 100
_TIMEOUT_SECONDS = 60

# Brand Radar 多平台資料源（2026-10 實測）：cited-domains / ai-responses 免 report_id
# 可 ad-hoc 查詢；claude 只支援 custom prompts（400 "models do not support Ahrefs
# dataset"）→ 一律排除（prepare_platforms 回傳 excluded 清單供上層聲明）。
BRAND_RADAR_PLATFORMS = (
    "chatgpt",
    "google_ai_overviews",
    "google_ai_mode",
    "gemini",
    "perplexity",
    "copilot",
    "grok",
)


@dataclass(frozen=True)
class KeywordMetric:
    keyword: str
    volume: int | None
    difficulty: int | None
    cpc: float | None
    intents: tuple[str, ...]
    parent_topic: str | None


@dataclass(frozen=True)
class ExpansionKeyword:
    keyword: str
    volume: int | None


@dataclass(frozen=True)
class OrganicKeyword:
    keyword: str
    volume: int | None
    best_position: int | None
    keyword_difficulty: int | None
    is_branded: bool = False


@dataclass(frozen=True)
class CitedDomain:
    domain: str
    pages: int | None
    responses: int | None


@dataclass(frozen=True)
class AiResponse:
    data_source: str | None
    country: str | None
    question: str | None
    volume: int | None
    links: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class BrandRadarCitations:
    """多平台引用快照；單一平台失敗 → 記 errors 續走其餘（ADR-004 變體：
    平台級降級而非整體回 None，供上層如實聲明覆蓋率）。"""

    citations_by_platform: dict[str, tuple[CitedDomain, ...]]
    errors: dict[str, str]


def _default_transport(token: str) -> Transport:
    def transport(path: str, form: dict[str, str]) -> dict:
        query = urllib.parse.urlencode(form)
        url = f"https://api.ahrefs.com/v3/{path}?{query}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    return transport


def prepare_keywords(keywords: list[str]) -> list[str]:
    """過濾含逗號與空字串、去重（保序）——含逗號會拆壞逗號批次（規格 §3）。"""
    cleaned = (kw.strip() for kw in keywords)
    return list(dict.fromkeys(kw for kw in cleaned if kw and "," not in kw))


def prepare_platforms(
    platforms: list[str] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """平台清單正規化（小寫、去空、去重保序）；None → 預設全集。
    回傳 (kept, excluded)：claude 一律排入 excluded（Ahrefs dataset 不支援，
    規格 §Brand Radar 實測 400），上層据此在輸出聲明。"""
    source = list(BRAND_RADAR_PLATFORMS) if platforms is None else [
        p.strip().lower() for p in platforms
    ]
    kept: list[str] = []
    excluded: list[str] = []
    for platform in source:
        if not platform:
            continue
        if platform == "claude":
            if "claude" not in excluded:
                excluded.append("claude")
            continue
        if platform not in kept:
            kept.append(platform)
    return tuple(kept), tuple(excluded)


def www_target(domain: str) -> str:
    """apex 域名（單一 dot、無 scheme）→ www 變體；其餘原樣（規格 §3）。

    已知限制：雙節 TLD（example.co.hk）不會被視為 apex，本版接受。
    """
    target = domain.strip().lower()
    for scheme in ("https://", "http://"):
        target = target.removeprefix(scheme)
    target = target.rstrip("/")
    if target.count(".") == 1:
        return f"www.{target}"
    return target


class AhrefsClient:
    def __init__(
        self,
        config: Config,
        transport: Transport | None = None,
        today: str | None = None,
    ) -> None:
        self._token = config.ahrefs_api_token
        self._transport = transport or _default_transport(self._token or "")
        base = today or date.today().isoformat()
        self._yesterday = (date.fromisoformat(base) - timedelta(days=1)).isoformat()

    @property
    def yesterday(self) -> str:
        return self._yesterday

    def _call(self, path: str, form: dict[str, str], expected_key: str = "keywords") -> dict | None:
        payload, _ = self._try_call(path, form, expected_key)
        return payload

    def _try_call(
        self, path: str, form: dict[str, str], expected_key: str = "keywords"
    ) -> tuple[dict | None, str | None]:
        """單次調用；回 (payload, error)。缺 key → (None, 'no token')；
        傳輸/解析錯 → (None, 訊息)。永不 raise、不重試（ADR-004）。"""
        if not self._token:
            return None, "no token"
        try:
            payload = self._transport(path, form)
        except Exception as exc:  # ADR-004：刻意 blind except，降級不重試
            return None, str(exc) or type(exc).__name__
        if not isinstance(payload, dict) or not isinstance(payload.get(expected_key), list):
            return None, f"malformed payload (missing '{expected_key}')"
        return payload, None

    def keyword_overview(
        self, keywords: list[str], country: str = "hk"
    ) -> dict[str, KeywordMetric] | None:
        """metrics 端點；批次 ≤100（規格 §2）；任一批次失敗 → 整體回 None。"""
        prepared = prepare_keywords(keywords)
        if not prepared:
            return {}
        results: dict[str, KeywordMetric] = {}
        for start in range(0, len(prepared), _BATCH_SIZE):
            chunk = prepared[start : start + _BATCH_SIZE]
            payload = self._call(
                "keywords-explorer/overview",
                {
                    "select": "keyword,volume,difficulty,cpc,intents,parent_topic",
                    "country": country,
                    "keywords": ",".join(chunk),
                },
            )
            if payload is None:
                return None
            for row in payload["keywords"]:
                keyword = row.get("keyword")
                if not keyword:
                    continue
                intents = row.get("intents")
                results[keyword] = KeywordMetric(
                    keyword=keyword,
                    volume=row.get("volume"),
                    difficulty=row.get("difficulty"),
                    cpc=row.get("cpc"),
                    intents=(
                        tuple(sorted(k for k, v in intents.items() if v))
                        if isinstance(intents, dict)
                        else ()
                    ),
                    parent_topic=row.get("parent_topic"),
                )
        return results

    def _expand(
        self, path: str, keywords: list[str], country: str, limit: int, extra: dict[str, str]
    ) -> list[ExpansionKeyword] | None:
        prepared = prepare_keywords(keywords)
        if not prepared:
            return []
        payload = self._call(
            path,
            {
                "select": "keyword,volume",
                "country": country,
                "keywords": ",".join(prepared),
                "order_by": "volume:desc",
                "limit": str(limit),
                **extra,
            },
        )
        if payload is None:
            return None
        return [
            ExpansionKeyword(keyword=row["keyword"], volume=row.get("volume"))
            for row in payload["keywords"]
            if row.get("keyword")
        ]

    def matching_terms(
        self, keywords: list[str], country: str = "hk", limit: int = 200
    ) -> list[ExpansionKeyword] | None:
        """三路擴展之一：matching terms（terms 模式）。"""
        return self._expand(
            "keywords-explorer/matching-terms",
            keywords,
            country,
            limit,
            {"match_mode": "terms", "terms": "all"},
        )

    def related_terms(
        self, keywords: list[str], country: str = "hk", limit: int = 200
    ) -> list[ExpansionKeyword] | None:
        """三路擴展之二：also rank for（同頁也排的詞）。"""
        return self._expand(
            "keywords-explorer/related-terms",
            keywords,
            country,
            limit,
            {"terms": "also_rank_for"},
        )

    def search_suggestions(
        self, keywords: list[str], country: str = "hk", limit: int = 200
    ) -> list[ExpansionKeyword] | None:
        """三路擴展之三：search suggestions（Suggest）。"""
        return self._expand(
            "keywords-explorer/search-suggestions",
            keywords,
            country,
            limit,
            {},
        )

    def organic_keywords(
        self, domain: str, country: str = "hk", limit: int = 200
    ) -> list[OrganicKeyword] | None:
        """gap 端點：對手在排的詞。date 必填 → 一律昨天（規格 §3）。"""
        payload = self._call(
            "site-explorer/organic-keywords",
            {
                "select": "keyword,volume,best_position,keyword_difficulty,is_branded",
                "target": www_target(domain),
                "date": self._yesterday,
                "country": country,
                "mode": "subdomains",
                "order_by": "volume:desc",
                "limit": str(limit),
            },
        )
        if payload is None:
            return None
        return [
            OrganicKeyword(
                keyword=row["keyword"],
                volume=row.get("volume"),
                best_position=row.get("best_position"),
                keyword_difficulty=row.get("keyword_difficulty"),
                is_branded=bool(row.get("is_branded")),
            )
            for row in payload["keywords"]
            if row.get("keyword")
        ]

    def brand_radar_cited_domains(
        self,
        brand: str,
        competitors: list[str],
        country: str = "hk",
        platforms: list[str] | None = None,
        limit: int = 1000,
    ) -> BrandRadarCitations | None:
        """Brand Radar：brand+competitors 競技組在每個 AI 平台被引用的域名。
        免 report_id（ad-hoc）；date=昨天（快照較完整）。
        單一平台失敗 → errors 記錄、其餘續走（平台級降級）。"""
        if not self._token or not brand.strip():
            return None
        kept, _ = prepare_platforms(platforms)
        if not kept:
            return None
        competitor_names = [c.strip() for c in competitors if c.strip()]
        citations: dict[str, tuple[CitedDomain, ...]] = {}
        errors: dict[str, str] = {}
        for platform in kept:
            payload, error = self._try_call(
                "brand-radar/cited-domains",
                {
                    "select": "domain,pages,responses",
                    "brand": brand,
                    "competitors": ",".join(competitor_names),
                    "data_source": platform,
                    "country": country,
                    "date": self._yesterday,
                    "limit": str(limit),
                },
                expected_key="domains",
            )
            if payload is None:
                errors[platform] = error or "unknown"
                continue
            citations[platform] = tuple(
                CitedDomain(
                    domain=row.get("domain", ""),
                    pages=row.get("pages"),
                    responses=row.get("responses"),
                )
                for row in payload["domains"]
                if row.get("domain")
            )
        return BrandRadarCitations(citations_by_platform=citations, errors=errors)

    def brand_radar_ai_responses(
        self,
        brand: str,
        competitors: list[str],
        country: str = "hk",
        platforms: list[str] | None = None,
        limit: int = 50,
    ) -> list[AiResponse] | None:
        """Brand Radar：真實 AI prompts（問題、平台、估算量、引用連結）。
        order_by=volume（此端點不接受 :desc 後綴，規格 §Brand Radar 實測 400）；
        claude 已排除（否則整批 400）。整體失敗 → None。"""
        kept, _ = prepare_platforms(platforms)
        if not self._token or not kept or not brand.strip():
            return None
        competitor_names = [c.strip() for c in competitors if c.strip()]
        payload = self._call(
            "brand-radar/ai-responses",
            {
                "select": "country,data_source,question,volume,links",
                "brand": brand,
                "competitors": ",".join(competitor_names),
                "data_source": ",".join(kept),
                "country": country,
                "order_by": "volume",
                "limit": str(limit),
            },
            expected_key="ai_responses",
        )
        if payload is None:
            return None
        return [
            AiResponse(
                data_source=row.get("data_source"),
                country=row.get("country"),
                question=row.get("question"),
                volume=row.get("volume"),
                links=tuple(
                    (link.get("url", ""), link.get("title"))
                    for link in row.get("links", [])
                    if isinstance(link, dict)
                ),
            )
            for row in payload["ai_responses"]
            if row.get("question")
        ]
