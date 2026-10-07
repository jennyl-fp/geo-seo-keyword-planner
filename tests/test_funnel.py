"""T1.7 驗收測試：BOFU > MOFU > 其餘 TOFU；中英各 ≥3 案例；
詞界（notebook 不含 book）。"""

import pytest

from rules.funnel import FUNNELS, classify_funnel


class TestEnglish:
    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("crm software price", "bofu"),
            ("buy running shoes online", "bofu"),
            ("seo tools free trial", "bofu"),
            ("booking system demo cost", "bofu"),
            ("best crm software", "mofu"),
            ("crm vs saas", "mofu"),
            ("top web hosting review", "mofu"),
            ("what is seo", "tofu"),
            ("how to start a blog", "tofu"),
        ],
    )
    def test_classification(self, keyword, expected):
        assert classify_funnel(keyword) == expected

    def test_word_boundary_book(self):
        assert classify_funnel("notebook bag") == "tofu"

    def test_word_boundary_buy(self):
        assert classify_funnel("smart office hong kong") == "tofu"


class TestChinese:
    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("鑽戒價錢", "bofu"),
            ("餐廳優惠", "bofu"),
            ("美容院預約 app", "bofu"),
            ("保險試用比較", "bofu"),
            ("智能門鎖推薦", "mofu"),
            ("裝修公司邊間好", "mofu"),
            ("信用卡邊款好", "mofu"),
            ("婴儿車點揀", "mofu"),
            ("智能辦公室介紹", "tofu"),
            ("seo入門指南", "tofu"),
        ],
    )
    def test_classification(self, keyword, expected):
        assert classify_funnel(keyword) == expected


class TestMixed:
    def test_english_signal_in_mixed(self):
        assert classify_funnel("buy 鑽戒") == "bofu"

    def test_chinese_signal_in_mixed(self):
        assert classify_funnel("smart office 價錢") == "bofu"


class TestPriority:
    def test_bofu_beats_mofu(self):
        assert classify_funnel("best crm price") == "bofu"

    def test_mofu_beats_default(self):
        assert classify_funnel("how to compare insurance") == "mofu"


class TestEdge:
    def test_empty_defaults_tofu(self):
        assert classify_funnel("") == "tofu"

    def test_funnel_order(self):
        assert FUNNELS == ("bofu", "mofu", "tofu")
