import pytest

from services.income_calculator import calculate_influence_income, INFLUENCE_CAP


@pytest.mark.parametrize("current", [0, 5000, 9600, 9900, 10000])
@pytest.mark.parametrize("upkeep", [0, 500_000, 1_000_000, 5_000_000])
def test_never_exceeds_cap(current, upkeep):
    gain = calculate_influence_income(0, 0, current, upkeep)
    assert current + gain <= INFLUENCE_CAP


def test_regression_9600_full_upkeep():
    gain = calculate_influence_income(0, 0, 9600, 1_000_000)
    assert gain == 400


def test_at_cap_yields_nothing():
    assert calculate_influence_income(0, 0, INFLUENCE_CAP, 1_000_000) == 0


def test_upkeep_bonus_applies_below_cap():
    without = calculate_influence_income(0, 0, 0, 0)
    with_bonus = calculate_influence_income(0, 0, 0, 1_000_000)
    assert with_bonus == min(without * 2, INFLUENCE_CAP)


def test_negative_net_generation_is_not_amplified():
    gain = calculate_influence_income(0, 5000, 8000, 1_000_000)
    assert gain == -2500


def test_generation_rate_floor():
    gain = calculate_influence_income(100_000, 0, 0, 0)
    assert gain == 50
