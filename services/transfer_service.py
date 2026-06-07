import asyncpg
import json
from datetime import datetime, timezone
from typing import Optional, List
from database.db_manager import db
from services.travel_time_service import calculate_travel_time, format_travel_time
from services.treasury_service import find_best_worlds_for_multiple_resources


def _resources_to_array(resources: dict) -> str:
    return json.dumps([{"name": k, "amount": v} for k, v in resources.items()])


async def deduct_resources(faction_id: int, world_id: Optional[int], resources: dict):
    try:
        await db.execute(
            "SELECT sp_deduct_resources($1, $2, $3::jsonb)",
            faction_id, world_id, _resources_to_array(resources)
        )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def add_resources(faction_id: int, world_id: Optional[int], resources: dict):
    try:
        await db.execute(
            "SELECT sp_add_resources($1, $2, $3::jsonb)",
            faction_id, world_id, _resources_to_array(resources)
        )
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
        await db.execute(
            "SELECT sp_upgrade_buildings($1, $2, $3, $4, $5, $6, $7::jsonb)",
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
) -> int:
    resource_rows = await db.fetch(
        "SELECT id, name FROM resources WHERE name = ANY($1)", list(resources.keys())
    )
    name_to_id = {r['name']: r['id'] for r in resource_rows}
    resources_array = json.dumps([
        {"resource_id": name_to_id[name], "amount": amount}
        for name, amount in resources.items()
        if name in name_to_id
    ])
    try:
        row = await db.fetchrow(
            "SELECT sp_create_transfer($1, $2, $3, $4, $5::jsonb, $6, $7) as transfer_id",
            from_faction_id, to_faction_id, from_world_id, to_world_id,
            resources_array, start_time, arrival_time
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
        await db.execute("SELECT sp_deposit_transfer($1)", transfer_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def intercept_transfer(transfer_id: int, fleet_id: int):
    try:
        await db.execute("SELECT sp_intercept_transfer($1, $2)", transfer_id, fleet_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def seize_transfer(transfer_id: int, faction_id: int, world_id: int):
    try:
        await db.execute("SELECT sp_seize_transfer($1, $2, $3)", transfer_id, faction_id, world_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def release_transfer(transfer_id: int, new_arrival: datetime):
    try:
        await db.execute("SELECT sp_release_transfer($1, $2)", transfer_id, new_arrival)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_transfer(transfer_id: int, status: str = None) -> Optional[dict]:
    condition = "AND rt.status = $2" if status else ""
    params = [transfer_id]
    if status:
        params.append(status)
    row = await db.fetchrow(f"""
        SELECT rt.*,
               ff.name as from_faction_name,
               tf.name as to_faction_name,
               fw.name as from_world_name,
               tw.name as to_world_name
        FROM resource_transfers rt
        JOIN factions ff ON rt.from_faction_id = ff.id
        JOIN factions tf ON rt.to_faction_id = tf.id
        JOIN worlds fw ON rt.from_world_id = fw.id
        JOIN worlds tw ON rt.to_world_id = tw.id
        WHERE rt.id = $1 {condition}
    """, *params)
    return dict(row) if row else None


async def get_intercepted_transfer(transfer_id: int, intercepting_faction_id: int) -> Optional[dict]:
    row = await db.fetchrow("""
        SELECT rt.*,
               ff.name as from_faction_name,
               tf.name as to_faction_name,
               fw.name as from_world_name,
               tw.name as to_world_name
        FROM resource_transfers rt
        JOIN factions ff ON rt.from_faction_id = ff.id
        JOIN factions tf ON rt.to_faction_id = tf.id
        JOIN worlds fw ON rt.from_world_id = fw.id
        JOIN worlds tw ON rt.to_world_id = tw.id
        WHERE rt.id = $1 AND rt.status = 'intercepted' AND rt.intercepting_faction_id = $2
    """, transfer_id, intercepting_faction_id)
    return dict(row) if row else None


async def get_transfer_resources(transfer_id: int) -> List[dict]:
    return await db.fetch("""
        SELECT tr.resource_id, tr.amount, r.name
        FROM transfer_resources tr
        JOIN resources r ON tr.resource_id = r.id
        WHERE tr.transfer_id = $1
    """, transfer_id)


async def get_fleets_at_world(faction_id: int, world_id: int) -> List[dict]:
    return await db.fetch("""
        SELECT f.id, f.name, f.faction_fleet_number, fs.name as status
        FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.faction_id = $1 AND f.position = $2
        ORDER BY f.faction_fleet_number
    """, faction_id, world_id)


async def check_blockade(world_id: int, faction_id: int) -> bool:
    row = await db.fetchrow("""
        SELECT b.id FROM blockades b
        JOIN blockade_targets bt ON b.id = bt.blockade_id
        WHERE b.world_id = $1 AND bt.faction_id = $2
    """, world_id, faction_id)
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
    await db.execute(
        "UPDATE faction_treasury SET amount = amount - $1 WHERE faction_id = $2 AND resource_id = $3",
        amount, from_faction_id, er_id
    )
    await db.execute("""
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = faction_treasury.amount + $3
    """, to_faction_id, er_id, amount)
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
) -> dict:
    travel_time = await calculate_travel_time(from_world_name, to_world_name, current_time)
    arrival_time = current_time + travel_time
    travel_str = await format_travel_time(travel_time)

    resources = {t['resource']: t['amount'] for t in transfers}
    transfer_id = await create_transfer(
        from_faction_id, to_faction_id,
        from_world_id, to_world_id,
        resources, current_time, arrival_time
    )
    return {
        'transfer_id': transfer_id,
        'arrival_time': arrival_time,
        'travel_str': travel_str,
    }


async def get_resource_name_to_id(resource_names: list[str]) -> dict:
    rows = await db.fetch("SELECT id, name FROM resources WHERE name = ANY($1)", resource_names)
    return {r['name']: r['id'] for r in rows}


async def get_world_for_faction(faction_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT w.id, w.name FROM worlds w
        JOIN world_factions wf ON w.id = wf.world_id
        WHERE wf.faction_id = $1 LIMIT 1
        """,
        faction_id,
    )
    return dict(row) if row else None


async def ensure_world_presence(world_id: int, faction_id: int):
    await db.execute(
        "INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, 0) ON CONFLICT DO NOTHING",
        world_id,
        faction_id,
    )


async def has_world_presence(world_id: int, faction_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT faction_id FROM world_factions WHERE world_id = $1 AND faction_id = $2",
        world_id,
        faction_id,
    )
    return row is not None


async def get_local_resource_amount(world_id: int, faction_id: int, resource_id: int) -> int:
    row = await db.fetchrow(
        "SELECT amount FROM local_treasury WHERE world_id = $1 AND faction_id = $2 AND resource_id = $3",
        world_id,
        faction_id,
        resource_id,
    )
    return row['amount'] if row else 0


async def list_pending_transfers(
    faction_id: Optional[int] = None,
    world_id: Optional[int] = None,
    filter_type: str = 'all',
) -> list[dict]:
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
    rows = await db.fetch(
        f"""
        SELECT rt.id, rt.status, rt.arrival_time,
               COALESCE(ff.formal_name, ff.name) as from_faction_name,
               COALESCE(tf.formal_name, tf.name) as to_faction_name,
               fw.name as from_world_name, tw.name as to_world_name,
               iw.name as interception_world_name,
               COALESCE(if_fac.formal_name, if_fac.name) as intercepting_faction_name
        FROM resource_transfers rt
        JOIN factions ff ON rt.from_faction_id = ff.id
        JOIN factions tf ON rt.to_faction_id = tf.id
        JOIN worlds fw ON rt.from_world_id = fw.id
        JOIN worlds tw ON rt.to_world_id = tw.id
        LEFT JOIN worlds iw ON rt.interception_world_id = iw.id
        LEFT JOIN factions if_fac ON rt.intercepting_faction_id = if_fac.id
        WHERE {where_clause} AND rt.status IN ('in_transit', 'intercepted')
        ORDER BY rt.arrival_time ASC
        """,
        *params,
    )
    return [dict(r) for r in rows]


async def get_transfer_resource_rows(transfer_ids: list[int]) -> list[dict]:
    if not transfer_ids:
        return []
    rows = await db.fetch(
        """
        SELECT tr.transfer_id, tr.amount, r.name
        FROM transfer_resources tr
        JOIN resources r ON tr.resource_id = r.id
        WHERE tr.transfer_id = ANY($1)
        """,
        transfer_ids,
    )
    return [dict(r) for r in rows]
