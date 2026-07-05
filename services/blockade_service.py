import asyncpg
from typing import Optional, List
from database.db_manager import db


async def start_blockade(fleet_id: int, world_id: int, target_faction_ids: List[int]) -> int:
    import json
    try:
        row = await db.fetchrow(
            "SELECT sp_start_blockade($1, $2, $3) as blockade_id",
            fleet_id, world_id, target_faction_ids
        )
        return row['blockade_id']
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def end_blockade(blockade_id: int, fleet_id: Optional[int]):
    try:
        await db.execute("SELECT sp_end_blockade($1, $2)", blockade_id, fleet_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_blockade(blockade_id: int) -> Optional[dict]:
    row = await db.fetchrow("""
        SELECT b.id, b.world_id, w.name as world_name
        FROM blockades b
        JOIN worlds w ON b.world_id = w.id
        WHERE b.id = $1
    """, blockade_id)
    return dict(row) if row else None


async def get_blockade_targets(blockade_id: int) -> List[str]:
    rows = await db.fetch("""
        SELECT COALESCE(f.formal_name, f.name) as display_name
        FROM blockade_targets bt
        JOIN factions f ON bt.faction_id = f.id
        WHERE bt.blockade_id = $1
    """, blockade_id)
    return [r['display_name'] for r in rows]


async def get_fleet_in_blockade(blockade_id: int, faction_id: int, fleet_identifier: str) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT f.id, f.name FROM fleets f
        JOIN blockade_fleets bf ON f.id = bf.fleet_id
        WHERE bf.blockade_id = $1 AND f.faction_id = $2
          AND (f.id::text = $3 OR LOWER(f.name) = LOWER($3))
    """, blockade_id, faction_id, fleet_identifier)


async def get_my_fleet_in_blockade(blockade_id: int, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT f.id FROM fleets f
        JOIN blockade_fleets bf ON f.id = bf.fleet_id
        WHERE bf.blockade_id = $1 AND f.faction_id = $2
        LIMIT 1
    """, blockade_id, faction_id)


async def get_blockades(faction_id=None, world_id=None) -> list:
    _BASE_QUERY = """
        SELECT
            b.id,
            w.name as world_name,
            b.date_start,
            COALESCE(array_agg(DISTINCT COALESCE(f.formal_name, f.name)) FILTER (WHERE f.id IS NOT NULL), ARRAY[]::text[]) as targets,
            COUNT(DISTINCT bf.fleet_id) as fleet_count,
            COALESCE(array_agg(DISTINCT COALESCE(f2.formal_name, f2.name)) FILTER (WHERE f2.id IS NOT NULL), ARRAY[]::text[]) as blockading_factions
        FROM blockades b
        JOIN worlds w ON b.world_id = w.id
        LEFT JOIN blockade_targets bt ON b.id = bt.blockade_id
        LEFT JOIN factions f ON bt.faction_id = f.id
        LEFT JOIN blockade_fleets bf ON b.id = bf.blockade_id
        LEFT JOIN fleets fl ON bf.fleet_id = fl.id
        LEFT JOIN factions f2 ON fl.faction_id = f2.id
        {where_clause}
        GROUP BY b.id, w.name, b.date_start
        ORDER BY b.date_start DESC
    """
    if faction_id and world_id:
        q = _BASE_QUERY.format(where_clause="WHERE b.world_id = $1 AND (bt.faction_id = $2 OR fl.faction_id = $2)")
        rows = await db.fetch(q, world_id, faction_id)
    elif faction_id:
        q = _BASE_QUERY.format(where_clause="WHERE bt.faction_id = $1 OR fl.faction_id = $1")
        rows = await db.fetch(q, faction_id)
    elif world_id:
        q = _BASE_QUERY.format(where_clause="WHERE b.world_id = $1")
        rows = await db.fetch(q, world_id)
    else:
        q = _BASE_QUERY.format(where_clause="")
        rows = await db.fetch(q)
    return [dict(r) for r in rows]


async def get_fleet_for_blockade(fleet_identifier: str, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT f.id, f.name, f.position, w.name as position_name,
               f.status_id, fs.name as status_name
        FROM fleets f
        JOIN worlds w ON f.position = w.id
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.faction_id = $1 AND (f.id::text = $2 OR LOWER(f.name) = LOWER($2))
    """, faction_id, fleet_identifier)


async def count_blockade_fleets(blockade_id: int) -> int:
    count = await db.fetchval("SELECT COUNT(*) FROM blockade_fleets WHERE blockade_id = $1", blockade_id)
    return count or 0


async def get_blockading_fleet_for_world(world_id: int, target_faction_id: int) -> Optional[int]:
    row = await db.fetchrow("""
        SELECT bf.fleet_id
        FROM blockades b
        JOIN blockade_targets bt ON b.id = bt.blockade_id
        JOIN blockade_fleets bf ON b.id = bf.blockade_id
        WHERE b.world_id = $1 AND bt.faction_id = $2
        LIMIT 1
    """, world_id, target_faction_id)
    return row['fleet_id'] if row else None


async def check_belt_station_blockade(faction_id: int) -> bool:
    """Return True if faction is blockaded on Ceres or Vesta (blocks both /ceres and /vesta)."""
    row = await db.fetchrow("""
        SELECT b.id FROM blockades b
        JOIN blockade_targets bt ON b.id = bt.blockade_id
        JOIN worlds w ON b.world_id = w.id
        WHERE bt.faction_id = $1 AND LOWER(w.name) IN ('ceres', 'vesta')
    """, faction_id)
    return row is not None
