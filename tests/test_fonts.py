"""字体解析——挑得到、画得出、缺字就报错。"""
from __future__ import annotations

import pytest

from aimkit import fonts


def test_the_bundled_font_files_are_in_the_repo():
    for path in fonts.BUNDLED_PATHS:
        assert path.is_file(), f"字体子集不在仓里：{path}"


def test_the_family_resolves():
    fonts.assert_font_available()


def test_a_common_chinese_character_is_drawn():
    assert fonts.missing_chars("深入数据库") == []


def test_a_character_the_font_lacks_is_reported():
    """字体里没有的字 → 报出来（不然画出来是豆腐块）。"""
    missing = fonts.missing_chars("深入数据库🦄")
    assert "🦄" in missing
    assert "深" not in missing


def test_check_glyphs_raises_for_a_character_the_font_lacks():
    with pytest.raises(fonts.MissingGlyphs) as excinfo:
        fonts.check_glyphs("深入数据库🦄")
    assert "🦄" in excinfo.value.chars
    assert excinfo.value.family


def test_check_glyphs_passes_for_text_the_font_has():
    fonts.check_glyphs("深入数据库")


def test_the_hinting_is_off():
    """hinting 会让几何不再是字体文件的性质——所以必须关掉。"""
    cairo = pytest.importorskip("cairo")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
    ctx = cairo.Context(surface)
    fonts.select_font(ctx)
    options = ctx.get_font_options()
    assert options.get_hint_style() == cairo.HINT_STYLE_NONE
    assert options.get_hint_metrics() == cairo.HINT_METRICS_OFF
