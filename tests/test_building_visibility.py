# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from services.intelligence_service import filter_visible_buildings, get_observed_worlds


def make_building(world_id, amount=1, name="Factory", level=1):
    return {'id': 1, 'name': name, 'amount': amount, 'level': level, 'world_id': world_id, 'world_name': f"World{world_id}"}


def test_own_buildings_always_visible():
    buildings = [make_building(1), make_building(2), make_building(3)]
    visible, hidden = filter_visible_buildings(buildings, True, set())
    assert visible == buildings
    assert hidden == 0


def test_other_faction_buildings_hidden_on_unobserved_world():
    buildings = [make_building(1, amount=5)]
    visible, hidden = filter_visible_buildings(buildings, False, set())
    assert visible == []
    assert hidden == 5


def test_other_faction_buildings_visible_on_observed_world():
    buildings = [make_building(1, amount=5), make_building(2, amount=3)]
    visible, hidden = filter_visible_buildings(buildings, False, {1})
    assert visible == [buildings[0]]
    assert hidden == 3


async def test_visible_on_world_shared_via_domestic_intelligence_pact(fake_db):
    fake_db.fetch_queue.append([{'world_id': 10}])
    fake_db.fetch_queue.append([{'pact_id': 99, 'domestic': True, 'foreign_alerts': False}])
    fake_db.fetch_queue.append([{'world_id': 20}])

    observed = await get_observed_worlds(1)
    assert observed == {10, 20}

    buildings = [make_building(20, amount=4), make_building(30, amount=2)]
    visible, hidden = filter_visible_buildings(buildings, False, observed)
    assert visible == [buildings[0]]
    assert hidden == 2


def test_hidden_count_aggregates_across_multiple_hidden_worlds():
    buildings = [make_building(1, amount=2), make_building(2, amount=3), make_building(3, amount=7)]
    visible, hidden = filter_visible_buildings(buildings, False, {2})
    assert visible == [buildings[1]]
    assert hidden == 9
