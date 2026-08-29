import pytest

from services.income_calculator import (
    calculate_population_growth,
    calculate_city_growth_bonus,
    population_cs_map,
    POPULATION_PER_CS,
)


def test_population_per_cs_is_5000():
    assert POPULATION_PER_CS == 5000


def test_population_cs_map_uses_new_ratio():
    result = population_cs_map([{"world_id": 1, "population": 5000}])
    assert result[1] == 1


def test_breakeven_ratio_matches_population_cs_map_cost():
    population = 500_000
    cs_needed = population / POPULATION_PER_CS
    growth = calculate_population_growth(
        population=population,
        global_cs=cs_needed,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
    )
    assert growth == 0


def test_max_growth_at_double_breakeven_cs():
    population = 500_000
    cs_needed = population / POPULATION_PER_CS
    growth = calculate_population_growth(
        population=population,
        global_cs=cs_needed * 2,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
    )
    assert growth == population * 10 // 100


def test_starving_population_shrinks():
    population = 500_000
    growth = calculate_population_growth(
        population=population,
        global_cs=0,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
    )
    assert growth < 0


def test_zero_population_returns_zero():
    assert calculate_population_growth(0, 1000, 1000, 1000, False) == 0


def test_city_bonus_single_level_ten_city_is_five_percent():
    bonus = calculate_city_growth_bonus([10], growth_percent=5)
    assert bonus == pytest.approx(5.0)


def test_city_bonus_level_one_city_is_one_tenth_effective_level():
    bonus_ten = calculate_city_growth_bonus([10], growth_percent=5)
    bonus_one = calculate_city_growth_bonus([1], growth_percent=5)
    assert bonus_one < bonus_ten
    assert bonus_one == pytest.approx(10 * (1 - 0.5 ** 0.1))


def test_city_bonus_never_exceeds_ten_percent():
    bonus = calculate_city_growth_bonus([10] * 50, growth_percent=5)
    assert bonus < 10.0


def test_city_bonus_diminishing_returns():
    one_city = calculate_city_growth_bonus([10], growth_percent=5)
    two_cities = calculate_city_growth_bonus([10, 10], growth_percent=5)
    three_cities = calculate_city_growth_bonus([10, 10, 10], growth_percent=5)
    assert (two_cities - one_city) > (three_cities - two_cities) > 0


def test_city_bonus_zero_at_zero_growth():
    assert calculate_city_growth_bonus([10], growth_percent=0) == 0


def test_city_bonus_zero_at_negative_growth():
    assert calculate_city_growth_bonus([10], growth_percent=-5) == 0


def test_city_bonus_scales_down_between_ratio_one_and_two():
    full = calculate_city_growth_bonus([10], growth_percent=5)
    half = calculate_city_growth_bonus([10], growth_percent=2.5)
    assert half == pytest.approx(full / 2)


def test_city_bonus_never_rescues_starving_world():
    population = 500_000
    growth_without_city = calculate_population_growth(
        population=population,
        global_cs=0,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
    )
    growth_with_city = calculate_population_growth(
        population=population,
        global_cs=0,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
        city_levels=[10, 10, 10],
    )
    assert growth_with_city == growth_without_city
    assert growth_with_city < 0


def test_city_bonus_no_cities_is_noop():
    population = 500_000
    cs_needed = population / POPULATION_PER_CS
    without = calculate_population_growth(
        population=population,
        global_cs=cs_needed * 2,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
    )
    with_empty_list = calculate_population_growth(
        population=population,
        global_cs=cs_needed * 2,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
        city_levels=[],
    )
    assert without == with_empty_list


def test_city_bonus_increases_growth_at_max_cs():
    population = 500_000
    cs_needed = population / POPULATION_PER_CS
    without_city = calculate_population_growth(
        population=population,
        global_cs=cs_needed * 2,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
    )
    with_city = calculate_population_growth(
        population=population,
        global_cs=cs_needed * 2,
        global_population=population,
        local_cs_production=0,
        is_blockaded=False,
        city_levels=[10],
    )
    assert with_city > without_city
