# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db


async def get_user_faction_id(user_id: int) -> Optional[dict]:
    row = await db.fetchrow("SELECT id FROM factions WHERE leader_id = $1", user_id)
    return dict(row) if row else None


async def has_presence_at_world(faction_id: int, world_id: int) -> Optional[dict]:
    row = await db.fetchrow(
        """
        SELECT 1 FROM world_factions
        WHERE world_id = $1 AND faction_id = $2 AND COALESCE(territory, 0) > 0
        UNION ALL
        SELECT 1 FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.position = $1 AND f.faction_id = $2 AND LOWER(fs.name) != 'debris'
        LIMIT 1
        """,
        world_id, faction_id
    )
    return dict(row) if row else None


async def get_observed_worlds(faction_id: int) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT world_id FROM world_factions
        WHERE faction_id = $1 AND COALESCE(territory, 0) > 0
        UNION
        SELECT f.position AS world_id FROM fleets f
        JOIN fleet_status fs ON f.status_id = fs.id
        WHERE f.faction_id = $1 AND LOWER(fs.name) != 'debris'
        """,
        faction_id
    )
    return [dict(r) for r in rows]
