# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db
from dtos.casino import CasinoPool


def get_connection():
    return db.get_connection()


async def get_resource_id(conn, resource: str):
    return await conn.fetchval("SELECT id FROM resources WHERE name = $1", resource)


async def get_pool_row(resource: str):
    row = await db.fetchrow(
        """
        SELECT r.name AS resource, cp.amount, cp.floor_amount, cp.resource_id
        FROM casino_pool cp
        JOIN resources r ON r.id = cp.resource_id
        WHERE r.name = $1
        """,
        resource,
    )
    return CasinoPool.from_row(row) if row else None


async def get_all_pool_rows():
    rows = await db.fetch(
        """
        SELECT r.name AS resource, cp.amount, cp.floor_amount, cp.resource_id
        FROM casino_pool cp
        JOIN resources r ON r.id = cp.resource_id
        """
    )
    return CasinoPool.from_rows(rows)


async def credit_pool(conn, resource_id: int, amount: int):
    await conn.execute(
        "UPDATE casino_pool SET amount = amount + $2 WHERE resource_id = $1",
        resource_id, amount,
    )


async def get_pool_for_update(conn, resource_id: int):
    return await conn.fetchrow("SELECT amount FROM casino_pool WHERE resource_id = $1 FOR UPDATE", resource_id)


async def debit_pool(conn, resource_id: int, amount: int):
    await conn.execute(
        "UPDATE casino_pool SET amount = amount - $2 WHERE resource_id = $1",
        resource_id, amount,
    )


async def lock_pool_row(conn, res_id: int):
    row = await conn.fetchrow(
        "SELECT resource_id, amount, floor_amount FROM casino_pool WHERE resource_id = $1 FOR UPDATE",
        res_id,
    )
    return CasinoPool.from_row(row) if row else None


async def get_local_treasury_amount(conn, faction_id: int, world_id: int, res_id: int):
    return await conn.fetchval(
        "SELECT COALESCE(amount, 0) FROM local_treasury WHERE faction_id = $1 AND world_id = $2 AND resource_id = $3",
        faction_id, world_id, res_id,
    )


async def debit_local_treasury(conn, faction_id: int, world_id: int, res_id: int, amount: int):
    await conn.execute(
        "UPDATE local_treasury SET amount = amount - $4 WHERE faction_id = $1 AND world_id = $2 AND resource_id = $3",
        faction_id, world_id, res_id, amount,
    )


async def get_faction_treasury_amount(conn, faction_id: int, res_id: int):
    return await conn.fetchval(
        "SELECT COALESCE(amount, 0) FROM faction_treasury WHERE faction_id = $1 AND resource_id = $2",
        faction_id, res_id,
    )


async def debit_faction_treasury(conn, faction_id: int, res_id: int, amount: int):
    await conn.execute(
        "UPDATE faction_treasury SET amount = amount - $3 WHERE faction_id = $1 AND resource_id = $2",
        faction_id, res_id, amount,
    )


async def credit_local_treasury(conn, world_id: int, faction_id: int, res_id: int, amount: int):
    await conn.execute(
        """
        INSERT INTO local_treasury (world_id, faction_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (world_id, faction_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + $4
        """,
        world_id, faction_id, res_id, amount,
    )


async def credit_faction_treasury(conn, faction_id: int, res_id: int, amount: int):
    await conn.execute(
        """
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (faction_id, resource_id)
        DO UPDATE SET amount = faction_treasury.amount + $3
        """,
        faction_id, res_id, amount,
    )


async def get_all_pool_rows_for_update(conn):
    rows = await conn.fetch(
        """
        SELECT r.name AS resource, cp.resource_id, cp.amount, cp.floor_amount
        FROM casino_pool cp
        JOIN resources r ON r.id = cp.resource_id
        FOR UPDATE
        """
    )
    return CasinoPool.from_rows(rows)
