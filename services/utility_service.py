from typing import Optional
from database.db_manager import db
from database.cache_manager import cache_manager


async def get_operator_for_player(discord_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id FROM operators WHERE discord_id = $1 AND locked = false", discord_id)
    return dict(row) if row else None


async def get_user_access_row(user_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT access_level, badge_ids FROM users WHERE id = $1", user_id)
    return dict(row) if row else None


async def set_custom_message_for_user(target_user_id: int, message: str, created_by: int):
    await db.execute(
        "INSERT INTO custom_user_messages (user_id, message, created_by) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET message = EXCLUDED.message, created_by = EXCLUDED.created_by",
        target_user_id,
        message,
        created_by,
    )
    cache_manager.set_custom_message(target_user_id, message)


async def delete_custom_message_for_user(target_user_id: int):
    await db.execute("DELETE FROM custom_user_messages WHERE user_id = $1", target_user_id)
    cache_manager.set_custom_message(target_user_id, None)


async def get_custom_message_for_user(target_user_id: int) -> Optional[str]:
    row = await db.fetchrow("SELECT message FROM custom_user_messages WHERE user_id = $1", target_user_id)
    return row['message'] if row else None


async def get_badge_by_identifier(badge: str) -> Optional[dict]:
    try:
        row = await db.fetchrow("SELECT id, name FROM badges WHERE id = $1", int(badge))
    except ValueError:
        row = await db.fetchrow("SELECT id, name FROM badges WHERE LOWER(name) = LOWER($1)", badge)
    return dict(row) if row else None


async def badge_name_exists(name: str) -> bool:
    row = await db.fetchrow("SELECT id FROM badges WHERE LOWER(name) = LOWER($1)", name)
    return row is not None


async def create_badge(name: str) -> int:
    row = await db.fetchrow("INSERT INTO badges (name) VALUES ($1) RETURNING id", name)
    return row['id']


async def get_all_badges() -> list[dict]:
    rows = await db.fetch("SELECT id, name FROM badges ORDER BY name ASC")
    return [dict(r) for r in rows]


async def add_badge_to_user(user_id: int, badge_id: int):
    await db.execute(
        "UPDATE users SET badge_ids = array_append(COALESCE(badge_ids, ARRAY[]::integer[]), $1) WHERE id = $2",
        badge_id,
        user_id,
    )


async def remove_badge_from_user(user_id: int, badge_id: int):
    await db.execute("UPDATE users SET badge_ids = array_remove(badge_ids, $1) WHERE id = $2", badge_id, user_id)


async def get_badge_names_for_user(user_id: int) -> list[str]:
    rows = await db.fetch(
        """
        SELECT b.name FROM users u
        LEFT JOIN badges b ON b.id = ANY(u.badge_ids)
        WHERE u.id = $1 ORDER BY b.name ASC
        """,
        user_id,
    )
    return [r['name'] for r in rows if r['name']]


async def get_recent_completed_transfers_count(minutes: int = 5) -> int:
    row = await db.fetchrow(
        """
        SELECT COUNT(*) as count
        FROM resource_transfers rt
        JOIN transfer_statuses ts ON rt.status_id = ts.id
        WHERE ts.name = 'completed' AND rt.arrival_time >= NOW() - ($1::text || ' minutes')::interval
        """,
        minutes,
    )
    return int(row['count'] or 0)


async def get_all_factions_min() -> list[dict]:
    rows = await db.fetch("SELECT id, name FROM factions")
    return [dict(r) for r in rows]


async def get_status_resource_cache() -> dict:
    statuses = await db.fetch("SELECT id, name FROM fleet_status")
    resources = await db.fetch("SELECT id, name FROM resources")
    return {
        'status_ids': {s['name'].lower(): s['id'] for s in statuses},
        'resource_map': {r['name']: r['id'] for r in resources},
    }


async def recalc_fleet_cs_for_faction(faction_id: int) -> int:
    result = await db.execute(
        """
        UPDATE fleets SET total_cs = (
            SELECT COALESCE(SUM(fv.amount * vc.amount), 0)
            FROM fleet_vehicles fv
            JOIN vehicle_costs vc ON fv.vehicle_id = vc.vehicle_id
            JOIN resources r ON vc.resource_id = r.id AND r.name = 'CS'
            WHERE fv.fleet_id = fleets.id
        )
        WHERE faction_id = $1
        """,
        faction_id,
    )
    return int(result.split()[-1]) if result and result.startswith("UPDATE") else 0


async def get_public_table_names_for_backup() -> list[str]:
    rows = await db.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename NOT IN ('auths', 'operators', 'operator_refresh_tokens', 'operator_assets') "
        "ORDER BY tablename"
    )
    return [r['tablename'] for r in rows]


async def get_all_rows_for_table(table_name: str) -> list[dict]:
    rows = await db.fetch(f"SELECT * FROM {table_name}")
    return [dict(r) for r in rows]
