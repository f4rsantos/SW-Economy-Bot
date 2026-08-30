# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from database.static_cache import static_cache
from services.income_calculator import (
    calculate_fleet_cs_cost_by_system,
    plan_cs_withdrawals_by_system,
    calculate_cs_deficit_by_system,
    plan_fleet_cs_damage,
)
from services.income_executor import (
    calculate_fleet_cs_usage_by_system,
    process_fleet_cs_damage_by_system,
)


STAR_A_ID = 1
PLANET_A_ID = 2
MOON_A_ID = 3
STAR_B_ID = 10
PLANET_B_ID = 11

IDLE_STATUS = 1
DEFENCE_STATUS = 2
DEBRIS_STATUS = 99


@pytest.fixture
def fake_executemany(monkeypatch, fake_db):
    from database.db_manager import db

    calls = []

    async def _executemany(query, args_list):
        calls.append((query, list(args_list)))
        return None

    monkeypatch.setattr(db, "executemany", _executemany)
    return calls


@pytest.fixture(autouse=True)
def seeded_worlds():
    static_cache.worlds_by_id = {
        STAR_A_ID: {'id': STAR_A_ID, 'name': 'Star A', 'orbit_of': None},
        PLANET_A_ID: {'id': PLANET_A_ID, 'name': 'Planet A', 'orbit_of': STAR_A_ID},
        MOON_A_ID: {'id': MOON_A_ID, 'name': 'Moon A', 'orbit_of': PLANET_A_ID},
        STAR_B_ID: {'id': STAR_B_ID, 'name': 'Star B', 'orbit_of': None},
        PLANET_B_ID: {'id': PLANET_B_ID, 'name': 'Planet B', 'orbit_of': STAR_B_ID},
    }
    static_cache.worlds = {w['name'].lower(): w for w in static_cache.worlds_by_id.values()}
    static_cache._build_system_map()

    static_cache.fleet_status_by_id = {
        IDLE_STATUS: 'idle',
        DEFENCE_STATUS: 'defence',
        DEBRIS_STATUS: 'debris',
    }
    yield


def test_moon_resolves_to_star_root():
    assert static_cache.get_system_id(MOON_A_ID) == STAR_A_ID
    assert static_cache.get_system_id(PLANET_A_ID) == STAR_A_ID
    assert static_cache.get_system_id(STAR_A_ID) == STAR_A_ID
    assert static_cache.get_system_name(MOON_A_ID) == 'Star A'


def test_two_root_worlds_are_distinct_systems():
    assert static_cache.get_system_id(PLANET_B_ID) == STAR_B_ID
    assert static_cache.get_system_id(PLANET_A_ID) != static_cache.get_system_id(PLANET_B_ID)


def test_cyclic_orbit_of_does_not_hang_and_resolves_to_a_root():
    cyclic_id_1 = 900
    cyclic_id_2 = 901
    static_cache.worlds_by_id = {
        cyclic_id_1: {'id': cyclic_id_1, 'name': 'Cycle A', 'orbit_of': cyclic_id_2},
        cyclic_id_2: {'id': cyclic_id_2, 'name': 'Cycle B', 'orbit_of': cyclic_id_1},
    }
    static_cache._build_system_map()

    root_1 = static_cache.get_system_id(cyclic_id_1)
    root_2 = static_cache.get_system_id(cyclic_id_2)
    assert root_1 == root_2
    assert root_1 in (cyclic_id_1, cyclic_id_2)


def test_missing_orbit_of_target_does_not_crash_and_resolves_to_a_stable_root():
    orphan_id = 950
    missing_parent_id = 99999
    static_cache.worlds_by_id = {
        orphan_id: {'id': orphan_id, 'name': 'Orphan', 'orbit_of': missing_parent_id},
    }
    static_cache._build_system_map()

    root = static_cache.get_system_id(orphan_id)
    assert root == missing_parent_id
    assert static_cache.get_system_id(orphan_id) == root


def test_overlong_chain_does_not_hang_and_resolves():
    chain = {}
    for i in range(50):
        chain[i] = {'id': i, 'name': f'World {i}', 'orbit_of': i + 1 if i < 49 else None}
    static_cache.worlds_by_id = chain
    static_cache._build_system_map()

    root = static_cache.get_system_id(0)
    assert root is not None


def test_fleet_cs_cost_grouped_by_system_never_mixes_systems():
    fleet_rows = [
        {'position': MOON_A_ID, 'status_id': IDLE_STATUS, 'total_cs': 800},
        {'position': PLANET_B_ID, 'status_id': IDLE_STATUS, 'total_cs': 1600},
    ]
    needs = calculate_fleet_cs_cost_by_system(
        fleet_rows,
        static_cache.get_system_id,
        static_cache.fleet_status_by_id.get,
    )
    assert needs[STAR_A_ID] == 100
    assert needs[STAR_B_ID] == 200


