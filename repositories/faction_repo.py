# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
from typing import List, Optional

from database.db_manager import db
from dtos.faction import Faction


async def list_factions(long_sort: bool = False) -> List[Faction]:
    if long_sort:
        rows = await db.fetch("""
            SELECT * FROM factions
            ORDER BY LENGTH(COALESCE(formal_name, name)) DESC, name ASC
        """)
    else:
        rows = await db.fetch("SELECT * FROM factions ORDER BY name ASC")
    return Faction.from_rows(rows)


async def search_faction_names(current: str, limit: int = 25) -> List[str]:
    rows = await db.fetch(
        "SELECT name FROM factions WHERE LOWER(name) LIKE $1 OR LOWER(formal_name) LIKE $1 ORDER BY name LIMIT $2",
        f"%{current.lower()}%",
        limit,
    )
    return [r['name'] for r in rows]


async def get_faction_row_by_id(faction_id: int) -> Optional[Faction]:
    row = await db.fetchrow("SELECT * FROM factions WHERE id = $1", faction_id)
    return Faction.from_row(row) if row else None


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


async def find_faction_by_name_excluding(name: str, faction_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT id FROM factions WHERE LOWER(name) = $1 AND id != $2", name, faction_id
    )
    return dict(row) if row else None


async def update_faction_name(faction_id: int, new_name: str) -> None:
    await db.execute("UPDATE factions SET name = $1 WHERE id = $2", new_name, faction_id)


async def user_exists(user_id: int) -> bool:
    row = await db.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    return row is not None


async def update_faction_leader(faction_id: int, user_id: int) -> None:
    await db.execute("UPDATE factions SET leader_id = $1 WHERE id = $2", user_id, faction_id)


async def update_faction_details(set_clause: str, values: list) -> Optional[Faction]:
    row = await db.fetchrow(f"UPDATE factions SET {set_clause} RETURNING *", *values)
    return Faction.from_row(row) if row else None


async def get_faction_fleet_ids(faction_id: int) -> List[int]:
    rows = await db.fetch("SELECT id FROM fleets WHERE faction_id = $1", faction_id)
    return [r['id'] for r in rows]


async def get_faction_vehicles(faction_id: int) -> List[dict]:
    rows = await db.fetch(
        "SELECT id, type, name, designation, vehicle_data FROM vehicles WHERE faction_id = $1",
        faction_id,
    )
    return [dict(r) for r in rows]


async def get_pact_ids_led_by(faction_id: int) -> List[int]:
    rows = await db.fetch("SELECT id FROM pacts WHERE leader_id = $1", faction_id)
    return [r['id'] for r in rows]


async def get_transfer_ids_involving(faction_id: int) -> List[int]:
    rows = await db.fetch(
        "SELECT id FROM resource_transfers WHERE from_faction_id = $1 OR to_faction_id = $1 OR intercepting_faction_id = $1",
        faction_id,
    )
    return [r['id'] for r in rows]


async def delete_fleet_dependencies(fleet_ids: list) -> None:
    await asyncio.gather(
        db.execute("DELETE FROM battle_participants WHERE fleet_id = ANY($1)", fleet_ids),
        db.execute("DELETE FROM blockade_fleets WHERE fleet_id = ANY($1)", fleet_ids),
        db.execute("DELETE FROM vehicle_construction WHERE fleet_id = ANY($1)", fleet_ids),
        db.execute("DELETE FROM fleet_vehicles WHERE fleet_id = ANY($1)", fleet_ids),
    )


async def delete_faction_fleets(faction_id: int) -> None:
    await db.execute("DELETE FROM fleets WHERE faction_id = $1", faction_id)


async def get_external_vehicle_usages(vehicle_ids: list, faction_id: int) -> List[dict]:
    rows = await db.fetch("""
        SELECT fv.fleet_id, fv.vehicle_id, fv.amount, f.faction_id AS owner_faction_id
        FROM fleet_vehicles fv
        JOIN fleets f ON f.id = fv.fleet_id
        WHERE fv.vehicle_id = ANY($1) AND f.faction_id != $2
    """, vehicle_ids, faction_id)
    return [dict(r) for r in rows]


async def insert_vehicle_copy(conn, owner_faction_id: int, original: dict, number: int) -> int:
    row = await conn.fetchrow("""
        INSERT INTO vehicles (faction_id, type, name, designation, vehicle_data, faction_vehicle_number)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
    """, owner_faction_id, original['type'], original['name'], original['designation'],
        original['vehicle_data'], number)
    return row['id']


async def acquire_vehicle_number_lock(conn, lock_id: int, owner_faction_id: int) -> None:
    await conn.execute("SELECT pg_advisory_xact_lock($1, $2)", lock_id, owner_faction_id)


async def repoint_fleet_vehicles(updates: list) -> None:
    await db.executemany(
        "UPDATE fleet_vehicles SET vehicle_id = $1 WHERE fleet_id = $2 AND vehicle_id = $3",
        updates,
    )


