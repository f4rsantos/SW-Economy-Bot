import asyncpg
import json
from datetime import datetime, timezone
from typing import Optional
from database.db_manager import db


async def create_war(name: str, faction_id: int, side: str) -> int:
    try:
        row = await db.fetchrow(
            "SELECT sp_create_war($1, $2, $3) as war_id",
            name, faction_id, side
        )
        await grant_war_spirits(faction_id)
        return row['war_id']
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def are_factions_at_war(faction_id_1: int, faction_id_2: int) -> bool:
    row = await db.fetchrow("""
        SELECT 1 FROM war_participants wp1
        JOIN war_participants wp2 ON wp1.war_id = wp2.war_id AND wp1.side != wp2.side
        WHERE wp1.faction_id = $1 AND wp2.faction_id = $2
    """, faction_id_1, faction_id_2)
    return row is not None


async def is_faction_at_war(faction_id: int) -> bool:
    row = await db.fetchrow("SELECT 1 FROM war_participants WHERE faction_id = $1", faction_id)
    return row is not None


WAR_SPIRIT_KEYS = ('war_effort', 'war_mobilization')


async def grant_war_spirits(faction_id: int) -> None:
    spirit_types = await db.fetch("SELECT id, fixed_value FROM spirit_types WHERE key = ANY($1)", list(WAR_SPIRIT_KEYS))
    for st in spirit_types:
        await db.execute(
            """
            INSERT INTO national_spirits (faction_id, spirit_type_id, modifier_value, expires_at)
            VALUES ($1, $2, $3, NULL)
            ON CONFLICT (faction_id, spirit_type_id) DO UPDATE SET modifier_value = EXCLUDED.modifier_value, expires_at = NULL
            """,
            faction_id, st['id'], st['fixed_value']
        )


async def revoke_war_spirits_if_not_at_war(faction_id: int) -> None:
    if await is_faction_at_war(faction_id):
        return
    await db.execute(
        "DELETE FROM national_spirits WHERE faction_id = $1 AND spirit_type_id IN (SELECT id FROM spirit_types WHERE key = ANY($2))",
        faction_id, list(WAR_SPIRIT_KEYS)
    )


async def end_war(war_id: int, faction_id: int, winning_sides: list[str], losing_sides: list[str]) -> dict:
    war = await db.fetchrow(
        "SELECT id, name, date_start FROM wars WHERE id = $1", war_id
    )
    if not war:
        return None

    participants = await db.fetch(
        "SELECT faction_id, side FROM war_participants WHERE war_id = $1", war_id
    )
    war_sides = {p['side'] for p in participants}
    overlap = set(winning_sides) & set(losing_sides)
    if overlap:
        raise ValueError(f"Side(s) {', '.join(sorted(overlap))} cannot be both winning and losing.")
    unknown = (set(winning_sides) | set(losing_sides)) - war_sides
    if unknown:
        raise ValueError(f"Side(s) {', '.join(sorted(unknown))} are not part of war #{war_id}.")

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

    spirit_type_rows = await db.fetch("SELECT id, key, fixed_value FROM spirit_types WHERE key IN ('victorious', 'recovering')")
    spirit_types = {r['key']: r for r in spirit_type_rows}

    war_days = (datetime.now(timezone.utc) - war['date_start']).days
    ramp = min(war_days / 50, 1.0)

    for p in participants:
        if p['side'] in winning_sides:
            spirit_type = spirit_types['victorious']
        elif p['side'] in losing_sides:
            spirit_type = spirit_types['recovering']
        else:
            continue
        scaled_value = spirit_type['fixed_value'] * ramp
        await db.execute(
            """
            INSERT INTO national_spirits (faction_id, spirit_type_id, modifier_value, expires_at) VALUES ($1, $2, $3, now())
            ON CONFLICT (faction_id, spirit_type_id) DO UPDATE SET modifier_value = EXCLUDED.modifier_value, granted_at = now(), expires_at = now()
            """,
            p['faction_id'], spirit_type['id'], scaled_value
        )

    try:
        await db.execute("SELECT sp_end_war($1, $2)", war_id, faction_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e

    for p in participants:
        await revoke_war_spirits_if_not_at_war(p['faction_id'])

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
        'winning_sides': winning_sides,
        'losing_sides': losing_sides,
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
    await grant_war_spirits(faction_id)
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
    await revoke_war_spirits_if_not_at_war(faction_id)
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
