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


def www_target(domain: str) -> str:
    """apex 域名（單一 dot、無 scheme）→ www 變體；其餘原樣（規格 §3）。

    已知限制：雙節 TLD（example.co.hk）不會被視為 apex，簡易版接受。
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

    def _call(self, path: str, form: dict[str, str]) -> dict | None:
        if not self._token:
            return None
        try:
            payload = self._transport(path, form)
        except Exception:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("keywords"), list):
            return None
        return payload

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
