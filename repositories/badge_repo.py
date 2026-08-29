# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db
from dtos.badge import BadgeCostRow, BadgeProgressRow, BadgeInfo


def get_connection():
    return db.get_connection()


async def get_badge_catalog_rows() -> list[BadgeCostRow]:
    return BadgeCostRow.from_rows(await db.fetch(
        """
        SELECT b.id, b.name, b.needs_world, b.icon_url, r.name AS resource_name, bc.amount
        FROM badges b
        JOIN badge_costs bc ON b.id = bc.badge_id
        JOIN resources r ON r.id = bc.resource_id
        WHERE b.is_purchasable = true
        ORDER BY b.id, r.name
        """
    ))


async def get_badge_names(badge_ids: list[int]) -> dict[int, str]:
    rows = await db.fetch("SELECT id, name FROM badges WHERE id = ANY($1)", badge_ids)
    return {r['id']: r['name'] for r in rows}


async def get_badges_info(badge_ids: list[int]) -> list[BadgeInfo]:
    return BadgeInfo.from_rows(await db.fetch(
        "SELECT id, name, icon_url FROM badges WHERE id = ANY($1) ORDER BY name",
        badge_ids
    ))


async def user_has_badge(user_id: int, badge_id: int) -> bool:
    return bool(await db.fetchval(
        "SELECT $1 = ANY(COALESCE(badge_ids, ARRAY[]::integer[])) FROM users WHERE id = $2",
        badge_id, user_id
    ))


async def get_user_badge_ids(user_id: int) -> list:
    return await db.fetchval("SELECT COALESCE(badge_ids, ARRAY[]::integer[]) FROM users WHERE id = $1", user_id)


async def get_user_badge_ids_for_update(conn, user_id: int, badge_id: int):
    return await conn.fetchval(
        "SELECT $1 = ANY(COALESCE(badge_ids, ARRAY[]::integer[])) FROM users WHERE id = $2 FOR UPDATE",
        badge_id, user_id
    )


async def append_badge_to_user(conn, user_id: int, badge_id: int) -> None:
    await conn.execute(
        """
        UPDATE users
        SET badge_ids = array_append(COALESCE(badge_ids, ARRAY[]::integer[]), $1)
        WHERE id = $2 AND NOT ($1 = ANY(COALESCE(badge_ids, ARRAY[]::integer[])))
        """,
        badge_id, user_id
    )


async def get_badge_progress_rows(user_id: int, badge_id: int) -> list[BadgeProgressRow]:
    return BadgeProgressRow.from_rows(await db.fetch(
        """
        SELECT r.name AS resource_name, bpr.current_amount
        FROM badge_progress_resources bpr
        JOIN resources r ON r.id = bpr.resource_id
        WHERE bpr.user_id = $1 AND bpr.badge_id = $2
        """,
        user_id, badge_id
    ))


async def upsert_badge_progress_resource(user_id: int, badge_id: int, resource_name: str, amount: int) -> dict:
    return await db.fetchrow(
        """
        INSERT INTO badge_progress_resources (user_id, badge_id, resource_id, current_amount, updated_at)
        VALUES ($1, $2, (SELECT id FROM resources WHERE name = $3), $4, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, badge_id, resource_id)
        DO UPDATE SET current_amount = badge_progress_resources.current_amount + $4,
                      updated_at = CURRENT_TIMESTAMP
        RETURNING current_amount
        """,
        user_id, badge_id, resource_name, amount
    )


async def delete_badge_progress(user_id: int, badge_id: int) -> None:
    await db.execute(
        "DELETE FROM badge_progress_resources WHERE user_id = $1 AND badge_id = $2",
        user_id, badge_id
    )
