"""T1.5 驗收測試：markdown 表格 parser；子進程 MCP（JSON-RPC）流程；
缺指令回 None；錯誤降級不重試。"""

import json

from fakes import (
    NO_KEY as NO_COMMAND,
)
from fakes import (
    FakeProcess,
    load_fixture_text,
    rpc,
    scripted_gkp_lines,
)

from config import Config
from gkp_adapter import (
    GkpAdapter,
    parse_markdown_table,
    volumes_from_payload,
    volumes_from_table,
)

WITH_COMMAND = Config(gkp_mcp_command="uv run keyword-planner-server")


def gkp_text() -> str:
    return load_fixture_text("fx_gkp_markdown.txt")


def scripted_process(text: str) -> FakeProcess:
    return FakeProcess(scripted_gkp_lines(text))


class TestParseMarkdownTable:
    def test_rows_and_headers(self):
        rows = parse_markdown_table(gkp_text())
        assert len(rows) == 4
        assert rows[0]["Keyword"] == "smart office"
        assert rows[0]["Avg. Monthly Searches"] == "2,400"
        assert rows[1]["Avg. Monthly Searches"] == "10 – 100"

    def test_no_table_returns_empty(self):
        assert parse_markdown_table("no table here\njust text") == []


class TestVolumesFromTable:
    def test_fixture(self):
        volumes = volumes_from_table(gkp_text())
        assert volumes == {
            "smart office": 2400,
            "smart office hong kong": 55,
            "智能辦公室": 880,
            "智能辦公室系統": 260,
        }

    def test_cjk_space_normalized(self):
        text = "| Keyword | Volume |\n|---|---|\n| 鑽戒 推薦 | 300 |"
        assert volumes_from_table(text) == {"鑽戒推薦": 300}

    def test_dash_cell_is_none(self):
        text = "| Keyword | Volume |\n|---|---|\n| abc | – |"
        assert volumes_from_table(text) == {"abc": None}

    def test_missing_volume_column_gives_none(self):
        text = "| Keyword | Competition |\n|---|---|\n| abc | LOW |"
        assert volumes_from_table(text) == {"abc": None}


class TestVolumesFromPayload:
    def test_json_envelope(self):
        text = json.dumps(
            {
                "geo": ["geoTargetConstants/2344"],
                "keywords": [
                    {"text": "smart office", "avgMonthlySearches": 110},
                    {"text": "智能辦公室", "avgMonthlySearches": 260},
                ],
            }
        )
        assert volumes_from_payload(text) == {"smart office": 110, "智能辦公室": 260}

    def test_json_envelope_missing_volume_is_none(self):
        text = json.dumps({"keywords": [{"text": "abc"}]})
        assert volumes_from_payload(text) == {"abc": None}

    def test_json_envelope_cjk_normalized(self):
        text = json.dumps({"keywords": [{"text": "鑽戒 推薦", "avgMonthlySearches": 300}]})
        assert volumes_from_payload(text) == {"鑽戒推薦": 300}

    def test_markdown_fallback(self):
        assert volumes_from_payload(gkp_text()) == {
            "smart office": 2400,
            "smart office hong kong": 55,
            "智能辦公室": 880,
            "智能辦公室系統": 260,
        }

    def test_json_ideas_envelope(self):
        text = json.dumps(
            {
                "seedKeywords": ["smart office"],
                "ideas": [
                    {"text": "smart office", "avgMonthlySearches": 110},
                    {"text": "crm smart", "avgMonthlySearches": 0},
                ],
            }
        )
        assert volumes_from_payload(text) == {"smart office": 110, "crm smart": 0}

    def test_non_envelope_json_falls_back_to_table(self):
        assert volumes_from_payload('{"count": 0}') == {}

    def test_plain_text_returns_empty(self):
        assert volumes_from_payload("no table, no json") == {}


