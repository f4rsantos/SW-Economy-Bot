# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
from typing import Optional
from database.cache_manager import cache_manager
from repositories import faction_repo
from utils.vehicle_utils import get_next_vehicle_number, VEHICLE_NUMBER_LOCK


async def list_factions(long_sort: bool = False) -> list:
    return await faction_repo.list_factions(long_sort)


async def search_faction_names(current: str, limit: int = 25) -> list[str]:
    return await faction_repo.search_faction_names(current, limit)


async def get_faction_row_by_id(faction_id: int) -> Optional[dict]:
    return await faction_repo.get_faction_row_by_id(faction_id)


async def get_faction_territory_summary(faction_id: int) -> dict:
    return await faction_repo.get_faction_territory_summary(faction_id)


async def get_faction_leader_role_id(faction_id: int) -> Optional[int]:
    return await faction_repo.get_faction_leader_role_id(faction_id)


async def rename_faction(faction_id: int, new_name: str):
    existing = await faction_repo.find_faction_by_name_excluding(new_name, faction_id)
    if existing:
        raise ValueError(f"A faction with the name '{new_name}' already exists.")
    await faction_repo.update_faction_name(faction_id, new_name)
    cache_manager.invalidate_faction(faction_id)


async def set_leader(faction_id: int, user_id: int):
    if not await faction_repo.user_exists(user_id):
        raise ValueError(f"User {user_id} is not registered in the database.")
    await faction_repo.update_faction_leader(faction_id, user_id)
    cache_manager.invalidate_faction(faction_id)


async def update_faction_details(faction_id: int, color: Optional[str], leader_treatment: Optional[str],
                                 formal_name: Optional[str], flag: Optional[str],
                                 capital_world_id: Optional[int] = None) -> dict:
    updates = []
    values = []
    param_count = 1
    if capital_world_id is not None:
        updates.append(f"capital_world_id = ${param_count}")
        values.append(capital_world_id)
        param_count += 1
    if color:
        updates.append(f"color = ${param_count}")
        values.append(color)
        param_count += 1
    if leader_treatment is not None:
        updates.append(f"leader = ${param_count}")
        values.append(leader_treatment)
        param_count += 1
    if formal_name:
        updates.append(f"formal_name = ${param_count}")
        values.append(formal_name)
        param_count += 1
    if flag is not None:
        updates.append(f"flag = ${param_count}")
        values.append(flag)
        param_count += 1
    values.append(faction_id)
    set_clause = f"{', '.join(updates)} WHERE id = ${param_count}"
    updated = await faction_repo.update_faction_details(set_clause, values)
    cache_manager.set_faction(faction_id, updated)
    return updated


async def _copy_vehicles_for_owner(owner_faction_id: int, vehicles: list) -> dict:
    copies = {}
    async with faction_repo.get_connection() as conn:
        async with conn.transaction():
            await faction_repo.acquire_vehicle_number_lock(conn, VEHICLE_NUMBER_LOCK, owner_faction_id)
            for vehicle_id, original in vehicles:
                number = await get_next_vehicle_number(owner_faction_id, conn=conn)
                copies[vehicle_id] = await faction_repo.insert_vehicle_copy(
                    conn, owner_faction_id, original, number
                )
    return copies


async def _reassign_external_vehicles(vehicle_ids: list, vehicle_map: dict, faction_id: int) -> None:
    external_usages = await faction_repo.get_external_vehicle_usages(vehicle_ids, faction_id)
    if not external_usages:
        return

    needed_by_owner: dict = {}
    for usage in external_usages:
        owner_faction_id = usage['owner_faction_id']
        vehicle_id = usage['vehicle_id']
        owner_vehicles = needed_by_owner.setdefault(owner_faction_id, {})
        owner_vehicles[vehicle_id] = vehicle_map[vehicle_id]

    copy_map: dict = {}
    for owner_faction_id, owner_vehicles in needed_by_owner.items():
        copies = await _copy_vehicles_for_owner(owner_faction_id, list(owner_vehicles.items()))
        for vehicle_id, new_id in copies.items():
            copy_map[(owner_faction_id, vehicle_id)] = new_id

    await faction_repo.repoint_fleet_vehicles([
        (copy_map[(usage['owner_faction_id'], usage['vehicle_id'])], usage['fleet_id'], usage['vehicle_id'])
        for usage in external_usages
    ])


