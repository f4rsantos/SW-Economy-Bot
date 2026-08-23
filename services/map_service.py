# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from database.static_cache import static_cache
from repositories import map_repo
from dtos.map import FactionLandEntry, WorldFactionPresence
from services.fleet_service import get_ftl_supply_capacity


async def _get_system_root_id(world_id: Optional[int]) -> Optional[int]:
    if world_id is None:
        return None
    row = await map_repo.get_system_root_id(world_id)
    return row['id'] if row else world_id


async def _count_off_capital_system_hexes(faction_id: int, capital_system_id: int) -> int:
    row = await map_repo.count_off_capital_system_hexes(faction_id, capital_system_id)
    return int(row['total']) if row else 0


async def get_world(world_name: str) -> Optional[dict]:
    return await map_repo.get_world(world_name)


async def get_world_by_id(world_id: int) -> Optional[dict]:
    return await map_repo.get_world_by_id(world_id)


async def get_worlds_by_ids(world_ids: list[int]) -> list[dict]:
    if not world_ids:
        return []
    return await map_repo.get_worlds_by_ids(world_ids)


async def search_world_names(current: str, limit: int = 25) -> list[str]:
    return await map_repo.search_world_names(f"%{current.lower()}%", limit)


async def add_world(name: str, orbit_of_id: int, hex_count: int, population_capacity_per_hex: int,
                    background: Optional[str], resource_percentages: dict) -> dict:
    world_id = await map_repo.insert_world(name, orbit_of_id, background, population_capacity_per_hex, hex_count)
    for res_name, percentage in resource_percentages.items():
        res_data = await map_repo.get_resource_id_by_name(res_name)
        if res_data:
            await map_repo.insert_world_resource(world_id, res_data['id'], percentage)
    await static_cache.load()
    return {'world_id': world_id}


async def delete_world(world_id: int, world_name: str) -> dict:
    children = await map_repo.count_child_worlds(world_id)
    if (children['count'] or 0) > 0:
        raise ValueError(f"{children['count']} world(s) orbit {world_name}. Delete them first.")
    fleets_count = await map_repo.count_fleets_at_world(world_id)
    fleet_count = fleets_count['count'] or 0
    if fleet_count > 0:
        await map_repo.delete_fleets_at_world(world_id)
    await map_repo.delete_world(world_id)
    await static_cache.load()
    return {'fleets_deleted': fleet_count}


async def get_world_asset_counts(world_id: int) -> dict:
    fleets_data = await map_repo.count_fleets_at_world(world_id)
    terr_data = await map_repo.count_territory_at_world(world_id)
    bldg_data = await map_repo.sum_buildings_at_world(world_id)
    return {
        'fleets': fleets_data['count'] or 0,
        'territory': terr_data['count'] or 0,
        'buildings': bldg_data['count'] or 0,
    }


async def rename_world(world_id: int, new_name: str):
    if await map_repo.find_world_by_name(new_name):
        raise ValueError(f"World named '{new_name}' already exists.")
    await map_repo.update_world_name(world_id, new_name)
    await static_cache.load()


async def modify_world(world_id: int, world_data: dict, hex_count: Optional[int], population_capacity_per_hex: Optional[int],
                       background: Optional[str], orbit_of_id: Optional[int], resource_updates: dict):
    if hex_count is not None and hex_count < world_data['hex_count']:
        claimed_data = await map_repo.sum_claimed_territory(world_id)
        if hex_count < (claimed_data['claimed'] or 0):
            raise ValueError(f"Cannot reduce hex count to {hex_count:,}. {claimed_data['claimed']:,} hexes already claimed.")
    updates = []
    params = [world_id]
    param_count = 2
    if hex_count is not None:
        updates.append(f"hex_count = ${param_count}")
        params.append(hex_count)
        param_count += 1
    if population_capacity_per_hex is not None:
        updates.append(f"population_capacity_per_hex = ${param_count}")
        params.append(population_capacity_per_hex)
        param_count += 1
    if background is not None:
        updates.append(f"background = ${param_count}")
        params.append(background)
        param_count += 1
    if orbit_of_id is not None:
        if orbit_of_id == world_id:
            raise ValueError("World cannot orbit itself.")
        updates.append(f"orbit_of = ${param_count}")
        params.append(orbit_of_id)
        param_count += 1
    if updates:
        await map_repo.update_world_fields(', '.join(updates), params)
    for res_name, percentage in resource_updates.items():
        res_data = await map_repo.get_resource_id_by_name(res_name)
        if res_data:
            await map_repo.upsert_world_resource(world_id, res_data['id'], percentage)
    await static_cache.load()


