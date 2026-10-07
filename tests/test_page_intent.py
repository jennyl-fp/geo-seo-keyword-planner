"""ADR-014 驗收：頁面類型→intent 對照；未知 page_type 報錯。"""

import pytest

from rules.page_intent import PAGE_INTENTS, intent_allowed


@pytest.mark.parametrize(
    "intent,page_type,allowed",
    [
        ("informational", "blog", True),
        ("commercial", "blog", True),
        ("transactional", "blog", False),
        ("navigational", "blog", False),
        ("transactional", "service", True),
        ("commercial", "service", True),
        ("informational", "service", False),
        ("navigational", "home", True),
        ("transactional", "home", True),
        ("informational", "home", False),
        ("informational", "any", True),
        ("navigational", "any", True),
    ],
)
def test_mapping(intent, page_type, allowed):
    assert intent_allowed(intent, page_type) is allowed


def test_unknown_page_type_raises():
    with pytest.raises(ValueError):
        intent_allowed("informational", "landing")


def test_all_four_intents_covered_in_any():
    assert set(PAGE_INTENTS["any"]) == {
        "transactional",
        "commercial",
        "navigational",
        "informational",
    }
