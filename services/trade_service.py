from typing import Optional
import asyncpg
from database.db_manager import db


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


async def begin_trade(sender_faction_id: int, receiver_faction_id: int, resource_id: int,
                      amount: int, sender_world_id: Optional[int], receiver_world_id: Optional[int],
                      escort_fleet_id: Optional[int] = None) -> int:
    row = await db.fetchrow(
        "INSERT INTO trade_deals (sender_faction_id, receiver_faction_id, resource_id, amount, sender_world_id, receiver_world_id, escort_fleet_id) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        sender_faction_id, receiver_faction_id, resource_id, amount, sender_world_id, receiver_world_id, escort_fleet_id
    )
    return row['id']


async def get_trade(trade_id: int) -> Optional[dict]:
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
    return dict(row) if row else None


async def end_trade(trade_id: int) -> dict:
    trade = await get_trade(trade_id)
    if not trade:
        raise ValueError("Trade not found.")
    await db.execute("DELETE FROM trade_deals WHERE id = $1", trade_id)
    return trade


async def get_faction_trades(faction_id: int) -> dict:
    outgoing = await db.fetch(_TRADE_QUERY.format(
        other_col="receiver_name", other_join="td.receiver_faction_id = f.id", where_col="td.sender_faction_id"
    ), faction_id)
    incoming = await db.fetch(_TRADE_QUERY.format(
        other_col="sender_name", other_join="td.sender_faction_id = f.id", where_col="td.receiver_faction_id"
    ), faction_id)
    return {'outgoing': [dict(r) for r in outgoing], 'incoming': [dict(r) for r in incoming]}


async def validate_world_for_trade(world_name: str, faction_id: int) -> int:
    world_row = await db.fetchrow("SELECT id FROM worlds WHERE LOWER(name) = LOWER($1)", world_name)
    if not world_row:
        raise ValueError(f"World '{world_name}' not found.")
    if not await db.fetchrow("SELECT faction_id FROM world_factions WHERE world_id = $1 AND faction_id = $2", world_row['id'], faction_id):
        raise ValueError(f"Faction has no territory on {world_name}.")
    return world_row['id']


async def get_trade_delivery_world(faction_id: int, world_name: Optional[str] = None) -> dict:
    if world_name:
        world_row = await db.fetchrow(
            """
            SELECT w.id, w.name FROM worlds w
            JOIN world_factions wf ON w.id = wf.world_id
            WHERE LOWER(w.name) = LOWER($1) AND wf.faction_id = $2
            """,
            world_name,
            faction_id,
        )
        if not world_row:
            raise ValueError(f"World '{world_name}' not found or faction has no presence there.")
        return dict(world_row)

    default_world = await db.fetchrow(
        """
        SELECT w.id, w.name FROM world_factions wf
        JOIN worlds w ON wf.world_id = w.id
        WHERE wf.faction_id = $1 LIMIT 1
        """,
        faction_id,
    )
    if not default_world:
        raise ValueError("Faction has no world presence.")
    return dict(default_world)


async def execute_ceres_trade(faction_id: int, world_id: int, gain: str, costs: list[tuple[int, str]]):
    try:
        for src_amt, src_name in costs:
            await db.execute(
                "SELECT sp_ceres_trade($1, $2, $3, $4, $5, $6)",
                faction_id, world_id, src_name, src_amt, gain, src_amt // 4,
            )
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e
