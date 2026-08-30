# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from database.static_cache import static_cache
from services.scripting.auto_econ_service import (
    AutoEconError,
    StopCondition,
    CHAIN_RESOURCES,
    FOCUS_OPTIONS,
    compute_resource_allocation,
    resolve_chain_buildings,
    resolve_single_building,
    generate_auto_econ_script,
    pick_best_world_per_resource,
    resolve_worlds_by_resource,
    save_auto_econ_script,
    is_auto_econ_name,
    script_name_for_faction,
    STOP_KIND_BUILDING_COUNT,
    STOP_KIND_RESOURCE_CAPACITY,
    STOP_KIND_DATE,
)
from services.scripting.parser import parse
from services.scripting.type_checker import check as type_check


@pytest.fixture(autouse=True)
def seeded_static_cache():
    static_cache.buildings = {
        1: {'id': 1, 'name': 'City'},
        2: {'id': 2, 'name': 'CM Refinery'},
        3: {'id': 3, 'name': 'EL Refinery'},
        4: {'id': 4, 'name': 'Factory'},
        5: {'id': 5, 'name': 'CM Extractor'},
        6: {'id': 6, 'name': 'EL Extractor'},
        7: {'id': 7, 'name': 'CS Refinery'},
        8: {'id': 8, 'name': 'CS Extractor'},
        9: {'id': 9, 'name': 'CM Storage'},
        10: {'id': 10, 'name': 'EL Storage'},
        11: {'id': 11, 'name': 'CS Storage'},
    }
    static_cache.buildings_by_name = {v['name'].lower(): v for v in static_cache.buildings.values()}
    static_cache.buildings_generators = [
        {'building_id': 2, 'resource_id': 10, 'is_refinery': True},
        {'building_id': 3, 'resource_id': 11, 'is_refinery': True},
        {'building_id': 5, 'resource_id': 10, 'is_refinery': False},
        {'building_id': 6, 'resource_id': 11, 'is_refinery': False},
        {'building_id': 7, 'resource_id': 12, 'is_refinery': True},
        {'building_id': 8, 'resource_id': 12, 'is_refinery': False},
    ]
    static_cache.buildings_storages = [
        {'building_id': 9, 'resource_id': 10},
        {'building_id': 10, 'resource_id': 11},
        {'building_id': 11, 'resource_id': 12},
    ]
    static_cache.resources = {
        'cm': {'id': 10, 'name': 'CM'},
        'el': {'id': 11, 'name': 'EL'},
        'cs': {'id': 12, 'name': 'CS'},
    }
    static_cache.resources_by_id = {
        10: {'id': 10, 'name': 'CM'},
        11: {'id': 11, 'name': 'EL'},
        12: {'id': 12, 'name': 'CS'},
    }
    yield


def _stop_all_three():
    return [
        StopCondition(kind=STOP_KIND_BUILDING_COUNT, threshold=20),
        StopCondition(kind=STOP_KIND_RESOURCE_CAPACITY, resource='CM', threshold=500_000_000),
        StopCondition(kind=STOP_KIND_DATE, day='SUNDAY', threshold=0),
    ]


def _worlds_all_at(world_name="Sol"):
    return {r: world_name for r in CHAIN_RESOURCES}


def test_balanced_allocation_splits_evenly():
    allocation = compute_resource_allocation("BALANCED", 100)
    assert set(allocation.keys()) == set(CHAIN_RESOURCES)
    assert sum(allocation.values()) == 100
    values = list(allocation.values())
    assert max(values) - min(values) <= 1


@pytest.mark.parametrize("focus,focus_pct", [("CM", 70), ("EL", 60), ("CS", 100)])
def test_focus_allocation_weights_focus_resource_more_heavily(focus, focus_pct):
    allocation = compute_resource_allocation(focus, focus_pct)
    assert allocation[focus] == focus_pct
    others = [r for r in CHAIN_RESOURCES if r != focus]
    for r in others:
        assert allocation[r] < allocation[focus]
    assert sum(allocation.values()) == 100


def test_factories_and_cities_return_empty_allocation():
    assert compute_resource_allocation("FACTORIES", 100) == {}
    assert compute_resource_allocation("CITIES", 100) == {}


