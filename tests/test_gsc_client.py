"""T1.4 驗收測試：top_queries() → {keyword: position}；end = today−3；
正規化鍵 + 同鍵取最佳排名；缺憑證回 None 不 raise。"""

import pytest
from fakes import FULL_GSC as FULL
from fakes import FakeGscTransport as FakeTransport
from fakes import load_fixture

from config import Config
from gsc_client import GscClient


def make_client(transport, config=FULL, today="2026-10-02"):
    return GscClient(config, transport=transport, today=today)


class TestMissingCredentials:
    @pytest.mark.parametrize(
        "config",
        [
            Config(),
            Config(gsc_site_url="sc-domain:example.hk"),
            Config(gsc_credentials_path="/sa.json"),
        ],
    )
    def test_returns_none_no_calls(self, config):
        transport = FakeTransport()
        assert make_client(transport, config=config).top_queries() is None
        assert transport.calls == []


class TestDates:
    def test_end_is_today_minus_3(self):
        transport = FakeTransport()
        make_client(transport).top_queries(window_days=90)
        body = transport.calls[0][1]
        assert body["endDate"] == "2026-09-29"
        assert body["startDate"] == "2026-07-02"
        assert body["dimensions"] == ["query"]

    def test_custom_window(self):
        transport = FakeTransport()
        make_client(transport).top_queries(window_days=28)
        body = transport.calls[0][1]
        assert (body["startDate"], body["endDate"]) == ("2026-09-02", "2026-09-29")

    def test_site_url_passed_through(self):
        transport = FakeTransport()
        make_client(transport).top_queries()
        assert transport.calls[0][0] == "sc-domain:example.hk"


class TestTopQueries:
    def test_fixture_normalized_and_merged(self):
        transport = FakeTransport(load_fixture("fx_gsc_top_queries.json"))
        result = make_client(transport).top_queries()
        assert result == {
            "smart office": 4.0,
            "鑽戒推薦": 18.7,
            "crm system": 12.5,
        }

    def test_empty_rows_returns_empty_dict(self):
        result = make_client(FakeTransport()).top_queries()
        assert result == {}

    def test_malformed_row_skipped(self):
        payload = {
            "rows": [
                {"keys": ["ok kw"], "position": 5},
                {"keys": [], "position": 2},
                {"keys": ["no pos"]},
                {"keys": ["str pos"], "position": "x"},
            ]
        }
        result = make_client(FakeTransport(payload)).top_queries()
        assert result == {"ok kw": 5.0}


class TestDegradation:
    def test_transport_error_returns_none_no_retry(self):
        transport = FakeTransport(error=RuntimeError("quota"))
        assert make_client(transport).top_queries() is None
        assert len(transport.calls) == 1

    def test_malformed_payload_returns_none(self):
        assert make_client(FakeTransport({"foo": 1})).top_queries() is None
        assert make_client(FakeTransport({"rows": None})).top_queries() is None


class TestDeterminism:
    def test_end_date_from_injected_today(self):
        client = make_client(FakeTransport(), today="2026-01-01")
        assert client.end_date == "2025-12-29"
