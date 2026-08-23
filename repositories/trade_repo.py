# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
import asyncpg
from database.db_manager import db
from dtos.trade import Trade, TradeSummary


_TRADE_QUERY = """
    SELECT td.id, td.amount, r.name as resource_name,
           COALESCE(f.formal_name, f.name) as {other_col},
           sw.name as sender_world, rw.name as receiver_world
    FROM trade_deals td
    JOIN resources r ON td.resource_id = r.id
    JOIN factions f ON {other_join}
    LEFT JOIN worlds sw ON td.sender_world_id = sw.id
    LEFT JOIN worlds rw ON td.receiver_world_id = rw.id
    WHERE {where_col} = $1
    ORDER BY td.id
"""


async def insert_trade(sender_faction_id: int, receiver_faction_id: int, resource_id: int,
                       amount: int, sender_world_id: Optional[int], receiver_world_id: Optional[int],
                       escort_fleet_id: Optional[int] = None) -> int:
    row = await db.fetchrow(
        "INSERT INTO trade_deals (sender_faction_id, receiver_faction_id, resource_id, amount, sender_world_id, receiver_world_id, escort_fleet_id) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        sender_faction_id, receiver_faction_id, resource_id, amount, sender_world_id, receiver_world_id, escort_fleet_id
    )
    return row['id']


async def get_trade_row(trade_id: int) -> Optional[Trade]:
    row = await db.fetchrow("""
        SELECT td.id, td.amount, r.name as resource_name,
               COALESCE(fs.formal_name, fs.name) as sender_name, fs.color as sender_color,
               COALESCE(fr.formal_name, fr.name) as receiver_name
        FROM trade_deals td
        JOIN resources r ON td.resource_id = r.id
        JOIN factions fs ON td.sender_faction_id = fs.id
        JOIN factions fr ON td.receiver_faction_id = fr.id
        WHERE td.id = $1
    """, trade_id)
    return Trade.from_row(row) if row else None


async def delete_trade(trade_id: int) -> None:
    await db.execute("DELETE FROM trade_deals WHERE id = $1", trade_id)


async def get_faction_trades_rows(faction_id: int) -> dict:
    outgoing = await db.fetch(_TRADE_QUERY.format(
        other_col="receiver_name", other_join="td.receiver_faction_id = f.id", where_col="td.sender_faction_id"
    ), faction_id)
    incoming = await db.fetch(_TRADE_QUERY.format(
        other_col="sender_name", other_join="td.sender_faction_id = f.id", where_col="td.receiver_faction_id"
    ), faction_id)
    return {
        'outgoing': TradeSummary.from_rows(outgoing, "receiver_name"),
        'incoming': TradeSummary.from_rows(incoming, "sender_name"),
    }


async def get_world_by_name(world_name: str) -> Optional[dict]:
    return await db.fetchrow("SELECT id FROM worlds WHERE LOWER(name) = LOWER($1)", world_name)


async def get_world_faction_presence(world_id: int, faction_id: int) -> Optional[dict]:
    return await db.fetchrow("SELECT faction_id FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_id, faction_id)


async def get_named_delivery_world(world_name: str, faction_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT w.id, w.name FROM worlds w
        JOIN world_factions wf ON w.id = wf.world_id
        WHERE LOWER(w.name) = LOWER($1) AND wf.faction_id = $2
        """,
        world_name,
        faction_id,
    )
    return dict(row) if row else None


async def get_default_delivery_world(faction_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT w.id, w.name FROM world_factions wf
        JOIN worlds w ON wf.world_id = w.id
        WHERE wf.faction_id = $1 LIMIT 1
        """,
        faction_id,
    )
    return dict(row) if row else None


async def call_ceres_trade(faction_id: int, world_id: int, src_name: str, src_amt: int, gain: str, refund: int) -> None:
    await db.execute(
        "SELECT sp_ceres_trade($1, $2, $3, $4, $5, $6)",
        faction_id, world_id, src_name, src_amt, gain, refund,
    )
