# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import replace

from dtos.casino import CasinoPool
from repositories import casino_repo

CASINO_RESOURCES = ('ER', 'CM', 'EL', 'CS')

LOCAL_RESOURCES = {'CM', 'EL', 'CS'}

RICH_MULTIPLIER = 10
TABLE_MAX_PCT_AT_FLOOR = 0.20
TABLE_MAX_PCT_AT_RICH = 0.05

EDGE_AT_FLOOR = 0.12
EDGE_AT_RICH = 0.04
EDGE_MIN = 0.05

TRIM_THRESHOLD_MULTIPLIER = 3
TRIM_EXCESS_FRACTION = 0.25


def _health_ratio(pool_amount: float, floor: float) -> float:
    if floor <= 0:
        return 0.0
    rich_amount = floor * RICH_MULTIPLIER
    span = rich_amount - floor
    if span <= 0:
        return 1.0
    ratio = (pool_amount - floor) / span
    return max(0.0, min(1.0, ratio))


def table_max_for_pool(pool_amount: float, floor: float) -> int:
    ratio = _health_ratio(pool_amount, floor)
    pct = TABLE_MAX_PCT_AT_FLOOR + (TABLE_MAX_PCT_AT_RICH - TABLE_MAX_PCT_AT_FLOOR) * ratio
    return int(pool_amount * pct)


def edge_for_pool(pool_amount: float, floor: float) -> float:
    ratio = _health_ratio(pool_amount, floor)
    edge = EDGE_AT_FLOOR + (EDGE_AT_RICH - EDGE_AT_FLOOR) * ratio
    return max(EDGE_MIN, edge)


def trim_amount_for_pool(pool_amount: float, floor: float) -> int:
    threshold = floor * TRIM_THRESHOLD_MULTIPLIER
    if pool_amount <= threshold:
        return 0
    excess = pool_amount - threshold
    return int(excess * TRIM_EXCESS_FRACTION)


async def _resource_id_by_name(conn, resource: str) -> int:
    res_id = await casino_repo.get_resource_id(conn, resource)
    if not res_id:
        raise ValueError(f"RESOURCE_NOT_FOUND: Unknown resource {resource}")
    return res_id


async def get_pool(resource: str) -> CasinoPool:
    row = await casino_repo.get_pool_row(resource)
    if not row:
        raise ValueError(f"POOL_NOT_FOUND: No casino pool configured for {resource}")
    return row


async def get_all_pools() -> dict:
    rows = await casino_repo.get_all_pool_rows()
    return {r.resource: r for r in rows}


async def get_table_max(resource: str) -> int:
    pool = await get_pool(resource)
    return table_max_for_pool(pool.amount, pool.floor_amount)


async def get_current_edge(resource: str) -> float:
    pool = await get_pool(resource)
    return edge_for_pool(pool.amount, pool.floor_amount)


async def credit_pool(conn, resource_id: int, amount: int):
    if amount <= 0:
        return
    await casino_repo.credit_pool(conn, resource_id, amount)


async def debit_pool(conn, resource_id: int, amount: int):
    if amount <= 0:
        return
    row = await casino_repo.get_pool_for_update(conn, resource_id)
    if not row or row["amount"] < amount:
        raise ValueError("POOL_INSUFFICIENT: Casino pool cannot cover this payout")
    await casino_repo.debit_pool(conn, resource_id, amount)


async def lock_pool(conn, resource: str) -> CasinoPool:
    res_id = await _resource_id_by_name(conn, resource)
    row = await casino_repo.lock_pool_row(conn, res_id)
    if not row:
        raise ValueError(f"POOL_NOT_FOUND: No casino pool configured for {resource}")
    return replace(row, resource=resource)


