# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from dtos.building import Building
from repositories import building_repo
from services import spend_service
from services.building_efficiency_service import (
    get_faction_building_count_unweighted,
    get_faction_building_count_actual,
    calculate_building_cap,
    get_faction_total_hexes,
)


MEGA_FACTORY_NAME = 'Mega Factory'


def is_mega_factory(building_id: int) -> bool:
    from database.static_cache import static_cache
    building = static_cache.get_building(MEGA_FACTORY_NAME)
    return bool(building) and building['id'] == building_id


MEGA_FACTORY_SCALE_RATE = 0.075


def _calculate_mega_factory_cost(base_costs: dict, current_count: int, amount: int, level: int) -> dict:
    upgrade_factor = 0.1
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        cost = 0
        for i in range(amount):
            scale = (1 + MEGA_FACTORY_SCALE_RATE) ** (current_count + i)
            cost += base * scale + base * sum_n(level - 1) * upgrade_factor
        total[resource] = int(cost)
    return total


def _calculate_building_cost(base_costs: dict, current_actual: int, amount: int, level: int, building_id: int) -> dict:
    scarcity_rate = 0.02
    upgrade_factor = 1.0
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        cost = 0
        for i in range(amount):
            idx = current_actual + i
            cost += base * (1 + scarcity_rate * idx) + base * sum_n(level - 1) * upgrade_factor
        total[resource] = int(cost)
    return total


def _calculate_refund(base_costs: dict, scaling_count: int, amount: int, level: int, week: bool, building_id: int) -> dict:
    refund_rate = 1.0 if week else 0.3
    scarcity_rate = 0.02
    upgrade_factor = 1.0
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        refund = 0
        for i in range(amount):
            idx = max(0, scaling_count - 1 - i)
            refund += (base * (1 + scarcity_rate * idx) + base * sum_n(level - 1) * upgrade_factor) * refund_rate
        total[resource] = int(refund)
    return total


def calculate_upgrade_cost(base_costs: dict, building_id: int, amount: int, source_level: int, target_level: int) -> dict:
    sum_n = lambda n: n * (n + 1) // 2
    upgrade_factor = 0.1 if is_mega_factory(building_id) else 1.0
    multiplier = sum_n(target_level - 1) - sum_n(source_level - 1)
    return {name: int(base * multiplier * upgrade_factor * amount) for name, base in base_costs.items()}


def check_building_cap(current_weighted: int, delta: int, building_cap: int) -> None:
    if current_weighted + delta > building_cap:
        raise ValueError(f"Building cap exceeded. Cap: {building_cap:,}, Current: {current_weighted:,}, Adding: {delta:,}")


def _calculate_mega_factory_refund(base_costs: dict, current_count: int, amount: int, level: int, week: bool) -> dict:
    refund_rate = 1.0 if week else 0.3
    upgrade_factor = 0.1
    sum_n = lambda n: n * (n + 1) // 2
    total = {}
    for resource, base in base_costs.items():
        refund = 0
        for i in range(amount):
            scale = (1 + MEGA_FACTORY_SCALE_RATE) ** (current_count - 1 - i)
            refund += (base * scale + base * sum_n(level - 1) * upgrade_factor) * refund_rate
        total[resource] = int(refund)
    return total


async def get_building(building_id: int) -> Optional[Building]:
    return await building_repo.get_building(building_id)


async def get_building_by_name(building_name: str) -> Optional[Building]:
    return await building_repo.get_building_by_name(building_name)


async def search_building_names(current: str, limit: int = 25) -> list[Building]:
    return await building_repo.search_building_names(current, limit)


async def resolve_building(identifier: str) -> Optional[Building]:
    if identifier is None:
        return None

    text = identifier.strip()
    if not text:
        return None

    if text.lower().startswith("building:"):
        text = text[len("building:"):].strip()

    if text.isdigit():
        found = await get_building(int(text))
        if found:
            return found

    found = await get_building_by_name(text)
    if found:
        return found

    matches = await building_repo.find_buildings_matching(text)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        candidates = ", ".join(f"{m.name} (ID: {m.id})" for m in matches[:8])
        more = f" and {len(matches) - 8} more" if len(matches) > 8 else ""
        raise ValueError(f"'{identifier}' matches several buildings: {candidates}{more}. Be more specific or use the building ID.")

    return None


async def get_buildings_catalog() -> list:
    return await building_repo.get_buildings_catalog()


async def get_all_building_cost_rows() -> list:
    return await building_repo.get_all_building_cost_rows()


async def get_faction_building_ids_at_level(faction_id: int, level: int) -> set:
    return await building_repo.get_faction_building_ids_at_level(faction_id, level)


async def get_building_ids_supporting_level(level: int) -> set:
    return await building_repo.get_building_ids_supporting_level(level)


