# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional, List
from repositories import pact_repo
from services.income_executor import calculate_influence_usage, preview_income
from repositories.income_repo import fetch_hex_count, fetch_current_influence
from services.income_calculator import calculate_influence_income


async def get_pact_type(pact_type: str) -> Optional[dict]:
    return await pact_repo.get_pact_type(pact_type)


async def get_pact_type_names() -> List[str]:
    return await pact_repo.get_pact_type_names()


async def get_pact(pact_id: int) -> Optional[dict]:
    return await pact_repo.get_pact(pact_id)


async def get_pact_members(pact_id: int) -> list:
    return await pact_repo.get_pact_members(pact_id)


async def is_pact_member(pact_id: int, faction_id: int) -> bool:
    return await pact_repo.is_pact_member(pact_id, faction_id)


async def get_faction_pacts(faction_id: int) -> dict:
    led = await pact_repo.get_faction_pacts_led(faction_id)
    member = await pact_repo.get_faction_pacts_member(faction_id)
    return {'led': led, 'member': member}


async def get_all_pact_types() -> list:
    return await pact_repo.get_all_pact_types()


async def create_pact(pact_name: str, pact_type_id: int, faction_id: int) -> dict:
    hex_count = await fetch_hex_count(faction_id)
    current_influence = await fetch_current_influence(faction_id)
    influence_usage = await calculate_influence_usage(faction_id)
    preview = await preview_income(faction_id)
    total_cs_upkeep = preview['usages']['fleet_cs'] + sum(preview['usages']['population_cs'].values())
    income = calculate_influence_income(hex_count, influence_usage, current_influence, total_cs_upkeep)
    if income < 0:
        raise ValueError(f"Influence income is {income:,} per week. Cannot create new pacts with negative influence income.")
    pact_id = await pact_repo.insert_pact(pact_name, pact_type_id, faction_id)
    await pact_repo.insert_pact_member(pact_id, faction_id)
    return {'pact_id': pact_id}


async def join_pact(pact_id: int, faction_id: int, pact_data) -> dict:
    if await is_pact_member(pact_id, faction_id):
        raise ValueError("Faction is already a member of this pact.")
    total_hexes = await pact_repo.get_faction_total_hexes(pact_data.leader_id)
    raw_generation = max(2500 - 0.25 * total_hexes, 50)
    pact_type_row = await pact_repo.get_pact_type_influence_cost(pact_data.pact_type)
    pact_cost_per_member = pact_type_row['influence_cost'] if pact_type_row else 0
    current_pact_costs = await calculate_influence_usage(pact_data.leader_id)
    new_net_income = raw_generation - (current_pact_costs + pact_cost_per_member)
    if new_net_income < 0:
        raise ValueError(f"Pact leader's influence income would become {int(new_net_income):,} per week. The pact leader cannot afford additional members.")
    await pact_repo.insert_pact_member(pact_id, faction_id)
    member_count = await pact_repo.get_pact_member_count(pact_id)
    return {'member_count': member_count}


async def end_pact(pact_id: int, faction_id: int) -> dict:
    pact_data = await get_pact(pact_id)
    if not pact_data:
        raise ValueError("Pact not found.")
    if pact_data.leader_id != faction_id:
        raise ValueError("Only the pact leader can dissolve this pact.")
    await pact_repo.delete_pact_members(pact_id)
    await pact_repo.delete_pact(pact_id)
    return {'name': pact_data.name, 'pact_type': pact_data.pact_type}


async def leave_pact(pact_id: int, faction_id: int) -> dict:
    pact_data = await get_pact(pact_id)
    if not pact_data:
        raise ValueError("Pact not found.")
    if pact_data.leader_id == faction_id:
        raise ValueError("Pact leader cannot leave. Use end-pact to dissolve it instead.")
    if not await is_pact_member(pact_id, faction_id):
        raise ValueError("Faction is not a member of this pact.")
    await pact_repo.delete_pact_member(pact_id, faction_id)
    return {'name': pact_data.name, 'pact_type': pact_data.pact_type, 'leader_name': pact_data.leader_name}


async def remove_pact_member(pact_id: int, leader_faction_id: int, target_faction_id: int) -> dict:
    pact_data = await get_pact(pact_id)
    if not pact_data:
        raise ValueError("Pact not found.")
    if pact_data.leader_id != leader_faction_id:
        raise ValueError("Only the pact leader can remove members.")
    if target_faction_id == leader_faction_id:
        raise ValueError("Leader cannot be removed. Use end-pact to dissolve the pact.")
    if not await is_pact_member(pact_id, target_faction_id):
        raise ValueError(f"Faction is not a member of pact {pact_id}.")
    await pact_repo.delete_pact_member(pact_id, target_faction_id)
    return {'name': pact_data.name, 'pact_type': pact_data.pact_type}
