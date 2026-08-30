# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from database.static_cache import static_cache
from services.scripting.parser import parse
from services.scripting.type_checker import check as type_check
from services.scripting.errors import FALSyntaxError

CHAIN_RESOURCES = ("CM", "EL", "CS")
FOCUS_OPTIONS = ("CM", "EL", "CS", "FACTORIES", "CITIES", "BALANCED")

MIN_FOCUS_PCT = 40
MAX_FOCUS_PCT = 100

STOP_KIND_BUILDING_COUNT = "building_count"
STOP_KIND_RESOURCE_CAPACITY = "resource_capacity"
STOP_KIND_DATE = "date"
STOP_KINDS = (STOP_KIND_BUILDING_COUNT, STOP_KIND_RESOURCE_CAPACITY, STOP_KIND_DATE)

AUTO_ECON_NAME_PREFIX = "auto-econ: "

MAX_BUDGET_PCT = 100
MIN_BUDGET_PCT = 1

BUY_LEVEL = 1
BUY_BATCHES_PER_RUN = 5

EXTRACTOR_BATCH = 3
REFINERY_BATCH = 3
STORAGE_BATCH = 1


class AutoEconError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StopCondition:
    kind: str
    threshold: int
    building_ref: Optional[int] = None
    resource: Optional[str] = None
    day: Optional[str] = None

    def __post_init__(self):
        if self.kind not in STOP_KINDS:
            raise AutoEconError(f"Unknown stop condition kind '{self.kind}'")
        if self.kind == STOP_KIND_DATE and not self.day:
            raise AutoEconError("Date stop condition requires a day")
        if self.kind == STOP_KIND_RESOURCE_CAPACITY and not self.resource:
            raise AutoEconError("Resource capacity stop condition requires a resource")


def script_name_for_faction(faction_name: str) -> str:
    return f"{AUTO_ECON_NAME_PREFIX}{faction_name}"


def is_auto_econ_name(name: str) -> bool:
    return name.lower().startswith(AUTO_ECON_NAME_PREFIX.lower())


def compute_resource_allocation(focus: str, focus_pct: int) -> dict:
    """Turn a focus keyword plus a focus_pct into a percentage allocation across CM/EL/CS.

    BALANCED always splits the three resources evenly regardless of focus_pct. Otherwise the
    named resource gets focus_pct percent and the remaining percentage is split evenly across
    the other two resources of the CM/EL/CS chain. FACTORIES and CITIES do not develop the
    CM/EL/CS chain at all, so they return an empty allocation; they are handled as a single
    building type elsewhere.
    """
    focus = focus.upper()

    if focus == "BALANCED":
        base = 100 // len(CHAIN_RESOURCES)
        remainder = 100 - base * len(CHAIN_RESOURCES)
        allocation = {r: base for r in CHAIN_RESOURCES}
        for r in CHAIN_RESOURCES[:remainder]:
            allocation[r] += 1
        return allocation

    if focus not in CHAIN_RESOURCES:
        return {}

    if not (MIN_FOCUS_PCT <= focus_pct <= MAX_FOCUS_PCT):
        raise AutoEconError(f"focus_pct must be between {MIN_FOCUS_PCT} and {MAX_FOCUS_PCT}")

    others = [r for r in CHAIN_RESOURCES if r != focus]
    remaining_pct = 100 - focus_pct
    base = remaining_pct // len(others)
    remainder = remaining_pct - base * len(others)

    allocation = {focus: focus_pct}
    for i, r in enumerate(others):
        allocation[r] = base + (1 if i < remainder else 0)
    return allocation


def resolve_chain_buildings(resource: str) -> dict:
    """Resolve a CM/EL/CS resource to its extractor, refinery, and storage buildings.

    Reads buildings_generators (extractor when is_refinery is False, refinery when True) and
    buildings_storages, both keyed by resource_id, per the static cache loaded from the
    buildings_generators / buildings_storages tables (see repositories/building_repo.py
    TYPE_EXPRESSION for the same classification used to report faction building stats).
    """
    resource_data = static_cache.get_resource(resource)
    if not resource_data:
        raise AutoEconError(f"Unknown resource '{resource}'")
    resource_id = resource_data["id"]

    extractor = None
    refinery = None
    for gen in static_cache.buildings_generators:
        if gen["resource_id"] != resource_id:
            continue
        building = static_cache.get_building_by_id(gen["building_id"])
        if not building:
            continue
        if gen["is_refinery"]:
            refinery = building
        else:
            extractor = building

    storage = None
    for st in static_cache.buildings_storages:
        if st["resource_id"] != resource_id:
            continue
        building = static_cache.get_building_by_id(st["building_id"])
        if building:
            storage = building
            break

    if not extractor:
        raise AutoEconError(f"No extractor building found for resource '{resource}'")
    if not refinery:
        raise AutoEconError(f"No refinery building found for resource '{resource}'")
    if not storage:
        raise AutoEconError(f"No storage building found for resource '{resource}'")

    return {"extractor": extractor, "refinery": refinery, "storage": storage}


