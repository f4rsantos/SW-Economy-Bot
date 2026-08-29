# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from services.income_calculator import apply_faction_population_limit
from services.faction_service import set_population_limit


async def test_set_valid_limit_below_capacity(fake_db):
    fake_db.fetchrow_queue.append({"max_pop": 1_000_000})
    result = await set_population_limit(1, 500_000)
    assert result == 500_000
    execute_calls = [c for c in fake_db.executed if c[0] == "execute"]
    assert len(execute_calls) == 1
    assert "population_limit" in execute_calls[0][1]
    assert execute_calls[0][2] == (500_000, 1)


async def test_reject_limit_above_physical_capacity(fake_db):
    fake_db.fetchrow_queue.append({"max_pop": 1_000_000})
    with pytest.raises(ValueError, match="1,000,000"):
        await set_population_limit(1, 1_500_000)


async def test_reject_negative_limit(fake_db):
    with pytest.raises(ValueError):
        await set_population_limit(1, -1)


async def test_clear_limit(fake_db):
    result = await set_population_limit(1, None)
    assert result is None
    execute_calls = [c for c in fake_db.executed if c[0] == "execute"]
    assert len(execute_calls) == 1
    assert execute_calls[0][2] == (None, 1)


def test_growth_allowed_below_limit():
    growth = {1: 100, 2: 200}
    result = apply_faction_population_limit(growth, current_total_population=1000, effective_limit=2000)
    assert result == growth


def test_growth_stops_exactly_at_limit():
    growth = {1: 500}
    result = apply_faction_population_limit(growth, current_total_population=1500, effective_limit=2000)
    assert result[1] == 500

    result_over = apply_faction_population_limit(growth, current_total_population=1999, effective_limit=2000)
    assert result_over[1] == 1

    result_at_cap = apply_faction_population_limit(growth, current_total_population=2000, effective_limit=2000)
    assert result_at_cap[1] == 0


def test_apportionment_across_multiple_worlds_sums_without_drift():
    growth = {1: 100, 2: 100, 3: 100}
    headroom_total_pop = 1000
    effective_limit = 1050
    result = apply_faction_population_limit(growth, current_total_population=headroom_total_pop, effective_limit=effective_limit)
    assert sum(result.values()) == 50
    for wid in growth:
        assert result[wid] >= 0
        assert result[wid] <= growth[wid]


def test_apportionment_odd_headroom_no_drift():
    growth = {1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30}
    result = apply_faction_population_limit(growth, current_total_population=0, effective_limit=100)
    assert sum(result.values()) == 100


def test_starvation_still_allowed_at_limit():
    growth = {1: -50, 2: 200}
    result = apply_faction_population_limit(growth, current_total_population=2000, effective_limit=2000)
    assert result[1] == -50
    assert result[2] == 0


def test_limit_exceeding_capacity_after_losing_world_clamped_by_min():
    faction_self_limit = 5_000_000
    physical_capacity_after_loss = 2_000_000
    effective_limit = min(faction_self_limit, physical_capacity_after_loss)
    assert effective_limit == physical_capacity_after_loss

    growth = {1: 100_000}
    result = apply_faction_population_limit(growth, current_total_population=1_950_000, effective_limit=effective_limit)
    assert result[1] == 50_000
