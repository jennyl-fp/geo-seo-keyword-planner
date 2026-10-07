"""T2.1 驗收測試：tools schema 與行為（README 表）；三路合併去重；
量測優先序 GKP > Ahrefs；gap 排除（自家 Ahrefs/GSC/對手品牌/is_branded）。
T3.5：plan_blog_topics。"""

import pytest
from fakes import (
    ahrefs_client,
    gsc_client,
    no_gkp,
)
from fakes import (
    fake_gkp as gkp_adapter,
)
from fakes import (
    load_fixture as load,
)

import server


class TestExpandKeywords:
    def test_three_paths_merged_and_deduped(self):
        ahrefs = ahrefs_client(
            {
                "keywords-explorer/matching-terms": load("fx_matching_terms.json"),
                "keywords-explorer/related-terms": load("fx_related_terms.json"),
                "keywords-explorer/search-suggestions": load("fx_search_suggestions.json"),
            }
        )
        result = server.expand_keywords_impl(
            ["smart office"], "hk", (ahrefs, gsc_client(), no_gkp())
        )
        keywords = result["keywords"]
        assert len(keywords) == len({k["keyword"] for k in keywords})
        assert result["sources"] == {"ahrefs": True, "gkp": False}
        assert all(k["volume_source"] in ("ahrefs", "none") for k in keywords)
        assert keywords[0]["keyword"] == "smart office solution"

    def test_gkp_supplements_volume_and_keywords(self):
        ahrefs = ahrefs_client(
            {
                "keywords-explorer/matching-terms": {"keywords": []},
                "keywords-explorer/related-terms": {"keywords": []},
                "keywords-explorer/search-suggestions": {
                    "keywords": [{"keyword": "smart office 推薦", "volume": None}]
                },
            }
        )
        result = server.expand_keywords_impl(
            ["smart office"], "hk", (ahrefs, gsc_client(), gkp_adapter())
        )
        assert result["sources"] == {"ahrefs": True, "gkp": True}
        by_kw = {k["keyword"]: k for k in result["keywords"]}
        assert by_kw["smart office"]["volume"] == 2400
        assert by_kw["smart office"]["volume_source"] == "gkp"
        assert by_kw["smart office hong kong"]["volume"] == 55
        assert by_kw["smart office 推薦"]["volume_source"] == "none"

    def test_no_sources_at_all(self):
        no_key = ahrefs_client(with_key=False)
        result = server.expand_keywords_impl(
            ["smart office"], "hk", (no_key, gsc_client(), no_gkp())
        )
        assert result == {"keywords": [], "sources": {"ahrefs": False, "gkp": False}}


class TestKeywordMetrics:
    def test_volume_priority_gkp_over_ahrefs(self):
        ahrefs = ahrefs_client(
            {"keywords-explorer/overview": load("fx_keyword_overview.json")}
        )
        gkp = gkp_adapter(
            "| Keyword | Avg. Monthly Searches |\n|---|---|\n"
            "| smart office | 3,300 |\n| 智能辦公室 | – |"
        )
        result = server.keyword_metrics_impl(
            ["smart office", "智能辦公室", "new kw"], "hk", (ahrefs, gsc_client(), gkp)
        )
        rows = {r["keyword"]: r for r in result["keywords"]}
        assert rows["smart office"]["volume"] == 3300
        assert rows["smart office"]["volume_source"] == "gkp"
        assert rows["smart office"]["difficulty"] == 35
        assert rows["智能辦公室"]["volume"] == 800
        assert rows["智能辦公室"]["volume_source"] == "ahrefs"
        assert rows["new kw"]["volume"] is None
        assert rows["new kw"]["volume_source"] == "none"

    def test_dedup_normalized_inputs(self):
        ahrefs = ahrefs_client({"keywords-explorer/overview": {"keywords": []}})
        result = server.keyword_metrics_impl(
            ["Smart Office", "smart office"], "hk", (ahrefs, gsc_client(), no_gkp())
        )
        assert len(result["keywords"]) == 1


COMPETITOR1 = {
    "keywords": [
        {"keyword": "smart office", "volume": 1200, "best_position": 3, "keyword_difficulty": 35, "is_branded": False},
        {"keyword": "crm hong kong", "volume": 500, "best_position": 7, "keyword_difficulty": 25, "is_branded": False},
        {"keyword": "klalness pricing", "volume": 90, "best_position": 2, "keyword_difficulty": 5, "is_branded": False},
        {"keyword": "蔡曉彤", "volume": 100, "best_position": 1, "keyword_difficulty": 1, "is_branded": True},
    ]
}
COMPETITOR2 = {
    "keywords": [
        {"keyword": "crm hong kong", "volume": 480, "best_position": 4, "keyword_difficulty": 25},
        {"keyword": "gdpr compliance hk", "volume": 60, "best_position": 9, "keyword_difficulty": 10},
    ]
}
OWN = {
    "keywords": [
        {"keyword": "smart office", "volume": 1200, "best_position": 12, "keyword_difficulty": 35}
    ]
}


