# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
from typing import Optional, List
from repositories import blockade_repo


async def start_blockade(fleet_id: int, world_id: int, target_faction_ids: List[int]) -> int:
    try:
        row = await blockade_repo.start_blockade(fleet_id, world_id, target_faction_ids)
        return row['blockade_id']
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def end_blockade(blockade_id: int, fleet_id: Optional[int]):
    try:
        await blockade_repo.end_blockade(blockade_id, fleet_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_blockade(blockade_id: int) -> Optional[dict]:
    return await blockade_repo.get_blockade(blockade_id)


async def get_blockade_targets(blockade_id: int) -> List[str]:
    return await blockade_repo.get_blockade_targets(blockade_id)


async def get_fleet_in_blockade(blockade_id: int, faction_id: int, fleet_identifier: str) -> Optional[dict]:
    return await blockade_repo.get_fleet_in_blockade(blockade_id, faction_id, fleet_identifier)


async def get_my_fleet_in_blockade(blockade_id: int, faction_id: int) -> Optional[dict]:
    return await blockade_repo.get_my_fleet_in_blockade(blockade_id, faction_id)


async def get_blockades(faction_id=None, world_id=None) -> list:
    return await blockade_repo.get_blockades(faction_id, world_id)


async def get_fleet_for_blockade(fleet_identifier: str, faction_id: int) -> Optional[dict]:
    return await blockade_repo.get_fleet_for_blockade(fleet_identifier, faction_id)


async def count_blockade_fleets(blockade_id: int) -> int:
    return await blockade_repo.count_blockade_fleets(blockade_id)


async def get_blockading_fleet_for_world(world_id: int, target_faction_id: int) -> Optional[int]:
    return await blockade_repo.get_blockading_fleet_for_world(world_id, target_faction_id)


async def get_interception_details(fleet_id: int) -> Optional[dict]:
    return await blockade_repo.get_interception_details(fleet_id)


async def check_belt_station_blockade(faction_id: int) -> bool:
    """Return True if faction is blockaded on Ceres or Vesta (blocks both /ceres and /vesta)."""
    return await blockade_repo.check_belt_station_blockade(faction_id)
