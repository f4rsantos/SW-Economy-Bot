# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from database.db_manager import db
from dtos.battle import Battle, BattleSideStat, BattleSummary


async def start_battle(war_id: int, fleet_id: int, side: str, world_id: int):
    return await db.fetchrow(
        "SELECT sp_start_battle($1, $2, $3, $4) as battle_id",
        war_id, fleet_id, side, world_id
    )


async def get_battle_stats(battle_id: int) -> List[BattleSideStat]:
    rows = await db.fetch("""
        SELECT bp.side,
               COUNT(DISTINCT bp.fleet_id) as fleet_count,
               COALESCE(SUM(f.total_cs), 0) as total_cs,
               COALESCE(AVG(f.health), 0) as avg_health
        FROM battle_participants bp
        JOIN fleets f ON bp.fleet_id = f.id
        WHERE bp.battle_id = $1
        GROUP BY bp.side ORDER BY bp.side
    """, battle_id)
    return BattleSideStat.from_rows(rows)


async def get_battle_fleet_count(battle_id: int) -> int:
    row = await db.fetchrow(
        "SELECT COUNT(*) as count FROM battle_participants WHERE battle_id = $1", battle_id
    )
    return row['count']


async def end_battle(battle_id: int, faction_id: int) -> None:
    await db.execute("SELECT sp_end_battle($1, $2)", battle_id, faction_id)


async def get_battle(battle_id: int) -> Optional[Battle]:
    row = await db.fetchrow("""
        SELECT b.id, b.war_id, b.world_id, w.name as world_name, b.date_start
        FROM battles b
        JOIN worlds w ON b.world_id = w.id
        WHERE b.id = $1
    """, battle_id)
    return Battle.from_row(row) if row else None


async def get_my_fleet_in_battle(battle_id: int, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT f.id FROM fleets f
        JOIN battle_participants bp ON f.id = bp.fleet_id
        WHERE bp.battle_id = $1 AND f.faction_id = $2
        LIMIT 1
    """, battle_id, faction_id)


async def damage_fleet(fleet_id: int, damage: int):
    await db.execute("SELECT sp_damage_fleet($1, $2)", fleet_id, damage)


async def repair_fleet(fleet_id: int, faction_id: int, repair_amount: int, costs_json):
    await db.execute(
        "SELECT sp_repair_fleet($1, $2, $3, $4::jsonb)",
        fleet_id, faction_id, repair_amount, costs_json
    )


async def get_fleet_costs(fleet_id: int) -> list:
    return await db.fetch("""
        SELECT r.name as resource_name, r.id as resource_id,
               SUM(fv.amount * vc.amount) as total_cost
        FROM fleet_vehicles fv
        JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
        JOIN resources r ON vc.resource_id = r.id
        WHERE fv.fleet_id = $1 AND r.name IN ('ER', 'CM', 'EL', 'CS')
        GROUP BY r.name, r.id
    """, fleet_id)


async def get_fleet_for_battle(fleet_identifier: str, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT f.id, f.name, f.position, w.name as position_name,
               f.status_id, fs.name as status_name, f.total_cs
        FROM fleets f
        JOIN worlds w ON f.position = w.id
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.faction_id = $1 AND (f.id::text = $2 OR LOWER(f.name) = LOWER($2))
    """, faction_id, fleet_identifier)


