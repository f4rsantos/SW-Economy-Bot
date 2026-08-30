# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db
from typing import Optional


async def get_vehicle_by_display_id(faction_id: int, display_id: int) -> Optional[dict]:
    query = """
        SELECT *,
               COALESCE((
                   SELECT (elem->>'length')::int
                   FROM unnest(vehicle_data) elem
                   WHERE elem->>'length' IS NOT NULL
                   LIMIT 1
               ), 0) as length
        FROM vehicles
        WHERE faction_id = $1 AND faction_vehicle_number = $2
    """
    return await db.fetchrow(query, faction_id, display_id)


VEHICLE_NUMBER_LOCK = 811001


async def get_next_vehicle_number(faction_id: int, conn=None) -> int:
    executor = conn if conn is not None else db
    query = """
        SELECT COALESCE(MIN(t.n), 1) as next_number
        FROM generate_series(
            1,
            (SELECT COALESCE(MAX(faction_vehicle_number), 0) + 1 FROM vehicles WHERE faction_id = $1)
        ) AS t(n)
        WHERE NOT EXISTS (
            SELECT 1 FROM vehicles v
            WHERE v.faction_id = $1 AND v.faction_vehicle_number = t.n
        )
    """
    result = await executor.fetchrow(query, faction_id)
    return result['next_number']
