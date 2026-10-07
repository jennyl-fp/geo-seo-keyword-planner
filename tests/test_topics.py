"""ADR-017 驗收：vol>0 硬過濾；intent 匹配；貪婪打包確定性；
secondary ≤4、<2 標 needs_more；parent_topic/簽章成組。"""

import pytest

from rules.topics import TopicKeyword, pack_topics


def kw(keyword, volume=100, intent="informational", score=10.0, parent_topic=None):
    return TopicKeyword(
        keyword=keyword,
        volume=volume,
        difficulty=None,
        intent=intent,
        score=score,
        parent_topic=parent_topic,
    )


GUITAR = [
    kw("結他班", 500, score=90),
    kw("學結他", 320, score=80),
    kw("結他課程", 140, score=70),
    kw("成人結他班", 50, score=60),
    kw("結他維修", 70, score=50),
    kw("結他線", 80, score=40),
]


class TestFilters:
    def test_zero_and_none_volume_excluded(self):
        topics = pack_topics(
            [*GUITAR, kw("結他教學", 0, score=99), kw("結他譜", None, score=99)]
        )
        members = {t.primary.keyword for t in topics}
        assert "結他教學" not in members
        assert "結他譜" not in members

    def test_intent_filter_blog_blocks_transactional(self):
        topics = pack_topics(
            [*GUITAR, kw("結他價錢", 300, intent="transactional", score=99)],
            page_type="blog",
        )
        members = {t.primary.keyword for t in topics}
        assert "結他價錢" not in members
        assert "結他班" in members

    def test_intent_filter_service_allows_transactional(self):
        topics = pack_topics(
            [*GUITAR, kw("結他價錢", 300, intent="transactional", score=99)],
            page_type="service",
        )
        members = {t.primary.keyword for t in topics}
        assert "結他價錢" in members
        assert "結他班" not in members

    def test_register_filter(self):
        topics = pack_topics(
            [
                kw("學結他邊間好", 100, intent="commercial", score=90),
                kw("如何學結他", 200, score=80),
                kw("結他", 300, score=70),
            ],
            register="colloquial",
        )
        members = {t.primary.keyword for t in topics}
        assert members == {"學結他邊間好"}

    def test_bad_register_raises(self):
        with pytest.raises(ValueError):
            pack_topics(GUITAR, register="formal")


class TestPackaging:
    def test_primary_plus_up_to_4_secondaries(self):
        topics = pack_topics(GUITAR)
        assert topics[0].primary.keyword == "結他班"
        assert len(topics[0].secondaries) <= 4
        assert topics[0].needs_more_keywords is False

    def test_primary_is_highest_score(self):
        topics = pack_topics(GUITAR)
        assert topics[0].primary.score == max(k.score for k in GUITAR)

    def test_signature_grouping(self):
        topics = pack_topics(GUITAR)
        guitar_topic = topics[0]
        secondary_names = {s.keyword for s in guitar_topic.secondaries}
        assert "學結他" in secondary_names or "結他課程" in secondary_names

    def test_parent_topic_grouping(self):
        topics = pack_topics(
            [
                kw("crm pricing", 300, score=90, parent_topic="crm software"),
                kw("crm cost", 200, score=80, parent_topic="crm software"),
                kw("unrelated topic", 100, score=70),
            ]
        )
        crm_topic = next(t for t in topics if t.primary.keyword == "crm pricing")
        assert {s.keyword for s in crm_topic.secondaries} == {"crm cost"}

    def test_secondaries_max_4(self):
        many = [kw(f"結他系列{i}", 10 * (20 - i), score=100 - i) for i in range(10)]
        topics = pack_topics(many)
        assert len(topics[0].secondaries) == 4

    def test_needs_more_flag(self):
        topics = pack_topics([kw("孤島主題", 100, score=90)])
        assert topics[0].secondaries == ()
        assert topics[0].needs_more_keywords is True

    def test_every_keyword_assigned_once(self):
        topics = pack_topics(GUITAR)
        all_members = [t.primary.keyword for t in topics] + [
            s.keyword for t in topics for s in t.secondaries
        ]
        assert len(all_members) == len(set(all_members)) == len(GUITAR)

    def test_determinism(self):
        assert pack_topics(GUITAR) == pack_topics(GUITAR)
        assert pack_topics(list(reversed(GUITAR))) == pack_topics(GUITAR)

    def test_total_volume(self):
        topics = pack_topics(GUITAR)
        first = topics[0]
        assert first.total_volume == (first.primary.volume or 0) + sum(
            s.volume or 0 for s in first.secondaries
        )

    def test_empty_pool(self):
        assert pack_topics([]) == []
