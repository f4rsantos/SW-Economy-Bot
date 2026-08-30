# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional, List
from repositories import pact_repo
from services.income_executor import calculate_influence_usage, preview_income
from repositories.income_repo import (
    fetch_hex_count,
    fetch_current_influence,
    fetch_level_10_building_count,
    INTELLIGENCE_SHARING_INFLUENCE_SINGLE_MODE,
    INTELLIGENCE_SHARING_INFLUENCE_BOTH_MODES,
)
from services.income_calculator import calculate_influence_income

INTELLIGENCE_SHARING_PACT_TYPE = pact_repo.INTELLIGENCE_SHARING_PACT_TYPE


def intelligence_sharing_rate(domestic: bool, foreign_alerts: bool) -> int:
    if domestic and foreign_alerts:
        return INTELLIGENCE_SHARING_INFLUENCE_BOTH_MODES
    return INTELLIGENCE_SHARING_INFLUENCE_SINGLE_MODE


def calculate_intelligence_sharing_cost(world_count: int, member_count: int, domestic: bool = True, foreign_alerts: bool = False) -> int:
    rate = intelligence_sharing_rate(domestic, foreign_alerts)
    return rate * world_count * max(member_count - 1, 0)


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
    level_10_building_count = await fetch_level_10_building_count(faction_id)
    income = calculate_influence_income(hex_count, influence_usage, current_influence, total_cs_upkeep, level_10_building_count)
    if income < 0:
        raise ValueError(f"Influence income is {income:,} per week. Cannot create new pacts with negative influence income.")
    pact_id = await pact_repo.insert_pact(pact_name, pact_type_id, faction_id)
    await pact_repo.insert_pact_member(pact_id, faction_id)
    return {'pact_id': pact_id}


async def create_intelligence_sharing_pact(
    pact_name: str,
    pact_type_id: int,
    faction_id: int,
    world_ids: List[int],
    domestic: bool,
    foreign_alerts: bool,
) -> dict:
    if not domestic and not foreign_alerts:
        raise ValueError("Enable at least one mode: domestic, foreign, or both.")
    if not world_ids:
        raise ValueError("Intelligence Sharing pacts need at least one shared world.")

    hex_count = await fetch_hex_count(faction_id)
    current_influence = await fetch_current_influence(faction_id)
    preview = await preview_income(faction_id)
    total_cs_upkeep = preview['usages']['fleet_cs'] + sum(preview['usages']['population_cs'].values())
    level_10_building_count = await fetch_level_10_building_count(faction_id)
    existing_influence_usage = await calculate_influence_usage(faction_id)
    new_pact_cost = calculate_intelligence_sharing_cost(len(world_ids), 1, domestic, foreign_alerts)
    income = calculate_influence_income(
        hex_count, existing_influence_usage + new_pact_cost, current_influence, total_cs_upkeep, level_10_building_count
    )
    if income < 0:
        raise ValueError(f"Influence income is {income:,} per week. Cannot create new pacts with negative influence income.")

    pact_id = await pact_repo.insert_pact(pact_name, pact_type_id, faction_id)
    await pact_repo.insert_pact_member(pact_id, faction_id)
    await pact_repo.insert_pact_worlds(pact_id, world_ids)
    await pact_repo.insert_pact_intelligence_sharing(pact_id, domestic, foreign_alerts)
    return {'pact_id': pact_id}


async def preview_intelligence_sharing_join(pact_id: int, joining_faction_id: int) -> dict:
    existing_member_ids = await pact_repo.get_pact_member_faction_ids(pact_id)
    world_count = await pact_repo.get_pact_world_count(pact_id)
    sharing = await pact_repo.get_pact_intelligence_sharing(pact_id)
    domestic = sharing.domestic if sharing else True
    foreign_alerts = sharing.foreign_alerts if sharing else False
    new_member_count = len(existing_member_ids) + 1
    new_cost = calculate_intelligence_sharing_cost(world_count, new_member_count, domestic, foreign_alerts)

    at_risk = []
    for member_faction_id in existing_member_ids:
        member_usage = await calculate_influence_usage(member_faction_id)
        old_cost = calculate_intelligence_sharing_cost(world_count, len(existing_member_ids), domestic, foreign_alerts)
        projected_usage = member_usage - old_cost + new_cost
        hex_count = await fetch_hex_count(member_faction_id)
        current_influence = await fetch_current_influence(member_faction_id)
        preview = await preview_income(member_faction_id)
        total_cs_upkeep = preview['usages']['fleet_cs'] + sum(preview['usages']['population_cs'].values())
        level_10_building_count = await fetch_level_10_building_count(member_faction_id)
        projected_income = calculate_influence_income(
            hex_count, projected_usage, current_influence, total_cs_upkeep, level_10_building_count
        )
        if projected_income < 0:
            at_risk.append({'faction_id': member_faction_id, 'projected_income': projected_income})

    return {'new_cost_per_member': new_cost, 'at_risk_faction_ids': [r['faction_id'] for r in at_risk]}


async def join_intelligence_sharing_pact(pact_id: int, faction_id: int, at_risk_faction_ids: List[int]) -> dict:
    if await is_pact_member(pact_id, faction_id):
        raise ValueError("Faction is already a member of this pact.")
    await pact_repo.insert_pact_member(pact_id, faction_id)
    removed = []
    for at_risk_faction_id in at_risk_faction_ids:
        if at_risk_faction_id == faction_id:
            continue
        if await is_pact_member(pact_id, at_risk_faction_id):
            await pact_repo.delete_pact_member(pact_id, at_risk_faction_id)
            removed.append(at_risk_faction_id)
    member_count = await pact_repo.get_pact_member_count(pact_id)
    return {'member_count': member_count, 'removed_faction_ids': removed}


async def join_pact(pact_id: int, faction_id: int, pact_data) -> dict:
    if pact_data.pact_type == INTELLIGENCE_SHARING_PACT_TYPE:
        raise ValueError("Use /pact join-intelligence-sharing for this pact type. Joining may push other members' influence income negative and requires confirmation.")
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
