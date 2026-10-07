"""T2.2 驗收測試：八節逐節對照 README §6 模板；表格欄位；無量測數據標示；
gap top 20 上限；GSC 未接略過；確定性（兩次渲染相同）。"""

from report import (
    GAP_TOP_N,
    ReportCluster,
    ReportData,
    ReportGapRow,
    ReportGeoCluster,
    ReportKeywordRow,
    ReportPrototype,
    ReportQuestion,
    ReportStrikeRow,
    render_report,
)


def make_data(**overrides):
    defaults = {
        "domain": "example.hk",
        "date": "2026-10-02",
        "keywords": (
            ReportKeywordRow("smart office", 1200, 35, "informational", "tofu", 32.7),
            ReportKeywordRow("what is smart office", None, 22, "informational", "tofu", 0.0),
        ),
        "clusters": (
            ReportCluster("smart office", "smart office", ("smart office", "what is smart office"), 1200),
        ),
        "geo": (
            ReportGeoCluster(
                "smart office",
                (
                    ReportQuestion("what is smart office", "tofu", "semantic"),
                    ReportQuestion("smart office 邊度買", "bofu", "transact"),
                ),
                (
                    ReportPrototype("definition", "What is smart office?", False),
                    ReportPrototype("buying", "Where can I buy smart office and how much does it cost?", False),
                ),
            ),
        ),
        "strike": (
            ReportStrikeRow("smart office system", 14.0, 300),
        ),
        "gap": (
            ReportGapRow("crm hong kong", 500, 25, ("klalness.com", "competitor2.hk")),
        ),
        "sources": {"ahrefs": True, "gkp": True, "gsc": True},
    }
    defaults.update(overrides)
    return ReportData(**defaults)


class TestStructure:
    def test_header_and_sections_in_order(self):
        markdown = render_report(make_data())
        lines = markdown.splitlines()
        assert lines[0] == "# 內容計劃 — example.hk（2026-10-02）"
        headers = [ln for ln in lines if ln.startswith("## ")]
        assert headers == [
            "## 1. 摘要",
            "## 2. 關鍵字清單",
            "## 3. 主題分組",
            "## 4. 內容路線",
            "## 5. GEO prompt 建議",
            "## 6. 自家排名機會",
            "## 7. 競爭對手差距",
            "## 8. 資料聲明",
        ]

    def test_summary_counts_and_sources(self):
        markdown = render_report(make_data())
        assert "關鍵字：2 個；主題分組：1 組" in markdown
        assert "Ahrefs=live" in markdown
        assert "GKP=live" in markdown
        assert "GSC=live" in markdown


class TestSectionTwo:
    def test_table_header_and_rows(self):
        markdown = render_report(make_data())
        assert "| keyword | volume | KD | intent | funnel | score |" in markdown
        assert "| smart office | 1200 | 35 | informational | tofu | 32.7 |" in markdown

    def test_no_volume_label(self):
        markdown = render_report(make_data())
        assert "| what is smart office | 無量測數據 | 22 | informational | tofu | 0.0 |" in markdown


class TestSectionsThreeFour:
    def test_cluster_table(self):
        markdown = render_report(make_data())
        assert "| smart office | smart office | 2 | 1200 |" in markdown

    def test_content_route_hub_spokes(self):
        markdown = render_report(make_data())
        assert "1. hub：smart office（總量 1200）→ spokes：what is smart office" in markdown

    def test_empty_spokes_note(self):
        data = make_data(
            clusters=(ReportCluster("孤島", "孤島", ("孤島",), 0),)
        )
        markdown = render_report(data)
        assert "spokes：（無 spoke）" in markdown


class TestSectionFive:
    def test_questions_with_labels(self):
        markdown = render_report(make_data())
        assert "「what is smart office」（funnel=tofu，fanout=semantic）" in markdown
        assert "「smart office 邊度買」（funnel=bofu，fanout=transact）" in markdown

    def test_prototypes_with_tags(self):
        markdown = render_report(make_data())
        assert "- 原型 [definition] What is smart office?" in markdown

    def test_branded_tag(self):
        data = make_data(
            geo=(
                ReportGeoCluster(
                    "smart office",
                    (),
                    (ReportPrototype("definition", "What is first page?", True),),
                ),
            )
        )
        assert "- 原型 [definition][branded] What is first page?" in render_report(data)

    def test_bluf_guidance_present(self):
        markdown = render_report(make_data())
        assert "答案在 H3 下首句直給（40–50 字 BLUF）" in markdown
        assert "134–167 字自足段落" in markdown

    def test_no_questions_note(self):
        prototypes = (ReportPrototype("definition", "What is smart office?", False),)
        data = make_data(geo=(ReportGeoCluster("smart office", (), prototypes),))
        assert "（本組未挖到問句）" in render_report(data)

    def test_prototypes_skipped_note(self):
        data = make_data(
            geo=(ReportGeoCluster("小組", (), (), True),)
        )
        markdown = render_report(data)
        assert "低優先，略過原型" in markdown


class TestSectionSix:
    def test_strike_rows(self):
        markdown = render_report(make_data())
        assert "| smart office system | 14 | 300 |" in markdown

    def test_gsc_off_skips_section(self):
        data = make_data(
            strike=(),
            sources={"ahrefs": True, "gkp": True, "gsc": False},
        )
        markdown = render_report(data)
        assert "GSC 未接，本節略" in markdown
        assert "keyword | 自家排名" not in markdown

    def test_gsc_on_no_strike(self):
        markdown = render_report(make_data(strike=()))
        assert "（近 90 天無排名 11–30 的詞）" in markdown


class TestSectionSeven:
    def test_gap_rows(self):
        markdown = render_report(make_data())
        assert "| crm hong kong | 500 | 25 | klalness.com、competitor2.hk |" in markdown

    def test_top20_cap(self):
        rows = tuple(
            ReportGapRow(f"gap kw {i}", 100 - i, 10, ("klalness.com",))
            for i in range(25)
        )
        markdown = render_report(make_data(gap=rows))
        body = [ln for ln in markdown.splitlines() if ln.startswith("| gap kw")]
        assert len(body) == GAP_TOP_N
        assert "| gap kw 24 |" not in markdown

    def test_empty_gap_note(self):
        markdown = render_report(make_data(gap=()))
        assert "（無差距資料" in markdown


class TestSectionEight:
    def test_single_line_declaration(self):
        markdown = render_report(make_data(sources={"ahrefs": True, "gkp": False, "gsc": False}))
        section = markdown.split("## 8. 資料聲明")[1]
        body = [ln for ln in section.splitlines() if ln.startswith("Ahrefs：")]
        assert len(body) == 1
        assert "Ahrefs：live" in body[0]
        assert "GKP：估算（未接）" in body[0]
        assert "GSC：估算（未接）" in body[0]


class TestDeterminism:
    def test_same_data_same_output(self):
        data = make_data()
        assert render_report(data) == render_report(data)
