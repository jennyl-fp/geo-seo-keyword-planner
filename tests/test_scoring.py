"""T1.11 驗收測試：公式組件；KD 邊界（None/79/80）；strike 邊界
（10/11/30/31）；無 volume 照列；批次全無量；排序確定性。"""

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

    def test_components_multiply(self):
        results = score_keywords(
            [entry("a", 1200, 35, "commercial"), entry("b", 2400)]
        )
        result = next(r for r in results if r.keyword == "a")
        assert result.components.volume_component == pytest.approx(
            __import__("math").log1p(1200) / __import__("math").log1p(2400), abs=1e-3
        )
        assert result.components.kd_feasibility == 0.606
        assert result.components.intent_weight == 0.8
        assert result.score == pytest.approx(
            result.components.volume_component * 0.606 * 0.8 * 100, abs=0.1
        )

    def test_each_row_has_components(self):
        results = score_keywords(
            [entry("a", 100, 10, "commercial"), entry("b", None)]
        )
        for row in results:
            assert row.components is not None
            assert isinstance(row.components.base_score, float)


class TestStrikeBonus:
    def _positions(self, pos):
        return {"a": float(pos)} if pos is not None else None

    @pytest.mark.parametrize("pos", [11, 20, 30])
    def test_strike_zone_adds_15(self, pos):
        result = score_keywords([entry("a", 100)], own_positions=self._positions(pos))[0]
        assert result.components.strike_bonus == 15.0
        assert result.own_position == float(pos)

    @pytest.mark.parametrize("pos", [1, 10, 31, 100])
    def test_outside_zone_no_bonus(self, pos):
        result = score_keywords([entry("a", 100)], own_positions=self._positions(pos))[0]
        assert result.components.strike_bonus == 0.0

    def test_top10_no_bonus_already_winning(self):
        result = score_keywords([entry("a", 100)], own_positions={"a": 3.0})[0]
        assert result.components.strike_bonus == 0.0

    def test_no_positions_no_bonus(self):
        result = score_keywords([entry("a", 100)])[0]
        assert result.components.strike_bonus == 0.0
        assert result.own_position is None


class TestNoVolume:
    def test_question_without_volume_still_listed(self):
        results = score_keywords([entry("what is crm", None, 20, "informational")])
        assert len(results) == 1
        assert results[0].has_volume_data is False
        assert results[0].score == 0.0

    def test_question_with_strike_bonus(self):
        results = score_keywords(
            [entry("what is crm", None, 20, "informational")],
            own_positions={"what is crm": 15.0},
        )
        assert results[0].score == 15.0

    def test_zero_volume_is_measured(self):
        results = score_keywords([entry("a", 0, 0, "transactional")])
        assert results[0].has_volume_data is True
        assert results[0].score == 0.0

    def test_batch_all_none_no_crash(self):
        results = score_keywords([entry("a", None), entry("b", None)])
        assert all(r.score == 0.0 for r in results)


class TestNormalizedPositionLookup:
    def test_case_insensitive_lookup(self):
        results = score_keywords(
            [entry("Smart Office", 100)], own_positions={"smart office": 12.0}
        )
        assert results[0].components.strike_bonus == 15.0

    def test_cjk_space_lookup(self):
        results = score_keywords(
            [entry("鑽戒 推薦", 100)], own_positions={normalize_keyword("鑽戒 推薦"): 12.0}
        )
        assert results[0].components.strike_bonus == 15.0


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
