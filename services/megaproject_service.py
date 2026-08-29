# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import math
from typing import Optional

from repositories import megaproject_repo
from services.transfer_service import deduct_resources
from dtos.megaproject import MegaprojectType, FactionMegaproject

TERRAFORMER = 'terraformer'
RECYCLING_CENTER = 'recycling_center'
EXTRACTORS_UPGRADE = 'extractors_upgrade'

TERRAFORMER_CM_PER_HEX = 20_000
TERRAFORMER_EL_PER_HEX = 20_000
TERRAFORMER_CS_PER_HEX = 30_000
TERRAFORMER_MAINT_CM_PER_HEX = 100
TERRAFORMER_MAINT_EL_PER_HEX = 100
TERRAFORMER_ALLOY_BASE = 100
TERRAFORMER_ALLOY_PER_HEXES = 1
TERRAFORMER_ALLOY_HEX_BLOCK = 50

RECYCLING_CENTER_CM_COST = 10_000_000
RECYCLING_CENTER_EL_COST = 10_000_000
RECYCLING_CENTER_CS_COST = 20_000_000
RECYCLING_CENTER_ALLOY_COST = 20
RECYCLING_CENTER_EFFICIENCY_PENALTY = 0.01
RECYCLING_CENTER_REFUND_RATE = 0.05

EXTRACTORS_UPGRADE_CM_COST = 10_000_000
EXTRACTORS_UPGRADE_EL_COST = 10_000_000
EXTRACTORS_UPGRADE_CS_COST = 20_000_000
EXTRACTORS_UPGRADE_ALLOY_COST = 20
EXTRACTOR_BASE_PRODUCTION = 1000
EXTRACTOR_SELF_REFINE_PRODUCTION = 700


def calculate_terraformer_cost(hex_count: int) -> dict:
    alloy_blocks = math.ceil(hex_count / TERRAFORMER_ALLOY_HEX_BLOCK)
    alloys = TERRAFORMER_ALLOY_BASE + TERRAFORMER_ALLOY_PER_HEXES * alloy_blocks
    return {
        'CM': TERRAFORMER_CM_PER_HEX * hex_count,
        'EL': TERRAFORMER_EL_PER_HEX * hex_count,
        'CS': TERRAFORMER_CS_PER_HEX * hex_count,
        'Alloys': alloys,
    }


def calculate_terraformer_maintenance(hex_count: int) -> dict:
    return {
        'CM': TERRAFORMER_MAINT_CM_PER_HEX * hex_count,
        'EL': TERRAFORMER_MAINT_EL_PER_HEX * hex_count,
    }


def calculate_recycling_center_cost() -> dict:
    return {
        'CM': RECYCLING_CENTER_CM_COST,
        'EL': RECYCLING_CENTER_EL_COST,
        'CS': RECYCLING_CENTER_CS_COST,
        'Alloys': RECYCLING_CENTER_ALLOY_COST,
    }


def calculate_extractors_upgrade_cost() -> dict:
    return {
        'CM': EXTRACTORS_UPGRADE_CM_COST,
        'EL': EXTRACTORS_UPGRADE_EL_COST,
        'CS': EXTRACTORS_UPGRADE_CS_COST,
        'Alloys': EXTRACTORS_UPGRADE_ALLOY_COST,
    }


def calculate_recycling_refund(last_cycle_refined_spend: dict) -> dict:
    refund = {}
    for resource_name, net_amount in last_cycle_refined_spend.items():
        spent = max(0, int(net_amount))
        if spent <= 0:
            continue
        amount = math.floor(spent * RECYCLING_CENTER_REFUND_RATE)
        if amount > 0:
            refund[resource_name] = amount
    return refund


async def get_type(code: str) -> MegaprojectType:
    project_type = await megaproject_repo.get_type_by_code(code)
    if not project_type:
        raise ValueError(f"Megaproject type '{code}' is not registered.")
    return project_type


async def build_terraformer(faction_id: int, world_id: int, world_name: str) -> dict:
    project_type = await get_type(TERRAFORMER)
    existing = await megaproject_repo.get_faction_project_by_type(faction_id, project_type.id, world_id)
    if existing:
        raise ValueError(f"A Terraformer has already been built on {world_name}.")

    existing_any = await megaproject_repo.get_active_projects_by_type_code(TERRAFORMER)
    if any(p['world_id'] == world_id for p in existing_any):
        raise ValueError(f"A Terraformer already exists on {world_name}.")

    hex_count = await megaproject_repo.get_world_hex_count(world_id)
    if hex_count is None:
        raise ValueError(f"World '{world_name}' has no recorded hex count.")

    costs = calculate_terraformer_cost(hex_count)

    async with megaproject_repo.get_connection() as conn:
        async with conn.transaction():
            await deduct_resources(faction_id, world_id, costs, conn=conn)
            project_id = await megaproject_repo.insert_project(conn, faction_id, project_type.id, world_id)

    forward_message = (
        f"MAPPING CORPS REROLL REQUEST\n"
        f"World: {world_name}\n"
        f"A Terraformer has completed construction on {world_name}. "
        f"Please reroll this world's CS rating to HIGH and reroll its resource percentages. "
        f"Forward this message to the mapping corps to process the reroll."
    )

    return {
        'project_id': project_id,
        'costs': costs,
        'hex_count': hex_count,
        'world_name': world_name,
        'forward_message': forward_message,
    }