class TestGkpAdapter:
    def _written_json(self, process):
        return [json.loads(line) for line in process.stdin.lines]

    def test_missing_command_returns_none_no_spawn(self):
        spawned = []
        adapter = GkpAdapter(NO_COMMAND, process_factory=lambda cmd: spawned.append(cmd))
        assert adapter.historical_metrics(["smart office"]) is None
        assert adapter.generate_ideas(["smart office"]) is None
        assert spawned == []

    def test_historical_metrics_happy_path(self):
        process = scripted_process(gkp_text())
        adapter = GkpAdapter(WITH_COMMAND, process_factory=lambda cmd: process)
        result = adapter.historical_metrics(["smart office", "智能辦公室"], country="hk")
        assert result == {
            "smart office": 2400,
            "smart office hong kong": 55,
            "智能辦公室": 880,
            "智能辦公室系統": 260,
        }
        messages = self._written_json(process)
        assert messages[0]["method"] == "initialize"
        calls = [m for m in messages if m["method"] == "tools/call"]
        assert len(calls) == 1
        assert calls[0]["params"]["name"] == "keyword-planner_get_historical_metrics"
        assert calls[0]["params"]["arguments"]["geo_target_constants"] == ["hk"]
        assert calls[0]["params"]["arguments"]["language"] == "zh-Hant"
        assert calls[0]["params"]["arguments"]["keywords"] == [
            "smart office",
            "智能辦公室",
        ]
        assert process.terminated is True

    def test_generate_ideas_happy_path(self):
        process = scripted_process(gkp_text())
        adapter = GkpAdapter(WITH_COMMAND, process_factory=lambda cmd: process)
        result = adapter.generate_ideas(["smart office"], country="hk")
        assert "smart office" in result
        calls = [m for m in self._written_json(process) if m["method"] == "tools/call"]
        assert calls[0]["params"]["name"] == "keyword-planner_generate_keyword_ideas"
        assert calls[0]["params"]["arguments"]["seed_keywords"] == ["smart office"]

    def test_empty_input_returns_empty_no_spawn(self):
        def fail_on_spawn(command):
            raise AssertionError("should not spawn")

        adapter = GkpAdapter(WITH_COMMAND, process_factory=fail_on_spawn)
        assert adapter.historical_metrics(["", "  "]) == {}
        assert adapter.generate_ideas([]) == {}

    def test_tool_not_found_returns_none(self):
        process = FakeProcess(
            [
                rpc({"capabilities": {}}, 1),
                rpc({"tools": [{"name": "unrelated_tool"}]}, 2),
            ]
        )
        adapter = GkpAdapter(WITH_COMMAND, process_factory=lambda cmd: process)
        assert adapter.historical_metrics(["x"]) is None

    def test_rpc_error_returns_none(self):
        process = FakeProcess(
            [
                rpc({"capabilities": {}}, 1),
                rpc({"tools": [{"name": "keyword-planner_get_historical_metrics"}]}, 2),
                json.dumps({"jsonrpc": "2.0", "id": 3, "error": {"code": -32000}}),
            ]
        )
        adapter = GkpAdapter(WITH_COMMAND, process_factory=lambda cmd: process)
        assert adapter.historical_metrics(["x"]) is None
        assert process.terminated is True

    def test_spawn_failure_returns_none(self):
        def boom(command):
            raise FileNotFoundError("command not found")

        adapter = GkpAdapter(WITH_COMMAND, process_factory=boom)
        assert adapter.historical_metrics(["x"]) is None

    def test_process_dies_returns_none(self):
        adapter = GkpAdapter(WITH_COMMAND, process_factory=lambda cmd: FakeProcess([]))
        assert adapter.historical_metrics(["x"]) is None

    def test_non_table_response_returns_empty(self):
        process = scripted_process("no table, just a friendly message")
        adapter = GkpAdapter(WITH_COMMAND, process_factory=lambda cmd: process)
        assert adapter.historical_metrics(["x"]) == {}
