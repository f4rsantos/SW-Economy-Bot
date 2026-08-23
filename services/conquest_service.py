# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
from repositories import conquest_repo


async def conquer_hexes(conqueror_faction_id: int, target_faction_id: int, world_id: int, hexes: int, grant_resources: bool) -> dict:
    try:
        row = await conquest_repo.conquer_hexes(conqueror_faction_id, target_faction_id, world_id, hexes, grant_resources)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e
    return dict(row)
