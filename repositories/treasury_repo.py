# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Dict, List, Optional

from database.db_manager import db
from dtos.treasury import LocalTreasuryEntry


async def find_world_with_resource(faction_id: int, resource_id: int, amount: int) -> Optional[int]:
    row = await db.fetchrow("""
        SELECT world_id FROM local_treasury
        WHERE faction_id = $1 AND resource_id = $2 AND amount >= $3
        ORDER BY amount DESC LIMIT 1
    """, faction_id, resource_id, amount)
    return row['world_id'] if row else None


async def get_world_resources(faction_id: int, world_id: int, resource_ids: list) -> Dict[int, int]:
    rows = await db.fetch("""
        SELECT resource_id, amount FROM local_treasury
        WHERE faction_id = $1 AND world_id = $2 AND resource_id = ANY($3)
    """, faction_id, world_id, resource_ids)
    return {r['resource_id']: r['amount'] for r in rows}


async def get_local_amounts_for_resources(faction_id: int, resource_ids: list) -> List[LocalTreasuryEntry]:
    rows = await db.fetch("""
        SELECT world_id, resource_id, amount FROM local_treasury
        WHERE faction_id = $1 AND resource_id = ANY($2)
    """, faction_id, resource_ids)
    return LocalTreasuryEntry.from_rows(rows)


async def get_local_amount(faction_id: int, world_id: int, resource_id: int) -> Optional[int]:
    row = await db.fetchrow(
        "SELECT amount FROM local_treasury WHERE faction_id = $1 AND world_id = $2 AND resource_id = $3",
        faction_id, world_id, resource_id
    )
    return row['amount'] if row else None


async def subtract_from_world(faction_id: int, world_id: int, resource_id: int, amount: int) -> None:
    await db.execute(
        "UPDATE local_treasury SET amount = amount - $1 WHERE faction_id = $2 AND world_id = $3 AND resource_id = $4",
        amount, faction_id, world_id, resource_id
    )


async def set_local_resource(faction_id: int, world_id: int, resource_id: int, amount: int) -> None:
    await db.execute("""
        INSERT INTO local_treasury (world_id, faction_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (world_id, faction_id, resource_id) DO UPDATE SET amount = $4
    """, world_id, faction_id, resource_id, amount)


async def set_faction_resource(faction_id: int, resource_id: int, amount: int) -> None:
    await db.execute("""
        INSERT INTO faction_treasury (faction_id, resource_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT (faction_id, resource_id) DO UPDATE SET amount = $3
    """, faction_id, resource_id, amount)


async def deposit_to_world(faction_id: int, world_id: int, resource_id: int, amount: int) -> None:
    await db.execute("""
        INSERT INTO local_treasury (faction_id, world_id, resource_id, amount)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (faction_id, world_id, resource_id)
        DO UPDATE SET amount = local_treasury.amount + $4
    """, faction_id, world_id, resource_id, amount)
