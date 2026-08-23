# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from database.db_manager import db


async def conquer_hexes(conqueror_faction_id: int, target_faction_id: int, world_id: int, hexes: int, grant_resources: bool):
    return await db.fetchrow(
        "SELECT * FROM sp_conquer_hexes($1, $2, $3, $4, $5)",
        conqueror_faction_id, target_faction_id, world_id, hexes, grant_resources
    )
