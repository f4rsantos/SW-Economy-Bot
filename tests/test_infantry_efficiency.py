import pytest

from services.building_efficiency_service import get_faction_infantry_penalty, get_infantry_allocation_by_world


async def test_infantry_penalty_ratio(fake_db):
    fake_db.fetchrow_queue.append({'total': 500})
    fake_db.fetchrow_queue.append({'total_population': 9500})
    ratio = await get_faction_infantry_penalty(1)
    assert ratio == pytest.approx(0.05)


async def test_infantry_penalty_zero_division_guard(fake_db):
    fake_db.fetchrow_queue.append({'total': 0})
    fake_db.fetchrow_queue.append({'total_population': 0})
    ratio = await get_faction_infantry_penalty(1)
    assert ratio == 0.0


async def test_infantry_penalty_no_infantry(fake_db):
    fake_db.fetchrow_queue.append({'total': 0})
    fake_db.fetchrow_queue.append({'total_population': 1000})
    ratio = await get_faction_infantry_penalty(1)
    assert ratio == 0.0


async def test_allocation_sums_to_total_with_even_split(fake_db):
    fake_db.fetchrow_queue.append({'total': 100})
    fake_db.fetch_queue.append([
        {'world_id': 1, 'population': 500},
        {'world_id': 2, 'population': 500},
    ])
    allocation = await get_infantry_allocation_by_world(1)
    assert sum(allocation.values()) == 100
    assert allocation[1] == 50
    assert allocation[2] == 50


async def test_allocation_sums_to_total_with_awkward_remainder(fake_db):
    fake_db.fetchrow_queue.append({'total': 10})
    fake_db.fetch_queue.append([
        {'world_id': 1, 'population': 1},
        {'world_id': 2, 'population': 1},
        {'world_id': 3, 'population': 1},
    ])
    allocation = await get_infantry_allocation_by_world(1)
    assert sum(allocation.values()) == 10
    assert set(allocation.keys()) == {1, 2, 3}


async def test_allocation_awkward_remainder_various_totals(fake_db):
    for total_infantry in range(0, 23):
        fake_db.fetchrow_queue.append({'total': total_infantry})
        fake_db.fetch_queue.append([
            {'world_id': 1, 'population': 7},
            {'world_id': 2, 'population': 13},
            {'world_id': 3, 'population': 3},
        ])
        allocation = await get_infantry_allocation_by_world(1)
        assert sum(allocation.values()) == total_infantry


async def test_allocation_zero_infantry_returns_zeros(fake_db):
    fake_db.fetchrow_queue.append({'total': 0})
    fake_db.fetch_queue.append([
        {'world_id': 1, 'population': 500},
        {'world_id': 2, 'population': 500},
    ])
    allocation = await get_infantry_allocation_by_world(1)
    assert allocation == {1: 0, 2: 0}


async def test_allocation_zero_population_returns_zeros(fake_db):
    fake_db.fetchrow_queue.append({'total': 50})
    fake_db.fetch_queue.append([
        {'world_id': 1, 'population': 0},
        {'world_id': 2, 'population': 0},
    ])
    allocation = await get_infantry_allocation_by_world(1)
    assert allocation == {1: 0, 2: 0}


async def test_allocation_no_worlds_returns_empty(fake_db):
    fake_db.fetchrow_queue.append({'total': 50})
    fake_db.fetch_queue.append([])
    allocation = await get_infantry_allocation_by_world(1)
    assert allocation == {}
