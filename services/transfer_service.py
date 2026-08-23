# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from dtos.transfer import Transfer, TransferResource, PendingTransfer
from repositories import transfer_repo
from services.travel_time_service import calculate_travel_time, format_travel_time
from services.treasury_service import find_best_worlds_for_multiple_resources

logger = logging.getLogger(__name__)


def _resources_to_array(resources: dict) -> str:
    return json.dumps([{"name": k, "amount": v} for k, v in resources.items()])


async def deduct_resources(faction_id: int, world_id: Optional[int], resources: dict, conn=None):
    try:
        await transfer_repo.call_deduct_resources(faction_id, world_id, _resources_to_array(resources), conn)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def add_resources(faction_id: int, world_id: Optional[int], resources: dict):
    try:
        await transfer_repo.call_add_resources(faction_id, world_id, _resources_to_array(resources))
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def upgrade_buildings(
    faction_id: int,
    world_id: int,
    building_id: int,
    amount: int,
    source_level: int,
    target_level: int,
    costs: dict,
):
    try:
        await transfer_repo.call_upgrade_buildings(
            faction_id, world_id, building_id, amount, source_level, target_level,
            json.dumps(costs)
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def create_transfer(
    from_faction_id: int,
    to_faction_id: int,
    from_world_id: int,
    to_world_id: int,
    resources: dict,
    start_time: datetime,
    arrival_time: datetime,
    escort_fleet_id: Optional[int] = None,
) -> int:
    resource_rows = await transfer_repo.get_resource_ids_by_names(list(resources.keys()))
    name_to_id = {r['name']: r['id'] for r in resource_rows}
    resources_array = json.dumps([
        {"resource_id": name_to_id[name], "amount": amount}
        for name, amount in resources.items()
        if name in name_to_id
    ])
    try:
        row = await transfer_repo.call_create_transfer(
            from_faction_id, to_faction_id, from_world_id, to_world_id,
            resources_array, start_time, arrival_time, escort_fleet_id
        )
        transfer_id = row['transfer_id']
        from services.event_queue import event_queue
        await event_queue.push(arrival_time, 'transfer_arrival', {
            'transfer_id': transfer_id, 'to_faction_id': to_faction_id, 'to_world_id': to_world_id
        })
        return transfer_id
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def deposit_transfer(transfer_id: int):
    try:
        await transfer_repo.call_deposit_transfer(transfer_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def intercept_transfer(transfer_id: int, fleet_id: int, world_id: int):
    try:
        await transfer_repo.call_intercept_transfer(transfer_id, fleet_id, world_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def seize_transfer(transfer_id: int, faction_id: int, world_id: int):
    try:
        await transfer_repo.call_seize_transfer(transfer_id, faction_id, world_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def destroy_transfer(transfer_id: int):
    try:
        await transfer_repo.call_destroy_transfer(transfer_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def release_transfer(transfer_id: int, new_arrival: datetime):
    try:
        await transfer_repo.call_release_transfer(transfer_id, new_arrival)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_transfer(transfer_id: int, status: str = None) -> Optional[Transfer]:
    return await transfer_repo.get_transfer_row(transfer_id, status)


async def get_intercepted_transfer(transfer_id: int, intercepting_faction_id: int) -> Optional[Transfer]:
    return await transfer_repo.get_intercepted_transfer_row(transfer_id, intercepting_faction_id)


async def get_transfer_resources(transfer_id: int) -> List[TransferResource]:
    return await transfer_repo.get_transfer_resources_rows(transfer_id)


async def get_fleets_at_world(faction_id: int, world_id: int) -> List[dict]:
    return await transfer_repo.get_fleets_at_world_rows(faction_id, world_id)


async def check_blockade(world_id: int, faction_id: int) -> bool:
    row = await transfer_repo.get_blockade_row(world_id, faction_id)
    return row is not None


async def execute_er_transfer(
    from_faction_id: int,
    to_faction_id: int,
    from_world_id: int,
    to_world_id: int,
    er_id: int,
    amount: int,
    current_time: datetime,
):
    await transfer_repo.debit_faction_treasury(from_faction_id, er_id, amount)
    await transfer_repo.credit_faction_treasury(to_faction_id, er_id, amount)
    return None


async def execute_physical_transfer(
    from_faction_id: int,
    to_faction_id: int,
    from_world_id: int,
    to_world_id: int,
    from_world_name: str,
    to_world_name: str,
    transfers: list,
    resource_map: dict,
    current_time: datetime,
    escort_fleet_id: Optional[int] = None,
    escort_fleet_name: Optional[str] = None,
) -> dict:
    travel_time = await calculate_travel_time(from_world_name, to_world_name, current_time)
    arrival_time = current_time + travel_time
    travel_str = await format_travel_time(travel_time)

    resources = {t['resource']: t['amount'] for t in transfers}
    transfer_id = await create_transfer(
        from_faction_id, to_faction_id,
        from_world_id, to_world_id,
        resources, current_time, arrival_time, escort_fleet_id
    )

    if escort_fleet_id is not None:
        from services.fleet_service import move_fleet
        from services.event_queue import event_queue
        await move_fleet(escort_fleet_id, to_world_id, current_time, notify=False)
        await event_queue.push(arrival_time, 'fleet_arrival', {'fleet_id': escort_fleet_id, 'to_world_id': to_world_id})

    from utils.currency import handle_return
    from services import notification_service
    cargo_lines = [f"{handle_return(t['amount'])} {t['resource']}" for t in transfers]
    try:
        await notification_service.notify_transfer_departure(
            from_faction_id, from_world_name, to_world_name,
            from_world_id, to_world_id, cargo_lines, escort_fleet_name
        )
    except Exception:
        logger.exception(f"Transfer {transfer_id} departure notification failed")

    return {
        'transfer_id': transfer_id,
        'arrival_time': arrival_time,
        'travel_str': travel_str,
    }


async def get_resource_name_to_id(resource_names: list[str]) -> dict:
    rows = await transfer_repo.get_resource_name_to_id_rows(resource_names)
    return {r['name']: r['id'] for r in rows}


async def get_world_for_faction(faction_id: int) -> Optional[dict]:
    return await transfer_repo.get_world_for_faction_row(faction_id)


async def ensure_world_presence(world_id: int, faction_id: int):
    await transfer_repo.ensure_world_presence(world_id, faction_id)


async def has_world_presence(world_id: int, faction_id: int) -> bool:
    row = await transfer_repo.get_world_presence_row(world_id, faction_id)
    return row is not None


async def get_local_resource_amount(world_id: int, faction_id: int, resource_id: int) -> int:
    row = await transfer_repo.get_local_resource_amount_row(world_id, faction_id, resource_id)
    return row['amount'] if row else 0


async def list_pending_transfers(
    faction_id: Optional[int] = None,
    world_id: Optional[int] = None,
    filter_type: str = 'all',
) -> list[PendingTransfer]:
    params = []
    where_parts = []

    if faction_id is not None:
        params.append(faction_id)
        n = len(params)
        if filter_type == 'incoming':
            where_parts.append(f"rt.to_faction_id = ${n}")
        elif filter_type == 'outgoing':
            where_parts.append(f"rt.from_faction_id = ${n}")
        else:
            where_parts.append(f"(rt.from_faction_id = ${n} OR rt.to_faction_id = ${n})")

    if world_id is not None:
        params.append(world_id)
        n = len(params)
        where_parts.append(f"(rt.from_world_id = ${n} OR rt.to_world_id = ${n})")

    if not where_parts:
        return []

    where_clause = " AND ".join(where_parts)
    return await transfer_repo.get_pending_transfers_rows(where_clause, params)


async def get_transfer_resource_rows(transfer_ids: list[int]) -> list:
    if not transfer_ids:
        return []
    return await transfer_repo.get_transfer_resource_rows_bulk(transfer_ids)
