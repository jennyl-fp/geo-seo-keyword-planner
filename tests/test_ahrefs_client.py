"""T1.3 驗收測試：缺 key 回 None 永不 raise；坑照抄（date=昨天、
best_position/keyword_difficulty、intents 複數、逗號過濾、apex→www）；
每 endpoint 一份 fixture；不重試。"""

import pytest
from fakes import NO_KEY, WITH_KEY, load_fixture
from fakes import FakeAhrefsTransport as FakeTransport

from ahrefs_client import (
    AhrefsClient,
    ExpansionKeyword,
    OrganicKeyword,
    prepare_keywords,
    www_target,
)


class TestMissingKey:
    @pytest.mark.parametrize(
        "method,args",
        [
            ("keyword_overview", {"keywords": ["smart office"]}),
            ("matching_terms", {"keywords": ["smart office"]}),
            ("related_terms", {"keywords": ["smart office"]}),
            ("search_suggestions", {"keywords": ["smart office"]}),
            ("organic_keywords", {"domain": "example.hk"}),
        ],
    )
    def test_returns_none_never_raises(self, method, args):
        transport = FakeTransport()
        client = AhrefsClient(NO_KEY, transport=transport, today="2026-10-02")
        assert getattr(client, method)(**args) is None
        assert transport.calls == []


class TestKeywordOverview:
    def test_fixture_happy_path(self):
        transport = FakeTransport(
            {"keywords-explorer/overview": load_fixture("fx_keyword_overview.json")}
        )
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        result = client.keyword_overview(["smart office", "智能辦公室"])
        assert result is not None
        assert set(result) == {"smart office", "smart office hong kong", "智能辦公室"}
        row = result["smart office"]
        assert row.volume == 1200
        assert row.difficulty == 35
        assert row.cpc == 250
        assert row.intents == ("commercial", "informational")
        assert row.parent_topic == "smart office"
        null_row = result["smart office hong kong"]
        assert null_row.cpc is None
        assert null_row.intents == ()

    def test_comma_and_empty_keywords_filtered_before_send(self):
        transport = FakeTransport()
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        client.keyword_overview(["a, b", "", "  ", "smart office", "smart office"])
        sent = transport.calls[0][1]["keywords"]
        assert sent == "smart office"

    def test_batch_chunks_of_100(self):
        transport = FakeTransport()
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        keywords = [f"kw{i}" for i in range(150)]
        client.keyword_overview(keywords)
        assert len(transport.calls) == 2
        first, second = transport.calls
        assert len(first[1]["keywords"].split(",")) == 100
        assert len(second[1]["keywords"].split(",")) == 50

    def test_chunk_failure_degrades_to_none(self):
        transport = FakeTransport(error=RuntimeError("network down"))
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        assert client.keyword_overview([f"kw{i}" for i in range(150)]) is None
        assert len(transport.calls) == 1

    def test_empty_input_returns_empty_no_calls(self):
        transport = FakeTransport()
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        assert client.keyword_overview(["", "a,b"]) == {}
        assert transport.calls == []


class TestExpansionThreePaths:
    def test_matching_terms_fixture(self):
        transport = FakeTransport(
            {"keywords-explorer/matching-terms": load_fixture("fx_matching_terms.json")}
        )
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        result = client.matching_terms(["smart office"])
        assert result == [
            ExpansionKeyword(keyword="smart office solution", volume=720),
            ExpansionKeyword(keyword="smart office system hong kong", volume=110),
            ExpansionKeyword(keyword="智能辦公室系統", volume=540),
            ExpansionKeyword(keyword="smart office 推薦", volume=None),
        ]
        form = transport.calls[0][1]
        assert form["match_mode"] == "terms"
        assert form["terms"] == "all"
        assert form["order_by"] == "volume:desc"

    def test_related_terms_fixture(self):
        transport = FakeTransport(
            {"keywords-explorer/related-terms": load_fixture("fx_related_terms.json")}
        )
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        result = client.related_terms(["smart office"])
        assert [r.keyword for r in result] == [
            "office automation",
            "ioT office solution",
            "辦公室自動化",
        ]
        assert transport.calls[0][1]["terms"] == "also_rank_for"

    def test_search_suggestions_fixture(self):
        transport = FakeTransport(
            {"keywords-explorer/search-suggestions": load_fixture("fx_search_suggestions.json")}
        )
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        result = client.search_suggestions(["smart office"])
        assert result[1] == ExpansionKeyword(keyword="smart office 公司", volume=None)


class TestOrganicKeywords:
    def _client(self, transport):
        return AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")

    def test_date_is_yesterday_required(self):
        transport = FakeTransport(
            {"site-explorer/organic-keywords": load_fixture("fx_organic_keywords.json")}
        )
        self._client(transport).organic_keywords("www.example.hk")
        form = transport.calls[0][1]
        assert form["date"] == "2026-10-01"

    def test_fixture_fields(self):
        transport = FakeTransport(
            {"site-explorer/organic-keywords": load_fixture("fx_organic_keywords.json")}
        )
        result = self._client(transport).organic_keywords("www.example.hk")
        assert result[0] == OrganicKeyword(
            keyword="smart office", volume=1200, best_position=3, keyword_difficulty=35
        )
        assert result[2].best_position is None
        assert result[3].is_branded is True
        assert result[0].is_branded is False

    def test_apex_domain_gets_www(self):
        transport = FakeTransport(
            {"site-explorer/organic-keywords": load_fixture("fx_organic_keywords.json")}
        )
        self._client(transport).organic_keywords("example.hk")
        assert transport.calls[0][1]["target"] == "www.example.hk"


class TestWwwTarget:
    @pytest.mark.parametrize(
        "domain,expected",
        [
            ("example.hk", "www.example.hk"),
            ("Example.HK", "www.example.hk"),
            ("https://example.hk/", "www.example.hk"),
            ("www.example.hk", "www.example.hk"),
            ("blog.example.hk", "blog.example.hk"),
            ("example.co.hk", "example.co.hk"),
        ],
    )
    def test_variants(self, domain, expected):
        assert www_target(domain) == expected


class TestDegradation:
    def test_transport_error_returns_none_no_retry(self):
        transport = FakeTransport(error=RuntimeError("boom"))
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        assert client.organic_keywords("example.hk") is None
        assert client.matching_terms(["x"]) is None
        assert len(transport.calls) == 2

    def test_malformed_payload_returns_none(self):
        transport = FakeTransport({"keywords-explorer/overview": {"error": "x"}})
        client = AhrefsClient(WITH_KEY, transport=transport, today="2026-10-02")
        assert client.keyword_overview(["smart office"]) is None


class TestPrepareKeywords:
    def test_filter_and_dedup_preserves_order(self):
        assert prepare_keywords(["b", "a, b", "", " a ", "b"]) == ["b", "a"]


class TestDeterminism:
    def test_yesterday_derived_from_injected_today(self):
        client = AhrefsClient(WITH_KEY, transport=FakeTransport(), today="2026-01-01")
        assert client.yesterday == "2025-12-31"
