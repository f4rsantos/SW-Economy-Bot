# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Awaitable, Callable, Dict, List

from database.db_manager import db
from dtos.spend import WeeklySpendTotal


async def record_spend(faction_id: int, resources: Dict[str, int], direction: int) -> None:
    if not resources:
        return
    rows = await db.fetch("SELECT id, name FROM resources WHERE name = ANY($1)", list(resources.keys()))
    name_to_id = {r['name']: r['id'] for r in rows}
    for name, amount in resources.items():
        if amount <= 0:
            continue
        resource_id = name_to_id.get(name)
        if resource_id is None:
            continue
        await db.execute("""
            INSERT INTO faction_weekly_spend (faction_id, resource_id, direction, amount)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (faction_id, resource_id, direction)
            DO UPDATE SET amount = faction_weekly_spend.amount + $4
        """, faction_id, resource_id, direction, int(amount))


async def reset_and_report(on_reset: Callable[[List[WeeklySpendTotal]], Awaitable[bool]]) -> List[WeeklySpendTotal]:
    async with db.get_connection() as conn:
        async with conn.transaction():
            rows = await conn.fetch("""
                WITH reset AS (
                    DELETE FROM faction_weekly_spend
                    RETURNING resource_id, amount, direction
                )
                SELECT r.name AS resource_name,
                       SUM(reset.amount * reset.direction) AS amount
                FROM reset
                JOIN resources r ON r.id = reset.resource_id
                GROUP BY r.name
                HAVING SUM(reset.amount * reset.direction) != 0
                ORDER BY r.name
            """)
            totals = WeeklySpendTotal.from_rows(rows)
            success = await on_reset(totals)
            if not success:
                raise RuntimeError("weekly spend report failed, rolling back reset")
            return totals


async def reset_snapshot_and_report(on_reset: Callable[[List[WeeklySpendTotal]], Awaitable[bool]]) -> List[WeeklySpendTotal]:
    async with db.get_connection() as conn:
        async with conn.transaction():
            reset_rows = await conn.fetch("""
                DELETE FROM faction_weekly_spend
                RETURNING faction_id, resource_id, amount, direction
            """)

            await conn.execute("TRUNCATE faction_last_cycle_spend")
            if reset_rows:
                await conn.executemany("""
                    INSERT INTO faction_last_cycle_spend (faction_id, resource_id, direction, amount)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (faction_id, resource_id, direction)
                    DO UPDATE SET amount = faction_last_cycle_spend.amount + $4
                """, [(r['faction_id'], r['resource_id'], r['direction'], r['amount']) for r in reset_rows])

            rows = await conn.fetch("""
                SELECT r.name AS resource_name,
                       SUM(fls.amount * fls.direction) AS amount
                FROM faction_last_cycle_spend fls
                JOIN resources r ON r.id = fls.resource_id
                GROUP BY r.name
                HAVING SUM(fls.amount * fls.direction) != 0
                ORDER BY r.name
            """)
            totals = WeeklySpendTotal.from_rows(rows)
            success = await on_reset(totals)
            if not success:
                raise RuntimeError("weekly spend report failed, rolling back reset")
            return totals
