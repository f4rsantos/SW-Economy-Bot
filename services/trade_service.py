# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
import asyncpg
from dtos.trade import Trade
from repositories import trade_repo


async def begin_trade(sender_faction_id: int, receiver_faction_id: int, resource_id: int,
                      amount: int, sender_world_id: Optional[int], receiver_world_id: Optional[int],
                      escort_fleet_id: Optional[int] = None) -> int:
    return await trade_repo.insert_trade(
        sender_faction_id, receiver_faction_id, resource_id, amount,
        sender_world_id, receiver_world_id, escort_fleet_id
    )


async def get_trade(trade_id: int) -> Optional[Trade]:
    return await trade_repo.get_trade_row(trade_id)


async def end_trade(trade_id: int) -> Trade:
    trade = await get_trade(trade_id)
    if not trade:
        raise ValueError("Trade not found.")
    await trade_repo.delete_trade(trade_id)
    return trade


async def get_faction_trades(faction_id: int) -> dict:
    return await trade_repo.get_faction_trades_rows(faction_id)


async def validate_world_for_trade(world_name: str, faction_id: int) -> int:
    world_row = await trade_repo.get_world_by_name(world_name)
    if not world_row:
        raise ValueError(f"World '{world_name}' not found.")
    if not await trade_repo.get_world_faction_presence(world_row['id'], faction_id):
        raise ValueError(f"Faction has no territory on {world_name}.")
    return world_row['id']


async def get_trade_delivery_world(faction_id: int, world_name: Optional[str] = None) -> dict:
    if world_name:
        world_row = await trade_repo.get_named_delivery_world(world_name, faction_id)
        if not world_row:
            raise ValueError(f"World '{world_name}' not found or faction has no presence there.")
        return world_row

    default_world = await trade_repo.get_default_delivery_world(faction_id)
    if not default_world:
        raise ValueError("Faction has no world presence.")
    return default_world


async def execute_ceres_trade(faction_id: int, world_id: int, gain: str, costs: list[tuple[int, str]]):
    try:
        for src_amt, src_name in costs:
            await trade_repo.call_ceres_trade(faction_id, world_id, src_name, src_amt, gain, src_amt // 4)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e
