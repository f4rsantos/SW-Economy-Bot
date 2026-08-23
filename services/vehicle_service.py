# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import json
from typing import Dict, Optional
from repositories import vehicle_repo
from dtos.vehicle import Vehicle
from utils.vehicle_utils import get_next_vehicle_number, VEHICLE_NUMBER_LOCK

_vehicle_def_cache: dict[int, dict] = {}


def build_days(length: float) -> float:
    if length <= 20.0:
        return 1.0
    if length <= 250.0:
        return 1.0 + (length - 20.0) / (250.0 - 20.0) * 6.0
    if length >= 1000.0:
        return 14.0
    return 7.0 + (length - 250.0) / (1000.0 - 250.0) * 7.0


def compute_refit(new_costs: dict, old_costs: dict) -> tuple:
    resource_names = set(new_costs) | set(old_costs)
    cost_deltas = []
    for name in resource_names:
        delta = int(new_costs.get(name, 0)) - int(old_costs.get(name, 0))
        if delta != 0:
            cost_deltas.append({'name': name, 'amount': delta})

    new_total = sum(v for k, v in new_costs.items() if k != 'ER')
    old_total = sum(v for k, v in old_costs.items() if k != 'ER')
    ratio = 4.0 if old_total <= 0 else new_total / old_total
    ratio = max(0.1, min(4.0, ratio))
    return cost_deltas, ratio


def _parse_vehicle_length(vehicle_data) -> float:
    if not vehicle_data:
        return 100.0
    try:
        for entry in vehicle_data:
            parsed = json.loads(entry) if isinstance(entry, str) else entry
            if parsed and 'length' in parsed:
                return float(parsed['length'])
    except Exception:
        pass
    return 100.0


async def get_vehicle_definition(vehicle_id: int) -> Optional[dict]:
    if vehicle_id in _vehicle_def_cache:
        return _vehicle_def_cache[vehicle_id]
    row, costs = await vehicle_repo.get_vehicle_row_and_costs(vehicle_id)
    if not row:
        return None
    defn = {
        'id': vehicle_id,
        'name': row.name,
        'designation': row.designation,
        'faction_id': row.faction_id,
        'faction_vehicle_number': row.faction_vehicle_number,
        'type': row.type,
        'type_name': row.type_name,
        'vehicle_data': row.vehicle_data,
        'length': _parse_vehicle_length(row.vehicle_data),
        'costs': {c.name: c.amount for c in costs},
    }
    _vehicle_def_cache[vehicle_id] = defn
    return defn


def invalidate_vehicle_definition(vehicle_id: int):
    _vehicle_def_cache.pop(vehicle_id, None)


async def get_vehicle_type_id(type_name: str) -> Optional[int]:
    from database.static_cache import static_cache
    type_id = static_cache.get_vehicle_type_id(type_name)
    if type_id is not None:
        return type_id
    return await vehicle_repo.get_vehicle_type_id_by_name(type_name)


async def check_vehicle_exists(faction_id: int, vehicle_name: str) -> Optional[Vehicle]:
    return await vehicle_repo.get_vehicle_by_name(faction_id, vehicle_name)


async def register_vehicle(
    faction_id: int,
    vehicle_name: str,
    designation: Optional[str],
    type_name: str,
    costs: Dict[str, int],
    vehicle_data: Optional[Dict] = None
) -> Vehicle:
    type_id = await get_vehicle_type_id(type_name)
    if type_id is None:
        raise ValueError(f"Invalid vehicle type: {type_name}")

    import json
    vehicle_data_array = [json.dumps(vehicle_data)] if vehicle_data else None

    from database.static_cache import static_cache

    async with vehicle_repo.get_connection() as conn:
        async with conn.transaction():
            await vehicle_repo.lock_vehicle_number(conn, VEHICLE_NUMBER_LOCK, faction_id)
            next_number = await get_next_vehicle_number(faction_id, conn=conn)

            vehicle = await vehicle_repo.insert_vehicle(
                conn, faction_id, type_id, vehicle_name, designation, next_number, vehicle_data_array
            )

            cost_rows = []
            for resource_name, amount in costs.items():
                if amount > 0:
                    res_id = static_cache.get_resource_id(resource_name)
                    if res_id:
                        cost_rows.append((vehicle.id, res_id, amount))
            await vehicle_repo.insert_vehicle_costs_conn(conn, vehicle.id, cost_rows)

    return vehicle


async def update_vehicle(
    vehicle_id: int,
    designation: Optional[str],
    costs: Dict[str, int],
    vehicle_data: Optional[Dict] = None
) -> Vehicle:
    import json
    vehicle_data_array = [json.dumps(vehicle_data)] if vehicle_data else None

    vehicle = await vehicle_repo.update_vehicle_row(designation, vehicle_data_array, vehicle_id)

    await vehicle_repo.delete_vehicle_costs(vehicle_id)
    invalidate_vehicle_definition(vehicle_id)

    from database.static_cache import static_cache
    cost_rows = []
    for resource_name, amount in costs.items():
        if amount > 0:
            res_id = static_cache.get_resource_id(resource_name)
            if res_id:
                cost_rows.append((vehicle_id, res_id, amount))
    await vehicle_repo.insert_vehicle_costs(vehicle_id, cost_rows)

    asyncio.create_task(_recalc_cs_for_vehicle(vehicle_id))
    return vehicle


async def _recalc_cs_for_vehicle(vehicle_id: int):
    await vehicle_repo.recalc_fleet_cs_for_vehicle(vehicle_id)


async def get_vehicle_costs(vehicle_id: int) -> Dict[str, int]:
    results = await vehicle_repo.get_vehicle_costs(vehicle_id)
    return {row.name: row.amount for row in results}


async def list_vehicles(faction_id: int) -> list:
    return await vehicle_repo.list_vehicles(faction_id)


async def rename_vehicle(vehicle_id: int, faction_id: int, new_name: Optional[str], designation: Optional[str]) -> dict:
    if new_name:
        existing = await vehicle_repo.find_vehicle_name_conflict(faction_id, new_name, vehicle_id)
        if existing:
            raise ValueError("A vehicle with that name already exists for this faction.")
    await vehicle_repo.update_vehicle_name_designation(new_name, designation, vehicle_id)
    invalidate_vehicle_definition(vehicle_id)


async def set_vehicle_type(vehicle_id: int, type_id: int):
    await vehicle_repo.update_vehicle_type(vehicle_id, type_id)
    invalidate_vehicle_definition(vehicle_id)


async def deregister_vehicle(vehicle_id: int):
    fleet_check = await vehicle_repo.get_fleet_vehicle_total(vehicle_id)
    if fleet_check and fleet_check['total'] and fleet_check['total'] > 0:
        raise ValueError(f"Cannot deregister vehicle. {fleet_check['total']} units still exist in fleets.")
    construction_check = await vehicle_repo.get_vehicle_construction_total(vehicle_id)
    if construction_check and construction_check['total'] and construction_check['total'] > 0:
        raise ValueError(f"Cannot deregister vehicle. {construction_check['total']} units under construction.")
    await vehicle_repo.delete_vehicle(vehicle_id)
    invalidate_vehicle_definition(vehicle_id)


async def get_vehicle_details(vehicle_id: int) -> tuple[Optional[Vehicle], list, list]:
    full_vehicle, costs, fleets_with_vehicle = await vehicle_repo.get_vehicle_details(vehicle_id)
    return full_vehicle, costs, [dict(f) for f in fleets_with_vehicle]
