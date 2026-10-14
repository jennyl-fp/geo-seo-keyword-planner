"""T1.11 驗收測試（v3，ADR-019）：公式組件；KD 邊界（None/79/80）；
自家排名分數帶（3/10/20/30/50/51）；相鄰匹配折扣；無 volume 照列；
批次全無量；排序確定性。"""

import pytest

from rules.cjk_norm import normalize_keyword
from scoring import KeywordForScoring, score_keywords


def entry(keyword, volume=None, difficulty=None, intent="informational"):
    return KeywordForScoring(
        keyword=keyword, volume=volume, difficulty=difficulty, intent=intent
    )


class TestKdFeasibility:
    def test_none_kd_is_half(self):
        assert score_keywords([entry("a", 100)])[0].components.kd_feasibility == 0.5

    def test_zero_kd(self):
        assert score_keywords([entry("a", 100, 0)])[0].components.kd_feasibility == 1.0

    def test_79(self):
        assert (
            score_keywords([entry("a", 100, 79)])[0].components.kd_feasibility == 0.111
        )

    def test_80_and_above_clamped(self):
        assert score_keywords([entry("a", 100, 80)])[0].components.kd_feasibility == 0.1
        assert score_keywords([entry("a", 100, 95)])[0].components.kd_feasibility == 0.1


class TestIntentWeights:
    @pytest.mark.parametrize(
        "intent,weight",
        [
            ("transactional", 1.0),
            ("commercial", 0.8),
            ("informational", 0.6),
            ("navigational", 0.3),
        ],
    )
    def test_mapping(self, intent, weight):
        result = score_keywords([entry("a", 100, 0, intent)])[0]
        assert result.components.intent_weight == weight


class TestFormula:
    def test_perfect_score_100(self):
        result = score_keywords([entry("a", 1000, 0, "transactional")])[0]
        assert result.score == 100.0

    def test_components_combine(self):
        results = score_keywords(
            [entry("a", 1200, 35, "commercial"), entry("b", 2400)]
        )
        result = next(r for r in results if r.keyword == "a")
        assert result.components.volume_component == pytest.approx(
            __import__("math").log1p(1200) / __import__("math").log1p(2400), abs=1e-3
        )
        assert result.components.kd_feasibility == 0.606
        assert result.components.feasibility == 0.606
        assert result.components.intent_weight == 0.8
        assert result.score == pytest.approx(
            100
            * (
                0.60 * 0.606
                + 0.25 * result.components.volume_component
                + 0.15 * 0.8
            ),
            abs=0.1,
        )

    def test_each_row_has_components(self):
        results = score_keywords(
            [entry("a", 100, 10, "commercial"), entry("b", None)]
        )
        for row in results:
            assert row.components is not None
            assert isinstance(row.components.base_score, float)


class TestOwnRankFeasibility:
    @pytest.mark.parametrize(
        "pos,expected",
        [(1, 1.0), (3, 1.0), (4, 0.95), (10, 0.95), (11, 0.85), (20, 0.85),
         (21, 0.70), (30, 0.70), (31, 0.55), (50, 0.55)],
    )
    def test_position_bands(self, pos, expected):
        result = score_keywords([entry("a", 100)], own_positions={"a": float(pos)})[0]
        assert result.components.own_rank_component == expected
        assert result.components.feasibility == expected
        assert result.own_position == float(pos)
        assert result.match_type == "exact"

    @pytest.mark.parametrize("pos", [51, 100])
    def test_beyond_50_no_rank_evidence(self, pos):
        result = score_keywords(
            [entry("a", 100, 0)], own_positions={"a": float(pos)}
        )[0]
        assert result.components.own_rank_component == 0.0
        assert result.components.feasibility == 1.0  # 回落 KD 可行率

    def test_no_positions_falls_back_to_kd(self):
        result = score_keywords([entry("a", 100, 0)])[0]
        assert result.own_position is None
        assert result.match_type == "none"
        assert result.components.feasibility == 1.0

    def test_rank_evidence_beats_bad_kd(self):
        result = score_keywords(
            [entry("a", 100, 70)], own_positions={"a": 8.0}
        )[0]
        assert result.components.kd_feasibility == 0.213
        assert result.components.feasibility == 0.95  # 自家排名證據優先


