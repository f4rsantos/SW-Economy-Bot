# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncpg
import json
from datetime import datetime, timezone
from typing import Optional
from repositories import war_repo


async def create_war(name: str, faction_id: int, side: str) -> int:
    try:
        row = await war_repo.create_war_sp(name, faction_id, side)
        await grant_war_spirits(faction_id)
        return row['war_id']
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e


async def are_factions_at_war(faction_id_1: int, faction_id_2: int) -> bool:
    return await war_repo.are_factions_at_war(faction_id_1, faction_id_2)


async def is_faction_at_war(faction_id: int) -> bool:
    return await war_repo.is_faction_at_war(faction_id)


WAR_SPIRIT_KEYS = ('war_effort', 'war_mobilization')


async def grant_war_spirits(faction_id: int) -> None:
    spirit_types = await war_repo.get_spirit_types_by_keys(list(WAR_SPIRIT_KEYS))
    for st in spirit_types:
        await war_repo.upsert_national_spirit(faction_id, st['id'], st['fixed_value'])


async def revoke_war_spirits_if_not_at_war(faction_id: int) -> None:
    if await is_faction_at_war(faction_id):
        return
    await war_repo.delete_war_spirits(faction_id, list(WAR_SPIRIT_KEYS))


async def end_war(war_id: int, faction_id: int, winning_sides: list[str], losing_sides: list[str]) -> dict:
    war = await war_repo.get_war_row(war_id)
    if not war:
        return None

    participants = await war_repo.get_war_participants(war_id)
    war_sides = {p['side'] for p in participants}
    overlap = set(winning_sides) & set(losing_sides)
    if overlap:
        raise ValueError(f"Side(s) {', '.join(sorted(overlap))} cannot be both winning and losing.")
    unknown = (set(winning_sides) | set(losing_sides)) - war_sides
    if unknown:
        raise ValueError(f"Side(s) {', '.join(sorted(unknown))} are not part of war #{war_id}.")

    stats = await war_repo.get_war_side_stats(war_id)

    total_battles_row = await war_repo.get_total_battles(war_id)

    spirit_type_rows = await war_repo.get_victorious_recovering_spirit_types()
    spirit_types = {r['key']: r for r in spirit_type_rows}

    war_days = (datetime.now(timezone.utc) - war.date_start).days
    ramp = min(war_days / 50, 1.0)

    for p in participants:
        if p['side'] in winning_sides:
            spirit_type = spirit_types['victorious']
        elif p['side'] in losing_sides:
            spirit_type = spirit_types['recovering']
        else:
            continue
        scaled_value = spirit_type['fixed_value'] * ramp
        await war_repo.upsert_national_spirit_ended(p['faction_id'], spirit_type['id'], scaled_value)

    try:
        await war_repo.end_war_sp(war_id, faction_id)
    except asyncpg.exceptions.RaiseError as e:
        raise ValueError(str(e)) from e

    for p in participants:
        await revoke_war_spirits_if_not_at_war(p['faction_id'])

    parsed_stats = []
    for s in stats:
        names = s.faction_names
        if isinstance(names, str):
            try:
                names = json.loads(names)
            except json.JSONDecodeError:
                names = []
        if not isinstance(names, list):
            names = [str(names)]
        parsed_stats.append({'side': s.side, 'faction_names': names})

    return {
        'war': war,
        'stats': parsed_stats,
        'total_battles': total_battles_row['count'],
        'winning_sides': winning_sides,
        'losing_sides': losing_sides,
    }


async def get_war(war_id: int) -> Optional[dict]:
    return await war_repo.get_war(war_id)


async def get_participant(war_id: int, faction_id: int) -> Optional[dict]:
    return await war_repo.get_participant(war_id, faction_id)


async def get_existing_war_for_faction(faction_id: int) -> Optional[dict]:
    return await war_repo.get_existing_war_for_faction(faction_id)


async def get_wars(faction_id=None) -> list:
    return await war_repo.get_wars(faction_id)


async def join_war(war_id: int, faction_id: int, side: str) -> dict:
    war = await get_war(war_id)
    if not war:
        raise ValueError("War not found.")
    existing = await get_participant(war_id, faction_id)
    if existing:
        raise ValueError(f"Faction is already in this war on side {existing['side']}.")
    await war_repo.insert_war_participant(war_id, faction_id, side)
    await grant_war_spirits(faction_id)
    stats = await war_repo.get_war_join_stats(war_id)
    battle_count = await war_repo.get_battle_count(war_id)
    return {'war': war, 'stats': stats, 'battle_count': battle_count['count']}


async def leave_war(war_id: int, faction_id: int) -> dict:
    war = await get_war(war_id)
    if not war:
        raise ValueError("War not found.")
    if not await get_participant(war_id, faction_id):
        raise ValueError("Faction is not participating in this war.")
    await war_repo.delete_war_participant(war_id, faction_id)
    await revoke_war_spirits_if_not_at_war(faction_id)
    remaining = await war_repo.count_war_participants(war_id)
    war_ended = False
    if remaining == 0:
        battles = await war_repo.get_battles(war_id)
        if battles:
            battle_ids = [b['id'] for b in battles]
            await war_repo.reset_fleets_for_battles(battle_ids)
            await war_repo.delete_battle_participants(battle_ids)
            await war_repo.delete_battles(war_id)
        await war_repo.delete_war(war_id)
        war_ended = True
    return {'war': war, 'remaining': remaining, 'war_ended': war_ended}
