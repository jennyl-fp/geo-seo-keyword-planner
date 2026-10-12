"""Brand Radar 驗收測試：缺 key 回 None 永不 raise；claude 一律排除；
逐平台查詢帶 data_source/country/date=昨天；平台級失敗記 errors 續走；
ai-responses 解析（links 元組、volume）；config AHREFS_API_KEY fallback。"""

from fakes import NO_KEY, WITH_KEY, ahrefs_client, load_fixture

from ahrefs_client import (
    BRAND_RADAR_PLATFORMS,
    AhrefsClient,
    AiResponse,
    BrandRadarCitations,
    CitedDomain,
    prepare_platforms,
)
from config import Config, load_config


class TestMissingKey:
    def test_cited_domains_returns_none_no_calls(self):
        client = ahrefs_client(with_key=False)
        assert client.brand_radar_cited_domains("Example", ["Comp A"]) is None

    def test_ai_responses_returns_none_no_calls(self):
        client = ahrefs_client(with_key=False)
        assert client.brand_radar_ai_responses("Example", ["Comp A"]) is None


class TestPreparePlatforms:
    def test_none_returns_full_set(self):
        kept, excluded = prepare_platforms(None)
        assert kept == BRAND_RADAR_PLATFORMS
        assert excluded == ()

    def test_claude_always_excluded(self):
        kept, excluded = prepare_platforms(["ChatGPT", "claude", "gemini", "claude"])
        assert kept == ("chatgpt", "gemini")
        assert excluded == ("claude",)

    def test_empty_and_dedup(self):
        kept, excluded = prepare_platforms(["", "grok", "Grok", " "])
        assert kept == ("grok",)
        assert excluded == ()


class TestCitedDomains:
    def _client(self, datasources=None):
        return ahrefs_client(
            datasources={"chatgpt": load_fixture("fx_brand_radar_cited.json")},
            payloads={"brand-radar/cited-domains": load_fixture("fx_brand_radar_cited.json")},
        )

    def test_per_platform_form_and_parse(self):
        client = self._client()
        result = client.brand_radar_cited_domains(
            "Origami Florist",
            ["Free Concept", "Simply Grand"],
            country="hk",
            platforms=["chatgpt"],
        )
        assert isinstance(result, BrandRadarCitations)
        path, form = client._transport.calls[0]
        assert path == "brand-radar/cited-domains"
        assert form["select"] == "domain,pages,responses"
        assert form["brand"] == "Origami Florist"
        assert form["competitors"] == "Free Concept,Simply Grand"
        assert form["data_source"] == "chatgpt"
        assert form["country"] == "hk"
        assert form["date"] == "2026-10-01"  # 昨天（today=2026-10-02 注入）
        assert result.citations_by_platform["chatgpt"][1] == CitedDomain(
            domain="origamiflorist.co", pages=1, responses=2
        )
        assert result.errors == {}

    def test_partial_platform_failure_degrades(self):
        client = ahrefs_client(
            datasources={"chatgpt": load_fixture("fx_brand_radar_cited.json")}
            # gemini 無 fixture → fallback {"keywords": []} → malformed → errors
        )
        result = client.brand_radar_cited_domains(
            "Example", ["Comp A"], platforms=["chatgpt", "gemini"]
        )
        assert set(result.citations_by_platform) == {"chatgpt"}
        assert "gemini" in result.errors

    def test_empty_brand_returns_none(self):
        client = self._client()
        assert client.brand_radar_cited_domains("  ", ["Comp A"]) is None

    def test_transport_error_recorded_not_raised(self):
        client = ahrefs_client(error=RuntimeError("boom"))
        result = client.brand_radar_cited_domains("Example", [], platforms=["chatgpt"])
        assert result.citations_by_platform == {}
        assert result.errors["chatgpt"] == "boom"


class TestAiResponses:
    def test_fixture_parse(self):
        client = ahrefs_client(
            payloads={"brand-radar/ai-responses": load_fixture("fx_brand_radar_ai_responses.json")}
        )
        result = client.brand_radar_ai_responses("Example", ["Comp A"], limit=20)
        assert result == [
            AiResponse(
                data_source="chatgpt",
                country="hk",
                question="香港邊間婚禮佈置公司好？",
                volume=120,
                links=(
                    ("https://www.misssuki.com/products/wedding", "婚禮場地佈置"),
                    ("https://example.hk/guide", None),
                ),
            ),
            AiResponse(
                data_source="perplexity",
                country="hk",
                question="how much does wedding decoration cost in hong kong?",
                volume=80,
                links=(),
            ),
        ]

    def test_claude_excluded_from_data_source(self):
        client = ahrefs_client(
            payloads={"brand-radar/ai-responses": load_fixture("fx_brand_radar_ai_responses.json")}
        )
        client.brand_radar_ai_responses("Example", [], platforms=["chatgpt", "claude"])
        assert client._transport.calls[0][1]["data_source"] == "chatgpt"

    def test_malformed_returns_none(self):
        client = ahrefs_client(payloads={"brand-radar/ai-responses": {"error": "x"}})
        assert client.brand_radar_ai_responses("Example", []) is None


class TestConfigFallback:
    def test_ahrefs_api_key_env_fallback(self):
        config = load_config({"AHREFS_API_KEY": "fallback-tok"})
        assert config == Config(ahrefs_api_token="fallback-tok")

    def test_primary_env_wins(self):
        config = load_config({"AHREFS_API_TOKEN": "primary", "AHREFS_API_KEY": "fallback"})
        assert config.ahrefs_api_token == "primary"


class TestServerImpl:
    def test_tracked_summary_matrix(self):
        import server

        datasources = {
            "chatgpt": load_fixture("fx_brand_radar_cited.json"),
            "gemini": {"domains": []},
        }
        transport_calls = []

        class Transport:
            def __call__(self, path, form):
                transport_calls.append((path, dict(form)))
                return datasources[form["data_source"]]

        _, gsc, gkp = server._build_clients()
        ahrefs = AhrefsClient(WITH_KEY, transport=Transport(), today="2026-10-02")
        result = server.brand_radar_audit_impl(
            brand="Origami Florist",
            competitors=["Free Concept"],
            tracked_domains=["www.origamiflorist.co", "3concept.com.hk", "weddinghashtag.hk"],
            country="hk",
            platforms=["chatgpt", "gemini"],
            clients=(ahrefs, gsc, gkp),
        )
        assert result["sources"] == {"ahrefs_brand_radar": True}
        # www. 前綴正規化後命中 chatgpt 引用
        assert result["tracked_summary"]["origamiflorist.co"]["chatgpt"] == {
            "responses": 2, "pages": 1
        }
        assert result["tracked_summary"]["3concept.com.hk"]["chatgpt"] == {
            "responses": 1, "pages": 0
        }
        assert result["tracked_summary"]["weddinghashtag.hk"]["gemini"] == {
            "responses": 0, "pages": 0
        }
        assert result["tracked_totals"] == {
            "origamiflorist.co": 2,
            "3concept.com.hk": 1,
            "weddinghashtag.hk": 0,
        }
        assert result["platforms_queried"] == ["chatgpt", "gemini"]

    def test_no_token_degrades_with_note(self):
        import server

        _, gsc, gkp = server._build_clients()
        ahrefs = AhrefsClient(NO_KEY, today="2026-10-02")
        result = server.brand_radar_audit_impl(
            brand="X", competitors=[], tracked_domains=["x.co"],
            country="hk", platforms=None, clients=(ahrefs, gsc, gkp),
        )
        assert result["sources"] == {"ahrefs_brand_radar": False}
        assert "note" in result
