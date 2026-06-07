import asyncio
from typing import Optional
from database.db_manager import db
from database.cache_manager import cache_manager


async def list_factions(long_sort: bool = False) -> list:
    if long_sort:
        rows = await db.fetch("""
            SELECT id, name, formal_name, COALESCE(formal_name, name) as display_name, color, leader, is_company
            FROM factions ORDER BY LENGTH(COALESCE(formal_name, name)) DESC, name ASC
        """)
    else:
        rows = await db.fetch("""
            SELECT id, name, formal_name, COALESCE(formal_name, name) as display_name, color, leader, is_company
            FROM factions ORDER BY name ASC
        """)
    return [dict(r) for r in rows]


async def search_faction_names(current: str, limit: int = 25) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM factions WHERE LOWER(name) LIKE $1 OR LOWER(formal_name) LIKE $1 ORDER BY name LIMIT $2",
        f"%{current.lower()}%",
        limit,
    )
    return [r['name'] for r in rows]


async def get_faction_row_by_id(faction_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT * FROM factions WHERE id = $1", faction_id)
    return dict(row) if row else None


async def get_faction_territory_summary(faction_id: int) -> dict:
    row = await db.fetchrow(
        "SELECT COUNT(*) as world_count, COALESCE(SUM(territory), 0) as total_territory FROM world_factions WHERE faction_id = $1",
        faction_id,
    )
    return {'world_count': row['world_count'] or 0, 'total_territory': row['total_territory'] or 0}


async def get_faction_leader_role_id(faction_id: int) -> Optional[int]:
    row = await db.fetchrow("SELECT leader FROM factions WHERE id = $1", faction_id)
    if not row:
        return None
    return row['leader']


async def rename_faction(faction_id: int, new_name: str):
    existing = await db.fetchrow("SELECT id FROM factions WHERE LOWER(name) = $1 AND id != $2", new_name, faction_id)
    if existing:
        raise ValueError(f"A faction with the name '{new_name}' already exists.")
    await db.execute("UPDATE factions SET name = $1 WHERE id = $2", new_name, faction_id)
    cache_manager.invalidate_faction(faction_id)


async def set_leader(faction_id: int, user_id: int):
    user_exists = await db.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    if not user_exists:
        raise ValueError(f"User {user_id} is not registered in the database.")
    await db.execute("UPDATE factions SET leader_id = $1 WHERE id = $2", user_id, faction_id)
    cache_manager.invalidate_faction(faction_id)


async def update_faction_details(faction_id: int, color: Optional[str], leader_treatment: Optional[str],
                                 formal_name: Optional[str], flag: Optional[str]) -> dict:
    updates = []
    values = []
    param_count = 1
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
    updated = await db.fetchrow(f"UPDATE factions SET {', '.join(updates)} WHERE id = ${param_count} RETURNING *", *values)
    cache_manager.set_faction(faction_id, dict(updated))
    return dict(updated)


async def delete_faction(faction_id: int):
    fleet_rows, vehicle_rows, led_pact_rows, transfer_rows = await asyncio.gather(
        db.fetch("SELECT id FROM fleets WHERE faction_id = $1", faction_id),
        db.fetch("SELECT id, type, name, designation, vehicle_data FROM vehicles WHERE faction_id = $1", faction_id),
        db.fetch("SELECT id FROM pacts WHERE leader_id = $1", faction_id),
        db.fetch("SELECT id FROM resource_transfers WHERE from_faction_id = $1 OR to_faction_id = $1 OR intercepting_faction_id = $1", faction_id),
    )

    fleet_ids = [r['id'] for r in fleet_rows]
    if fleet_ids:
        await asyncio.gather(
            db.execute("DELETE FROM battle_participants WHERE fleet_id = ANY($1)", fleet_ids),
            db.execute("DELETE FROM blockade_fleets WHERE fleet_id = ANY($1)", fleet_ids),
            db.execute("DELETE FROM vehicle_construction WHERE fleet_id = ANY($1)", fleet_ids),
            db.execute("DELETE FROM fleet_vehicles WHERE fleet_id = ANY($1)", fleet_ids),
        )
    await db.execute("DELETE FROM fleets WHERE faction_id = $1", faction_id)

    vehicle_ids = [r['id'] for r in vehicle_rows]
    vehicle_map = {r['id']: r for r in vehicle_rows}
    if vehicle_ids:
        external_usages = await db.fetch("""
            SELECT fv.fleet_id, fv.vehicle_id, fv.amount, f.faction_id AS owner_faction_id
            FROM fleet_vehicles fv
            JOIN fleets f ON f.id = fv.fleet_id
            WHERE fv.vehicle_id = ANY($1) AND f.faction_id != $2
        """, vehicle_ids, faction_id)
        if external_usages:
            next_num_cache: dict = {}

            async def get_next_vehicle_num(f_id: int) -> int:
                if f_id not in next_num_cache:
                    row = await db.fetchrow(
                        "SELECT COALESCE(MAX(faction_vehicle_number), 0) + 1 AS n FROM vehicles WHERE faction_id = $1", f_id
                    )
                    next_num_cache[f_id] = row['n']
                else:
                    next_num_cache[f_id] += 1
                return next_num_cache[f_id]

            copy_map: dict = {}
            for usage in external_usages:
                key = (usage['owner_faction_id'], usage['vehicle_id'])
                if key not in copy_map:
                    orig = vehicle_map[usage['vehicle_id']]
                    num = await get_next_vehicle_num(usage['owner_faction_id'])
                    new_id = await db.fetchrow("""
                        INSERT INTO vehicles (faction_id, type, name, designation, vehicle_data, faction_vehicle_number)
                        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
                    """, usage['owner_faction_id'], orig['type'], orig['name'], orig['designation'], orig['vehicle_data'], num)
                    copy_map[key] = new_id['id']
            for usage in external_usages:
                key = (usage['owner_faction_id'], usage['vehicle_id'])
                await db.execute(
                    "UPDATE fleet_vehicles SET vehicle_id = $1 WHERE fleet_id = $2 AND vehicle_id = $3",
                    copy_map[key], usage['fleet_id'], usage['vehicle_id']
                )
        await asyncio.gather(
            db.execute("DELETE FROM fleet_vehicles WHERE vehicle_id = ANY($1)", vehicle_ids),
            db.execute("DELETE FROM vehicle_construction WHERE vehicle_id = ANY($1)", vehicle_ids),
        )

    led_pact_ids = [r['id'] for r in led_pact_rows]
    transfer_ids = [r['id'] for r in transfer_rows]

    gather_tasks = [
        db.execute("DELETE FROM vehicles WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM pact_members WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM war_participants WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM blockade_targets WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM trade_deals WHERE sender_faction_id = $1 OR receiver_faction_id = $1", faction_id),
        db.execute("DELETE FROM faction_world_buildings WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM faction_treasury WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM local_treasury WHERE faction_id = $1", faction_id),
        db.execute("DELETE FROM world_factions WHERE faction_id = $1", faction_id),
    ]
    if led_pact_ids:
        gather_tasks.append(db.execute("DELETE FROM pact_members WHERE pact_id = ANY($1)", led_pact_ids))
        gather_tasks.append(db.execute("DELETE FROM pacts WHERE id = ANY($1)", led_pact_ids))
    if transfer_ids:
        gather_tasks.append(db.execute("DELETE FROM transfer_resources WHERE transfer_id = ANY($1)", transfer_ids))
        gather_tasks.append(db.execute("DELETE FROM resource_transfers WHERE id = ANY($1)", transfer_ids))

    await asyncio.gather(*gather_tasks)
    await db.execute("DELETE FROM factions WHERE id = $1", faction_id)
    cache_manager.invalidate_faction(faction_id)


async def merge_aux(from_faction_id: int, to_faction_id: int) -> dict:
    territories = await db.fetch("SELECT world_id, territory FROM world_factions WHERE faction_id = $1", from_faction_id)
    if not territories:
        raise ValueError("Source faction has no territories to transfer.")
    for t in territories:
        await db.execute("""
            INSERT INTO world_factions (world_id, faction_id, territory)
            VALUES ($1, $2, $3)
            ON CONFLICT (world_id, faction_id)
            DO UPDATE SET territory = world_factions.territory + EXCLUDED.territory
        """, t['world_id'], to_faction_id, t['territory'])
    await db.execute("DELETE FROM world_factions WHERE faction_id = $1", from_faction_id)
    await db.execute("DELETE FROM factions WHERE id = $1", from_faction_id)
    cache_manager.invalidate_faction(from_faction_id)
    return {'territories_transferred': len(territories)}


async def create_faction_in_db(conn, name: str, formal_name: str, color: str, leader_name: str,
                               flag: str, leader_id: int, is_company: bool, starting_world_id: Optional[int]) -> dict:
    faction = await conn.fetchrow("""
        INSERT INTO factions (name, formal_name, color, leader, flag, leader_id, is_company)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, name, formal_name, color, leader, flag, leader_id, is_company
    """, name, formal_name, color, leader_name, flag, leader_id, is_company)
    if starting_world_id and not is_company:
        await conn.execute("INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, 50)", starting_world_id, faction['id'])
    if starting_world_id:
        await _initialize_faction_assets(conn, faction['id'], starting_world_id, faction['is_company'])
    return dict(faction)


async def _initialize_faction_assets(conn, faction_id: int, world_id: Optional[int], is_company: bool = False):
    er_res = await conn.fetchrow("SELECT id FROM resources WHERE name = 'ER'")
    if er_res:
        await conn.execute("""
            INSERT INTO faction_treasury (faction_id, resource_id, amount)
            VALUES ($1, $2, 50000000000)
            ON CONFLICT (faction_id, resource_id)
            DO UPDATE SET amount = faction_treasury.amount + EXCLUDED.amount
        """, faction_id, er_res['id'])
    if not world_id:
        return
    if is_company:
        await conn.execute("""
            INSERT INTO world_factions (world_id, faction_id, territory)
            VALUES ($1, $2, 0)
            ON CONFLICT (world_id, faction_id) DO NOTHING
        """, world_id, faction_id)
    rows = await conn.fetch("SELECT id, name FROM resources WHERE name = ANY($1)", ['CM', 'CS', 'EL', 'Population'])
    res_map = {r['name']: r['id'] for r in rows}
    for name in ['CM', 'CS', 'EL']:
        if name in res_map:
            await conn.execute("""
                INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
                VALUES ($1, $2, $3, 100000)
                ON CONFLICT (faction_id, world_id, resource_id)
                DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
            """, faction_id, world_id, res_map[name])
    if not is_company and 'Population' in res_map:
        await conn.execute("""
            INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
            VALUES ($1, $2, $3, 40000000)
            ON CONFLICT (faction_id, world_id, resource_id)
            DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
        """, faction_id, world_id, res_map['Population'])
    if is_company:
        buildings = [(9, 1, 1), (11, 1, 1), (10, 1, 1), (13, 1, 1), (15, 1, 1), (14, 1, 1)]
    else:
        buildings = [
            (1, 10, 4), (2, 1, 3), (4, 1, 3), (3, 1, 2),
            (5, 1, 3), (7, 1, 3), (6, 1, 2),
            (9, 1, 1), (11, 1, 1), (10, 1, 1),
            (13, 1, 1), (15, 1, 1), (14, 1, 1), (16, 1, 1),
        ]
    for b_id, level, amount in buildings:
        await conn.execute("""
            INSERT INTO faction_world_buildings (faction_id, world_id, building_id, level, amount)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (faction_id, world_id, building_id, level)
            DO UPDATE SET amount = faction_world_buildings.amount + EXCLUDED.amount
        """, faction_id, world_id, b_id, level, amount)


async def check_world_space(conn, world_id: int) -> bool:
    world_check = await conn.fetchrow("SELECT hex_count FROM worlds WHERE id = $1", world_id)
    if not world_check:
        return False
    claimed = await conn.fetchrow("SELECT COALESCE(SUM(territory), 0) as claimed FROM world_factions WHERE world_id = $1", world_id)
    return world_check['hex_count'] - (claimed['claimed'] if claimed else 0) >= 50
