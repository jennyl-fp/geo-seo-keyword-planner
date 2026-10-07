"""共享測試 fakes — client/adapter 的可注入傳輸與子進程（離線契約）。

pytest importmode=prepend 會把 tests/ 放進 sys.path（無 __init__.py），
故各測試檔可直接 `from fakes import ...`。
"""

import json
from pathlib import Path

from ahrefs_client import AhrefsClient
from config import Config
from gkp_adapter import GkpAdapter
from gsc_client import GscClient

FIXTURES = Path(__file__).parent / "fixtures"
WITH_KEY = Config(ahrefs_api_token="tok")
NO_KEY = Config()
FULL_GSC = Config(gsc_credentials_path="/sa.json", gsc_site_url="sc-domain:example.hk")
TODAY = "2026-10-02"


def load_fixture(name: str) -> dict:
    return json.loads(load_fixture_text(name))


def load_fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeAhrefsTransport:
    """payloads: path → 回應；targets: form.target → 回應（優先，organic 用）；
    error: 所有呼叫拋出。calls 記錄 (path, form)。"""

    def __init__(self, payloads=None, targets=None, error=None):
        self._payloads = payloads or {}
        self._targets = targets or {}
        self._error = error
        self.calls = []

    def __call__(self, path, form):
        self.calls.append((path, dict(form)))
        if self._error is not None:
            raise self._error
        target = form.get("target")
        if target in self._targets:
            return self._targets[target]
        return self._payloads.get(path, {"keywords": []})


def ahrefs_client(payloads=None, targets=None, error=None, today=TODAY, with_key=True):
    return AhrefsClient(
        WITH_KEY if with_key else NO_KEY,
        transport=FakeAhrefsTransport(payloads, targets, error),
        today=today,
    )


class FakeGscTransport:
    """payload: 固定回應（預設空 rows）；error: 全拋。calls 記錄 (site_url, body)。"""

    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error
        self.calls = []

    def __call__(self, site_url, body):
        self.calls.append((site_url, dict(body)))
        if self._error is not None:
            raise self._error
        return self._payload if self._payload is not None else {"rows": []}


def gsc_client(payload=None, error=None, today=TODAY, config=FULL_GSC):
    return GscClient(config, transport=FakeGscTransport(payload, error), today=today)


class FakeStdin:
    def __init__(self):
        self.lines = []

    def write(self, data):
        self.lines.append(data)

    def flush(self):
        pass

    def close(self):
        pass


class FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines)

    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class FakeProcess:
    def __init__(self, response_lines):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(response_lines)
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def rpc(result, request_id):
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})


def scripted_gkp_lines(text):
    """標準 initialize → tools/list（兩工具）→ tools/call 三行腳本。"""
    return [
        rpc({"capabilities": {}}, 1),
        rpc(
            {
                "tools": [
                    {"name": "keyword-planner_generate_keyword_ideas"},
                    {"name": "keyword-planner_get_historical_metrics"},
                ]
            },
            2,
        ),
        rpc({"content": [{"type": "text", "text": text}]}, 3),
    ]


def fake_gkp(text=None, command="uv run kp"):
    """每次呼叫 spawn 新 FakeProcess（stdout 自帶副本，可重複使用）。"""
    if text is None:
        text = load_fixture_text("fx_gkp_markdown.txt")
    lines = scripted_gkp_lines(text)
    return GkpAdapter(
        Config(gkp_mcp_command=command),
        process_factory=lambda cmd: FakeProcess(lines),
    )


def no_gkp():
    return GkpAdapter(NO_KEY)


class FakeFirstpageCaller:
    def __init__(self, rows=None, sites=None, error=None):
        self._rows = rows
        self._sites = sites
        self._error = error
        self.calls = []

    def tool_names(self):
        if self._error:
            raise self._error
        return [
            "firstpage_gsc_list_sites",
            "firstpage_gsc_search_performance",
            "firstpage_ga4_list_properties",
        ]

    def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if self._error:
            raise self._error
        if name.endswith("gsc_list_sites"):
            return [
                {"external_id": site, "display_name": site, "gmail_email": "a@b.c"}
                for site in self._sites or []
            ]
        return self._rows or []
