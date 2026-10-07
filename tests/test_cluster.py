"""T1.9 驗收測試：parent_topic 同組；共享 4+ 英文字／2+ 中文字段；
hub=最高量；去重；確定性（輸入順序無關）。"""

from rules.cluster import ClusterEntry, cluster_keywords


def e(keyword, volume=None, parent_topic=None):
    return ClusterEntry(keyword=keyword, volume=volume, parent_topic=parent_topic)


class TestParentTopic:
    def test_same_topic_same_group(self):
        clusters = cluster_keywords(
            [
                e("smart office", 1200, "smart office"),
                e("smart office hong kong", 390, "smart office"),
                e("智能辦公室", 800, "智能辦公室"),
            ]
        )
        assert len(clusters) == 2
        assert clusters[0].name == "smart office"
        assert clusters[0].total_volume == 1590
        assert len(clusters[0].members) == 2
        assert clusters[1].name == "智能辦公室"

    def test_topic_merges_disjoint_keywords(self):
        clusters = cluster_keywords(
            [
                e("crm pricing", 100, "crm software"),
                e("best saas tools", 200, "crm software"),
            ]
        )
        assert len(clusters) == 1
        assert clusters[0].hub == "best saas tools"


class TestSignatureEnglish:
    def test_shared_english_run_merges(self):
        clusters = cluster_keywords(
            [e("smart office system", 300), e("smart office price", 100)]
        )
        assert len(clusters) == 1

    def test_crm_too_short_no_merge(self):
        clusters = cluster_keywords([e("crm system", 300), e("crm software", 200)])
        assert len(clusters) == 2

    def test_no_shared_run_separate(self):
        clusters = cluster_keywords([e("web design", 300), e("seo services", 200)])
        assert len(clusters) == 2


class TestSignatureChinese:
    def test_shared_2char_cjk_merges(self):
        clusters = cluster_keywords([e("智能辦公室", 500), e("智能門鎖", 300)])
        assert len(clusters) == 1
        assert clusters[0].hub == "智能辦公室"

    def test_single_char_overlap_no_merge(self):
        clusters = cluster_keywords([e("智能門鎖", 300), e("門禁系統", 200)])
        assert len(clusters) == 2

    def test_chained_merge_three(self):
        clusters = cluster_keywords(
            [e("智能辦公室", 500), e("辦公室設計", 400), e("智能門鎖", 300)]
        )
        assert len(clusters) == 1
        assert clusters[0].total_volume == 1200


class TestMixedSignature:
    def test_mixed_keyword_merges_with_english(self):
        clusters = cluster_keywords([e("smart office 香港", 100), e("smart office", 900)])
        assert len(clusters) == 1
        assert clusters[0].hub == "smart office"


class TestHubAndOrder:
    def test_hub_is_highest_volume(self):
        clusters = cluster_keywords([e("smart office system", 100), e("smart office price", 700)])
        assert clusters[0].hub == "smart office price"

    def test_none_volume_loses_to_real(self):
        clusters = cluster_keywords([e("smart office", None), e("smart office hk", 50)])
        assert clusters[0].hub == "smart office hk"

    def test_volume_tie_uses_lexicographic(self):
        clusters = cluster_keywords([e("seo audit", 100), e("seo tools", 100)])
        hubs = {c.hub for c in clusters}
        assert hubs == {"seo audit", "seo tools"}
        merged = cluster_keywords([e("seo audit tools", 100), e("seo audit guide", 100)])
        assert merged[0].hub == "seo audit guide"

    def test_clusters_sorted_by_total_volume_desc(self):
        clusters = cluster_keywords(
            [
                e("smart office system", 100),
                e("smart office price", 700),
                e("獨立主題", 5000),
            ]
        )
        assert [c.name for c in clusters] == ["獨立主題", "smart office price"]


class TestGenericSignatureStop:
    def test_teacher_words_no_longer_chain(self):
        clusters = cluster_keywords(
            [e("鋼琴老師", 300), e("影子老師", 200), e("鋼琴", 100)]
        )
        assert len(clusters) == 2
        by_name = {c.name: c for c in clusters}
        assert set(by_name["鋼琴老師"].members) == {e("鋼琴老師", 300), e("鋼琴", 100)}

    def test_song_words_no_longer_chain(self):
        clusters = cluster_keywords(
            [e("破曉歌詞意思", 100), e("越唱越強歌詞", 80), e("學唱歌", 300)]
        )
        assert len(clusters) == 3

    def test_topic_word_still_merges(self):
        clusters = cluster_keywords(
            [e("結他", 2900), e("學結他", 320), e("結他班", 200), e("結他課程", 140)]
        )
        assert len(clusters) == 1

    def test_geo_words_no_longer_chain(self):
        clusters = cluster_keywords(
            [e("crm hong kong", 100), e("seo services hong kong", 80)]
        )
        assert len(clusters) == 2


class TestDedup:
    def test_same_normalized_key_keeps_max_volume(self):
        clusters = cluster_keywords([e("Smart Office", 1200), e("smart office", None)])
        assert len(clusters) == 1
        assert clusters[0].members == (e("Smart Office", 1200),)

    def test_cjk_space_variant_dedupes(self):
        clusters = cluster_keywords([e("鑽戒 推薦", 300), e("鑽戒推薦", 500)])
        assert len(clusters) == 1
        assert clusters[0].hub == "鑽戒推薦"


class TestDeterminism:
    def test_shuffled_input_same_output(self):
        entries = [
            e("smart office", 1200, "smart office"),
            e("smart office hong kong", 390, "smart office"),
            e("智能辦公室", 800),
            e("智能門鎖", 300),
            e("crm system", 100),
        ]
        first = cluster_keywords(list(entries))
        second = cluster_keywords(list(reversed(entries)))
        assert first == second

    def test_empty_input(self):
        assert cluster_keywords([]) == []