async def deduct_wager_from_faction(conn, faction_id: int, world_id: int, resource: str, amount: int, res_id: int = None):
    if res_id is None:
        res_id = await _resource_id_by_name(conn, resource)

    if resource in LOCAL_RESOURCES:
        if world_id is None:
            raise ValueError("WORLD_REQUIRED: A world is required for this resource")
        available = await casino_repo.get_local_treasury_amount(conn, faction_id, world_id, res_id) or 0
        if available < amount:
            raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {resource}. Need {amount:,}, have {available:,}")
        await casino_repo.debit_local_treasury(conn, faction_id, world_id, res_id, amount)
    else:
        available = await casino_repo.get_faction_treasury_amount(conn, faction_id, res_id) or 0
        if available < amount:
            raise ValueError(f"RESOURCE_INSUFFICIENT: Insufficient {resource}. Need {amount:,}, have {available:,}")
        await casino_repo.debit_faction_treasury(conn, faction_id, res_id, amount)
    return res_id


async def pay_winnings_to_faction(conn, faction_id: int, world_id: int, resource: str, res_id: int, amount: int):
    if amount <= 0:
        return
    if resource in LOCAL_RESOURCES:
        await casino_repo.credit_local_treasury(conn, world_id, faction_id, res_id, amount)
    else:
        await casino_repo.credit_faction_treasury(conn, faction_id, res_id, amount)


async def validate_wager(resource: str, wager: int, max_possible_multiplier: float) -> dict:
    pool = await get_pool(resource)
    table_max = table_max_for_pool(pool.amount, pool.floor_amount)
    if wager > table_max:
        raise ValueError(
            f"TABLE_LIMIT: The table limit for {resource} is {table_max:,}. Your wager of {wager:,} exceeds it"
        )
    max_payout = int(wager * max_possible_multiplier)
    if max_payout > pool.amount:
        raise ValueError(
            f"POOL_INSUFFICIENT: The {resource} pool cannot cover the maximum possible payout of this bet"
        )
    edge = edge_for_pool(pool.amount, pool.floor_amount)
    return {'pool': pool, 'table_max': table_max, 'edge': edge}


async def settle_bet(
    faction_id: int,
    world_id: int,
    resource: str,
    wager: int,
    payout_multiplier: float,
) -> dict:
    if wager <= 0:
        raise ValueError("Wager must be greater than zero.")

    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            pool = await lock_pool(conn, resource)
            res_id = pool.resource_id
            table_max = table_max_for_pool(pool.amount, pool.floor_amount)
            if wager > table_max:
                raise ValueError(
                    f"TABLE_LIMIT: The table limit for {resource} is {table_max:,}. Your wager of {wager:,} exceeds it"
                )

            payout = int(wager * payout_multiplier)

            await deduct_wager_from_faction(conn, faction_id, world_id, resource, wager, res_id)
            await credit_pool(conn, res_id, wager)

            if payout > 0:
                pool_available = pool.amount + wager
                if payout > pool_available:
                    payout = pool_available
                await debit_pool(conn, res_id, payout)
                await pay_winnings_to_faction(conn, faction_id, world_id, resource, res_id, payout)

            net = payout - wager

            return {
                'resource': resource,
                'wager': wager,
                'payout': payout,
                'net': net,
                'pool_before': pool.amount,
            }


async def open_chicken_round(faction_id: int, world_id: int, resource: str, wager: int) -> dict:
    if wager <= 0:
        raise ValueError("Wager must be greater than zero.")

    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            pool = await lock_pool(conn, resource)
            res_id = pool.resource_id
            table_max = table_max_for_pool(pool.amount, pool.floor_amount)
            if wager > table_max:
                raise ValueError(
                    f"TABLE_LIMIT: The table limit for {resource} is {table_max:,}. Your wager of {wager:,} exceeds it"
                )

            edge = edge_for_pool(pool.amount, pool.floor_amount)
            from utils.casino_games import chicken_max_multiplier
            max_multiplier = chicken_max_multiplier(edge)
            max_payout = int(wager * max_multiplier)
            if max_payout > pool.amount:
                raise ValueError(
                    f"POOL_INSUFFICIENT: The {resource} pool cannot cover the maximum possible payout of this bet"
                )

            await deduct_wager_from_faction(conn, faction_id, world_id, resource, wager, res_id)
            await credit_pool(conn, res_id, wager)

            return {
                'resource': resource,
                'wager': wager,
                'edge': edge,
                'res_id': res_id,
                'pool_before': pool.amount,
            }