async def delete_vehicle_dependencies(vehicle_ids: list) -> None:
    await asyncio.gather(
        db.execute("DELETE FROM fleet_vehicles WHERE vehicle_id = ANY($1)", vehicle_ids),
        db.execute("DELETE FROM vehicle_construction WHERE vehicle_id = ANY($1)", vehicle_ids),
    )


async def delete_faction_records(faction_id: int, led_pact_ids: list, transfer_ids: list) -> None:
    tasks = [
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
        tasks.append(db.execute("DELETE FROM pact_members WHERE pact_id = ANY($1)", led_pact_ids))
        tasks.append(db.execute("DELETE FROM pacts WHERE id = ANY($1)", led_pact_ids))
    if transfer_ids:
        tasks.append(db.execute("DELETE FROM transfer_resources WHERE transfer_id = ANY($1)", transfer_ids))
        tasks.append(db.execute("DELETE FROM resource_transfers WHERE id = ANY($1)", transfer_ids))
    await asyncio.gather(*tasks)


async def delete_faction(faction_id: int) -> None:
    await db.execute("DELETE FROM factions WHERE id = $1", faction_id)


async def get_faction_territories(faction_id: int) -> List[dict]:
    rows = await db.fetch(
        "SELECT world_id, territory FROM world_factions WHERE faction_id = $1", faction_id
    )
    return [dict(r) for r in rows]


async def merge_territories(territories: list, to_faction_id: int) -> None:
    await db.executemany("""
        INSERT INTO world_factions (world_id, faction_id, territory)
        VALUES ($1, $2, $3)
        ON CONFLICT (world_id, faction_id)
        DO UPDATE SET territory = world_factions.territory + EXCLUDED.territory
    """, [(t['world_id'], to_faction_id, t['territory']) for t in territories])


async def delete_faction_territories(faction_id: int) -> None:
    await db.execute("DELETE FROM world_factions WHERE faction_id = $1", faction_id)


def get_connection():
    return db.get_connection()


async def insert_faction(conn, name: str, formal_name: str, color: str, leader_name: str,
                         flag: str, leader_id: int, faction_type: int,
                         capital_world_id: Optional[int]) -> Faction:
    row = await conn.fetchrow("""
        INSERT INTO factions (name, formal_name, color, leader, flag, leader_id, faction_type, capital_world_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
    """, name, formal_name, color, leader_name, flag, leader_id, faction_type, capital_world_id)
    return Faction.from_row(row)


async def claim_starting_territory(conn, world_id: int, faction_id: int) -> None:
    await conn.execute(
        "INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, 50)",
        world_id, faction_id
    )


async def get_resource_id_by_name(conn, name: str) -> Optional[int]:
    row = await conn.fetchrow("SELECT id FROM resources WHERE name = $1", name)
    return row['id'] if row else None


async def get_resource_ids_by_names(conn, names: list) -> dict:
    rows = await conn.fetch("SELECT id, name FROM resources WHERE name = ANY($1)", names)
    return {r['name']: r['id'] for r in rows}


async def add_faction_treasury(conn, faction_id: int, resource_id: int, amount: int) -> None:
    await conn.execute("""
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = faction_treasury.amount + EXCLUDED.amount
    """, faction_id, resource_id, amount)


async def ensure_world_presence(conn, world_id: int, faction_id: int) -> None:
    await conn.execute("""
        INSERT INTO world_factions (world_id, faction_id, territory)
        VALUES ($1, $2, 0)
        ON CONFLICT (world_id, faction_id) DO NOTHING
    """, world_id, faction_id)


async def add_local_treasury(conn, faction_id: int, world_id: int, resource_id: int, amount: int) -> None:
    await conn.execute("""
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + EXCLUDED.amount
    """, faction_id, world_id, resource_id, amount)


async def add_starting_buildings(conn, faction_id: int, world_id: int, buildings: list) -> None:
    await conn.executemany("""
        INSERT INTO faction_world_buildings (faction_id, world_id, building_id, level, amount)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (faction_id, world_id, building_id, level)
        DO UPDATE SET amount = faction_world_buildings.amount + EXCLUDED.amount
    """, [(faction_id, world_id, b_id, level, amount) for b_id, level, amount in buildings])


async def get_world_hex_count(conn, world_id: int) -> Optional[int]:
    row = await conn.fetchrow("SELECT hex_count FROM worlds WHERE id = $1", world_id)
    return row['hex_count'] if row else None


async def get_world_claimed_territory(conn, world_id: int) -> int:
    row = await conn.fetchrow(
        "SELECT COALESCE(SUM(territory), 0) as claimed FROM world_factions WHERE world_id = $1",
        world_id
    )
    return row['claimed'] if row else 0


async def faction_name_exists(conn, name: str) -> bool:
    row = await conn.fetchrow("SELECT id FROM factions WHERE LOWER(name) = $1", name)
    return row is not None


async def user_is_registered(conn, user_id: int) -> bool:
    row = await conn.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
    return row is not None