def test_focus_pct_out_of_range_raises():
    with pytest.raises(AutoEconError):
        compute_resource_allocation("CM", 10)
    with pytest.raises(AutoEconError):
        compute_resource_allocation("CM", 101)


@pytest.mark.parametrize("resource,extractor_id,refinery_id,storage_id", [
    ("CM", 5, 2, 9),
    ("EL", 6, 3, 10),
    ("CS", 8, 7, 11),
])
def test_resolve_chain_buildings_returns_full_chain(resource, extractor_id, refinery_id, storage_id):
    chain = resolve_chain_buildings(resource)
    assert chain["extractor"]["id"] == extractor_id
    assert chain["refinery"]["id"] == refinery_id
    assert chain["storage"]["id"] == storage_id


def test_resolve_chain_buildings_missing_storage_raises():
    static_cache.buildings_storages = []
    with pytest.raises(AutoEconError):
        resolve_chain_buildings("CM")


@pytest.mark.parametrize("focus,expected_building_id", [
    ("CITIES", 1),
])
def test_single_building_resolves_to_expected_building(focus, expected_building_id):
    building = resolve_single_building(focus)
    assert building["id"] == expected_building_id


def test_factories_focus_excludes_refineries():
    building = resolve_single_building("FACTORIES")
    assert building["id"] == 4


def test_unknown_focus_raises():
    with pytest.raises(AutoEconError):
        resolve_single_building("NOT_A_FOCUS")


def test_balanced_mode_generates_script_touching_all_three_resources():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="BALANCED",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=_stop_all_three(),
    )
    for building_id in (5, 2, 9, 6, 3, 10, 8, 7, 11):
        assert f"BUY BUILDING {building_id} " in script
    ast = parse(script)
    tc = type_check(ast)
    assert tc.ok, tc.errors


def test_focus_ratio_develops_only_positively_allocated_resources():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=_stop_all_three(),
    )
    assert "BUY BUILDING 5 " in script
    assert "BUY BUILDING 2 " in script
    assert "BUY BUILDING 9 " in script
    assert "BUY BUILDING 6 " not in script
    assert "BUY BUILDING 8 " not in script
    ast = parse(script)
    assert type_check(ast).ok


@pytest.mark.parametrize("focus,focus_pct", [
    ("CM", 40), ("CM", 70), ("CM", 100),
    ("EL", 40), ("EL", 100),
    ("CS", 40), ("CS", 100),
    ("BALANCED", 100),
    ("FACTORIES", 100),
    ("CITIES", 100),
])
@pytest.mark.parametrize("budget_pct", [1, 50, 100])
def test_generated_script_always_parses_and_type_checks(focus, focus_pct, budget_pct):
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus=focus,
        focus_pct=focus_pct,
        budget_pct=budget_pct,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=_stop_all_three(),
    )
    ast = parse(script)
    tc = type_check(ast)
    assert tc.ok, tc.errors


def test_chain_includes_extractor_refinery_and_storage_per_resource():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="BALANCED",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=_stop_all_three(),
    )
    assert "BUY BUILDING 5 " in script
    assert "BUY BUILDING 2 " in script
    assert "BUY BUILDING 9 " in script


def test_budget_fraction_reflected_as_reserved_floor():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="CM",
        focus_pct=100,
        budget_pct=30,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=_stop_all_three(),
    )
    assert "SET floor = CM * 70 / 100" in script
    assert "IF CM > floor:" in script


def test_budget_floor_guarantee_holds_with_multiple_chains():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="BALANCED",
        focus_pct=100,
        budget_pct=20,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=_stop_all_three(),
    )
    assert "SET floor = CM * 80 / 100" in script
    buy_lines = [line for line in script.splitlines() if "BUY BUILDING" in line]
    assert len(buy_lines) > 1
    guard_lines = [line for line in script.splitlines() if "IF CM > floor:" in line]
    assert len(guard_lines) == len(buy_lines)


def test_budget_out_of_range_raises():
    with pytest.raises(AutoEconError):
        generate_auto_econ_script(
            faction_name="Athena",
            focus="CM",
            focus_pct=100,
            budget_pct=0,
            worlds_by_resource=_worlds_all_at("Sol"),
            stop_conditions=_stop_all_three(),
        )
    with pytest.raises(AutoEconError):
        generate_auto_econ_script(
            faction_name="Athena",
            focus="CM",
            focus_pct=100,
            budget_pct=101,
            worlds_by_resource=_worlds_all_at("Sol"),
            stop_conditions=_stop_all_three(),
        )


