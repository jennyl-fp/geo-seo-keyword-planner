"""ADR-010 驗收測試：firstpage MCP GSC client——top_queries 契約、
today−3、site 解析（env 優先→domain 匹配）、降級不 raise。"""

from fakes import FakeFirstpageCaller as FakeCaller

from config import Config
from firstpage_client import FirstpageGscClient, _extract_payload

NO_TOKEN = Config()
WITH_TOKEN = Config(firstpage_token="bearer-xyz")

ROWS = [
    {"keys": ["smart office"], "clicks": 12, "impressions": 340, "position": 8.2},
    {"keys": ["Smart  Office"], "clicks": 1, "impressions": 50, "position": 4.0},
    {"keys": ["鑽戒 推薦"], "clicks": 3, "impressions": 90, "position": 18.7},
    {"keys": [""], "clicks": 0, "impressions": 5, "position": 33.0},
]

SITES = ["http://example.com.hk/", "https://example.com.hk/", "https://www.example.com.hk/", "https://other.hk/"]


def make_client(caller, config=WITH_TOKEN, today="2026-10-02", site=None):
    cfg = Config(
        firstpage_token=config.firstpage_token,
        gsc_site_url=site or config.gsc_site_url,
    )
    return FirstpageGscClient(cfg, caller=caller, today=today)


class TestMissingToken:
    def test_returns_none_no_calls(self):
        client = FirstpageGscClient(NO_TOKEN, today="2026-10-02")
        assert client.top_queries(domain="example.com.hk") is None
        assert client.gsc_sites() is None


class TestTopQueries:
    def test_contract_normalized_and_merged(self):
        caller = FakeCaller(rows=ROWS, sites=SITES)
        result = make_client(caller).top_queries(domain="example.com.hk")
        assert result == {"smart office": 4.0, "鑽戒推薦": 18.7}

    def test_dates_today_minus_3_and_window(self):
        caller = FakeCaller(rows=ROWS, sites=SITES)
        make_client(caller).top_queries(window_days=28, domain="example.com.hk")
        arguments = [args for name, args in caller.calls if name.endswith("gsc_search_performance")]
        assert arguments[0]["start_date"] == "2026-09-02"
        assert arguments[0]["end_date"] == "2026-09-29"
        assert arguments[0]["group_by"] == ["query"]
        assert arguments[0]["site_url"] == "https://www.example.com.hk/"

    def test_site_env_overrides_discovery(self):
        caller = FakeCaller(rows=ROWS, sites=SITES)
        make_client(caller, site="https://fixed.hk/").top_queries(domain="example.com.hk")
        arguments = [args for name, args in caller.calls if name.endswith("gsc_search_performance")]
        assert arguments[0]["site_url"] == "https://fixed.hk/"

    def test_subdomain_fallback_match(self):
        caller = FakeCaller(rows=ROWS, sites=["https://shop.example.com.hk/"])
        result = make_client(caller).top_queries(domain="example.com.hk")
        assert result is not None

    def test_https_www_preferred_among_exact_matches(self):
        caller = FakeCaller(rows=ROWS, sites=SITES)
        make_client(caller).top_queries(domain="example.com.hk")
        arguments = [args for name, args in caller.calls if name.endswith("gsc_search_performance")]
        assert arguments[0]["site_url"] == "https://www.example.com.hk/"

    def test_no_matching_site_returns_none(self):
        caller = FakeCaller(rows=ROWS, sites=["https://unrelated.hk/"])
        assert make_client(caller).top_queries(domain="example.com.hk") is None

    def test_no_domain_and_no_env_returns_none(self):
        caller = FakeCaller(rows=ROWS, sites=SITES)
        assert make_client(caller, site=None).top_queries() is None

    def test_empty_rows_returns_empty_dict(self):
        caller = FakeCaller(rows=[], sites=SITES)
        assert make_client(caller).top_queries(domain="example.com.hk") == {}


class TestDegradation:
    def test_error_returns_none(self):
        caller = FakeCaller(error=RuntimeError("http 500"))
        client = make_client(caller)
        assert client.top_queries(domain="example.com.hk") is None
        assert client.gsc_sites() is None

    def test_tool_not_found_returns_none(self):
        class NoTools(FakeCaller):
            def tool_names(self):
                return ["unrelated"]

        assert make_client(NoTools(rows=ROWS)).top_queries(domain="x.hk") is None

    def test_malformed_rows_skipped(self):
        rows = [
            {"keys": ["ok kw"], "position": 5},
            {"keys": [], "position": 2},
            {"keys": ["str pos"], "position": "x"},
            "garbage",
        ]
        caller = FakeCaller(rows=rows, sites=SITES)
        assert make_client(caller).top_queries(domain="example.com.hk") == {"ok kw": 5.0}


class TestExtractPayload:
    def test_data_attribute_first(self):
        from typing import ClassVar

        class R:
            data: ClassVar = [{"a": 1}]
            content = None

        assert _extract_payload(R()) == [{"a": 1}]

    def test_content_text_json(self):
        from typing import ClassVar

        class Part:
            text = '[{"b": 2}]'

        class R:
            data = None
            content: ClassVar = [Part()]

        assert _extract_payload(R()) == [{"b": 2}]

    def test_plain_text_passthrough(self):
        from typing import ClassVar

        class Part:
            text = "no json"

        class R:
            data = None
            content: ClassVar = [Part()]

        assert _extract_payload(R()) == "no json"


class TestDeterminism:
    def test_end_date_from_injected_today(self):
        client = make_client(FakeCaller(), today="2026-01-01")
        assert client.end_date == "2025-12-29"
