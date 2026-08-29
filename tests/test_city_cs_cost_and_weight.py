# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from repositories.building_repo import get_faction_building_count_weighted
from services.building_service import _calculate_building_cost, _calculate_refund


NON_MEGA_FACTORY_BUILDING_ID = 6


def test_city_cost_with_cs_scales_like_any_other_resource():
    base_costs = {"CM": 5000, "EL": 2000, "CS": 20000}
    cost = _calculate_building_cost(base_costs, current_actual=0, amount=1, level=1, building_id=NON_MEGA_FACTORY_BUILDING_ID)

    assert cost["CS"] == 20000
    assert cost["CM"] == 5000
    assert cost["EL"] == 2000


def test_city_refund_mirrors_cs_cost_at_full_rate():
    base_costs = {"CM": 5000, "EL": 2000, "CS": 20000}
    cost = _calculate_building_cost(base_costs, current_actual=0, amount=1, level=1, building_id=NON_MEGA_FACTORY_BUILDING_ID)
    refund = _calculate_refund(base_costs, scaling_count=1, amount=1, level=1, week=True, building_id=NON_MEGA_FACTORY_BUILDING_ID)

    assert refund == cost


def test_city_refund_at_partial_rate_is_less_than_cost():
    base_costs = {"CS": 20000}
    cost = _calculate_building_cost(base_costs, current_actual=0, amount=1, level=1, building_id=NON_MEGA_FACTORY_BUILDING_ID)
    refund = _calculate_refund(base_costs, scaling_count=1, amount=1, level=1, week=False, building_id=NON_MEGA_FACTORY_BUILDING_ID)

    assert refund["CS"] < cost["CS"]
    assert refund["CS"] == pytest.approx(cost["CS"] * 0.3, abs=1)


@pytest.mark.asyncio
async def test_weighted_count_rounds_fractional_city_total_instead_of_truncating(fake_db):
    fake_db.fetchrow_queue.append({"total_count": 0.9})

    total = await get_faction_building_count_weighted(faction_id=1)

    assert total == 1


@pytest.mark.asyncio
async def test_weighted_count_rounds_down_below_half(fake_db):
    fake_db.fetchrow_queue.append({"total_count": 0.3})

    total = await get_faction_building_count_weighted(faction_id=1)

    assert total == 0


@pytest.mark.asyncio
async def test_weighted_count_none_is_zero(fake_db):
    fake_db.fetchrow_queue.append({"total_count": None})

    total = await get_faction_building_count_weighted(faction_id=1)

    assert total == 0
