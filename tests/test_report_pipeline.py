"""T2.3 驗收測試：一鍵編排全管線（expand→metrics→分組→評分→問句/fanout
→原型→渲染）；量測優先序；估算降級；byte-level 確定性（diff 為空）。"""

import filecmp

from fakes import NO_KEY, ahrefs_client, fake_gkp, gsc_client, no_gkp

from report import build_report

MATCHING = {
    "keywords": [
        {"keyword": "smart office solution", "volume": 720},
        {"keyword": "what is smart office", "volume": 90},
        {"keyword": "智能辦公室幾錢", "volume": 30},
    ]
}
OVERVIEW = {
    "keywords": [
        {
            "keyword": "smart office",
            "volume": 1200,
            "difficulty": 35,
            "intents": {"informational": True},
            "parent_topic": "smart office",
        },
        {
            "keyword": "smart office solution",
            "volume": 720,
            "difficulty": 30,
            "intents": {"commercial": True},
            "parent_topic": "smart office",
        },
        {
            "keyword": "what is smart office",
            "volume": 90,
            "difficulty": 12,
            "intents": {"informational": True},
            "parent_topic": "smart office",
        },
        {
            "keyword": "智能辦公室幾錢",
            "volume": 30,
            "difficulty": 8,
            "intents": {"transactional": True},
            "parent_topic": "smart office",
        },
    ]
}
OWN = {"keywords": [{"keyword": "smart office", "volume": 1200, "best_position": 9, "keyword_difficulty": 35}]}
COMPETITOR = {
    "keywords": [
        {"keyword": "smart office", "volume": 1200, "best_position": 3, "keyword_difficulty": 35},
        {"keyword": "crm hong kong", "volume": 500, "best_position": 7, "keyword_difficulty": 25},
        {"keyword": "klalness pricing", "volume": 90, "best_position": 2, "keyword_difficulty": 5},
    ]
}
GKP_TABLE = (
    "| Keyword | Avg. Monthly Searches |\n|---|---|\n| smart office | 3,300 |"
)

_PATH_PAYLOADS = {
    "keywords-explorer/matching-terms": MATCHING,
    "keywords-explorer/related-terms": {"keywords": []},
    "keywords-explorer/search-suggestions": {"keywords": []},
    "keywords-explorer/overview": OVERVIEW,
}


def full_clients():
    return (
        ahrefs_client(
            payloads=_PATH_PAYLOADS,
            targets={"www.ownsite.hk": OWN, "www.klalness.com": COMPETITOR},
        ),
        gsc_client(
            payload={"rows": [{"keys": ["smart office solution"], "position": 14.0}]}
        ),
        fake_gkp(GKP_TABLE),
    )


def run_full(**overrides):
    params = {
        "seeds": ["smart office"],
        "domain": "ownsite.hk",
        "competitors": ["klalness.com"],
        "country": "hk",
        "today": "2026-10-02",
        "clients": full_clients(),
    }
    params.update(overrides)
    return build_report(**params)


class TestFullPipeline:
    def test_header_and_sources(self):
        markdown = run_full()
        assert markdown.splitlines()[0] == "# 內容計劃 — ownsite.hk（2026-10-02）"
        assert "Ahrefs=live" in markdown
        assert "GKP=live" in markdown
        assert "GSC=live" in markdown

    def test_volume_priority_gkp_wins(self):
        markdown = run_full()
        assert "| smart office | 3300 | 35 |" in markdown

    def test_scores_and_order(self):
        markdown = run_full()
        rows = markdown.splitlines()
        assert "| 智能辦公室幾錢 | 30 | 8 | transactional | bofu | 38.6 |" in rows
        assert "| smart office solution | 720 | 30 | informational | tofu | 47.3 |" in rows
        assert "| smart office | 3300 | 35 | informational | tofu | 36.4 |" in rows
        assert "| what is smart office | 90 | 12 | informational | tofu | 28.9 |" in rows
        section2 = markdown.split("## 2. 關鍵字清單")[1].split("## 3.")[0]
        ordered = [ln for ln in section2.splitlines() if ln.startswith("| ")]
        scores = [ln.rsplit("|", 2)[-2] for ln in ordered[2:]]
        assert scores == sorted(scores, key=float, reverse=True)

    def test_cluster_and_route(self):
        markdown = run_full()
        assert "| smart office | smart office | 4 | 4140 |" in markdown
        assert "1. hub：smart office（總量 4140）" in markdown

    def test_geo_questions_with_labels(self):
        markdown = run_full()
        assert "「what is smart office」（funnel=tofu，fanout=semantic）" in markdown
        assert "「智能辦公室幾錢」（funnel=bofu，fanout=attribute）" in markdown

    def test_prototypes_five(self):
        markdown = run_full()
        assert "- 原型 [definition] What is smart office?" in markdown
        assert "- 原型 [buying] Where can I buy smart office and how much does it cost?" in markdown
        assert "- 原型 [comparison] Which is better, smart office or klalness.com?" in markdown

    def test_branded_when_brand_in_hub(self):
        markdown = run_full(brands=("smart office",))
        assert "- 原型 [definition][branded] What is smart office?" in markdown

    def test_strike_section(self):
        markdown = run_full()
        assert "| smart office solution | 14 | 720 |" in markdown

    def test_gap_section(self):
        markdown = run_full()
        assert "| crm hong kong | 500 | 25 | klalness.com |" in markdown
        assert "klalness pricing" not in markdown


class TestDegradedPipeline:
    def test_all_sources_off_estimation_labels(self):
        clients = (
            ahrefs_client(with_key=False),
            gsc_client(config=NO_KEY),
            no_gkp(),
        )
        markdown = build_report(
            seeds=["smart office"],
            domain="ownsite.hk",
            competitors=["klalness.com"],
            today="2026-10-02",
            clients=clients,
        )
        assert "Ahrefs=估算（未接）" in markdown
        assert "GKP=估算（未接）" in markdown
        assert "GSC=估算（未接）" in markdown
        assert "| smart office | 無量測數據 | — | informational | tofu | 0.0 |" in markdown
        assert "GSC 未接，本節略" in markdown
        assert "（無差距資料" in markdown
        assert "主題分組：1 組" in markdown

    def test_no_competitors_skips_gap_calls(self):
        markdown = run_full(competitors=[])
        assert "（無差距資料" in markdown


class TestByteLevelDeterminism:
    def test_two_runs_identical(self, tmp_path):
        first = run_full(output_path=tmp_path / "a.md")
        second = run_full(output_path=tmp_path / "b.md")
        assert first == second
        assert filecmp.cmp(tmp_path / "a.md", tmp_path / "b.md", shallow=False)
        assert (tmp_path / "a.md").read_bytes() == (tmp_path / "b.md").read_bytes()

    def test_output_file_written(self, tmp_path):
        markdown = run_full(output_path=tmp_path / "report.md")
        assert (tmp_path / "report.md").read_text(encoding="utf-8") == markdown
