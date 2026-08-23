# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from database.db_manager import db


async def get_world_root(world_name: str) -> Optional[dict]:
    return await db.fetchrow("""
        WITH RECURSIVE world_tree AS (
            SELECT id, name, orbit_of, 0 as depth FROM worlds WHERE LOWER(name) = LOWER($1)
            UNION ALL
            SELECT w.id, w.name, w.orbit_of, wt.depth + 1
            FROM worlds w INNER JOIN world_tree wt ON w.id = wt.orbit_of
            WHERE wt.depth < 10
        )
        SELECT name FROM world_tree ORDER BY depth DESC LIMIT 1
    """, world_name)
