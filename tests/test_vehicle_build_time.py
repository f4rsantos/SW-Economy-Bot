# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from services.vehicle_service import build_days


@pytest.mark.parametrize("length,expected", [
    (1, 1.0),
    (20, 1.0),
    (250, 7.0),
    (1000, 14.0),
    (1500, 14.0),
])
def test_build_days_anchor_points(length, expected):
    assert build_days(length) == pytest.approx(expected)


def test_build_days_between_20_and_250_is_linear():
    assert build_days(110) == pytest.approx(1.0 + (110 - 20) / 230 * 6.0)


def test_build_days_between_250_and_1000_is_linear():
    assert build_days(600) == pytest.approx(7.0 + (600 - 250) / 750 * 7.0)


def test_build_days_monotonic_increasing():
    lengths = [1, 20, 50, 100, 200, 400, 700, 1000, 2000]
    days = [build_days(l) for l in lengths]
    assert days == sorted(days)


def test_build_days_never_exceeds_bounds():
    for length in [0, 5, 20, 200, 999, 1000, 5000, 1_000_000]:
        d = build_days(length)
        assert 1.0 <= d <= 14.0
