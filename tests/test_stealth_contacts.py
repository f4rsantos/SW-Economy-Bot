# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
from types import SimpleNamespace

from services.intelligence_service import (
    build_contact_labels,
    get_stealth_fleet_map,
    is_masked_contact,
)


def _row(fleet_id, amount, stealth):
    return {
        "fleet_id": fleet_id,
        "amount": amount,
        "vehicle_data": json.dumps({"stealth": stealth}),
    }


def _unit(fleet_id, faction_id, status="idle"):
    return SimpleNamespace(id=fleet_id, faction_id=faction_id, status=status)


async def test_stealth_map_marks_only_fully_stealth_fleets(fake_db):
    fake_db.fetch_queue.append([
        _row(1, 3, True),
        _row(1, 2, True),
        _row(2, 4, True),
        _row(2, 1, False),
        _row(3, 5, False),
    ])
    result = await get_stealth_fleet_map([1, 2, 3])
    assert result == {1: 5}


async def test_stealth_map_accepts_string_stealth_values(fake_db):
    fake_db.fetch_queue.append([_row(9, 2, "yes"), _row(9, 1, "low")])
    assert await get_stealth_fleet_map([9]) == {9: 3}


async def test_stealth_map_ignores_zero_ship_fleets(fake_db):
    fake_db.fetch_queue.append([_row(4, 0, True)])
    assert await get_stealth_fleet_map([4]) == {}


async def test_stealth_map_short_circuits_without_ids(fake_db):
    assert await get_stealth_fleet_map([]) == {}
    assert fake_db.executed == []


def test_own_fleets_are_never_masked():
    assert is_masked_contact(True, "idle", 1, {1: 4}) is False


def test_fleets_in_battle_are_revealed():
    assert is_masked_contact(False, "in combat", 1, {1: 4}) is False
    assert is_masked_contact(False, "blockading", 1, {1: 4}) is False
    assert is_masked_contact(False, "idle", 1, {1: 4}) is True


def test_non_stealth_fleets_are_not_masked():
    assert is_masked_contact(False, "idle", 2, {1: 4}) is False


def test_contact_labels_are_sequential_and_skip_visible_units():
    units = [
        _unit(10, 1),
        _unit(11, 2),
        _unit(12, 2),
        _unit(13, 2, status="in combat"),
    ]
    stealth_map = {10: 1, 11: 2, 12: 3, 13: 4}
    labels = build_contact_labels(units, stealth_map, viewer_faction_id=1)
    assert labels == {11: "Contact 1", 12: "Contact 2"}


def test_ref_mode_reveals_every_unit():
    units = [_unit(11, 2), _unit(12, 2)]
    labels = build_contact_labels(units, {11: 1, 12: 1}, viewer_faction_id=1, ref_mode=True)
    assert labels == {}