def resolve_single_building(focus: str) -> dict:
    """Resolve FACTORIES or CITIES to the single building type they build."""
    focus = focus.upper()

    if focus == "FACTORIES":
        refinery_ids = {g["building_id"] for g in static_cache.buildings_generators if g["is_refinery"]}
        for building in static_cache.buildings.values():
            name = building["name"]
            if "factory" not in name.lower():
                continue
            if building["id"] in refinery_ids:
                continue
            return building
        raise AutoEconError("No factory building found in the buildings catalog")

    if focus == "CITIES":
        building = static_cache.get_building("city")
        if not building:
            raise AutoEconError("No City building found in the buildings catalog")
        return building

    raise AutoEconError(f"Unknown focus '{focus}'. Must be one of {FOCUS_OPTIONS}")


async def pick_best_world_per_resource(faction_id: int, resources: list) -> dict:
    """Pick, for each requested resource, the faction-held world with the highest world_resources
    percentage for that resource. Generation-time selection (rather than a runtime FAL primitive)
    was chosen because FAL has no construct to rank or compare worlds at execution time (see
    SCRIPTING.md World Name Reference and Expressions sections); the generator queries the
    faction's worlds now and bakes concrete world names into the emitted script.

    Raises AutoEconError if the faction holds no world with any percentage for a resource.
    """
    from repositories import building_repo

    rows = await building_repo.get_faction_worlds_with_resource_percentages(faction_id)

    best: dict = {}
    for row in rows:
        resource_name = row["resource_name"]
        if resource_name not in resources:
            continue
        pct = row["percentage"] or 0
        current = best.get(resource_name)
        if current is None or pct > current["percentage"]:
            best[resource_name] = {
                "world_id": row["world_id"],
                "world_name": row["world_name"],
                "percentage": pct,
            }

    missing = [r for r in resources if r not in best]
    if missing:
        raise AutoEconError(
            f"Faction has no world with data for resource(s): {', '.join(missing)}. "
            f"It must hold at least one world to auto pick a build site."
        )

    return best


def _quote_world(world_name: str) -> str:
    return f'"{world_name}"' if " " in world_name else world_name


def _stop_block_lines(stop: StopCondition, primary_building_id: int, primary_world_name: str) -> list[str]:
    if stop.kind == STOP_KIND_BUILDING_COUNT:
        ref = stop.building_ref if stop.building_ref is not None else primary_building_id
        return [
            f"IF BUILDINGS {ref} AT {_quote_world(primary_world_name)} >= {stop.threshold}:",
            "    STOP",
        ]
    if stop.kind == STOP_KIND_RESOURCE_CAPACITY:
        return [
            f"IF {stop.resource.upper()} >= {stop.threshold}:",
            "    STOP",
        ]
    if stop.kind == STOP_KIND_DATE:
        return [
            f"IF TODAY IS {stop.day.upper()}:",
            "    STOP",
        ]
    raise AutoEconError(f"Unknown stop condition kind '{stop.kind}'")


def _chain_build_lines(resource: str, world_name: str, buildings: dict) -> list[str]:
    world_ref = _quote_world(world_name)
    lines = [f"# {resource} chain at {world_name}: extractor/refinery {EXTRACTOR_BATCH}:{REFINERY_BATCH}, "
             f"storage {STORAGE_BATCH} per batch so refining capacity tracks extraction and storage "
             f"never becomes the bottleneck"]
    lines.append(f"REPEAT {BUY_BATCHES_PER_RUN} TIMES:")
    lines.append(f"    IF CM > floor:")
    lines.append(f"        BUY BUILDING {buildings['extractor']['id']} {EXTRACTOR_BATCH} AT {world_ref} LEVEL {BUY_LEVEL}")
    lines.append(f"    IF CM > floor:")
    lines.append(f"        BUY BUILDING {buildings['refinery']['id']} {REFINERY_BATCH} AT {world_ref} LEVEL {BUY_LEVEL}")
    lines.append(f"    IF CM > floor:")
    lines.append(f"        BUY BUILDING {buildings['storage']['id']} {STORAGE_BATCH} AT {world_ref} LEVEL {BUY_LEVEL}")
    return lines


