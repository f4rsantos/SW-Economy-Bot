import pytest

from services.income_calculator import (
    calculate_influence_income,
    calculate_level_10_building_influence_bonus,
    INFLUENCE_CAP,
)


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


def test_level_10_bonus_first_building_gives_ten():
    assert calculate_level_10_building_influence_bonus(1) == 10


def test_level_10_bonus_marginal_rounds_to_zero_at_twenty():
    marginal_at_20 = max(0.0, 10 - 0.5 * (20 - 1))
    assert round(marginal_at_20) == 0


def test_level_10_bonus_flat_beyond_twenty():
    assert calculate_level_10_building_influence_bonus(20) == calculate_level_10_building_influence_bonus(30)


def test_level_10_bonus_zero_for_no_buildings():
    assert calculate_level_10_building_influence_bonus(0) == 0


def test_level_10_bonus_monotonically_non_decreasing():
    values = [calculate_level_10_building_influence_bonus(n) for n in range(0, 25)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_level_10_bonus_added_to_influence_income():
    without = calculate_influence_income(0, 0, 0, 0, 0)
    with_bonus = calculate_influence_income(0, 0, 0, 0, 1)
    assert with_bonus == without + 10


def test_level_10_bonus_still_capped_by_influence_cap():
    gain = calculate_influence_income(0, 0, INFLUENCE_CAP - 5, 0, 5)
    assert gain == 5


def test_level_10_bonus_negative_count_treated_as_zero():
    assert calculate_level_10_building_influence_bonus(-3) == 0
