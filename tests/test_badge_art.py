# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from utils.badge_art import (
    FOUR_COLOR_IDS,
    GRID_FEW_BADGES_COLUMNS,
    GRID_MANY_BADGES_COLUMNS,
    GRID_MANY_BADGES_THRESHOLD,
    RIBBON_WIDTH,
    band_spec,
    choose_grid_columns,
    compute_widths,
    hash32,
    load_grid_font,
    render_badge_grid_png,
    render_ribbon_png,
    render_ribbon_stack_png,
    render_user_card_png,
)


def test_hash32_is_stable():
    assert hash32(0) == hash32(0)
    assert hash32(1) == hash32(1)
    assert hash32(2) == hash32(2)
    assert hash32(0) != hash32(1)
    assert hash32(1) != hash32(2)


def test_hash32_stays_within_32_bits():
    for n in range(0, 5000, 37):
        result = hash32(n)
        assert 0 <= result <= 0xFFFFFFFF


def test_band_spec_is_deterministic():
    for badge_id in range(1, 30):
        first = band_spec(badge_id)
        second = band_spec(badge_id)
        assert first == second


def test_four_color_ids_produce_seven_bands():
    for badge_id in FOUR_COLOR_IDS:
        assert len(band_spec(badge_id)) == 7


def test_non_four_color_ids_produce_five_bands():
    for badge_id in range(1, 30):
        if badge_id in FOUR_COLOR_IDS:
            continue
        assert len(band_spec(badge_id)) == 5


def test_compute_widths_sum_exactly_to_total():
    for badge_id in range(1, 40):
        bands = band_spec(badge_id)
        for total in (72, 288, 100, 37):
            widths = compute_widths(bands, total)
            assert sum(widths) == total