def _single_building_lines(building: dict, world_name: str) -> list[str]:
    world_ref = _quote_world(world_name)
    return [
        f"REPEAT {BUY_BATCHES_PER_RUN} TIMES:",
        f"    IF CM > floor:",
        f"        BUY BUILDING {building['id']} 1 AT {world_ref} LEVEL {BUY_LEVEL}",
    ]


def generate_auto_econ_script(
    faction_name: str,
    focus: str,
    focus_pct: int,
    budget_pct: int,
    worlds_by_resource: dict,
    stop_conditions: list[StopCondition],
    trigger_day: Optional[str] = None,
) -> str:
    """Generate a readable FAL script implementing the requested auto econ parameters.

    focus/focus_pct express a ratio, not an all-or-nothing choice: BALANCED splits development
    evenly across CM, EL, and CS; any of CM/EL/CS as focus puts focus_pct percent of development
    into that resource and spreads the rest evenly across the other two. FACTORIES and CITIES
    remain single building focuses, unrelated to the CM/EL/CS ratio.

    For each developed resource, the script builds the full extractor/refinery/storage chain
    (not just one building type) in a repeating 3:3:1 batch, so a faction does not end up with
    extractors and no refining capacity, or vice versa. See resolve_chain_buildings for how each
    building is looked up, and the module docstring-level comment on EXTRACTOR_BATCH etc. for why
    that ratio was chosen from services/income_calculator.py compute_world_production: refinery
    throughput is capped by min(refinery capacity, unrefined supply, storage headroom), so
    extractor and refinery counts are grown in lockstep regardless of their underlying per
    building production constants, while storage only needs to buffer a few cycles rather than
    match the flow rate 1:1.

    worlds_by_resource maps each developed resource name to the world name to build it at,
    already chosen (by the caller, generation time) as the faction's best-percentage world for
    that resource, or supplied directly when the user pinned a specific world.

    Budget semantics: at most budget_pct percent of the faction's current CM treasury is put
    at risk of being spent this run. The script computes a floor equal to the reserved
    (100 - budget_pct) percent of the treasury measured at the start of the run, and only
    buys buildings while the live CM balance remains above that floor. Since buying deducts
    CM immediately, this guarantees the script never spends its way below the reserved floor,
    which is a hard ceiling on how much of the starting treasury the run can spend, regardless
    of how many resource chains or building types are being developed.

    Stop conditions permanently end the script (via STOP) the moment they are met, checked
    before any spending happens this run.

    Raises AutoEconError if the parameters cannot be satisfied (e.g. unresolved building,
    or no eligible world for a resource) or if the generated script fails to parse or type check.
    """
    if not (MIN_BUDGET_PCT <= budget_pct <= MAX_BUDGET_PCT):
        raise AutoEconError(f"Budget must be between {MIN_BUDGET_PCT} and {MAX_BUDGET_PCT} percent")

    focus_upper = focus.upper()
    if focus_upper not in FOCUS_OPTIONS:
        raise AutoEconError(f"Unknown focus '{focus}'. Must be one of {FOCUS_OPTIONS}")

    reserved_pct = 100 - budget_pct

    lines: list[str] = []
    lines.append(f"START ON {trigger_day.upper()}" if trigger_day else "START ON MONDAY")
    lines.append("")
    lines.append(f"# Generated by /script auto-econ for {faction_name}")
    lines.append(f"# Budget: at most {budget_pct}% of CM treasury spent per run")

    primary_building_id = None
    primary_world_name = None
    build_sections: list[list[str]] = []

    if focus_upper in ("FACTORIES", "CITIES"):
        building = resolve_single_building(focus_upper)
        world_name = next(iter(worlds_by_resource.values()))
        lines.append(f"# Focus: {focus_upper} -> {building['name']} (id {building['id']}) at {world_name}")
        primary_building_id = building["id"]
        primary_world_name = world_name
        build_sections.append(_single_building_lines(building, world_name))
    else:
        allocation = compute_resource_allocation(focus_upper, focus_pct)
        alloc_desc = ", ".join(f"{r} {pct}%" for r, pct in allocation.items())
        lines.append(f"# Focus: {focus_upper} ratio -> {alloc_desc}")
        for resource in CHAIN_RESOURCES:
            if allocation.get(resource, 0) <= 0:
                continue
            world_name = worlds_by_resource.get(resource)
            if not world_name:
                raise AutoEconError(f"No world selected for resource '{resource}'")
            buildings = resolve_chain_buildings(resource)
            lines.append(f"#   {resource}: {allocation[resource]}% at {world_name} "
                          f"(extractor id {buildings['extractor']['id']}, "
                          f"refinery id {buildings['refinery']['id']}, "
                          f"storage id {buildings['storage']['id']})")
            if primary_building_id is None:
                primary_building_id = buildings["extractor"]["id"]
                primary_world_name = world_name
            build_sections.append(_chain_build_lines(resource, world_name, buildings))

    lines.append("")

    for stop in stop_conditions:
        lines.extend(_stop_block_lines(stop, primary_building_id, primary_world_name))
        lines.append("")

    lines.append(f"SET floor = CM * {reserved_pct} / 100")
    lines.append("")

    for i, section in enumerate(build_sections):
        if i > 0:
            lines.append("")
        lines.extend(section)

    script_text = "\n".join(lines).rstrip() + "\n"

    try:
        ast = parse(script_text)
    except FALSyntaxError as e:
        raise AutoEconError(f"Generated script failed to parse: {e}") from e

    tc = type_check(ast)
    if not tc.ok:
        raise AutoEconError(f"Generated script failed type checking: {'; '.join(tc.errors)}")

    return script_text


