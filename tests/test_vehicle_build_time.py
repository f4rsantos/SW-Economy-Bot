import pytest
from services.vehicle_service import build_days


@pytest.mark.parametrize("length,expected", [
    (1, 2.0),
    (20, 2.0),
    (200, 8.0),
    (1000, 14.0),
    (1500, 14.0),
])
def test_build_days_anchor_points(length, expected):
    assert build_days(length) == pytest.approx(expected)


def test_build_days_between_20_and_200_is_linear():
    assert build_days(110) == pytest.approx(2.0 + (110 - 20) / 180 * 6.0)


def test_build_days_between_200_and_1000_is_linear():
    assert build_days(600) == pytest.approx(8.0 + (600 - 200) / 800 * 6.0)


def test_build_days_monotonic_increasing():
    lengths = [1, 20, 50, 100, 200, 400, 700, 1000, 2000]
    days = [build_days(l) for l in lengths]
    assert days == sorted(days)


def test_build_days_never_exceeds_bounds():
    for length in [0, 5, 20, 200, 999, 1000, 5000, 1_000_000]:
        d = build_days(length)
        assert 2.0 <= d <= 14.0
