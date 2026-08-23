# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import List, Optional
from database.db_manager import db
from dtos.war import War, WarSideStat, WarSummary


async def create_war_sp(name: str, faction_id: int, side: str) -> dict:
    return await db.fetchrow(
        "SELECT sp_create_war($1, $2, $3) as war_id",
        name, faction_id, side
    )


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


async def get_spirit_types_by_keys(keys: list) -> list:
    return await db.fetch("SELECT id, fixed_value FROM spirit_types WHERE key = ANY($1)", keys)


async def upsert_national_spirit(faction_id: int, spirit_type_id: int, modifier_value) -> None:
    await db.execute(
        """
        INSERT INTO national_spirits (faction_id, spirit_type_id, modifier_value, expires_at)
        VALUES ($1, $2, $3, NULL)
        ON CONFLICT (faction_id, spirit_type_id) DO UPDATE SET modifier_value = EXCLUDED.modifier_value, expires_at = NULL
        """,
        faction_id, spirit_type_id, modifier_value
    )


async def delete_war_spirits(faction_id: int, keys: list) -> None:
    await db.execute(
        "DELETE FROM national_spirits WHERE faction_id = $1 AND spirit_type_id IN (SELECT id FROM spirit_types WHERE key = ANY($2))",
        faction_id, keys
    )


async def get_war_row(war_id: int) -> Optional[War]:
    row = await db.fetchrow(
        "SELECT id, name, date_start FROM wars WHERE id = $1", war_id
    )
    return War.from_row(row) if row else None


async def get_war_participants(war_id: int) -> list:
    return await db.fetch(
        "SELECT faction_id, side FROM war_participants WHERE war_id = $1", war_id
    )


async def get_war_side_stats(war_id: int) -> List[WarSideStat]:
    rows = await db.fetch("""
        SELECT wp.side,
               COUNT(DISTINCT wp.faction_id) as faction_count,
               json_agg(COALESCE(f.formal_name, f.name)) as faction_names
        FROM war_participants wp
        JOIN factions f ON wp.faction_id = f.id
        WHERE wp.war_id = $1
        GROUP BY wp.side ORDER BY wp.side
    """, war_id)
    return WarSideStat.from_rows(rows)


async def get_total_battles(war_id: int) -> dict:
    return await db.fetchrow(
        "SELECT COUNT(*) as count FROM battles WHERE war_id = $1", war_id
    )


async def get_victorious_recovering_spirit_types() -> list:
    return await db.fetch("SELECT id, key, fixed_value FROM spirit_types WHERE key IN ('victorious', 'recovering')")


async def upsert_national_spirit_ended(faction_id: int, spirit_type_id: int, scaled_value) -> None:
    await db.execute(
        """
        INSERT INTO national_spirits (faction_id, spirit_type_id, modifier_value, expires_at) VALUES ($1, $2, $3, now())
        ON CONFLICT (faction_id, spirit_type_id) DO UPDATE SET modifier_value = EXCLUDED.modifier_value, granted_at = now(), expires_at = now()
        """,
        faction_id, spirit_type_id, scaled_value
    )


async def end_war_sp(war_id: int, faction_id: int) -> None:
    await db.execute("SELECT sp_end_war($1, $2)", war_id, faction_id)


async def get_war(war_id: int) -> Optional[War]:
    row = await db.fetchrow(
        "SELECT id, name, date_start FROM wars WHERE id = $1", war_id
    )
    return War.from_row(row) if row else None


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


async def get_wars(faction_id=None) -> List[WarSummary]:
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
    return WarSummary.from_rows(rows)


async def insert_war_participant(war_id: int, faction_id: int, side: str) -> None:
    await db.execute("INSERT INTO war_participants (war_id, faction_id, side) VALUES ($1, $2, $3)", war_id, faction_id, side)


async def get_war_join_stats(war_id: int) -> List[WarSideStat]:
    rows = await db.fetch("""
        SELECT wp.side, json_agg(COALESCE(f.formal_name, f.name)) as faction_names
        FROM war_participants wp JOIN factions f ON wp.faction_id = f.id
        WHERE wp.war_id = $1 GROUP BY wp.side ORDER BY wp.side
    """, war_id)
    return WarSideStat.from_rows(rows)


async def get_battle_count(war_id: int) -> dict:
    return await db.fetchrow("SELECT COUNT(*) as count FROM battles WHERE war_id = $1", war_id)


async def delete_war_participant(war_id: int, faction_id: int) -> None:
    await db.execute("DELETE FROM war_participants WHERE war_id = $1 AND faction_id = $2", war_id, faction_id)


async def count_war_participants(war_id: int) -> int:
    return await db.fetchval("SELECT COUNT(*) FROM war_participants WHERE war_id = $1", war_id)


async def get_battles(war_id: int) -> list:
    return await db.fetch("SELECT id FROM battles WHERE war_id = $1", war_id)


async def reset_fleets_for_battles(battle_ids: list) -> None:
    await db.execute("""
        UPDATE fleets SET status_id = (SELECT id FROM fleet_status WHERE name = 'Idle'), fighting_fleet_id = NULL
        WHERE id IN (SELECT fleet_id FROM battle_participants WHERE battle_id = ANY($1))
    """, battle_ids)


async def delete_battle_participants(battle_ids: list) -> None:
    await db.execute("DELETE FROM battle_participants WHERE battle_id = ANY($1)", battle_ids)


async def delete_battles(war_id: int) -> None:
    await db.execute("DELETE FROM battles WHERE war_id = $1", war_id)


async def delete_war(war_id: int) -> None:
    await db.execute("DELETE FROM wars WHERE id = $1", war_id)