def test_withdrawals_never_cross_systems():
    needed_by_system = {STAR_A_ID: 100, STAR_B_ID: 200}
    worlds_by_system = {
        STAR_A_ID: [{'world_id': PLANET_A_ID, 'cs_amount': 500}],
        STAR_B_ID: [{'world_id': PLANET_B_ID, 'cs_amount': 50}],
    }
    withdrawals = plan_cs_withdrawals_by_system(needed_by_system, worlds_by_system)

    assert withdrawals[STAR_A_ID] == {PLANET_A_ID: 100}
    assert withdrawals[STAR_B_ID] == {PLANET_B_ID: 50}

    deficits = calculate_cs_deficit_by_system(needed_by_system, withdrawals)
    assert STAR_A_ID not in deficits
    assert deficits[STAR_B_ID] == 150


def test_rich_system_cs_cannot_pay_poor_system_fleets():
    needed_by_system = {STAR_B_ID: 500}
    worlds_by_system = {
        STAR_A_ID: [{'world_id': PLANET_A_ID, 'cs_amount': 10_000}],
        STAR_B_ID: [],
    }
    withdrawals = plan_cs_withdrawals_by_system(needed_by_system, worlds_by_system)

    assert withdrawals[STAR_B_ID] == {}
    deficits = calculate_cs_deficit_by_system(needed_by_system, withdrawals)
    assert deficits[STAR_B_ID] == 500


@pytest.mark.asyncio
async def test_calculate_fleet_cs_usage_by_system_uses_repo_rows(fake_db):
    fake_db.fetchrow_queue.append({'id': DEBRIS_STATUS})
    fake_db.fetch_queue.append([
        {'id': 1, 'position': MOON_A_ID, 'status_id': IDLE_STATUS, 'total_cs': 800},
        {'id': 2, 'position': PLANET_B_ID, 'status_id': IDLE_STATUS, 'total_cs': 1600},
    ])

    needs = await calculate_fleet_cs_usage_by_system(faction_id=1)

    assert needs[STAR_A_ID] == 100
    assert needs[STAR_B_ID] == 200


@pytest.mark.asyncio
async def test_deficit_in_one_system_only_damages_that_systems_fleets(fake_db, fake_executemany):
    fake_db.fetchrow_queue.append({'id': DEBRIS_STATUS})
    fake_db.fetch_queue.append([
        {'id': 1, 'name': 'Fleet A', 'health': 100, 'total_cs': 800, 'status_id': IDLE_STATUS,
         'position': MOON_A_ID, 'status_name': 'idle'},
        {'id': 2, 'name': 'Fleet B', 'health': 100, 'total_cs': 1600, 'status_id': IDLE_STATUS,
         'position': PLANET_B_ID, 'status_name': 'idle'},
    ])

    deficits_by_system = {STAR_B_ID: 50}
    await process_fleet_cs_damage_by_system(faction_id=1, deficits_by_system=deficits_by_system)

    damage_calls = [call for call in fake_executemany if 'UPDATE fleets SET health' in call[0]]
    assert len(damage_calls) == 1
    _, updates = damage_calls[0]
    updated_fleet_ids = {fleet_id for _, fleet_id in updates}
    assert updated_fleet_ids == {2}


@pytest.mark.asyncio
async def test_healthy_system_untouched_when_only_other_system_has_deficit(fake_db, fake_executemany):
    fake_db.fetchrow_queue.append({'id': DEBRIS_STATUS})
    fake_db.fetch_queue.append([
        {'id': 1, 'name': 'Fleet A', 'health': 100, 'total_cs': 800, 'status_id': IDLE_STATUS,
         'position': MOON_A_ID, 'status_name': 'idle'},
        {'id': 2, 'name': 'Fleet B', 'health': 100, 'total_cs': 1600, 'status_id': IDLE_STATUS,
         'position': PLANET_B_ID, 'status_name': 'idle'},
    ])

    deficits_by_system = {STAR_A_ID: 0, STAR_B_ID: 50}
    await process_fleet_cs_damage_by_system(faction_id=1, deficits_by_system=deficits_by_system)

    updated_fleet_ids = set()
    for _, updates in fake_executemany:
        for _, fleet_id in updates:
            updated_fleet_ids.add(fleet_id)
    assert 1 not in updated_fleet_ids


@pytest.mark.asyncio
async def test_no_deficit_skips_damage_entirely(fake_db, fake_executemany):
    await process_fleet_cs_damage_by_system(faction_id=1, deficits_by_system={})
    assert fake_db.executed == []
    assert fake_executemany == []

    await process_fleet_cs_damage_by_system(faction_id=1, deficits_by_system={STAR_A_ID: 0})
    assert fake_db.executed == []
    assert fake_executemany == []
