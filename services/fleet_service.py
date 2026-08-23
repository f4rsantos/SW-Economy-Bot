# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
import logging
import math
from typing import List, Optional
from repositories import fleet_repo
from dtos.fleet import Fleet, FleetDamageInfo, FleetListing
from services.building_efficiency_service import calculate_effective_efficiency
from services.local_deduction import deduct_local_proportional

logger = logging.getLogger(__name__)


async def create_fleet(faction_id: int, name: Optional[str], world_id: int) -> dict:
    try:
        return await fleet_repo.call_create_fleet(faction_id, name, world_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def set_fleet_status(fleet_id: int, status_name: str):
    try:
        await fleet_repo.call_set_fleet_status(fleet_id, status_name)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def move_fleet(fleet_id: int, destination_id: int, moved_since, notify: bool = True):
    origin = await fleet_repo.get_fleet_row(fleet_id) if notify else None
    try:
        await fleet_repo.call_move_fleet(fleet_id, destination_id, moved_since)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e

    if not notify:
        return

    try:
        await _notify_movement(origin, destination_id)
    except Exception:
        logger.exception(f"Fleet {fleet_id} departure notification failed")


async def _notify_movement(origin, destination_id: int):
    if origin is None or origin.position is None:
        return
    if origin.position == destination_id:
        return

    from repositories import notification_repo
    from services import notification_service
    from services.map_service import get_world_by_id

    vehicle_count = await notification_repo.get_fleet_vehicle_count(origin.id)
    if vehicle_count <= 0:
        return

    destination = await get_world_by_id(destination_id)
    if not destination:
        return

    fleet_name = origin.name or f"Unit #{origin.faction_fleet_number}"
    await notification_service.notify_fleet_departure(
        origin.faction_id, fleet_name, vehicle_count,
        origin.position_name, destination['name'],
        origin.position, destination_id
    )


async def add_vehicle_to_fleet(fleet_id: int, vehicle_id: int, amount: int):
    try:
        await fleet_repo.call_add_vehicle_to_fleet(fleet_id, vehicle_id, amount)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def refund_vehicle(fleet_id: int, vehicle_id: int, amount: int, refund_faction_id: int, refund_pct: float):
    try:
        await fleet_repo.call_refund_vehicle(fleet_id, vehicle_id, amount, refund_faction_id, refund_pct)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def salvage_fleet(salvager_faction_id: int, debris_fleet_id: int) -> dict:
    try:
        return await fleet_repo.call_salvage_fleet(salvager_faction_id, debris_fleet_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_fleet(fleet_id: int) -> Optional[Fleet]:
    return await fleet_repo.get_fleet_row(fleet_id)


async def get_unit_vehicle_resource_totals(unit_id: int) -> dict:
    rows = await fleet_repo.get_unit_vehicle_resource_totals_rows(unit_id)
    return {row['name']: int(row['total']) for row in rows}


async def buy_vehicle(faction_id: int, world_id: int, fleet_id: int, vehicle_id: int,
                      amount: int, factory_space: int, completion, costs: list) -> int:
    import json
    from datetime import datetime, timedelta, timezone
    try:
        row = await fleet_repo.call_buy_vehicle(
            faction_id, world_id, fleet_id, vehicle_id, amount, factory_space, completion,
            json.dumps(costs)
        )
        order_id = row['order_id']
        if hasattr(completion, 'tzinfo'):
            due = completion if completion.tzinfo else completion.replace(tzinfo=timezone.utc)
        else:
            due = completion
        from services.event_queue import event_queue
        await event_queue.push(due, 'construction_complete', {
            'order_id': order_id, 'fleet_id': fleet_id, 'vehicle_id': vehicle_id, 'quantity': amount
        })
        return order_id
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e



async def refit_vehicle(faction_id: int, fleet_id: int, vehicle_id: int, amount: int,
                        world_id: int, factory_space: int, completion, cost_deltas: list) -> int:
    import json
    from datetime import timezone
    try:
        row = await fleet_repo.call_refit_vehicle(
            faction_id, fleet_id, vehicle_id, amount, world_id, factory_space, completion,
            json.dumps(cost_deltas)
        )
        order_id = row['order_id']
        if hasattr(completion, 'tzinfo'):
            due = completion if completion.tzinfo else completion.replace(tzinfo=timezone.utc)
        else:
            due = completion
        from services.event_queue import event_queue
        await event_queue.push(due, 'construction_complete', {
            'order_id': order_id, 'fleet_id': fleet_id, 'vehicle_id': vehicle_id, 'quantity': amount
        })
        return order_id
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def transfer_vehicle(from_fleet_id: int, to_fleet_id: int, vehicle_id: int, amount: int):
    try:
        await fleet_repo.call_transfer_vehicle(from_fleet_id, to_fleet_id, vehicle_id, amount)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_fleet_by_identifier(fleet_identifier: str, faction_id: int) -> Optional[Fleet]:
    return await fleet_repo.get_fleet_by_identifier_row(fleet_identifier, faction_id)


async def rename_fleet(fleet_id: int, new_name: str):
    await fleet_repo.rename_fleet(fleet_id, new_name)


async def delete_fleet(fleet_id: int):
    await fleet_repo.delete_fleet(fleet_id)


async def get_fleet_vehicles(fleet_id: int) -> list:
    rows = await fleet_repo.get_fleet_vehicles_rows(fleet_id)
    return [dict(r) for r in rows]


async def get_fleet_vehicle_count(fleet_id: int) -> int:
    row = await fleet_repo.get_fleet_vehicle_count_row(fleet_id)
    return row['total'] or 0


async def get_factory_progress(faction_id: int, world_id: Optional[int] = None) -> list:
    if world_id:
        rows = await fleet_repo.get_factory_progress_rows_for_world(faction_id, world_id)
    else:
        rows = await fleet_repo.get_factory_progress_rows_all(faction_id)
    return [dict(r) for r in rows]


async def get_fleets(faction_id: Optional[int] = None, world_id: Optional[int] = None) -> List[FleetListing]:
    conditions = []
    args = []
    if faction_id:
        conditions.append(f"f.faction_id = ${len(args) + 1}")
        args.append(faction_id)
    if world_id:
        conditions.append(f"f.position = ${len(args) + 1}")
        args.append(world_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return await fleet_repo.get_fleets_rows(where, args)


async def get_fleet_for_damage(fleet_identifier: str, faction_id: Optional[int]) -> Optional[FleetDamageInfo]:
    if faction_id:
        return await fleet_repo.get_fleet_for_damage_row_with_faction(fleet_identifier, faction_id)
    return await fleet_repo.get_fleet_for_damage_row(fleet_identifier)


async def list_debris_fleets(faction_id: Optional[int] = None, world_id: Optional[int] = None) -> list[dict]:
    query = """
        SELECT f.id, f.name, f.faction_fleet_number,
               fac.name as faction_name, w.name as world_name, f.total_cs
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        JOIN factions fac ON f.faction_id = fac.id
        JOIN worlds w ON f.position = w.id
        WHERE LOWER(fs.name) = 'debris'
    """
    args = []

    if faction_id is not None:
        args.append(faction_id)
        query += f" AND f.faction_id = ${len(args)}"

    if world_id is not None:
        args.append(world_id)
        query += f" AND f.position = ${len(args)}"

    query += " ORDER BY f.total_cs DESC"
    rows = await fleet_repo.get_debris_fleets_rows(query, args)
    return [dict(r) for r in rows]


async def get_factory_info(world_id: int, faction_id: int, is_large: bool) -> tuple[int, int]:
    target_building = 'Mega Factory' if is_large else 'Factory'
    capacity_per_level = 1000 if is_large else 200

    cap_row = await fleet_repo.get_factory_capacity_row(world_id, faction_id, target_building, capacity_per_level)

    used_row = await fleet_repo.get_factory_used_space_row(world_id, faction_id, is_large)

    eff = await calculate_effective_efficiency(faction_id, building_type='factory')
    total = math.floor((cap_row['total_capacity'] or 0) * eff)
    used = used_row['used_space'] or 0
    return int(total), int(used)



async def get_ftl_supply_capacity(faction_id: int) -> int:
    row = await fleet_repo.get_ftl_supply_capacity_row(faction_id)
    return int(row['total_cargo']) if row else 0


async def get_vehicle_length(vehicle_id: int) -> float:
    from services.vehicle_service import get_vehicle_definition
    defn = await get_vehicle_definition(vehicle_id)
    return defn['length'] if defn else 100.0


async def get_vehicle_cost_rows(vehicle_id: int) -> list:
    from services.vehicle_service import get_vehicle_definition
    defn = await get_vehicle_definition(vehicle_id)
    if not defn:
        return []
    return [{'name': name, 'amount': amt} for name, amt in defn['costs'].items()]


async def set_unit_type(unit_id: int, type_name: str):
    from database.static_cache import static_cache
    type_id = static_cache.get_fleet_type_id(type_name)
    if not type_id:
        type_row = await fleet_repo.get_fleet_type_row_by_name(type_name)
        if not type_row:
            raise ValueError(f"Unit type '{type_name}' not found.")
        type_id = type_row['id']
    await fleet_repo.set_fleet_type(unit_id, type_id)


async def get_total_faction_infantry(faction_id: int) -> int:
    row = await fleet_repo.get_total_faction_infantry_row(faction_id)
    return int(row['total']) if row else 0


async def recruit_infantry_to_unit(unit_id: int, faction_id: int, amount: int, costs: dict, completion) -> int:
    async with fleet_repo.get_connection() as conn:
        async with conn.transaction():
            pop_id = await fleet_repo.get_resource_id_by_name(conn, 'Population')
            available_pop = await fleet_repo.get_local_treasury_total(conn, faction_id, pop_id)
            if available_pop < amount:
                raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient Population — need {amount:,}, have {available_pop:,}")

            await deduct_local_proportional(conn, faction_id, pop_id, available_pop, amount)

            local_resources = {'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS'}
            for res_name, per_unit in costs.items():
                total_cost = per_unit * amount
                res_id = await fleet_repo.get_resource_id_by_name(conn, res_name)
                if not res_id:
                    raise ValueError(f"RESOURCE_NOT_FOUND: Unknown resource {res_name}")
                if res_name in local_resources:
                    available = await fleet_repo.get_local_treasury_total(conn, faction_id, res_id)
                    if available < total_cost:
                        raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {res_name} — need {total_cost:,}, have {available:,}")
                    await deduct_local_proportional(conn, faction_id, res_id, available, total_cost)
                else:
                    available = await fleet_repo.get_faction_treasury_amount(conn, faction_id, res_id)
                    if available < total_cost:
                        raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {res_name} — need {total_cost:,}, have {available:,}")
                    await fleet_repo.debit_faction_treasury(conn, faction_id, res_id, total_cost)

            rec_id = await fleet_repo.insert_military_recruitment(conn, faction_id, amount, completion, unit_id)
            return rec_id


async def dismiss_infantry_from_unit(unit_id: int, faction_id: int, amount: int):
    async with fleet_repo.get_connection() as conn:
        async with conn.transaction():
            current = await fleet_repo.get_fleet_infantry_count(conn, unit_id, faction_id)
            if current is None:
                raise ValueError("Unit not found.")
            if current < amount:
                raise ValueError(f"INSUFFICIENT_INFANTRY: Unit has {current:,} infantry, cannot dismiss {amount:,}.")

            await fleet_repo.adjust_fleet_infantry_count(conn, unit_id, amount)

            pop_id = await fleet_repo.get_resource_id_by_name(conn, 'Population')
            total_pop = await fleet_repo.get_local_treasury_total(conn, faction_id, pop_id)
            if total_pop > 0:
                await fleet_repo.distribute_population_by_share(conn, faction_id, pop_id, total_pop, amount)
            else:
                territories = await fleet_repo.get_territories_with_population(conn, faction_id)
                total_territory = sum(t['territory'] for t in territories)
                if total_territory > 0:
                    for t in territories:
                        share = (t['territory'] / total_territory) * amount
                        await fleet_repo.add_local_treasury_share(conn, faction_id, t['world_id'], pop_id, share)


async def transfer_infantry_between_units(from_unit_id: int, to_unit_id: int, faction_id: int, amount: int):
    async with fleet_repo.get_connection() as conn:
        async with conn.transaction():
            from_infantry = await fleet_repo.get_fleet_infantry_count(conn, from_unit_id, faction_id)
            if from_infantry is None:
                raise ValueError("Source unit not found or does not belong to this faction.")
            if from_infantry < amount:
                raise ValueError(f"Source unit only has {from_infantry:,} infantry.")

            to_check = await fleet_repo.fleet_exists_for_faction(conn, to_unit_id, faction_id)
            if not to_check:
                raise ValueError("Destination unit not found or does not belong to this faction.")

            await fleet_repo.adjust_fleet_infantry_count(conn, from_unit_id, amount)
            await fleet_repo.increase_fleet_infantry_count(conn, to_unit_id, amount)