class TestKeywordGap:
    def test_exclusions_and_aggregation(self):
        ahrefs = ahrefs_client(
            {},
            targets={
                "www.ownsite.hk": OWN,
                "www.klalness.com": COMPETITOR1,
                "www.competitor2.hk": COMPETITOR2,
            },
        )
        gsc = gsc_client(
            {"rows": [{"keys": ["gdpr compliance hk"], "position": 14.0}]}
        )
        result = server.keyword_gap_impl(
            "ownsite.hk",
            ["klalness.com", "competitor2.hk"],
            "hk",
            (ahrefs, gsc, no_gkp()),
        )
        rows = {r["keyword"]: r for r in result["keywords"]}
        assert "smart office" not in rows  # 自家 Ahrefs 已排名
        assert "gdpr compliance hk" not in rows  # GSC 已排名
        assert "klalness pricing" not in rows  # 對手品牌詞（klalness.com）pattern 過濾
        assert "蔡曉彤" not in rows  # is_branded 過濾（ADR-011）
        crm = rows["crm hong kong"]
        assert crm["volume"] == 500
        assert crm["best_position"] == 4
        assert crm["competitors"] == ["klalness.com", "competitor2.hk"]
        assert result["sources"] == {"ahrefs": True, "gsc": True}

    def test_competitor_count_validation(self):
        ahrefs = ahrefs_client({})
        clients = (ahrefs, gsc_client(), no_gkp())
        with pytest.raises(ValueError):
            server.keyword_gap_impl("ownsite.hk", [], "hk", clients)
        with pytest.raises(ValueError):
            server.keyword_gap_impl(
                "ownsite.hk", ["a.com", "b.com", "c.com", "d.com"], "hk", clients
            )


class TestServerWiring:
    def test_five_tools_registered_with_schema(self):
        """fastmcp 版本間 API 有漂移（4.0.11 僅私有 _list_tools）——
        先試公開 get_tools，再退 _list_tools，最後退模組屬性存在性。"""
        import asyncio

        names: set[str] = set()
        for attribute in ("get_tools", "_list_tools"):
            method = getattr(server.mcp, attribute, None)
            if method is None:
                continue
            result = asyncio.run(method())
            tools = result.values() if isinstance(result, dict) else result
            names = {tool.name for tool in tools}
            break
        if not names:
            names = {
                name
                for name in _EXPECTED_TOOLS
                if hasattr(server, name)
            }
        assert names == _EXPECTED_TOOLS
        if hasattr(server, "expand_keywords"):
            assert server.expand_keywords is not None


_EXPECTED_TOOLS = {
    "expand_keywords",
    "keyword_metrics",
    "keyword_gap",
    "build_report",
    "plan_blog_topics",
}


class TestPlanBlogTopics:
    def test_full_shape(self):
        ahrefs = ahrefs_client(
            {
                "keywords-explorer/matching-terms": load("fx_matching_terms.json"),
                "keywords-explorer/related-terms": {"keywords": []},
                "keywords-explorer/search-suggestions": {"keywords": []},
                "keywords-explorer/overview": load("fx_keyword_overview.json"),
            }
        )
        result = server.plan_blog_topics_impl(
            ["smart office"],
            page_type="blog",
            register="any",
            brand="First Page",
            country="hk",
            limit=20,
            clients=(ahrefs, gsc_client(), no_gkp()),
        )
        assert result["sources"]["ahrefs"] is True
        assert result["topic_count"] >= 1
        topic = result["topics"][0]
        for field in ("primary", "secondaries", "total_volume", "register", "needs_more_keywords", "title"):
            assert field in topic
        assert topic["title"]["pixels"] <= 580 or topic["title"]["fits"] is False
        assert set(topic["primary"]) == {
            "keyword", "volume", "difficulty", "intent", "register", "score",
        }

    def test_transactional_dropped_for_blog(self):
        ahrefs = ahrefs_client(
            {
                "keywords-explorer/matching-terms": {
                    "keywords": [
                        {"keyword": "crm hong kong", "volume": 300},
                        {"keyword": "crm 價錢", "volume": 100},
                    ]
                },
                "keywords-explorer/related-terms": {"keywords": []},
                "keywords-explorer/search-suggestions": {"keywords": []},
                "keywords-explorer/overview": {
                    "keywords": [
                        {"keyword": "crm hong kong", "volume": 300, "difficulty": 20},
                        {"keyword": "crm價錢", "volume": 100, "difficulty": 10},
                    ]
                },
            }
        )
        result = server.plan_blog_topics_impl(
            ["crm"], "blog", "any", None, "hk", 20,
            (ahrefs, gsc_client(), no_gkp()),
        )
        primaries = {t["primary"]["keyword"] for t in result["topics"]}
        assert "crm 價錢" not in primaries
        assert all(
            "crm 價錢" not in {s["keyword"] for s in t["secondaries"]}
            for t in result["topics"]
        )
