"""ADR-016 驗收：口語／書面語／中性；「關係」不誤中口語。"""

import pytest

from rules.register import classify_register


class TestColloquial:
    @pytest.mark.parametrize(
        "keyword",
        [
            "學結他邊間好",
            "點樣學唱歌",
            "智能門鎖好唔好",
            "crm係咩",
            "有冇免費試用",
            "結他班咁貴",
            "邊度買結他",
            "保險係咪一定要買",
        ],
    )
    def test_colloquial(self, keyword):
        assert classify_register(keyword) == "colloquial"


class TestWritten:
    @pytest.mark.parametrize(
        "keyword",
        [
            "如何選擇crm系統",
            "什麼是智能辦公室",
            "裝修收費標準",
            "智能門鎖比較",
            "保險是否必要",
        ],
    )
    def test_written(self, keyword):
        assert classify_register(keyword) == "written"


class TestNeutralAndGuards:
    @pytest.mark.parametrize(
        "keyword",
        ["smart office", "智能辦公室", "結他班價錢", "鋼琴老師"],
    )
    def test_neutral(self, keyword):
        assert classify_register(keyword) == "neutral"

    def test_gwaan_hai_not_colloquial(self):
        assert classify_register("人際關係技巧") == "neutral"

    def test_colloquial_beats_written(self):
        assert classify_register("點樣收費先合理") == "colloquial"

    def test_empty_neutral(self):
        assert classify_register("") == "neutral"
