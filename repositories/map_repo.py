# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from database.db_manager import db
from dtos.map import FactionLandEntry, WorldFactionPresence


async def get_system_root_id(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("""
        WITH RECURSIVE system_tree AS (
            SELECT id, orbit_of FROM worlds WHERE id = $1
            UNION ALL
            SELECT w.id, w.orbit_of FROM worlds w
            INNER JOIN system_tree st ON w.id = st.orbit_of
        )
        SELECT id FROM system_tree WHERE orbit_of IS NULL
    """, world_id)
    return dict(row) if row else None


async def count_off_capital_system_hexes(faction_id: int, capital_system_id: int) -> Optional[dict]:
    row = await db.fetchrow("""
        WITH RECURSIVE capital_system AS (
            SELECT id FROM worlds WHERE id = $2
            UNION ALL
            SELECT w.id FROM worlds w INNER JOIN capital_system cs ON w.orbit_of = cs.id
        )
        SELECT COALESCE(SUM(wf.territory), 0) as total
        FROM world_factions wf
        WHERE wf.faction_id = $1 AND wf.territory > 0
          AND wf.world_id NOT IN (SELECT id FROM capital_system)
    """, faction_id, capital_system_id)
    return dict(row) if row else None


async def get_world(world_name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name, hex_count, population_capacity_per_hex FROM worlds WHERE LOWER(name) = LOWER($1)", world_name)
    return dict(row) if row else None


async def get_world_by_id(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id, name, hex_count, population_capacity_per_hex FROM worlds WHERE id = $1", world_id)
    return dict(row) if row else None


async def get_worlds_by_ids(world_ids: list[int]) -> list[dict]:
    rows = await db.fetch("SELECT id, name FROM worlds WHERE id = ANY($1::int[])", world_ids)
    return [dict(r) for r in rows]


async def search_world_names(current: str, limit: int) -> list[str]:
    rows = await db.fetch(
        "SELECT name FROM worlds WHERE LOWER(name) LIKE $1 ORDER BY name LIMIT $2",
        current,
        limit,
    )
    return [r['name'] for r in rows]


async def insert_world(name: str, orbit_of_id: int, background: Optional[str], population_capacity_per_hex: int, hex_count: int) -> int:
    row = await db.fetchrow("""
        INSERT INTO worlds (name, orbit_of, background, population_capacity_per_hex, hex_count)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
    """, name, orbit_of_id, background, population_capacity_per_hex, hex_count)
    return row['id']


async def get_resource_id_by_name(res_name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id FROM resources WHERE name = $1", res_name)
    return dict(row) if row else None


async def insert_world_resource(world_id: int, resource_id: int, percentage):
    await db.execute("INSERT INTO world_resources (world_id, resource_id, percentage) VALUES ($1, $2, $3)", world_id, resource_id, percentage)


async def count_child_worlds(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COUNT(*) as count FROM worlds WHERE orbit_of = $1", world_id)
    return dict(row) if row else None


async def count_fleets_at_world(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COUNT(*) as count FROM fleets WHERE position = $1", world_id)
    return dict(row) if row else None


async def delete_fleets_at_world(world_id: int):
    await db.execute("DELETE FROM fleets WHERE position = $1", world_id)


async def delete_world(world_id: int):
    await db.execute("DELETE FROM worlds WHERE id = $1", world_id)


async def count_territory_at_world(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COUNT(*) as count FROM world_factions WHERE world_id = $1", world_id)
    return dict(row) if row else None


async def sum_buildings_at_world(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COALESCE(SUM(amount), 0) as count FROM faction_world_buildings WHERE world_id = $1", world_id)
    return dict(row) if row else None


async def find_world_by_name(new_name: str) -> Optional[dict]:
    row = await db.fetchrow("SELECT id FROM worlds WHERE LOWER(name) = LOWER($1)", new_name)
    return dict(row) if row else None


async def update_world_name(world_id: int, new_name: str):
    await db.execute("UPDATE worlds SET name = $2 WHERE id = $1", world_id, new_name)


async def sum_claimed_territory(world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COALESCE(SUM(territory), 0) as claimed FROM world_factions WHERE world_id = $1", world_id)
    return dict(row) if row else None


async def update_world_fields(set_clause: str, params: list):
    await db.execute(f"UPDATE worlds SET {set_clause} WHERE id = $1", *params)


async def upsert_world_resource(world_id: int, resource_id: int, percentage):
    await db.execute("""
        INSERT INTO world_resources (world_id, resource_id, percentage) VALUES ($1, $2, $3)
        ON CONFLICT (world_id, resource_id) DO UPDATE SET percentage = $3
    """, world_id, resource_id, percentage)


async def get_world_faction_territory(world_id: int, faction_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COALESCE(territory, 0) as territory FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)
    return dict(row) if row else None


async def has_fleet_at_world(faction_id: int, world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT EXISTS (SELECT 1 FROM fleets f WHERE f.faction_id = $1 AND f.position = $2) as has_fleet", faction_id, world_id)
    return dict(row) if row else None


async def get_faction_capital_world_id(faction_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT capital_world_id FROM factions WHERE id = $1", faction_id)
    return dict(row) if row else None


async def get_faction_influence(faction_id: int) -> Optional[dict]:
    row = await db.fetchrow("""
        SELECT COALESCE(amount, 0) as influence FROM faction_treasury ft
        JOIN resources r ON ft.resource_id = r.id
        WHERE ft.faction_id = $1 AND r.name = 'Influence'
    """, faction_id)
    return dict(row) if row else None


async def get_influence_resource() -> Optional[dict]:
    row = await db.fetchrow("SELECT id FROM resources WHERE name = 'Influence'")
    return dict(row) if row else None


async def deduct_faction_influence(faction_id: int, resource_id: int, amount: int):
    await db.execute("UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2", faction_id, resource_id, amount)


async def claim_territory(world_id: int, faction_id: int, hexes: int):
    await db.execute("""
        INSERT INTO world_factions (world_id, faction_id, territory) VALUES ($1, $2, $3)
        ON CONFLICT (world_id, faction_id) DO UPDATE SET territory = world_factions.territory + EXCLUDED.territory
    """, world_id, faction_id, hexes)


async def get_world_faction_territory_row(world_id: int, faction_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT territory FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)
    return dict(row) if row else None


async def sum_faction_buildings_at_world(faction_id: int, world_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM faction_world_buildings WHERE faction_id = $1 AND world_id = $2", faction_id, world_id)
    return dict(row) if row else None


async def delete_world_faction(world_id: int, faction_id: int):
    await db.execute("DELETE FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)


async def update_world_faction_territory(world_id: int, faction_id: int, hexes: int):
    await db.execute("UPDATE world_factions SET territory = territory - $3 WHERE world_id = $1 AND faction_id = $2", world_id, faction_id, hexes)


async def get_faction_land(faction_id: int) -> List[FactionLandEntry]:
    rows = await db.fetch("""
        SELECT w.name, wf.territory FROM world_factions wf
        JOIN worlds w ON wf.world_id = w.id
        WHERE wf.faction_id = $1 AND wf.territory > 0
        ORDER BY wf.territory DESC, w.name
    """, faction_id)
    return FactionLandEntry.from_rows(rows)


async def get_world_factions(world_id: int) -> List[WorldFactionPresence]:
    rows = await db.fetch("""
        SELECT COALESCE(f.formal_name, f.name) as display_name, wf.territory, f.color
        FROM world_factions wf
        JOIN factions f ON wf.faction_id = f.id
        WHERE wf.world_id = $1 AND wf.territory > 0
        ORDER BY wf.territory DESC, display_name
    """, world_id)
    return WorldFactionPresence.from_rows(rows)


async def has_faction_presence(world_id: int, faction_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM world_factions WHERE world_id = $1 AND faction_id = $2",
        world_id,
        faction_id,
    )
    return row is not None
