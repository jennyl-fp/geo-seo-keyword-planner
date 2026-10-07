"""GKP adapter — 子進程 Keyword Planner MCP server，量測覆蓋（T1.5；ADR-006）。

  KEYWORD_PLANNER_MCP_COMMAND（stdio 指令）→ Popen → JSON-RPC 2.0（行分隔 JSON）
  → tools/list 找工具（名稱以後綴比對，容忍 server 前綴差異）
  → tools/call → 回傳是 markdown 表格（規格 §3 坑）→ 自寫 parser。

只在 metrics 步驟做量測覆蓋；量測優先序 GKP > Ahrefs（ADR-008）。
每次呼叫起一個全新 session（低用量，免 stale state）。
缺指令 / spawn 失敗 / 逾時 / RPC 錯誤 → None、永不 raise、不重試（ADR-004）。
None =「來源不可用」，{} = 查無資料。today 不介入（GKP 無日期參數）。
"""

from __future__ import annotations

import itertools
import json
import os
import re
import select
import shlex
import subprocess
import time
from collections.abc import Callable

from config import Config
from rules.cjk_norm import normalize_keyword

ProcessFactory = Callable[[str], object]

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "geo-keyword-planner", "version": "0.1.0"}
_TIMEOUT_SECONDS = 60

_LANGUAGE_BY_COUNTRY = {"hk": "zh-Hant", "tw": "zh-Hant", "cn": "zh-Hans", "sg": "en"}

_IDEAS_SUFFIX = "generate_keyword_ideas"
_METRICS_SUFFIX = "get_historical_metrics"


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    """把 markdown 表格解析成 dict 列；首行管線行 = header，跳過分隔行。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if not lines:
        return []
    header = _split_cells(lines[0])
    if not header:
        return []
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if _is_separator(line):
            continue
        cells = _split_cells(line)
        rows.append(dict(zip(header, cells, strict=False)))
    return rows


def _split_cells(line: str) -> list[str]:
    parts = line.split("|")
    return [p.strip() for p in parts[1:-1]]


def _is_separator(line: str) -> bool:
    cells = _split_cells(line)
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def _volume_from_cell(cell: str) -> int | None:
    """「1,000」→1000；區間「10 – 100」→中點 55；「–」/無數字→None。"""
    numbers = re.findall(r"\d[\d,.]*", cell)
    if not numbers:
        return None
    values = [float(n.replace(",", "")) for n in numbers]
    if len(values) == 1:
        return int(values[0])
    return round((values[0] + values[1]) / 2)


def volumes_from_table(text: str) -> dict[str, int | None]:
    """markdown 表格 → {正規化關鍵字: volume}；volume 欄 = header 含
    search/volume 者；關鍵字欄 = header 含 keyword 者，缺省用首欄。
    同鍵首見為準（保序、確定性）。"""
    rows = parse_markdown_table(text)
    if not rows:
        return {}
    header = list(rows[0].keys())
    keyword_col = next((h for h in header if "keyword" in h.lower()), header[0])
    volume_col = next(
        (h for h in header if "search" in h.lower() or "volume" in h.lower()), None
    )
    volumes: dict[str, int | None] = {}
    for row in rows:
        keyword = normalize_keyword(row.get(keyword_col, ""))
        if not keyword:
            continue
        if keyword not in volumes:
            volumes[keyword] = _volume_from_cell(row.get(volume_col or "", ""))
    return volumes


def volumes_from_payload(text: str) -> dict[str, int | None]:
    """工具回應文字 → {正規化關鍵字: volume}。

    兩種已知形態（2026-10-06 live 驗證 + 規格 §3 坑）：
      1. JSON envelope（kwp-mcp-hk.js 現行版）：historical 用
         {"keywords": [...]}；ideas 用 {"ideas": [...]}——
         行內皆 {"text": ..., "avgMonthlySearches": ...}
      2. markdown 表格（規格 §3 記載的舊版）→ fallback volumes_from_table。
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        payload = None
    rows = None
    if isinstance(payload, dict):
        rows = payload.get("keywords") or payload.get("ideas")
    if not isinstance(rows, list):
        return volumes_from_table(text)
    volumes: dict[str, int | None] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        keyword = normalize_keyword(str(row.get("text") or row.get("keyword") or ""))
        if not keyword:
            continue
        volume = row.get(
            "avgMonthlySearches", row.get("avg_monthly_searches", row.get("volume"))
        )
        if keyword not in volumes:
            volumes[keyword] = int(volume) if isinstance(volume, (int, float)) else None
    return volumes


