# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from services.map_service import _get_system_root_id, _count_off_capital_system_hexes
from services.fleet_service import get_ftl_supply_capacity


@pytest.mark.asyncio
async def test_get_system_root_id_returns_root(fake_db):
    fake_db.fetchrow_queue.append({"id": 1})
    root = await _get_system_root_id(50)
    assert root == 1


@pytest.mark.asyncio
async def test_get_system_root_id_none_when_no_world(fake_db):
    root = await _get_system_root_id(None)
    assert root is None
    assert fake_db.executed == []


@pytest.mark.asyncio
async def test_count_off_capital_system_hexes(fake_db):
    fake_db.fetchrow_queue.append({"total": 37})
    total = await _count_off_capital_system_hexes(faction_id=9, capital_system_id=1)
    assert total == 37


@pytest.mark.asyncio
async def test_ftl_supply_capacity_sums_cargo(fake_db):
    fake_db.fetchrow_queue.append({"total_cargo": 450})
    capacity = await get_ftl_supply_capacity(faction_id=9)
    assert capacity == 450


@pytest.mark.asyncio
async def test_ftl_supply_capacity_zero_when_no_fleets(fake_db):
    fake_db.fetchrow_queue.append(None)
    capacity = await get_ftl_supply_capacity(faction_id=9)
    assert capacity == 0