async def resolve_worlds_by_resource(
    faction_id: int,
    focus: str,
    pinned_world_name: Optional[str],
) -> dict:
    """Work out which world each developed resource should be built at.

    When the caller pinned a world (the world parameter was supplied), that world is used for
    every developed resource, preserving the old "everything built at one world" behaviour.
    Otherwise the faction's held worlds are queried and the highest resource percentage world is
    picked per resource (see pick_best_world_per_resource); FACTORIES/CITIES do not care about
    resource percentages so they just need one world and pick the faction's first available one
    among CM/EL/CS listings, falling back to raising if the faction holds no world at all.
    """
    focus_upper = focus.upper()

    if pinned_world_name:
        if focus_upper in ("FACTORIES", "CITIES"):
            return {"_single": pinned_world_name}
        return {r: pinned_world_name for r in CHAIN_RESOURCES}

    if focus_upper in ("FACTORIES", "CITIES"):
        best = await pick_best_world_per_resource(faction_id, list(CHAIN_RESOURCES))
        any_world = next(iter(best.values()))
        return {"_single": any_world["world_name"]}

    best = await pick_best_world_per_resource(faction_id, list(CHAIN_RESOURCES))
    return {resource: data["world_name"] for resource, data in best.items()}


async def find_existing_auto_econ_script(faction_id: int, faction_name: str):
    """Return the faction's existing auto econ script, if any, identified by the is_auto_econ
    flag (the naming convention is a readable label, not the source of truth)."""
    from services.scripting import script_service

    scripts = await script_service.get_active_scripts(faction_id)
    for s in scripts:
        if s.is_auto_econ:
            return s
    name = script_name_for_faction(faction_name)
    return await script_service.get_script_by_name(faction_id, name)


async def save_auto_econ_script(
    faction_id: int,
    faction_name: str,
    created_by: int,
    focus: str,
    focus_pct: int,
    budget_pct: int,
    stop_conditions: list[StopCondition],
    world_name: Optional[str] = None,
    trigger_day: Optional[str] = None,
):
    """Generate, validate, and store an auto econ script, overwriting the faction's prior
    auto econ script if one exists. Never touches a hand-written script that isn't flagged
    as auto econ; the caller is responsible for confirming overwrite with the user first."""
    from services.scripting import script_service
    from repositories import script_repo

    worlds_by_resource = await resolve_worlds_by_resource(faction_id, focus, world_name)
    if "_single" in worlds_by_resource:
        worlds_by_resource = {r: worlds_by_resource["_single"] for r in CHAIN_RESOURCES}

    script_text = generate_auto_econ_script(
        faction_name=faction_name,
        focus=focus,
        focus_pct=focus_pct,
        budget_pct=budget_pct,
        worlds_by_resource=worlds_by_resource,
        stop_conditions=stop_conditions,
        trigger_day=trigger_day,
    )

    name = script_name_for_faction(faction_name)
    existing = await find_existing_auto_econ_script(faction_id, faction_name)

    if existing:
        row = await script_repo.update_auto_econ_script(
            script_id=existing.id,
            faction_id=faction_id,
            script_text=script_text,
            trigger_day=trigger_day,
        )
        if not row:
            raise AutoEconError("Failed to update the existing auto econ script")
        return row

    row = await script_service.create_script(
        faction_id=faction_id,
        name=name,
        script_text=script_text,
        trigger_day=trigger_day,
        created_by=created_by,
        is_auto_econ=True,
    )
    return row
