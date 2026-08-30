# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
from typing import Optional
from repositories import intelligence_repo

BATTLE_STATUSES = {'battle', 'in combat', 'blockading'}


async def get_user_faction_id(user_id: int) -> Optional[int]:
    row = await intelligence_repo.get_user_faction_id(user_id)
    return row['id'] if row else None


async def has_presence_at_world(faction_id: int, world_id: int) -> bool:
    row = await intelligence_repo.has_presence_at_world(faction_id, world_id)
    if row is not None:
        return True
    shared_worlds = await get_intelligence_shared_worlds(faction_id)
    return world_id in shared_worlds


async def get_observed_worlds(faction_id: int) -> set:
    rows = await intelligence_repo.get_observed_worlds(faction_id)
    observed = {r['world_id'] for r in rows}
    observed |= await get_intelligence_shared_worlds(faction_id)
    return observed


async def get_intelligence_shared_worlds(faction_id: int) -> set:
    from repositories import pact_repo
    pacts = await pact_repo.get_intelligence_sharing_pacts_for_faction(faction_id, domestic_only=True)
    if not pacts:
        return set()
    worlds = set()
    for pact in pacts:
        world_ids = await pact_repo.get_pact_world_ids(pact['pact_id'])
        worlds.update(world_ids)
    return worlds


async def get_foreign_shared_worlds(faction_id: int) -> dict:
    from repositories import pact_repo
    pacts = await pact_repo.get_intelligence_sharing_pacts_for_faction(faction_id, foreign_only=True)
    if not pacts:
        return {}
    result = {}
    for pact in pacts:
        world_ids = await pact_repo.get_pact_world_ids(pact['pact_id'])
        if not world_ids:
            continue
        partners = {
            fid for fid in await pact_repo.get_pact_member_faction_ids(pact['pact_id'])
            if fid != faction_id
        }
        for world_id in world_ids:
            result.setdefault(world_id, set()).update(partners)
    return result


def is_foreign_visible(foreign_worlds: dict, world_id: int, owner_faction_id: int) -> bool:
    partners = foreign_worlds.get(world_id)
    if partners is None:
        return False
    return owner_faction_id not in partners


def is_stealth_vehicle(vehicle_data) -> bool:
    if not vehicle_data:
        return False
    raw = vehicle_data[0] if isinstance(vehicle_data, (list, tuple)) else vehicle_data
    if raw is None:
        return False
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return False
    if not isinstance(raw, dict):
        return False
    value = raw.get('stealth')
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('yes', 'low', 'true')
    return False


def is_in_battle(status_name: Optional[str]) -> bool:
    return bool(status_name) and status_name.strip().lower() in BATTLE_STATUSES


def filter_visible_vehicles(vehicles: list, is_own: bool, status_name: Optional[str]) -> tuple:
    if is_own or is_in_battle(status_name):
        return list(vehicles), 0

    visible = []
    hidden = 0
    for v in vehicles:
        if is_stealth_vehicle(v.get('vehicle_data')):
            hidden += v.get('amount', 0) or 0
        else:
            visible.append(v)
    return visible, hidden


def filter_visible_buildings(buildings: list, is_own: bool, observed_worlds: set,
                             foreign_worlds: dict = None, owner_faction_id: int = None) -> tuple:
    if is_own:
        return list(buildings), 0

    foreign_worlds = foreign_worlds or {}
    visible = []
    hidden = 0
    for b in buildings:
        world_id = b.get('world_id')
        if world_id in observed_worlds:
            visible.append(b)
        elif owner_faction_id is not None and is_foreign_visible(foreign_worlds, world_id, owner_faction_id):
            visible.append(b)
        else:
            hidden += b.get('amount', 0) or 0
    return visible, hidden
