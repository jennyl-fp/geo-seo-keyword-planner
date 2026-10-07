"""T1.8 驗收測試：英文開頭詞（詞界防誤中）+ 中文標記；
裸「點」不觸發（特點/賣點/地點）。"""

import pytest

from rules.questions import is_question


class TestEnglish:
    @pytest.mark.parametrize(
        "keyword",
        [
            "what is seo",
            "how to tie a tie",
            "who invented the internet",
            "which crm is best for smes",
            "can i deduct home office expenses",
            "is wordpress good for seo",
            "are air fryers healthy",
            "why is my website slow",
        ],
    )
    def test_questions(self, keyword):
        assert is_question(keyword) is True

    @pytest.mark.parametrize(
        "keyword",
        [
            "whatsapp business api",
            "island tour package",
            "canva login",
            "best seo tools",
            "smart office hong kong",
            "seo what not to do",
        ],
    )
    def test_not_questions(self, keyword):
        assert is_question(keyword) is False


class TestChinese:
    @pytest.mark.parametrize(
        "keyword",
        [
            "點樣揀CRM系統",
            "點解要買保險",
            "如何學seo",
            "邊個洗碗機好用",
            "裝修公司邊間好",
            "幾時換雪櫃",
            "智能門鎖幾錢",
            "crm係咩嚟㗎",
            "呢間餐廳好唔好",
            "呢排有咩好做",
        ],
    )
    def test_questions(self, keyword):
        assert is_question(keyword) is True

    @pytest.mark.parametrize("keyword", ["手機特點", "產品賣點", "旅遊地點", "智能辦公室"])
    def test_bare_dim_not_triggered(self, keyword):
        assert is_question(keyword) is False


class TestMixed:
    def test_english_start_with_cjk_tail(self):
        assert is_question("what is CRM系統") is True

    def test_chinese_marker_with_english(self):
        assert is_question("smart office 好唔好呢") is True

    def test_english_word_mid_keyword_not_question(self):
        assert is_question("seo 點樣做") is True
        assert is_question("office how to guide 2026") is False


class TestEdge:
    def test_empty(self):
        assert is_question("") is False

    def test_idempotent_form(self):
        assert is_question("What  is SEO") is True