async def delete_faction(faction_id: int):
    fleet_ids, vehicle_rows, led_pact_ids, transfer_ids = await asyncio.gather(
        faction_repo.get_faction_fleet_ids(faction_id),
        faction_repo.get_faction_vehicles(faction_id),
        faction_repo.get_pact_ids_led_by(faction_id),
        faction_repo.get_transfer_ids_involving(faction_id),
    )

    if fleet_ids:
        await faction_repo.delete_fleet_dependencies(fleet_ids)
    await faction_repo.delete_faction_fleets(faction_id)

    vehicle_ids = [r['id'] for r in vehicle_rows]
    vehicle_map = {r['id']: r for r in vehicle_rows}
    if vehicle_ids:
        await _reassign_external_vehicles(vehicle_ids, vehicle_map, faction_id)
        await faction_repo.delete_vehicle_dependencies(vehicle_ids)

    await faction_repo.delete_faction_records(faction_id, led_pact_ids, transfer_ids)
    await faction_repo.delete_faction(faction_id)
    cache_manager.invalidate_faction(faction_id)


async def merge_aux(from_faction_id: int, to_faction_id: int) -> dict:
    territories = await faction_repo.get_faction_territories(from_faction_id)
    if not territories:
        raise ValueError("Source faction has no territories to transfer.")
    await faction_repo.merge_territories(territories, to_faction_id)
    await faction_repo.delete_faction_territories(from_faction_id)
    await faction_repo.delete_faction(from_faction_id)
    cache_manager.invalidate_faction(from_faction_id)
    return {'territories_transferred': len(territories)}


async def create_faction_in_db(conn, name: str, formal_name: str, color: str, leader_name: str,
                               flag: str, leader_id: int, faction_type: int, starting_world_id: Optional[int]) -> dict:
    is_company = faction_type == 1
    faction = await faction_repo.insert_faction(
        conn, name, formal_name, color, leader_name, flag, leader_id, faction_type,
        starting_world_id if faction_type == 0 else None
    )
    if starting_world_id and not is_company:
        await faction_repo.claim_starting_territory(conn, starting_world_id, faction.id)
    if starting_world_id:
        await _initialize_faction_assets(conn, faction.id, starting_world_id, is_company)
    return faction


STARTING_ER = 50000000000
STARTING_LOCAL_RESOURCE = 100000
STARTING_POPULATION = 40000000

COMPANY_STARTING_BUILDINGS = [(9, 1, 1), (11, 1, 1), (10, 1, 1), (13, 1, 1), (15, 1, 1), (14, 1, 1)]
FACTION_STARTING_BUILDINGS = [
    (1, 10, 4), (2, 1, 3), (4, 1, 3), (3, 1, 2),
    (5, 1, 3), (7, 1, 3), (6, 1, 2),
    (9, 1, 1), (11, 1, 1), (10, 1, 1),
    (13, 1, 1), (15, 1, 1), (14, 1, 1), (16, 1, 1),
]


async def _initialize_faction_assets(conn, faction_id: int, world_id: Optional[int], is_company: bool = False):
    er_id = await faction_repo.get_resource_id_by_name(conn, 'ER')
    if er_id:
        await faction_repo.add_faction_treasury(conn, faction_id, er_id, STARTING_ER)
    if not world_id:
        return
    if is_company:
        await faction_repo.ensure_world_presence(conn, world_id, faction_id)
    res_map = await faction_repo.get_resource_ids_by_names(conn, ['CM', 'CS', 'EL', 'Population'])
    for name in ['CM', 'CS', 'EL']:
        if name in res_map:
            await faction_repo.add_local_treasury(conn, faction_id, world_id, res_map[name], STARTING_LOCAL_RESOURCE)
    if not is_company and 'Population' in res_map:
        await faction_repo.add_local_treasury(conn, faction_id, world_id, res_map['Population'], STARTING_POPULATION)
    buildings = COMPANY_STARTING_BUILDINGS if is_company else FACTION_STARTING_BUILDINGS
    await faction_repo.add_starting_buildings(conn, faction_id, world_id, buildings)


async def check_world_space(conn, world_id: int) -> bool:
    hex_count = await faction_repo.get_world_hex_count(conn, world_id)
    if hex_count is None:
        return False
    claimed = await faction_repo.get_world_claimed_territory(conn, world_id)
    return hex_count - claimed >= 50


async def faction_name_exists(conn, name: str) -> bool:
    return await faction_repo.faction_name_exists(conn, name)


async def user_is_registered(conn, user_id: int) -> bool:
    return await faction_repo.user_is_registered(conn, user_id)


async def get_world_hex_count(conn, world_id: int) -> Optional[int]:
    return await faction_repo.get_world_hex_count(conn, world_id)


async def get_world_available_hexes(conn, world_id: int, hex_count: int) -> int:
    claimed = await faction_repo.get_world_claimed_territory(conn, world_id)
    return hex_count - claimed