async def get_faction_mega_factory_count(faction_id: int) -> int:
    return await building_repo.get_faction_mega_factory_count(faction_id)


async def get_building_base_costs(building_id: int) -> dict:
    return await building_repo.get_building_base_costs(building_id)


async def get_company_er(faction_id: int) -> int:
    return await building_repo.get_company_er(faction_id)


def _company_building_cap(er: int) -> int:
    if er >= 10_000_000_000_000:
        return 600
    elif er >= 5_000_000_000_000:
        return 500
    elif er >= 1_000_000_000_000:
        return 300
    elif er >= 500_000_000_000:
        return 200
    return 100


async def buy_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int, is_company: bool) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    if is_company and building.name.lower() == 'city':
        raise ValueError("Companies cannot build cities.")
    if is_company:
        await building_repo.ensure_world_presence(world_id, faction_id)
    else:
        if not await building_repo.faction_has_presence(world_id, faction_id):
            raise ValueError("Faction has no presence on this world.")
    base_costs = await get_building_base_costs(building_id)
    current_weighted = await get_faction_building_count_unweighted(faction_id)
    if is_company:
        er = await get_company_er(faction_id)
        building_cap = _company_building_cap(er)
    else:
        building_cap = await calculate_building_cap(faction_id)
    check_building_cap(current_weighted, amount * level, building_cap)
    if is_mega_factory(building_id):
        current_mega = await get_faction_mega_factory_count(faction_id)
        total_costs = _calculate_mega_factory_cost(base_costs, current_mega, amount, level)
    else:
        current_actual = await get_faction_building_count_actual(faction_id)
        scaling_count = max(0, current_actual - 27)
        total_costs = _calculate_building_cost(base_costs, scaling_count, amount, level, building_id)
    try:
        await building_repo.buy_building(faction_id, world_id, building_id, amount, level, total_costs)
    except Exception as e:
        raise ValueError(str(e)) from e
    await spend_service.record_spend(faction_id, total_costs, spend_service.SPEND)
    return {'building_name': building.name, 'costs': total_costs}


async def destroy_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    try:
        await building_repo.destroy_building(faction_id, world_id, building_id, amount, level)
    except Exception as e:
        raise ValueError(str(e)) from e
    return {'building_name': building.name}


async def transfer_building(from_faction_id: int, to_faction_id: int, world_id: int, building_id: int, amount: int, level: int) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    if not await building_repo.faction_has_presence(world_id, to_faction_id):
        raise ValueError("Destination faction has no presence on this world.")
    current = await get_faction_building_count_unweighted(to_faction_id)
    building_cap = await calculate_building_cap(to_faction_id)
    new_total = current + (amount * level)
    if new_total > building_cap:
        raise ValueError(f"Building cap exceeded. Cap: {building_cap:,}, Current: {current:,}, Adding: {amount * level:,}")
    try:
        await building_repo.transfer_building(from_faction_id, to_faction_id, world_id, building_id, amount, level)
    except Exception as e:
        raise ValueError(str(e)) from e
    return {'building_name': building.name}


async def refund_building(faction_id: int, world_id: int, building_id: int, amount: int, level: int, week: bool) -> dict:
    building = await get_building(building_id)
    if not building:
        raise ValueError("Building not found.")
    base_costs = await get_building_base_costs(building_id)
    if is_mega_factory(building_id):
        current_mega = await get_faction_mega_factory_count(faction_id)
        refunds = _calculate_mega_factory_refund(base_costs, current_mega, amount, level, week)
    else:
        current_actual = await get_faction_building_count_actual(faction_id)
        scaling_count = max(0, current_actual - 27)
        refunds = _calculate_refund(base_costs, scaling_count, amount, level, week, building_id)
    try:
        await building_repo.refund_building(faction_id, world_id, building_id, amount, level, refunds)
    except Exception as e:
        raise ValueError(str(e)) from e
    await spend_service.record_spend(faction_id, refunds, spend_service.REFUND)
    return {'building_name': building.name, 'refunds': refunds}


async def get_building_cap_info(faction_id: int, is_company: bool) -> dict:
    building_count = await get_faction_building_count_unweighted(faction_id)
    total_hexes = await get_faction_total_hexes(faction_id)
    if is_company:
        er = await get_company_er(faction_id)
        building_cap = _company_building_cap(er)
        return {'building_count': building_count, 'building_cap': building_cap, 'total_hexes': total_hexes, 'er': er, 'is_company': True}
    building_cap = await calculate_building_cap(faction_id)
    return {'building_count': building_count, 'building_cap': building_cap, 'total_hexes': total_hexes, 'is_company': False}


async def list_faction_buildings(
    faction_id: int,
    world_id: Optional[int] = None,
    building_id: Optional[int] = None,
) -> list[dict]:
    return await building_repo.list_faction_buildings(faction_id, world_id, building_id)