class TestAdjacentMatch:
    def test_substring_match_discounted(self):
        result = score_keywords(
            [entry("魚油功效", 100, 90)], own_positions={"魚油": 7.0}
        )[0]
        assert result.own_position == 7.0
        assert result.match_type == "adjacent"
        assert result.components.own_rank_component == round(0.95 * 0.85, 3)
        assert result.components.feasibility == round(0.95 * 0.85, 3)

    def test_superset_candidate_also_matches(self):
        result = score_keywords(
            [entry("魚油", 100)], own_positions={"魚油功效": 12.0}
        )[0]
        assert result.match_type == "adjacent"
        assert result.own_position == 12.0

    def test_exact_beats_adjacent(self):
        result = score_keywords(
            [entry("魚油", 100)],
            own_positions={"魚油": 20.0, "魚油功效": 3.0},
        )[0]
        assert result.match_type == "exact"
        assert result.own_position == 20.0

    def test_unrelated_no_match(self):
        result = score_keywords(
            [entry("益生菌推薦", 100)], own_positions={"魚油": 7.0}
        )[0]
        assert result.match_type == "none"
        assert result.own_position is None


class TestNoVolume:
    def test_question_without_volume_still_listed(self):
        results = score_keywords([entry("what is crm", None, 20, "informational")])
        assert len(results) == 1
        assert results[0].has_volume_data is False
        # 無量不等於零分：可行性（KD 20 → 0.775）+ intent 仍有貢獻（ADR-019）
        assert results[0].score == pytest.approx(100 * (0.6 * 0.775 + 0.15 * 0.6), abs=0.1)

    def test_question_with_own_rank(self):
        results = score_keywords(
            [entry("what is crm", None, 20, "informational")],
            own_positions={"what is crm": 15.0},
        )
        # 自家 #15 → 0.85 > KD 0.775 → feasibility 0.85
        assert results[0].components.feasibility == 0.85
        assert results[0].score == pytest.approx(100 * (0.6 * 0.85 + 0.15 * 0.6), abs=0.1)

    def test_zero_volume_is_measured(self):
        results = score_keywords([entry("a", 0, 0, "transactional")])
        assert results[0].has_volume_data is True
        assert results[0].components.volume_component == 0.0

    def test_batch_all_none_no_crash(self):
        results = score_keywords([entry("a", None), entry("b", None)])
        assert all(r.components.volume_component == 0.0 for r in results)


class TestNormalizedPositionLookup:
    def test_case_insensitive_lookup(self):
        results = score_keywords(
            [entry("Smart Office", 100)], own_positions={"smart office": 12.0}
        )
        assert results[0].own_position == 12.0
        assert results[0].match_type == "exact"

    def test_cjk_space_lookup(self):
        results = score_keywords(
            [entry("鑽戒 推薦", 100)], own_positions={normalize_keyword("鑽戒 推薦"): 12.0}
        )
        assert results[0].own_position == 12.0
        assert results[0].match_type == "exact"


class TestOrderAndDeterminism:
    def test_sorted_score_desc_then_keyword_asc(self):
        results = score_keywords(
            [entry("b", 100, 0, "transactional"), entry("a", 100, 0, "transactional"),
             entry("c", 1000, 0, "transactional")]
        )
        assert [r.keyword for r in results] == ["c", "a", "b"]

    def test_same_input_same_output(self):
        entries = [entry("a", 100, 20, "commercial"), entry("b", 50)]
        assert score_keywords(entries) == score_keywords(entries)