async def build_recycling_center(faction_id: int) -> dict:
    project_type = await get_type(RECYCLING_CENTER)
    existing = await megaproject_repo.get_faction_project_by_type(faction_id, project_type.id, None)
    if existing:
        raise ValueError("Your faction already has a Resource Recycling Center.")

    costs = calculate_recycling_center_cost()

    async with megaproject_repo.get_connection() as conn:
        async with conn.transaction():
            await deduct_resources(faction_id, None, costs, conn=conn)
            project_id = await megaproject_repo.insert_project(conn, faction_id, project_type.id, None)

    return {'project_id': project_id, 'costs': costs}


async def build_extractors_upgrade(faction_id: int) -> dict:
    project_type = await get_type(EXTRACTORS_UPGRADE)
    existing = await megaproject_repo.get_faction_project_by_type(faction_id, project_type.id, None)
    if existing:
        raise ValueError("Your faction already has the Extractors Upgrade.")

    costs = calculate_extractors_upgrade_cost()

    async with megaproject_repo.get_connection() as conn:
        async with conn.transaction():
            await deduct_resources(faction_id, None, costs, conn=conn)
            project_id = await megaproject_repo.insert_project(conn, faction_id, project_type.id, None)

    return {'project_id': project_id, 'costs': costs}


async def list_faction_megaprojects(faction_id: int) -> list[FactionMegaproject]:
    return await megaproject_repo.list_faction_projects(faction_id)


async def get_megaproject_detail(faction_id: int, project_id: int) -> Optional[FactionMegaproject]:
    return await megaproject_repo.get_project_detail(faction_id, project_id)


async def has_active_recycling_center(faction_id: int) -> bool:
    row = await megaproject_repo.get_faction_active_project_by_code(faction_id, RECYCLING_CENTER)
    return bool(row and row['is_active'])


async def has_active_extractors_upgrade(faction_id: int) -> bool:
    row = await megaproject_repo.get_faction_active_project_by_code(faction_id, EXTRACTORS_UPGRADE)
    return bool(row and row['is_active'])


async def charge_megaproject_maintenance(faction_id: int) -> list[dict]:
    results = []

    projects = await megaproject_repo.get_faction_active_projects_by_type_code(faction_id, TERRAFORMER)
    for project in projects:
        world_id = project['world_id']
        hex_count = await megaproject_repo.get_world_hex_count(world_id)
        if not hex_count:
            continue
        maintenance = calculate_terraformer_maintenance(hex_count)
        outcome = await _charge_or_disable(faction_id, None, project['id'], maintenance, world_id)
        results.append({'type_code': TERRAFORMER, 'project_id': project['id'], **outcome})

    return results


async def _charge_or_disable(faction_id: int, world_id: Optional[int], project_id: int, costs: dict, deduct_world_id: Optional[int] = None) -> dict:
    try:
        await deduct_resources(faction_id, deduct_world_id, costs)
        return {'charged': True, 'costs': costs, 'disabled': False}
    except ValueError:
        result = await megaproject_repo.set_active(project_id, False)
        return {'charged': False, 'costs': costs, 'disabled': result != "UPDATE 0"}


async def reactivate_project(faction_id: int, project_id: int) -> dict:
    project = await megaproject_repo.get_project_detail(faction_id, project_id)
    if not project:
        raise ValueError("Megaproject not found.")
    if project.is_active:
        raise ValueError("This megaproject is already active.")

    if project.type_code == TERRAFORMER:
        hex_count = await megaproject_repo.get_world_hex_count(project.world_id)
        costs = calculate_terraformer_maintenance(hex_count or 0)
    else:
        costs = {}

    if costs:
        await deduct_resources(faction_id, project.world_id, costs)

    result = await megaproject_repo.set_active(project_id, True)
    if result == "UPDATE 0":
        raise ValueError("This megaproject could not be reactivated.")
    return {'project_id': project_id, 'costs': costs}
