# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import io
import math
import pytest

from PIL import Image

from services.solar_map_service import radial_pan_step, angular_pan_step, render_solar_map


def test_radial_in_moves_toward_centre():
    pan_x, pan_y = radial_pan_step(100.0, 0.0, 40.0, "in")
    assert pan_x == pytest.approx(60.0)
    assert pan_y == pytest.approx(0.0)


def test_radial_out_moves_away_from_centre():
    pan_x, pan_y = radial_pan_step(100.0, 0.0, 40.0, "out")
    assert pan_x == pytest.approx(140.0)
    assert pan_y == pytest.approx(0.0)


def test_radial_in_clamps_at_centre():
    pan_x, pan_y = radial_pan_step(30.0, 0.0, 100.0, "in")
    assert pan_x == pytest.approx(0.0)
    assert pan_y == pytest.approx(0.0)


def test_radial_in_preserves_direction():
    pan_x, pan_y = radial_pan_step(30.0, 40.0, 10.0, "in")
    assert math.hypot(pan_x, pan_y) == pytest.approx(40.0)
    assert pan_x / pan_y == pytest.approx(30.0 / 40.0)


def test_radial_at_centre_in_stays_at_centre():
    pan_x, pan_y = radial_pan_step(0.0, 0.0, 50.0, "in")
    assert pan_x == 0.0
    assert pan_y == 0.0


def test_radial_at_centre_out_picks_default_direction():
    pan_x, pan_y = radial_pan_step(0.0, 0.0, 50.0, "out")
    assert pan_x == pytest.approx(0.0)
    assert pan_y == pytest.approx(-50.0)
    assert math.hypot(pan_x, pan_y) == pytest.approx(50.0)


def test_radial_invalid_direction_raises():
    with pytest.raises(ValueError):
        radial_pan_step(1.0, 1.0, 10.0, "sideways")


def test_angular_rotation_preserves_radius():
    pan_x, pan_y = angular_pan_step(100.0, 0.0, 50.0, "cw")
    assert math.hypot(pan_x, pan_y) == pytest.approx(100.0)


def test_angular_cw_and_ccw_are_opposite():
    cw_x, cw_y = angular_pan_step(100.0, 0.0, 50.0, "cw")
    ccw_x, ccw_y = angular_pan_step(100.0, 0.0, 50.0, "ccw")
    assert cw_y == pytest.approx(-ccw_y)
    assert cw_x == pytest.approx(ccw_x)


def test_angular_at_centre_is_noop():
    pan_x, pan_y = angular_pan_step(0.0, 0.0, 50.0, "cw")
    assert pan_x == 0.0
    assert pan_y == 0.0


def test_angular_invalid_direction_raises():
    with pytest.raises(ValueError):
        angular_pan_step(1.0, 1.0, 10.0, "diagonal")


def test_angular_full_circle_returns_to_start():
    x, y = 100.0, 0.0
    circumference = 2 * math.pi * 100.0
    steps = 36
    step_len = circumference / steps
    for _ in range(steps):
        x, y = angular_pan_step(x, y, step_len, "cw")
    assert x == pytest.approx(100.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def _assert_valid_png(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes))
    assert img.format == "PNG"


def test_route_two_bodies_produces_valid_png():
    image_bytes, title, game_date_label, closest_body = render_solar_map(
        system_name="Sol",
        route=["Earth", "Mars"],
    )
    _assert_valid_png(image_bytes)
    assert title == "Sol System"


def test_route_unknown_world_name_does_not_raise():
    image_bytes, title, game_date_label, closest_body = render_solar_map(
        system_name="Sol",
        route=["Earth", "Nonexistent Planet Zeta"],
    )
    _assert_valid_png(image_bytes)


def test_route_single_body_draws_nothing_extra():
    baseline_bytes, _, _, _ = render_solar_map(system_name="Sol", date_str="2123-05-01")
    single_route_bytes, _, _, _ = render_solar_map(system_name="Sol", date_str="2123-05-01", route=["Earth"])
    assert len(single_route_bytes) == len(baseline_bytes)


def test_route_same_origin_and_destination_does_not_raise():
    image_bytes, title, game_date_label, closest_body = render_solar_map(
        system_name="Sol",
        route=["Earth", "Earth"],
    )
    _assert_valid_png(image_bytes)


def test_route_omitted_matches_existing_behaviour():
    with_none_bytes, _, _, _ = render_solar_map(system_name="Sol", date_str="2123-05-01", route=None)
    without_param_bytes, _, _, _ = render_solar_map(system_name="Sol", date_str="2123-05-01")
    assert len(with_none_bytes) == len(without_param_bytes)


def test_route_moon_in_overview_does_not_raise():
    image_bytes, title, game_date_label, closest_body = render_solar_map(
        system_name="Sol",
        route=["Earth", "Luna"],
    )
    _assert_valid_png(image_bytes)


def test_route_in_focus_view_produces_valid_png():
    image_bytes, title, game_date_label, closest_body = render_solar_map(
        system_name="Sol",
        focus="Earth",
        route=["Earth", "Luna"],
    )
    _assert_valid_png(image_bytes)
    assert title == "Earth System"
