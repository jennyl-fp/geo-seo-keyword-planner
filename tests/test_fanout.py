"""T1.10 驗收測試：8 類分類（表序優先）；topic 清洗（spec 例子）；
5 原型；13/14 詞與 26/27 字邊界；branded 標記。"""

import pytest

from rules.fanout import (
    FANOUT_TYPES,
    TEMPLATE_ORDER,
    build_prototypes,
    classify_fanout,
    clean_topic,
)


class TestClassifyEnglish:
    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("crm vs saas", "comparison"),
            ("alternatives to hubspot", "comparison"),
            ("where to buy standing desk", "transact"),
            ("standing desk discount hong kong", "transact"),
            ("standing desk price", "attribute"),
            ("how much is seo", "attribute"),
            ("is ahrefs worth it", "perspective"),
            ("ahrefs review", "perspective"),
            ("what to do after company registration", "follow_up"),
            ("how long does botox last", "follow_up"),
            ("best crm 2026", "recency"),
            ("latest iphone", "recency"),
            ("how to do seo", "tutorial"),
            ("step by step guide", "tutorial"),
            ("what is crm", "semantic"),
        ],
    )
    def test_classification(self, keyword, expected):
        assert classify_fanout(keyword) == expected


class TestClassifyChinese:
    @pytest.mark.parametrize(
        "keyword,expected",
        [
            ("crm系統比較", "comparison"),
            ("智能門鎖邊個好", "comparison"),
            ("裝修公司邊間好", "comparison"),
            ("standing desk邊度買", "transact"),
            ("餐廳優惠", "transact"),
            ("裝修幾錢", "attribute"),
            ("智能手錶規格", "attribute"),
            ("呢間餐廳好唔好", "perspective"),
            ("smart office值唔值得買", "perspective"),
            ("裝修之後點算", "follow_up"),
            ("botox幾耐見效", "follow_up"),
            ("2026新款手機", "recency"),
            ("人工智能最新發展", "recency"),
            ("點樣學seo", "tutorial"),
            ("crm入門", "tutorial"),
            ("crm係咩", "semantic"),
            ("智能辦公室", "semantic"),
        ],
    )
    def test_classification(self, keyword, expected):
        assert classify_fanout(keyword) == expected


class TestClassifyPriority:
    def test_vs_beats_recency_and_price(self):
        assert classify_fanout("crm 2026 vs semrush price") == "comparison"

    def test_perspective_beats_recency(self):
        assert classify_fanout("best crm 2026 review") == "perspective"

    def test_bare_year_is_recency(self):
        assert classify_fanout("2026") == "recency"

    def test_year_glued_to_cjk(self):
        assert classify_fanout("2026新款") == "recency"

    def test_old_year_not_recency(self):
        assert classify_fanout("best crm 2023") == "semantic"


class TestCleanTopic:
    def test_spec_example(self):
        assert clean_topic("what does an ai seo company do") == "ai seo company"

    def test_simple_prefix(self):
        assert clean_topic("what is seo") == "seo"

    def test_prefix_and_suffix(self):
        assert clean_topic("how much does crm cost") == "crm"

    def test_how_long_does_last(self):
        assert clean_topic("how long does botox last") == "botox"

    def test_article_stripped(self):
        assert clean_topic("the best crm") == "best crm"

    def test_non_question_passthrough(self):
        assert clean_topic("smart office") == "smart office"

    def test_zh_suffix(self):
        assert clean_topic("crm係咩") == "crm"

    def test_zh_prefix(self):
        assert clean_topic("什麼是seo") == "seo"

    def test_zh_passthrough(self):
        assert clean_topic("智能辦公室") == "智能辦公室"

    def test_empty(self):
        assert clean_topic("") == ""


class TestBuildPrototypes:
    def test_english_hub_five_templates(self):
        prototypes = build_prototypes("smart office")
        assert [p.template for p in prototypes] == list(TEMPLATE_ORDER)
        assert all(p.lang == "en" for p in prototypes)
        assert all(not p.branded for p in prototypes)
        assert prototypes[0].prompt == "What is smart office?"

    def test_zh_hub_uses_zh_templates(self):
        prototypes = build_prototypes("智能辦公室")
        assert all(p.lang == "zh" for p in prototypes)
        assert prototypes[0].prompt == "智能辦公室係咩？"
        assert prototypes[4].prompt == "智能辦公室邊度買？幾錢？"

    def test_question_hub_cleaned_before_templating(self):
        prototypes = build_prototypes("what is smart office")
        assert prototypes[0].prompt == "What is smart office?"

    def test_en_word_boundary_13_kept(self):
        topic = "smart office system"  # buying: 10 固定詞 + 3 = 13 → 生成
        prototypes = build_prototypes(topic)
        assert "buying" in [p.template for p in prototypes]

    def test_en_word_boundary_14_dropped(self):
        topic = "smart office system hong"  # buying: 10 + 4 = 14 → 不生成
        templates = [p.template for p in build_prototypes(topic)]
        assert "buying" not in templates
        assert "definition" in templates

    def test_zh_char_boundary_26_kept(self):
        topic = "智能辦公室系統解決方案管理平台hk01"  # 19 字；buying 模板 7 字 = 26
        prototypes = build_prototypes(topic)
        assert "buying" in [p.template for p in prototypes]

    def test_zh_char_boundary_27_dropped(self):
        topic = "智能辦公室系統解決方案管理平台hk012"  # 20 字；buying = 27 → 不生成
        templates = [p.template for p in build_prototypes(topic)]
        assert "buying" not in templates

    def test_branded_flag(self):
        prototypes = build_prototypes("first page seo", brands=("first page",))
        assert all(p.branded for p in prototypes)

    def test_branded_case_insensitive(self):
        prototypes = build_prototypes("Smart Office", brands=("SMART office",))
        assert all(p.branded for p in prototypes)

    def test_competitor_variant_en(self):
        prototypes = build_prototypes("smart office", competitors=("Klalness",))
        comparison = next(p for p in prototypes if p.template == "comparison")
        assert comparison.prompt == "Which is better, smart office or Klalness?"

    def test_competitor_ignored_for_zh(self):
        prototypes = build_prototypes("智能辦公室", competitors=("Klalness",))
        comparison = next(p for p in prototypes if p.template == "comparison")
        assert comparison.prompt == "智能辦公室同其他選擇比較邊個好？"

    def test_empty_topic_returns_empty(self):
        assert build_prototypes("") == []

    def test_template_order_constant(self):
        assert TEMPLATE_ORDER == (
            "definition",
            "comparison",
            "alternatives",
            "use_case",
            "buying",
        )

    def test_fanout_types_constant(self):
        assert len(FANOUT_TYPES) == 8
        assert FANOUT_TYPES[-1] == "semantic"