def test_building_count_stop_condition_generates_correct_fal():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=[StopCondition(kind=STOP_KIND_BUILDING_COUNT, threshold=15)],
    )
    assert "AT Sol >= 15:" in script
    assert "    STOP" in script
    ast = parse(script)
    assert type_check(ast).ok


def test_resource_capacity_stop_condition_generates_correct_fal():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=[StopCondition(kind=STOP_KIND_RESOURCE_CAPACITY, resource="CM", threshold=1_000_000)],
    )
    assert "IF CM >= 1000000:" in script
    assert "    STOP" in script
    ast = parse(script)
    assert type_check(ast).ok


def test_date_stop_condition_generates_correct_fal():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Sol"),
        stop_conditions=[StopCondition(kind=STOP_KIND_DATE, day="FRIDAY", threshold=0)],
    )
    assert "IF TODAY IS FRIDAY:" in script
    assert "    STOP" in script
    ast = parse(script)
    assert type_check(ast).ok


def test_date_stop_condition_requires_day():
    with pytest.raises(AutoEconError):
        StopCondition(kind=STOP_KIND_DATE, threshold=0)


def test_resource_capacity_stop_condition_requires_resource():
    with pytest.raises(AutoEconError):
        StopCondition(kind=STOP_KIND_RESOURCE_CAPACITY, threshold=100)


def test_script_name_uses_recognisable_prefix():
    name = script_name_for_faction("Athena")
    assert is_auto_econ_name(name)
    assert "Athena" in name


def test_unresolvable_chain_building_raises_before_storing():
    static_cache.buildings_generators = []
    with pytest.raises(AutoEconError):
        generate_auto_econ_script(
            faction_name="Athena",
            focus="CM",
            focus_pct=100,
            budget_pct=50,
            worlds_by_resource=_worlds_all_at("Sol"),
            stop_conditions=_stop_all_three(),
        )


def test_multi_word_world_names_are_quoted():
    script = generate_auto_econ_script(
        faction_name="Athena",
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        worlds_by_resource=_worlds_all_at("Deo Gloria"),
        stop_conditions=_stop_all_three(),
    )
    assert '"Deo Gloria"' in script
    ast = parse(script)
    assert type_check(ast).ok


async def test_pick_best_world_per_resource_picks_highest_percentage(fake_db):
    fake_db.fetch_queue.append([
        {"world_id": 1, "world_name": "Sol", "resource_name": "CM", "percentage": 80},
        {"world_id": 2, "world_name": "Ceres", "resource_name": "CM", "percentage": 40},
        {"world_id": 1, "world_name": "Sol", "resource_name": "EL", "percentage": 20},
        {"world_id": 2, "world_name": "Ceres", "resource_name": "EL", "percentage": 90},
        {"world_id": 1, "world_name": "Sol", "resource_name": "CS", "percentage": 50},
    ])

    best = await pick_best_world_per_resource(faction_id=1, resources=["CM", "EL", "CS"])

    assert best["CM"]["world_name"] == "Sol"
    assert best["EL"]["world_name"] == "Ceres"
    assert best["CS"]["world_name"] == "Sol"


async def test_pick_best_world_per_resource_raises_when_no_world_has_data(fake_db):
    fake_db.fetch_queue.append([])
    with pytest.raises(AutoEconError):
        await pick_best_world_per_resource(faction_id=1, resources=["CM"])


async def test_resolve_worlds_by_resource_uses_pinned_world_when_given(fake_db):
    worlds = await resolve_worlds_by_resource(faction_id=1, focus="BALANCED", pinned_world_name="Sol")
    assert all(w == "Sol" for w in worlds.values())


