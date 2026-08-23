# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db


def get_connection():
    return db.get_connection()


async def get_resource_id(conn, name: str):
    return await conn.fetchval("SELECT id FROM resources WHERE name = $1", name)


async def get_faction_treasury_amount(conn, faction_id: int, resource_id: int):
    return await conn.fetchval(
        "SELECT COALESCE(amount, 0) FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id
    )


async def get_local_treasury_total(conn, faction_id: int, resource_id: int):
    return await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM local_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id
    )


async def credit_faction_treasury(conn, faction_id: int, resource_id: int, amount: int) -> None:
    await conn.execute("""
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = faction_treasury.amount + $3
    """, faction_id, resource_id, amount)


async def debit_faction_treasury(conn, faction_id: int, resource_id: int, amount: int) -> None:
    await conn.execute(
        "UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2",
        faction_id, resource_id, amount
    )


async def get_top_territory_world(conn, faction_id: int):
    return await conn.fetchval("""
        SELECT world_id FROM world_factions
        WHERE faction_id = $1
        ORDER BY territory DESC
        LIMIT 1
    """, faction_id)


async def credit_local_treasury(conn, world_id: int, faction_id: int, resource_id: int, amount: int) -> None:
    await conn.execute("""
        INSERT INTO local_treasury (world_id, faction_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (world_id, faction_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + $4
    """, world_id, faction_id, resource_id, amount)


async def get_alloys_id() -> int:
    return await db.fetchval("SELECT id FROM resources WHERE name = 'Alloys'")


async def get_faction_alloys_amount(faction_id: int, alloys_id: int):
    row = await db.fetchrow(
        "SELECT COALESCE(amount, 0) AS amount FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, alloys_id
    )
    return row['amount'] if row else 0