def _default_spawn(command: str) -> object:
    """GKP_MCP_DEBUG=1 時 stderr 直通（除錯 spawn）；預設 DEVNULL。"""
    args = shlex.split(command)
    return subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None if os.environ.get("GKP_MCP_DEBUG") else subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )


class _StdioMcpSession:
    """最小 stdio MCP client：initialize → tools/list → tools/call。"""

    def __init__(self, process: object, timeout: float = _TIMEOUT_SECONDS) -> None:
        self._process = process
        self._timeout = timeout
        self._ids = itertools.count(1)

    def _send(self, message: dict) -> None:
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _read(self, expected_id: int) -> dict:
        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("GKP MCP response timeout")
            try:
                ready, _, _ = select.select([self._process.stdout], [], [], remaining)
                if not ready:
                    raise TimeoutError("GKP MCP response timeout")
            except (OSError, ValueError, TypeError):
                pass
            line = self._process.stdout.readline()
            if not line:
                raise EOFError("GKP MCP process closed stdout")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == expected_id:
                if "error" in message:
                    raise RuntimeError(f"GKP MCP error: {message['error']}")
                return message.get("result") or {}

    def start(self) -> None:
        request_id = next(self._ids)
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": _CLIENT_INFO,
                },
            }
        )
        self._read(request_id)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def find_tool(self, suffix: str) -> str | None:
        request_id = next(self._ids)
        self._send({"jsonrpc": "2.0", "id": request_id, "method": "tools/list"})
        result = self._read(request_id)
        for tool in result.get("tools") or []:
            name = tool.get("name", "")
            if name.endswith(suffix):
                return name
        return None

    def call_tool(self, name: str, arguments: dict) -> dict:
        request_id = next(self._ids)
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        return self._read(request_id)

    def close(self) -> None:
        try:
            self._process.stdin.close()
        except Exception:
            pass
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except Exception:
            pass


class GkpAdapter:
    def __init__(self, config: Config, process_factory: ProcessFactory | None = None) -> None:
        self._command = config.gkp_mcp_command
        self._spawn = process_factory or _default_spawn

    def _query(self, tool_suffix: str, arguments: dict) -> dict[str, int | None] | None:
        if not self._command:
            return None
        try:
            session = _StdioMcpSession(self._spawn(self._command))
            try:
                session.start()
                tool_name = session.find_tool(tool_suffix)
                if tool_name is None:
                    return None
                result = session.call_tool(tool_name, arguments)
            finally:
                session.close()
        except Exception:
            return None
        return volumes_from_payload(_response_text(result))

    def historical_metrics(
        self,
        keywords: list[str],
        country: str = "hk",
        language: str | None = None,
    ) -> dict[str, int | None] | None:
        """精確關鍵字量測 — metrics 步驟的 volume 覆蓋（ADR-008 優先序用）。"""
        cleaned = [kw.strip() for kw in keywords if kw.strip()]
        if not cleaned:
            return {}
        return self._query(
            _METRICS_SUFFIX,
            {
                "keywords": cleaned,
                "geo_target_constants": [country],
                "language": language or _LANGUAGE_BY_COUNTRY.get(country, "zh-Hant"),
            },
        )

    def generate_ideas(
        self,
        seeds: list[str],
        country: str = "hk",
        language: str | None = None,
    ) -> dict[str, int | None] | None:
        """種子 → 關鍵字建議（含量測）— expand 步驟的 GKP 補量測。"""
        cleaned = [kw.strip() for kw in seeds if kw.strip()]
        if not cleaned:
            return {}
        return self._query(
            _IDEAS_SUFFIX,
            {
                "seed_keywords": cleaned,
                "geo_target_constants": [country],
                "language": language or _LANGUAGE_BY_COUNTRY.get(country, "zh-Hant"),
            },
        )


def _response_text(result: dict) -> str:
    parts = result.get("content") or []
    return "\n".join(
        part.get("text", "") for part in parts if isinstance(part, dict)
    )
