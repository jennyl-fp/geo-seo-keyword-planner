"""ADR-015 驗收：像素估算邊界（580 內/外）；品牌後綴棄用；確定性。"""

from rules.title import (
    TITLE_MAX_PIXELS,
    check_title,
    estimate_title_pixels,
    suggest_title,
)


class TestPixelEstimation:
    def test_cjk_36_chars_fits(self):
        title = "智" * 36
        assert estimate_title_pixels(title) == 576
        assert check_title(title)[1] is True

    def test_cjk_37_chars_overflow(self):
        title = "智" * 37
        assert estimate_title_pixels(title) == 592
        assert check_title(title)[1] is False

    def test_latin_lowercase(self):
        # smart: s m a r(8×4) + t(4) = 36；空格 4；office: o c e(8×3) + f f i(4×3) = 36
        assert estimate_title_pixels("smart office") == 76

    def test_uppercase_and_wide(self):
        assert estimate_title_pixels("SEO") == 10 + 10 + 10
        assert estimate_title_pixels("W") == 12

    def test_narrow_chars(self):
        assert estimate_title_pixels("ill.,") == 5 * 4

    def test_mixed_cjk_latin(self):
        title = "學唱歌推薦"
        assert estimate_title_pixels(title) == 5 * 16


class TestSuggestTitle:
    def test_brand_suffix_when_fits(self):
        result = suggest_title("學唱歌價錢", brand="Parkland Music")
        assert result.title == "學唱歌價錢 | Parkland Music"
        assert result.fits is True
        assert result.dropped_brand is False

    def test_brand_dropped_when_overflow(self):
        primary = "智" * 33  # 528px；加品牌會超
        result = suggest_title(primary, brand="Parkland Music")
        assert result.dropped_brand is True
        assert result.title == primary
        assert result.fits is True

    def test_still_overflow_without_brand(self):
        primary = "智" * 40  # 640px
        result = suggest_title(primary, brand=None)
        assert result.fits is False
        assert result.dropped_brand is False

    def test_deterministic(self):
        assert suggest_title("結他班", "Parkland") == suggest_title("結他班", "Parkland")

    def test_max_constant(self):
        assert TITLE_MAX_PIXELS == 580
