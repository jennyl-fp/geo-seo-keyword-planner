"""T1.1 驗收測試：中英各 ≥3 案例 + 邊界 + 冪等性（規格 §4.4）。"""

import pytest

from rules.cjk_norm import contains_cjk, match_form, normalize_keyword


class TestChinese:
    def test_spec_case(self):
        assert normalize_keyword("鑽戒 推薦") == "鑽戒推薦"

    def test_mixed_cjk_latin_strips_all_internal_space(self):
        assert normalize_keyword("SEO 公司 香港 ") == "seo公司香港"

    def test_fullwidth_space(self):
        assert normalize_keyword("鑽戒　推薦") == "鑽戒推薦"

    def test_mixed_removes_space_between_latin_words(self):
        assert normalize_keyword("How to 揀 CRM 系統") == "howto揀crm系統"


class TestEnglish:
    def test_lowercase_trim_collapse(self):
        assert normalize_keyword("  Smart   Office ") == "smart office"

    def test_preserves_word_boundaries(self):
        assert normalize_keyword("Best CRM Software") == "best crm software"

    def test_fullwidth_space_latin_only(self):
        assert normalize_keyword("SMART　OFFICE") == "smart office"

    def test_plain(self):
        assert normalize_keyword("What is AI?") == "what is ai?"


class TestEdge:
    @pytest.mark.parametrize("empty", ["", "   ", "\u3000"])
    def test_empty_variants(self, empty):
        assert normalize_keyword(empty) == ""

    def test_punctuation_untouched(self):
        assert normalize_keyword("!!!") == "!!!"


class TestContainsCjk:
    def test_true(self):
        assert contains_cjk("鑽戒推薦")

    def test_false(self):
        assert not contains_cjk("office 365")

    def test_mixed(self):
        assert contains_cjk("ai seo 公司")


class TestProperties:
    @pytest.mark.parametrize(
        "kw", ["鑽戒 推薦", "Smart Office", "AI SEO 公司", "", "點樣揀CRM"]
    )
    def test_idempotent(self, kw):
        once = normalize_keyword(kw)
        assert normalize_keyword(once) == once


class TestMatchForm:
    def test_preserves_word_boundaries_in_mixed(self):
        assert match_form("google ads login教學") == "google ads login教學"

    def test_collapse_and_lowercase(self):
        assert match_form("  Smart   OFFICE ") == "smart office"

    def test_cjk_space_kept_for_matching(self):
        assert match_form("鑽戒 推薦") == "鑽戒 推薦"

    def test_empty(self):
        assert match_form("") == ""

    @pytest.mark.parametrize("kw", ["鑽戒 推薦", "how to 揀 CRM"])
    def test_idempotent(self, kw):
        once = match_form(kw)
        assert match_form(once) == once
