"""First Page agency MCP adapter — GSC 經 remote MCP（ADR-010）。

  FIRSTPAGE_MCP_TOKEN（Bearer）+ FIRSTPAGE_MCP_URL
  （預設 https://mcp.firstpage.com.hk/mcp/，取自 opencode 設定）
  → fastmcp Client（StreamableHttpTransport）
  → tools：gsc_list_sites（發現 properties）、gsc_search_performance
  （GSC API 原生 rows：keys/clicks/impressions/ctr/position）。

工具名以後綴比對（容忍 server 端前綴差異，同 gkp_adapter 模式）。
top_queries() 契約與 gsc_client.GscClient 相同：正規化鍵、同鍵取最佳
（最小）position、end = today−3（finalization lag，規格 §3 坑不變）。
site 解析順序：GSC_SITE_URL env → 依報表 domain 從 gsc_list_sites
匹配（host 全等優先，其次子字串，external_id 排序後首見——確定性）。
缺 token / 錯誤 → None、永不 raise、不重試（ADR-004）。
GA4 工具（ga4_list_properties 等）本 server 亦有，簡易版規格未用到，
列為升級路徑（DECISIONS.md ADR-010）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta
from typing import Any, Protocol

from config import Config
from rules.cjk_norm import normalize_keyword

_TIMEOUT_SECONDS = 60


class McpCaller(Protocol):
    def call_tool(self, name: str, arguments: dict) -> Any: ...

    def tool_names(self) -> list[str]: ...


class FastMcpCaller:
    """fastmcp HTTP caller；每次呼叫建立新連線（低用量，免 stale session）。"""

    def __init__(self, url: str, token: str, timeout: float = _TIMEOUT_SECONDS) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout

    def _run(self, coroutine):
        return asyncio.run(
            asyncio.wait_for(coroutine, timeout=self._timeout)
        )

    def _client(self):
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        transport = StreamableHttpTransport(
            url=self._url,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        return Client(transport)

    def call_tool(self, name: str, arguments: dict) -> Any:
        async def run():
            async with self._client() as client:
                result = await client.call_tool(name, arguments)
                return _extract_payload(result)

        return self._run(run())

    def tool_names(self) -> list[str]:
        async def run():
            async with self._client() as client:
                tools = await client.list_tools()
                return [tool.name for tool in tools]

        return self._run(run())


def _extract_payload(result: Any) -> Any:
    """fastmcp CallToolResult → Python 資料（data → structured → content JSON）。"""
    for attribute in ("data", "structured_content", "structuredContent"):
        value = getattr(result, attribute, None)
        if value is not None:
            return value
    parts = getattr(result, "content", None) or []
    texts = [
        part.text for part in parts if hasattr(part, "text") and isinstance(part.text, str)
    ]
    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except (json.JSONDecodeError, TypeError):
        return joined or None


class FirstpageGscClient:
    def __init__(
        self,
        config: Config,
        caller: McpCaller | None = None,
        today: str | None = None,
    ) -> None:
        self._token = config.firstpage_token
        self._url = config.resolved_firstpage_url
        self._site_url = config.gsc_site_url
        self._caller = caller or (
            FastMcpCaller(self._url, self._token) if self._token else None
        )
        base = today or date.today().isoformat()
        self._end = (date.fromisoformat(base) - timedelta(days=3)).isoformat()
        self._tool_cache: dict[str, str | None] = {}

    @property
    def end_date(self) -> str:
        return self._end

    def _find_tool(self, suffix: str) -> str | None:
        if suffix not in self._tool_cache:
            try:
                names = self._caller.tool_names()
                self._tool_cache[suffix] = next(
                    (name for name in names if name.endswith(suffix)), None
                )
            except Exception:
                self._tool_cache[suffix] = None
        return self._tool_cache[suffix]

    def _call(self, suffix: str, arguments: dict) -> Any:
        if not self._token or self._caller is None:
            return None
        name = self._find_tool(suffix)
        if name is None:
            return None
        try:
            return self._caller.call_tool(name, arguments)
        except Exception:
            return None

    def gsc_sites(self) -> list[str] | None:
        payload = self._call("gsc_list_sites", {})
        if not isinstance(payload, list):
            return None
        return sorted(
            site.get("external_id")
            for site in payload
            if isinstance(site, dict) and site.get("external_id")
        )

    def _resolve_site(self, domain: str | None) -> str | None:
        if self._site_url:
            return self._site_url
        if not domain:
            return None
        sites = self.gsc_sites()
        if sites is None:
            return None
        host = domain.lower().strip()
        for scheme in ("https://", "http://"):
            host = host.removeprefix(scheme)
        host = host.split("/")[0].removeprefix("www.")
        exact = [s for s in sites if _site_host(s) == host]
        if exact:
            exact.sort(key=lambda s: (0 if s.startswith("https") else 1, 0 if "www." in s else 1))
            return exact[0]
        fuzzy = [s for s in sites if host in _site_host(s)]
        return fuzzy[0] if fuzzy else None

    def top_queries(
        self, window_days: int = 90, domain: str | None = None
    ) -> dict[str, float] | None:
        """近 window_days 天各 query 平均 position（契約同 GscClient.top_queries）。"""
        site = self._resolve_site(domain)
        if not site:
            return None
        end = date.fromisoformat(self._end)
        start = (end - timedelta(days=window_days - 1)).isoformat()
        payload = self._call(
            "gsc_search_performance",
            {
                "site_url": site,
                "start_date": start,
                "end_date": self._end,
                "group_by": ["query"],
                "row_limit": 25000,
            },
        )
        if not isinstance(payload, list):
            return None
        positions: dict[str, float] = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
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


def _site_host(site_url: str) -> str:
    host = site_url.lower().strip()
    for scheme in ("https://", "http://"):
        host = host.removeprefix(scheme)
    return host.split("/")[0].removeprefix("www.")
