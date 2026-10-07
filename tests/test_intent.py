"""T1.6 驗收測試：EN 詞界（ASCII 邊界）/ ZH 子字串；§4.1 表序優先；
中英各 ≥3 案例；混合詞回歸（buy鑽戒）。"""

import pytest

from rules.intent import INTENTS, classify_intent


class TestEnglish:
    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("buy engagement ring online", "transactional"),
            ("CRM software price", "transactional"),
            ("web design cost hong kong", "transactional"),
            ("best crm software", "commercial"),
            ("crm vs saas", "commercial"),
            ("top 10 website builders", "commercial"),
            ("ahrefs login", "navigational"),
            ("canva official website", "navigational"),
            ("what is seo", "informational"),
            ("seo tutorial for beginners", "informational"),
        ],
    )
    def test_classification(self, keyword, expected):
        assert classify_intent(keyword) == expected

    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("bookshop hong kong", "informational"),
            ("topshop sale", "transactional"),
            ("workshop booking system", "informational"),
        ],
    )
    def test_word_boundaries(self, keyword, expected):
        assert classify_intent(keyword) == expected


class TestChinese:
    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("鑽戒價錢", "transactional"),
            ("裝修報價", "transactional"),
            ("餐廳訂座優惠", "transactional"),
            ("智能門鎖推薦", "commercial"),
            ("crm系統比較", "commercial"),
            ("租樓邊間好", "commercial"),
            ("google登入", "navigational"),
            ("brand官網", "navigational"),
            ("seo教學", "informational"),
            ("點解要買保險", "informational"),
        ],
    )
    def test_classification(self, keyword, expected):
        assert classify_intent(keyword) == expected

    def test_no_signal_defaults_informational(self):
        assert classify_intent("智能辦公室") == "informational"


class TestMixed:
    def test_english_signal_survives_cjk_normalization(self):
        assert classify_intent("buy 鑽戒") == "transactional"

    def test_cjk_glued_english_signal(self):
        assert classify_intent("鑽戒buy") == "transactional"

    def test_mixed_commercial(self):
        assert classify_intent("smart office 邊款好") == "commercial"


class TestPriorityOrder:
    def test_spec_accepted_error_best_to_buy(self):
        assert classify_intent("best crm to buy") == "transactional"

    def test_how_to_buy_beats_informational(self):
        assert classify_intent("how to buy laptop") == "transactional"

    def test_transactional_beats_commercial(self):
        assert classify_intent("crm comparison price") == "transactional"

    def test_commercial_beats_informational(self):
        assert classify_intent("how to choose best crm") == "commercial"

    def test_navigational_beats_informational(self):
        assert classify_intent("google ads login教學") == "navigational"


class TestEdge:
    def test_empty_defaults_informational(self):
        assert classify_intent("") == "informational"

    def test_all_intents_exist(self):
        assert INTENTS == (
            "transactional",
            "commercial",
            "navigational",
            "informational",
        )
