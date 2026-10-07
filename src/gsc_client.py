"""GSC client — 自家排名 grounding（T1.4；ADR-007）。

一個函式就好（規格 §8.1）：top_queries() → {keyword: position}。
用途：① strike-distance 加分 ② gap 排除自家已排名詞。

規格 §3 坑（GSC finalization lag）：end date = today−3，
否則尾部天數是 0 假值。today 可注入（ADR-009 確定性）。

回傳鍵一律經 cjk_norm 正規化（T1.1 是跨源比對地基）；
同鍵碰撞取最佳（最小）position。
缺憑證/site URL 或任何錯誤 → None、永不 raise、不重試（ADR-004）；
None =「來源不可用」，{} = 查無資料。
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, timedelta

from config import Config
from rules.cjk_norm import normalize_keyword

Transport = Callable[[str, dict], dict]

_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
_TIMEOUT_SECONDS = 60
_ROW_LIMIT = 25000


def _default_transport(credentials_path: str) -> Transport:
    """service account → access token → REST query（google-auth 惰性匯入，
    離線測試套件不依賴它；live 驗證見 T2.4）。"""

    def transport(site_url: str, body: dict) -> dict:
        import google.auth.transport.requests
        import google.oauth2.service_account

        credentials = google.oauth2.service_account.Credentials.from_service_account_file(
            credentials_path, scopes=[_SCOPE]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        url = (
            "https://searchconsole.googleapis.com/webmasters/v3/sites/"
            f"{urllib.parse.quote(site_url, safe='')}/searchAnalytics/query"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    return transport


class GscClient:
    def __init__(
        self,
        config: Config,
        transport: Transport | None = None,
        today: str | None = None,
    ) -> None:
        self._site_url = config.gsc_site_url
        self._credentials_path = config.gsc_credentials_path
        self._transport = transport or _default_transport(self._credentials_path or "")
        base = today or date.today().isoformat()
        self._end = (date.fromisoformat(base) - timedelta(days=3)).isoformat()

    @property
    def end_date(self) -> str:
        return self._end

    def _call(self, body: dict) -> dict | None:
        if not self._site_url or not self._credentials_path:
            return None
        try:
            payload = self._transport(self._site_url, body)
        except Exception:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
            return None
        return payload

    def top_queries(self, window_days: int = 90, domain: str | None = None) -> dict[str, float] | None:
        """近 window_days 天（end 含當日）各 query 的平均 position。

        domain 參數為 firstpage 介面對齊而設，本 client site 由 env 固定，忽略。
        已知限制：單次請求 rowLimit 25000，不分頁（低用量，簡易版接受）。
        """
        end = date.fromisoformat(self._end)
        start = (end - timedelta(days=window_days - 1)).isoformat()
        payload = self._call(
            {
                "startDate": start,
                "endDate": self._end,
                "dimensions": ["query"],
                "rowLimit": _ROW_LIMIT,
            }
        )
        if payload is None:
            return None
        positions: dict[str, float] = {}
        for row in payload["rows"]:
            keys = row.get("keys")
            if not isinstance(keys, list) or not keys:
                continue
            keyword = normalize_keyword(str(keys[0]))
            position = row.get("position")
            if not keyword or not isinstance(position, (int, float)):
                continue
            if keyword not in positions or position < positions[keyword]:
                positions[keyword] = float(position)
        return positions
