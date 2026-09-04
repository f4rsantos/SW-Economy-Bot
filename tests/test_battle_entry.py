# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
from types import SimpleNamespace

import pytest

from services import battle_service
from services.battle_service import next_side_letter, sides_of


def test_first_side_is_a():
    assert next_side_letter([]) == "A"


def test_next_side_skips_taken_letters():
    assert next_side_letter(["A"]) == "B"
    assert next_side_letter(["A", "B"]) == "C"


def test_next_side_ignores_case_and_order():
    assert next_side_letter(["b", "a"]) == "C"


def test_next_side_fills_gaps():
    assert next_side_letter(["B"]) == "A"


def test_next_side_exhausted_raises():
    with pytest.raises(ValueError):
        next_side_letter(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


def test_sides_of_parses_json_string():
    battle = SimpleNamespace(sides=json.dumps([{"side": "A"}, {"side": "B"}, {"side": "A"}]))
    assert sides_of(battle) == ["A", "B"]


def test_sides_of_handles_list_and_empty():
    assert sides_of(SimpleNamespace(sides=[{"side": "A"}])) == ["A"]
    assert sides_of(SimpleNamespace(sides=None)) == []
    assert sides_of(SimpleNamespace(sides="not json")) == []


async def test_enter_battle_creates_war_and_battle_with_side_a(monkeypatch):
    calls = {}

    async def fake_create_war(world_name, faction_id, side):
        calls['war'] = (world_name, faction_id, side)
        return 11

    async def fake_start(war_id, fleet_id, side, world_id):
        calls['start'] = (war_id, fleet_id, side, world_id)
        return 22

    async def fake_stats(battle_id):
        calls['stats'] = battle_id
        return []

    monkeypatch.setattr(battle_service, "create_standalone_war", fake_create_war)
    monkeypatch.setattr(battle_service, "start_battle", fake_start)
    monkeypatch.setattr(battle_service.battle_repo, "get_battle_stats", fake_stats)

    result = await battle_service.enter_battle(5, 4, 9, "Terra")

    assert calls['war'] == ("Terra", 4, "A")
    assert calls['start'] == (11, 5, "A", 9)
    assert result['created'] is True
    assert result['battle_id'] == 22
    assert result['war_id'] == 11
    assert result['side'] == "A"


async def test_enter_battle_joins_existing_battle(monkeypatch):
    calls = {}

    async def fake_join(battle_id, fleet_id, side):
        calls['join'] = (battle_id, fleet_id, side)
        return {'stats': []}

    async def fake_get_battle(_battle_id):
        return SimpleNamespace(war_id=77)

    monkeypatch.setattr(battle_service, "join_battle", fake_join)
    monkeypatch.setattr(battle_service.battle_repo, "get_battle", fake_get_battle)

    result = await battle_service.enter_battle(5, 4, 9, "Terra", battle_id=33, side="B")

    assert calls['join'] == (33, 5, "B")
    assert result['created'] is False
    assert result['battle_id'] == 33
    assert result['war_id'] == 77
    assert result['side'] == "B"


async def test_enter_existing_battle_requires_side():
    with pytest.raises(ValueError):
        await battle_service.enter_battle(5, 4, 9, "Terra", battle_id=33)