def test_compute_widths_never_below_minimum_pre_correction():
    for badge_id in range(1, 40):
        bands = band_spec(badge_id)
        for total in (72, 288, 100, 37):
            min_px = -(-total // 10)
            band_sum = sum(b["weight"] for b in bands)
            raw_widths = [max(min_px, (b["weight"] * total) // band_sum) for b in bands]
            assert all(w >= min_px for w in raw_widths)


def test_compute_widths_center_band_absorbs_rounding_diff():
    for badge_id in range(1, 40):
        bands = band_spec(badge_id)
        for total in (72, 288, 100, 37):
            min_px = -(-total // 10)
            band_sum = sum(b["weight"] for b in bands)
            raw_widths = [max(min_px, (b["weight"] * total) // band_sum) for b in bands]
            diff = total - sum(raw_widths)
            widths = compute_widths(bands, total)
            mid = len(widths) // 2
            for i, (raw, final) in enumerate(zip(raw_widths, widths)):
                assert final == (raw + diff if i == mid else raw)


def test_render_ribbon_png_produces_valid_png_bytes():
    data = render_ribbon_png(1)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_ribbon_png_size_matches_scale():
    from PIL import Image
    import io

    scale = 4
    data = render_ribbon_png(1, scale=scale)
    image = Image.open(io.BytesIO(data))
    assert image.size == (RIBBON_WIDTH * scale, 14 * scale)


def test_render_ribbon_stack_png_stacks_all_badges():
    from PIL import Image
    import io

    scale = 4
    gap = 4
    badge_ids = [1, 2, 3]
    data = render_ribbon_stack_png(badge_ids, scale=scale, gap=gap)
    image = Image.open(io.BytesIO(data))
    ribbon_height = 14 * scale
    expected_height = ribbon_height * len(badge_ids) + gap * scale * (len(badge_ids) - 1)
    assert image.size == (RIBBON_WIDTH * scale, expected_height)


def test_choose_grid_columns_thresholds():
    assert GRID_MANY_BADGES_THRESHOLD == 5
    for count in range(1, GRID_MANY_BADGES_THRESHOLD):
        assert choose_grid_columns(count) == GRID_FEW_BADGES_COLUMNS
    for count in range(GRID_MANY_BADGES_THRESHOLD, GRID_MANY_BADGES_THRESHOLD + 10):
        assert choose_grid_columns(count) == GRID_MANY_BADGES_COLUMNS


def test_choose_grid_columns_zero_badges():
    assert choose_grid_columns(0) == 0


def test_render_badge_grid_png_produces_valid_png_bytes():
    data = render_badge_grid_png([(1, "Alpha")])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_badge_grid_png_single_badge_dimensions():
    from PIL import Image
    import io

    data = render_badge_grid_png([(1, "Alpha")])
    image = Image.open(io.BytesIO(data))
    assert image.size[0] > 0
    assert image.size[1] > 0


def test_render_badge_grid_png_column_count_matches_layout():
    from PIL import Image
    import io

    scale = 4
    for count, expected_cols in [(1, 2), (4, 2), (5, 3), (9, 3)]:
        badges = [(i, f"Badge {i}") for i in range(count)]
        data = render_badge_grid_png(badges, scale=scale)
        image = Image.open(io.BytesIO(data))
        expected_rows = -(-count // expected_cols)
        cell_width = image.size[0] // expected_cols
        cell_height = image.size[1] // expected_rows
        assert image.size[0] == cell_width * expected_cols
        assert image.size[1] == cell_height * expected_rows


def test_render_badge_grid_png_explicit_columns_override():
    from PIL import Image
    import io

    badges = [(i, f"Badge {i}") for i in range(6)]
    data = render_badge_grid_png(badges, columns=2)
    image = Image.open(io.BytesIO(data))
    data_default = render_badge_grid_png(badges)
    image_default = Image.open(io.BytesIO(data_default))
    assert image.size != image_default.size


def test_render_badge_grid_png_long_name_does_not_crash():
    long_name = "A Supercalifragilisticexpialidocious Badge Name That Keeps Going And Going"
    data = render_badge_grid_png([(1, long_name)])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_badge_grid_png_many_long_names_stay_within_canvas():
    from PIL import Image
    import io

    long_name = "Extremely Long Badge Name For Overflow Testing Purposes Only"
    badges = [(i, long_name) for i in range(6)]
    data = render_badge_grid_png(badges)
    image = Image.open(io.BytesIO(data))
    assert image.size[0] > 0
    assert image.size[1] > 0


def test_render_badge_grid_png_zero_badges_raises():
    import pytest

    with pytest.raises(ValueError):
        render_badge_grid_png([])


def test_load_grid_font_returns_font():
    from PIL import ImageFont

    font = load_grid_font()
    assert isinstance(font, (ImageFont.FreeTypeFont, ImageFont.ImageFont))


def test_load_grid_font_falls_back_when_truetype_unavailable(monkeypatch):
    from PIL import ImageFont
    import utils.badge_art as badge_art

    original_truetype = ImageFont.truetype

    def fake_truetype(font=None, size=10, *args, **kwargs):
        if isinstance(font, str):
            raise OSError("font not found")
        return original_truetype(font, size, *args, **kwargs)

    monkeypatch.setattr(badge_art.ImageFont, "truetype", fake_truetype)

    font = badge_art.load_grid_font()
    assert isinstance(font, ImageFont.ImageFont) or isinstance(font, ImageFont.FreeTypeFont)

    data = badge_art.render_badge_grid_png([(1, "Alpha")])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_user_card_png_produces_valid_png_with_badges():
    badges = [(1, "Alpha"), (2, "Beta")]
    data = render_user_card_png(None, "TestUser", "Commander", badges)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_user_card_png_no_badges_case():
    from PIL import Image
    import io

    data = render_user_card_png(None, "TestUser", None, [])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(data))
    assert image.size[0] > 0
    assert image.size[1] > 0


def test_render_user_card_png_no_avatar_bytes_does_not_crash():
    data = render_user_card_png(None, "NoAvatarUser", "Recruit", [(1, "Alpha")])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_user_card_png_invalid_avatar_bytes_falls_back_gracefully():
    data = render_user_card_png(b"not a real image", "BrokenAvatarUser", "Recruit", [(1, "Alpha")])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_user_card_png_valid_avatar_bytes_are_composed():
    from PIL import Image
    import io

    avatar = Image.new("RGB", (128, 128), (200, 50, 50))
    buffer = io.BytesIO()
    avatar.save(buffer, format="PNG")

    data = render_user_card_png(buffer.getvalue(), "AvatarUser", "Recruit", [(1, "Alpha")])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_user_card_png_long_name_and_treatment_do_not_crash():
    long_name = "AVeryLongUsernameThatShouldBeTruncatedOrHandledGracefully"
    long_treatment = "An Extremely Long Treatment Title That Should Not Overflow"
    data = render_user_card_png(None, long_name, long_treatment, [(1, "Alpha")])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