async def test_resolve_worlds_by_resource_auto_picks_when_world_omitted(fake_db):
    fake_db.fetch_queue.append([
        {"world_id": 1, "world_name": "Sol", "resource_name": "CM", "percentage": 90},
        {"world_id": 2, "world_name": "Ceres", "resource_name": "EL", "percentage": 70},
        {"world_id": 2, "world_name": "Ceres", "resource_name": "CS", "percentage": 60},
    ])
    worlds = await resolve_worlds_by_resource(faction_id=1, focus="BALANCED", pinned_world_name=None)
    assert worlds["CM"] == "Sol"
    assert worlds["EL"] == "Ceres"
    assert worlds["CS"] == "Ceres"


async def test_save_creates_new_script_when_none_exists(fake_db, monkeypatch):
    import services.scripting.script_service as script_service

    async def fake_get_active_scripts(faction_id):
        return []

    async def fake_get_script_by_name(faction_id, name):
        return None

    created = {}

    async def fake_create_script(faction_id, name, script_text, trigger_day, created_by, trigger_type=None, is_auto_econ=False):
        created.update(dict(
            faction_id=faction_id, name=name, script_text=script_text,
            trigger_day=trigger_day, created_by=created_by, is_auto_econ=is_auto_econ,
        ))
        return {"id": 99, "name": name}

    monkeypatch.setattr(script_service, "get_active_scripts", fake_get_active_scripts)
    monkeypatch.setattr(script_service, "get_script_by_name", fake_get_script_by_name)
    monkeypatch.setattr(script_service, "create_script", fake_create_script)

    row = await save_auto_econ_script(
        faction_id=1,
        faction_name="Athena",
        created_by=42,
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        world_name="Sol",
        stop_conditions=_stop_all_three(),
    )

    assert row["id"] == 99
    assert created["is_auto_econ"] is True
    assert is_auto_econ_name(created["name"])


async def test_save_overwrites_existing_auto_econ_script(fake_db, monkeypatch):
    import services.scripting.script_service as script_service
    from repositories import script_repo
    from dtos.script import Script

    existing = Script(
        id=7, name="auto-econ: Athena", script_text="OLD", trigger_day=None,
        trigger_type=None, created_at=None, updated_at=None, last_run_at=None,
        run_count=1, is_active=True, created_by=1, faction_id=1, is_company=False,
        is_auto_econ=True,
    )

    async def fake_get_active_scripts(faction_id):
        return [existing]

    updated = {}

    async def fake_update_auto_econ_script(script_id, faction_id, script_text, trigger_day):
        updated.update(dict(
            script_id=script_id, faction_id=faction_id,
            script_text=script_text, trigger_day=trigger_day,
        ))
        return existing

    async def fail_create_script(*args, **kwargs):
        raise AssertionError("create_script should not be called when an auto econ script already exists")

    monkeypatch.setattr(script_service, "get_active_scripts", fake_get_active_scripts)
    monkeypatch.setattr(script_repo, "update_auto_econ_script", fake_update_auto_econ_script)
    monkeypatch.setattr(script_service, "create_script", fail_create_script)

    row = await save_auto_econ_script(
        faction_id=1,
        faction_name="Athena",
        created_by=42,
        focus="EL",
        focus_pct=60,
        budget_pct=25,
        world_name="Sol",
        stop_conditions=_stop_all_three(),
    )

    assert updated["script_id"] == 7
    assert "BUY BUILDING 3 " in updated["script_text"]
    assert row is existing


async def test_save_never_overwrites_hand_written_script_with_different_name(fake_db, monkeypatch):
    import services.scripting.script_service as script_service

    async def fake_get_active_scripts(faction_id):
        return []

    async def fake_get_script_by_name(faction_id, name):
        return None

    created = {}

    async def fake_create_script(faction_id, name, script_text, trigger_day, created_by, trigger_type=None, is_auto_econ=False):
        created["name"] = name
        return {"id": 1, "name": name}

    monkeypatch.setattr(script_service, "get_active_scripts", fake_get_active_scripts)
    monkeypatch.setattr(script_service, "get_script_by_name", fake_get_script_by_name)
    monkeypatch.setattr(script_service, "create_script", fake_create_script)

    await save_auto_econ_script(
        faction_id=1,
        faction_name="Athena",
        created_by=42,
        focus="CM",
        focus_pct=100,
        budget_pct=50,
        world_name="Sol",
        stop_conditions=_stop_all_three(),
    )

    assert created["name"] == "auto-econ: Athena"