async def claim_hex(faction_id: int, world_id: int, world_name: str, max_hexes: int, hexes: int) -> dict:
    current_territory = await map_repo.get_world_faction_territory(world_id, faction_id)
    has_presence = current_territory and current_territory['territory'] > 0
    if not has_presence:
        fleet_check = await map_repo.has_fleet_at_world(faction_id, world_id)
        if not fleet_check['has_fleet']:
            raise ValueError(f"To claim your first hex on {world_name}, you need a fleet present on the world.")
    influence_cost = hexes * 20

    target_system_id = await _get_system_root_id(world_id)
    capital_row = await map_repo.get_faction_capital_world_id(faction_id)
    capital_world_id = capital_row['capital_world_id'] if capital_row else None
    capital_system_id = await _get_system_root_id(capital_world_id) if capital_world_id else None
    off_capital_system = capital_system_id is not None and target_system_id != capital_system_id

    if off_capital_system:
        influence_cost *= 5

    influence_data = await map_repo.get_faction_influence(faction_id)
    current_influence = influence_data['influence'] if influence_data else 0
    if current_influence < influence_cost:
        raise ValueError(f"Need {influence_cost:,} Influence, have {current_influence:,}.")
    claimed_data = await map_repo.sum_claimed_territory(world_id)
    current_claimed = claimed_data['claimed'] or 0
    if current_claimed + hexes > max_hexes:
        raise ValueError(f"Only {max_hexes - current_claimed} hex(es) available on {world_name}.")

    if off_capital_system:
        existing_off = await _count_off_capital_system_hexes(faction_id, capital_system_id)
        projected_off = existing_off + hexes
        required_cargo = 200 * projected_off
        ftl_cargo = await get_ftl_supply_capacity(faction_id)
        if ftl_cargo < required_cargo:
            raise ValueError(
                f"Claiming hexes outside your capital system requires 200 FTL supply cargo capacity per off-system hex. "
                f"Need {required_cargo:,} for {projected_off:,} hex(es), have {ftl_cargo:,}. "
                f"Assign FTL-capable ships to a fleet in FTL supply status."
            )

    influence_res = await map_repo.get_influence_resource()
    if influence_res:
        await map_repo.deduct_faction_influence(faction_id, influence_res['id'], influence_cost)
    await map_repo.claim_territory(world_id, faction_id, hexes)
    new_total = (current_territory['territory'] if current_territory else 0) + hexes
    return {'influence_cost': influence_cost, 'new_total': new_total, 'off_capital_system': off_capital_system}


async def unclaim_hex(faction_id: int, world_id: int, world_name: str, hexes: int) -> dict:
    territory_data = await map_repo.get_world_faction_territory_row(world_id, faction_id)
    if not territory_data:
        raise ValueError(f"Faction has no hexes on {world_name}.")
    current_hexes = territory_data['territory']
    if hexes > current_hexes:
        raise ValueError(f"Cannot unclaim {hexes} hex(es). Only have {current_hexes} claimed.")
    buildings_data = await map_repo.sum_faction_buildings_at_world(faction_id, world_id)
    total_buildings = buildings_data['total'] or 0
    remaining_hexes = current_hexes - hexes
    if remaining_hexes < total_buildings:
        raise ValueError(f"Cannot unclaim {hexes} hex(es). Need at least {total_buildings} hex(es) for {total_buildings} building(s).")
    if remaining_hexes == 0:
        await map_repo.delete_world_faction(world_id, faction_id)
    else:
        await map_repo.update_world_faction_territory(world_id, faction_id, hexes)
    return {'remaining_hexes': remaining_hexes, 'total_buildings': total_buildings}


async def get_faction_land(faction_id: int) -> List[FactionLandEntry]:
    return await map_repo.get_faction_land(faction_id)


async def get_world_factions(world_id: int) -> List[WorldFactionPresence]:
    return await map_repo.get_world_factions(world_id)


async def has_faction_presence(world_id: int, faction_id: int) -> bool:
    return await map_repo.has_faction_presence(world_id, faction_id)
