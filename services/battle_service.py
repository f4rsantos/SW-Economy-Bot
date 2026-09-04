# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
import json
import logging
from typing import Optional
from repositories import battle_repo
from services import notification_service

logger = logging.getLogger(__name__)


async def start_battle(war_id: int, fleet_id: int, side: str, world_id: int) -> int:
    try:
        row = await battle_repo.start_battle(war_id, fleet_id, side, world_id)
        return row['battle_id']
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def end_battle(battle_id: int, faction_id: int) -> dict:
    stats = await battle_repo.get_battle_stats(battle_id)

    fleet_count = await battle_repo.get_battle_fleet_count(battle_id)
    battle_data = await battle_repo.get_battle(battle_id)
    participant_faction_ids = await battle_repo.get_battle_participant_faction_ids(battle_id)

    try:
        await battle_repo.end_battle(battle_id, faction_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e

    try:
        if battle_data:
            await notification_service.notify_battle_ended(
                battle_id, battle_data.world_name, participant_faction_ids
            )
    except Exception as e:
        logger.warning(f"Battle end notification failed for battle {battle_id}: {e}")

    return {'stats': stats, 'fleet_count': fleet_count}


async def get_battle(battle_id: int) -> Optional[dict]:
    return await battle_repo.get_battle(battle_id)


async def get_my_fleet_in_battle(battle_id: int, faction_id: int) -> Optional[dict]:
    return await battle_repo.get_my_fleet_in_battle(battle_id, faction_id)


async def damage_fleet(fleet_id: int, damage: int):
    try:
        await battle_repo.damage_fleet(fleet_id, damage)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def repair_fleet(fleet_id: int, faction_id: int, repair_amount: int, costs: dict):
    costs_json = json.dumps([{"name": k, "amount": v} for k, v in costs.items()]) if costs else None
    try:
        await battle_repo.repair_fleet(fleet_id, faction_id, repair_amount, costs_json)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def get_fleet_costs(fleet_id: int) -> list:
    return await battle_repo.get_fleet_costs(fleet_id)


async def get_battles(faction_id=None, world_id=None) -> list:
    return await battle_repo.get_battles(faction_id, world_id)


async def join_battle(battle_id: int, fleet_id: int, side: str) -> dict:
    if await battle_repo.get_battle_participant_side(battle_id, fleet_id):
        raise ValueError("Fleet is already in this battle.")
    await battle_repo.insert_battle_participant(battle_id, fleet_id, side)
    combat_status = await battle_repo.get_fleet_status_by_name('in combat')
    if combat_status:
        await battle_repo.set_fleet_status(fleet_id, combat_status['id'])
    stats = await battle_repo.get_battle_stats(battle_id)
    return {'stats': stats}


async def leave_battle(battle_id: int, faction_id: int) -> dict:
    user_fleets = await battle_repo.get_user_fleets_in_battle(battle_id, faction_id)
    if not user_fleets:
        raise ValueError("Faction has no fleets in this battle.")
    fleet_ids = [f['id'] for f in user_fleets]
    fleet_names = [f['name'] or f"Unit #{f['faction_fleet_number']}" for f in user_fleets]
    await battle_repo.remove_battle_participants(battle_id, fleet_ids)
    idle_status = await battle_repo.get_fleet_status_by_name('idle')
    if idle_status:
        await battle_repo.set_fleets_status(fleet_ids, idle_status['id'])
    remaining = await battle_repo.count_battle_participants(battle_id)
    if remaining == 0:
        await battle_repo.delete_battle(battle_id)
    return {'fleet_names': fleet_names, 'fleet_count': len(user_fleets), 'remaining': remaining, 'battle_ended': remaining == 0}


async def create_standalone_war(world_name: str, faction_id: int, side: str) -> int:
    row = await battle_repo.create_war(f"Battle at {world_name}")
    war_id = row['id']
    await battle_repo.add_war_participant(war_id, faction_id, side)
    return war_id


SIDE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def next_side_letter(existing_sides) -> str:
    taken = {str(side).strip().upper() for side in existing_sides if side}
    for letter in SIDE_LETTERS:
        if letter not in taken:
            return letter
    raise ValueError("No side labels remain available for this battle.")


def sides_of(battle) -> list:
    raw = getattr(battle, 'sides', None)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return []
    sides = []
    for entry in (raw or []):
        if not isinstance(entry, dict):
            continue
        side = entry.get('side')
        if side and side not in sides:
            sides.append(side)
    return sides


async def enter_battle(fleet_id: int, faction_id: int, world_id: int, world_name: str,
                       battle_id: Optional[int] = None, side: Optional[str] = None) -> dict:
    if battle_id is None:
        chosen_side = side or SIDE_LETTERS[0]
        war_id = await create_standalone_war(world_name, faction_id, chosen_side)
        new_battle_id = await start_battle(war_id, fleet_id, chosen_side, world_id)
        stats = await battle_repo.get_battle_stats(new_battle_id)
        return {
            'battle_id': new_battle_id,
            'war_id': war_id,
            'side': chosen_side,
            'created': True,
            'stats': stats,
        }

    if side is None:
        raise ValueError("A side must be chosen to join an existing battle.")

    result = await join_battle(battle_id, fleet_id, side)
    battle = await battle_repo.get_battle(battle_id)
    return {
        'battle_id': battle_id,
        'war_id': battle.war_id if battle else None,
        'side': side,
        'created': False,
        'stats': result['stats'],
    }


async def get_fleet_side_in_battle(battle_id: int, fleet_id: int) -> Optional[str]:
    return await battle_repo.get_fleet_side_in_battle(battle_id, fleet_id)