async def get_battles(faction_id=None, world_id=None) -> List[BattleSummary]:
    _SIDES_SUBQUERY = """
        COALESCE(json_agg(DISTINCT jsonb_build_object(
            'side', bp.side,
            'count', (SELECT COUNT(*) FROM battle_participants bp2 WHERE bp2.battle_id = b.id AND bp2.side = bp.side),
            'cs', (SELECT COALESCE(SUM(f2.total_cs), 0) FROM battle_participants bp2 JOIN fleets f2 ON bp2.fleet_id = f2.id WHERE bp2.battle_id = b.id AND bp2.side = bp.side),
            'factions', (SELECT json_agg(DISTINCT COALESCE(fa.formal_name, fa.name)) FROM battle_participants bp2 JOIN fleets f2 ON bp2.fleet_id = f2.id JOIN factions fa ON f2.faction_id = fa.id WHERE bp2.battle_id = b.id AND bp2.side = bp.side)
        )) FILTER (WHERE bp.side IS NOT NULL), '[]') as sides
    """
    base = f"""
        SELECT b.id, b.war_id, w.name as world_name, b.date_start,
               COUNT(DISTINCT bp.fleet_id) as fleet_count, {_SIDES_SUBQUERY}
        FROM battles b JOIN worlds w ON b.world_id = w.id
        LEFT JOIN battle_participants bp ON b.id = bp.battle_id
        {{join_clause}}
        {{where_clause}}
        GROUP BY b.id, b.war_id, w.name, b.date_start
        ORDER BY b.date_start DESC
    """
    if faction_id and world_id:
        q = base.format(
            join_clause="LEFT JOIN fleets f ON bp.fleet_id = f.id",
            where_clause="WHERE b.world_id = $1 AND f.faction_id = $2"
        )
        rows = await db.fetch(q, world_id, faction_id)
    elif faction_id:
        q = base.format(
            join_clause="LEFT JOIN fleets f ON bp.fleet_id = f.id",
            where_clause="WHERE b.id IN (SELECT DISTINCT b2.id FROM battles b2 JOIN battle_participants bp2 ON b2.id = bp2.battle_id JOIN fleets f2 ON bp2.fleet_id = f2.id WHERE f2.faction_id = $1)"
        )
        rows = await db.fetch(q, faction_id)
    elif world_id:
        q = base.format(join_clause="", where_clause="WHERE b.world_id = $1")
        rows = await db.fetch(q, world_id)
    else:
        q = base.format(join_clause="", where_clause="")
        rows = await db.fetch(q)
    return BattleSummary.from_rows(rows)


async def get_battle_participant_side(battle_id: int, fleet_id: int) -> Optional[dict]:
    return await db.fetchrow("SELECT side FROM battle_participants WHERE battle_id = $1 AND fleet_id = $2", battle_id, fleet_id)


async def insert_battle_participant(battle_id: int, fleet_id: int, side: str) -> None:
    await db.execute("INSERT INTO battle_participants (battle_id, fleet_id, side) VALUES ($1, $2, $3)", battle_id, fleet_id, side)


async def get_fleet_status_by_name(name: str) -> Optional[dict]:
    return await db.fetchrow("SELECT id FROM fleet_status WHERE LOWER(name) = $1", name)


async def set_fleet_status(fleet_id: int, status_id: int) -> None:
    await db.execute("UPDATE fleets SET status_id = $1 WHERE id = $2", status_id, fleet_id)


async def get_user_fleets_in_battle(battle_id: int, faction_id: int) -> list:
    return await db.fetch("""
        SELECT f.id, f.name FROM fleets f JOIN battle_participants bp ON f.id = bp.fleet_id
        WHERE bp.battle_id = $1 AND f.faction_id = $2
    """, battle_id, faction_id)


async def remove_battle_participants(battle_id: int, fleet_ids: list) -> None:
    await db.execute("DELETE FROM battle_participants WHERE battle_id = $1 AND fleet_id = ANY($2)", battle_id, fleet_ids)


async def set_fleets_status(fleet_ids: list, status_id: int) -> None:
    await db.execute("UPDATE fleets SET status_id = $1, fighting_fleet_id = NULL WHERE id = ANY($2)", status_id, fleet_ids)


async def count_battle_participants(battle_id: int) -> int:
    return await db.fetchval("SELECT COUNT(*) FROM battle_participants WHERE battle_id = $1", battle_id)


async def delete_battle(battle_id: int) -> None:
    await db.execute("DELETE FROM battles WHERE id = $1", battle_id)


async def create_war(name: str):
    return await db.fetchrow(
        "INSERT INTO wars (name, date_start) VALUES ($1, CURRENT_TIMESTAMP) RETURNING id",
        name
    )


async def add_war_participant(war_id: int, faction_id: int, side: str) -> None:
    await db.execute(
        "INSERT INTO war_participants (war_id, faction_id, side) VALUES ($1, $2, $3)",
        war_id, faction_id, side
    )


async def get_fleet_side_in_battle(battle_id: int, fleet_id: int) -> Optional[str]:
    row = await db.fetchrow(
        "SELECT side FROM battle_participants WHERE battle_id = $1 AND fleet_id = $2",
        battle_id,
        fleet_id,
    )
    return row['side'] if row else None
