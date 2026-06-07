import asyncpg
import json
from typing import Optional
from database.db_manager import db


async def create_war(name: str, faction_id: int, side: str) -> int:
    try:
        row = await db.fetchrow(
            "SELECT sp_create_war($1, $2, $3) as war_id",
            name, faction_id, side
        )
        return row['war_id']
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def end_war(war_id: int, faction_id: int) -> dict:
    war = await db.fetchrow(
        "SELECT id, name, date_start FROM wars WHERE id = $1", war_id
    )
    if not war:
        return None

    stats = await db.fetch("""
        SELECT wp.side,
               COUNT(DISTINCT wp.faction_id) as faction_count,
               json_agg(COALESCE(f.formal_name, f.name)) as faction_names
        FROM war_participants wp
        JOIN factions f ON wp.faction_id = f.id
        WHERE wp.war_id = $1
        GROUP BY wp.side ORDER BY wp.side
    """, war_id)

    total_battles_row = await db.fetchrow(
        "SELECT COUNT(*) as count FROM battles WHERE war_id = $1", war_id
    )

    try:
        await db.execute("SELECT sp_end_war($1, $2)", war_id, faction_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e

    parsed_stats = []
    for s in stats:
        names = s['faction_names']
        if isinstance(names, str):
            try:
                names = json.loads(names)
            except json.JSONDecodeError:
                names = []
        if not isinstance(names, list):
            names = [str(names)]
        parsed_stats.append({'side': s['side'], 'faction_names': names})

    return {
        'war': dict(war),
        'stats': parsed_stats,
        'total_battles': total_battles_row['count'],
    }


async def get_war(war_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        "SELECT id, name, date_start FROM wars WHERE id = $1", war_id
    )
    return dict(row) if row else None


async def get_participant(war_id: int, faction_id: int) -> Optional[dict]:
    return await db.fetchrow(
        "SELECT side FROM war_participants WHERE war_id = $1 AND faction_id = $2",
        war_id, faction_id
    )


async def get_existing_war_for_faction(faction_id: int) -> Optional[dict]:
    return await db.fetchrow("""
        SELECT w.id, w.name, wp.side
        FROM wars w
        JOIN war_participants wp ON w.id = wp.war_id
        WHERE wp.faction_id = $1
    """, faction_id)


async def get_wars(faction_id=None) -> list:
    query = """
        SELECT w.id, w.name, w.date_start,
               COUNT(DISTINCT wp.faction_id) as faction_count,
               COUNT(DISTINCT b.id) as active_battles,
               json_agg(DISTINCT jsonb_build_object(
                   'side', wp.side,
                   'factions', (
                       SELECT json_agg(COALESCE(f2.formal_name, f2.name))
                       FROM war_participants wp2 JOIN factions f2 ON wp2.faction_id = f2.id
                       WHERE wp2.war_id = w.id AND wp2.side = wp.side
                   )
               )) FILTER (WHERE wp.side IS NOT NULL) as sides
        FROM wars w
        {join_clause}
        LEFT JOIN war_participants wp ON w.id = wp.war_id
        LEFT JOIN battles b ON w.id = b.war_id
        {where_clause}
        GROUP BY w.id, w.name, w.date_start
        ORDER BY w.date_start DESC
    """
    if faction_id:
        full_query = query.format(
            join_clause="JOIN war_participants wp_filter ON w.id = wp_filter.war_id AND wp_filter.faction_id = $1",
            where_clause=""
        )
        rows = await db.fetch(full_query, faction_id)
    else:
        full_query = query.format(join_clause="", where_clause="")
        rows = await db.fetch(full_query)
    return [dict(r) for r in rows]


async def join_war(war_id: int, faction_id: int, side: str) -> dict:
    war = await get_war(war_id)
    if not war:
        raise ValueError("War not found.")
    existing = await get_participant(war_id, faction_id)
    if existing:
        raise ValueError(f"Faction is already in this war on side {existing['side']}.")
    await db.execute("INSERT INTO war_participants (war_id, faction_id, side) VALUES ($1, $2, $3)", war_id, faction_id, side)
    stats = await db.fetch("""
        SELECT wp.side, json_agg(COALESCE(f.formal_name, f.name)) as faction_names
        FROM war_participants wp JOIN factions f ON wp.faction_id = f.id
        WHERE wp.war_id = $1 GROUP BY wp.side ORDER BY wp.side
    """, war_id)
    battle_count = await db.fetchrow("SELECT COUNT(*) as count FROM battles WHERE war_id = $1", war_id)
    return {'war': war, 'stats': [dict(s) for s in stats], 'battle_count': battle_count['count']}


async def leave_war(war_id: int, faction_id: int) -> dict:
    war = await get_war(war_id)
    if not war:
        raise ValueError("War not found.")
    if not await get_participant(war_id, faction_id):
        raise ValueError("Faction is not participating in this war.")
    await db.execute("DELETE FROM war_participants WHERE war_id = $1 AND faction_id = $2", war_id, faction_id)
    remaining = await db.fetchval("SELECT COUNT(*) FROM war_participants WHERE war_id = $1", war_id)
    war_ended = False
    if remaining == 0:
        battles = await db.fetch("SELECT id FROM battles WHERE war_id = $1", war_id)
        if battles:
            battle_ids = [b['id'] for b in battles]
            await db.execute("""
                UPDATE fleets SET status_id = (SELECT id FROM fleet_status WHERE name = 'Idle'), fighting_fleet_id = NULL
                WHERE id IN (SELECT fleet_id FROM battle_participants WHERE battle_id = ANY($1))
            """, battle_ids)
            await db.execute("DELETE FROM battle_participants WHERE battle_id = ANY($1)", battle_ids)
            await db.execute("DELETE FROM battles WHERE war_id = $1", war_id)
        await db.execute("DELETE FROM wars WHERE id = $1", war_id)
        war_ended = True
    return {'war': war, 'remaining': remaining, 'war_ended': war_ended}