async def close_chicken_round_cashout(faction_id: int, world_id: int, resource: str, res_id: int, wager: int, payout_multiplier: float) -> dict:
    payout = int(wager * payout_multiplier)

    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            pool = await casino_repo.get_pool_for_update(conn, res_id)
            if not pool:
                raise ValueError(f"POOL_NOT_FOUND: No casino pool configured for {resource}")
            if payout > pool["amount"]:
                payout = pool["amount"]

            if payout > 0:
                await debit_pool(conn, res_id, payout)
                await pay_winnings_to_faction(conn, faction_id, world_id, resource, res_id, payout)

            return {'resource': resource, 'wager': wager, 'payout': payout, 'net': payout - wager}


async def close_chicken_round_crash(resource: str, res_id: int, wager: int) -> dict:
    return {'resource': resource, 'wager': wager, 'payout': 0, 'net': -wager}


async def close_chicken_round_refund(faction_id: int, world_id: int, resource: str, res_id: int, wager: int) -> dict:
    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            await debit_pool(conn, res_id, wager)
            await pay_winnings_to_faction(conn, faction_id, world_id, resource, res_id, wager)
    return {'resource': resource, 'wager': wager, 'payout': wager, 'net': 0}


async def open_blackjack_round(faction_id: int, world_id: int, resource: str, wager: int) -> dict:
    if wager <= 0:
        raise ValueError("Wager must be greater than zero.")

    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            pool = await lock_pool(conn, resource)
            res_id = pool.resource_id
            table_max = table_max_for_pool(pool.amount, pool.floor_amount)
            if wager > table_max:
                raise ValueError(
                    f"TABLE_LIMIT: The table limit for {resource} is {table_max:,}. Your wager of {wager:,} exceeds it"
                )

            edge = edge_for_pool(pool.amount, pool.floor_amount)
            from utils.casino_games import blackjack_max_multiplier
            max_multiplier = blackjack_max_multiplier()
            max_payout = int(wager * max_multiplier)
            if max_payout > pool.amount:
                raise ValueError(
                    f"POOL_INSUFFICIENT: The {resource} pool cannot cover the maximum possible payout of this bet"
                )

            await deduct_wager_from_faction(conn, faction_id, world_id, resource, wager, res_id)
            await credit_pool(conn, res_id, wager)

            return {
                'resource': resource,
                'wager': wager,
                'edge': edge,
                'res_id': res_id,
                'pool_before': pool.amount,
            }


async def close_blackjack_round(faction_id: int, world_id: int, resource: str, res_id: int, wager: int, payout_multiplier: float) -> dict:
    payout = int(wager * payout_multiplier)

    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            pool = await casino_repo.get_pool_for_update(conn, res_id)
            if not pool:
                raise ValueError(f"POOL_NOT_FOUND: No casino pool configured for {resource}")
            if payout > pool["amount"]:
                payout = pool["amount"]

            if payout > 0:
                await debit_pool(conn, res_id, payout)
                await pay_winnings_to_faction(conn, faction_id, world_id, resource, res_id, payout)

            return {'resource': resource, 'wager': wager, 'payout': payout, 'net': payout - wager}


async def apply_weekly_trim() -> list[dict]:
    results = []
    async with casino_repo.get_connection() as conn:
        async with conn.transaction():
            rows = await casino_repo.get_all_pool_rows_for_update(conn)
            for row in rows:
                trimmed = trim_amount_for_pool(row.amount, row.floor_amount)
                if trimmed > 0:
                    await casino_repo.debit_pool(conn, row.resource_id, trimmed)
                results.append({
                    'resource': row.resource,
                    'pool_before': row.amount,
                    'pool_after': row.amount - trimmed,
                    'trimmed': trimmed,
                })
    return results
