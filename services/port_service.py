# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from datetime import timedelta
from typing import Optional

from repositories import megaproject_repo, port_repo
from services.transfer_service import deduct_resources
from services.travel_time_service import calculate_travel_time
from utils.lane_pathfinding import LaneEdge, RouteResult, build_lane_graph, find_fastest_route

INTERPLANETARY_PORT = 'interplanetary_port'

PORT_CM_COST = 5_000_000
PORT_EL_COST = 5_000_000
PORT_CS_COST = 5_000_000
PORT_ALLOY_COST = 25

LANE_CS_COST = 10_000_000
LANE_ALLOY_COST = 10

TRAFFIC_TRANSFERS = 'transfers'
TRAFFIC_UNITS = 'units'
TRAFFIC_TYPES = (TRAFFIC_TRANSFERS, TRAFFIC_UNITS)

POLICY_ALLOW = 'allow'
POLICY_DENY = 'deny'


def calculate_port_cost() -> dict:
    return {
        'CM': PORT_CM_COST,
        'EL': PORT_EL_COST,
        'CS': PORT_CS_COST,
        'Alloys': PORT_ALLOY_COST,
    }


def calculate_lane_cost() -> dict:
    return {
        'CS': LANE_CS_COST,
        'Alloys': LANE_ALLOY_COST,
    }


async def get_port_type():
    project_type = await megaproject_repo.get_type_by_code(INTERPLANETARY_PORT)
    if not project_type:
        raise ValueError("Interplanetary Port megaproject type is not registered.")
    return project_type


async def build_port(faction_id: int, world_id: int, world_name: str) -> dict:
    project_type = await get_port_type()
    existing = await port_repo.get_port_by_world(faction_id, world_id)
    if existing:
        raise ValueError(f"Your faction already has a port on {world_name}.")

    costs = calculate_port_cost()

    async with megaproject_repo.get_connection() as conn:
        async with conn.transaction():
            await deduct_resources(faction_id, world_id, costs, conn=conn)
            project_id = await megaproject_repo.insert_project(conn, faction_id, project_type.id, world_id)

    return {'project_id': project_id, 'costs': costs, 'world_name': world_name}


async def build_lane(faction_id: int, port_a_id: int, port_b_id: int) -> dict:
    if port_a_id == port_b_id:
        raise ValueError("A lane must connect two different ports.")

    port_a = await port_repo.get_port_by_id(port_a_id)
    if not port_a or port_a.faction_id != faction_id:
        raise ValueError("You do not own the first port.")

    port_b = await port_repo.get_port_by_id(port_b_id)
    if not port_b or port_b.faction_id != faction_id:
        raise ValueError("You do not own the second port.")

    existing = await port_repo.get_lane_between(port_a_id, port_b_id)
    if existing:
        raise ValueError(f"A lane between {port_a.world_name} and {port_b.world_name} already exists.")

    costs = calculate_lane_cost()

    async with megaproject_repo.get_connection() as conn:
        async with conn.transaction():
            await deduct_resources(faction_id, None, costs, conn=conn)
            lane_id = await port_repo.insert_lane(conn, faction_id, port_a_id, port_b_id)

    return {
        'lane_id': lane_id,
        'costs': costs,
        'port_a_world': port_a.world_name,
        'port_b_world': port_b.world_name,
    }


async def list_faction_ports(faction_id: int):
    return await port_repo.get_faction_ports(faction_id)


async def list_faction_lanes(faction_id: int):
    return await port_repo.get_faction_lanes(faction_id)


def _validate_traffic_type(traffic_type: str) -> None:
    if traffic_type not in TRAFFIC_TYPES:
        raise ValueError(f"Traffic type must be one of: {', '.join(TRAFFIC_TYPES)}.")


def _validate_policy(policy: str) -> None:
    if policy not in (POLICY_ALLOW, POLICY_DENY):
        raise ValueError("Policy must be either allow or deny.")


async def set_access_rule_for_port(
    faction_id: int,
    port_id: int,
    traffic_type: str,
    policy: str,
    other_faction_id: Optional[int] = None,
) -> dict:
    _validate_traffic_type(traffic_type)
    _validate_policy(policy)

    port = await port_repo.get_port_by_id(port_id)
    if not port or port.faction_id != faction_id:
        raise ValueError("You do not own this port.")

    rule_id = await port_repo.upsert_access_rule(port_id, other_faction_id, traffic_type, policy)
    return {'rule_id': rule_id, 'port_id': port_id, 'faction_id': other_faction_id, 'traffic_type': traffic_type, 'policy': policy}


async def clear_access_rule_for_port(
    faction_id: int,
    port_id: int,
    traffic_type: str,
    other_faction_id: Optional[int] = None,
) -> bool:
    _validate_traffic_type(traffic_type)

    port = await port_repo.get_port_by_id(port_id)
    if not port or port.faction_id != faction_id:
        raise ValueError("You do not own this port.")

    result = await port_repo.delete_access_rule(port_id, other_faction_id, traffic_type)
    return result != "DELETE 0"


async def list_access_rules_for_port(faction_id: int, port_id: int):
    port = await port_repo.get_port_by_id(port_id)
    if not port or port.faction_id != faction_id:
        raise ValueError("You do not own this port.")
    return await port_repo.get_rules_for_port(port_id)


def is_traffic_allowed(
    rules: list,
    port_owner_faction_id: int,
    traveling_faction_id: int,
    traffic_type: str,
) -> bool:
    if port_owner_faction_id == traveling_faction_id:
        return True

    specific_rule = None
    default_rule = None
    for rule in rules:
        if rule.traffic_type != traffic_type:
            continue
        if rule.faction_id == traveling_faction_id:
            specific_rule = rule
        elif rule.faction_id is None:
            default_rule = rule

    if specific_rule is not None:
        return specific_rule.policy == POLICY_ALLOW
    if default_rule is not None:
        return default_rule.policy == POLICY_ALLOW
    return True


async def _build_lane_edges(traveling_faction_id: int, traffic_type: str) -> dict:
    ports = await port_repo.get_all_active_ports()
    ports_by_id = {p.id: p for p in ports}

    lanes = await port_repo.get_all_active_lanes()
    if not lanes:
        return {}

    port_ids = list({lane.port_a_id for lane in lanes} | {lane.port_b_id for lane in lanes})
    all_rules = await port_repo.get_all_rules_for_ports(port_ids)
    rules_by_port: dict = {}
    for rule in all_rules:
        rules_by_port.setdefault(rule.port_id, []).append(rule)

    edges: dict = {}
    for lane in lanes:
        port_a = ports_by_id.get(lane.port_a_id)
        port_b = ports_by_id.get(lane.port_b_id)
        if not port_a or not port_b:
            continue

        base_duration = await calculate_travel_time(port_a.world_name, port_b.world_name)
        lane_duration = base_duration.total_seconds() / 2

        a_allowed = is_traffic_allowed(
            rules_by_port.get(port_a.id, []), port_a.faction_id, traveling_faction_id, traffic_type,
        )
        b_allowed = is_traffic_allowed(
            rules_by_port.get(port_b.id, []), port_b.faction_id, traveling_faction_id, traffic_type,
        )
        if not (a_allowed and b_allowed):
            continue

        edges.setdefault(port_a.world_id, []).append(
            LaneEdge(to_world_id=port_b.world_id, duration_seconds=lane_duration, is_lane=True, port_world_id=port_b.world_id)
        )
        edges.setdefault(port_b.world_id, []).append(
            LaneEdge(to_world_id=port_a.world_id, duration_seconds=lane_duration, is_lane=True, port_world_id=port_a.world_id)
        )

    return edges


async def calculate_best_route(
    from_world_id: int,
    from_world_name: str,
    to_world_id: int,
    to_world_name: str,
    traveling_faction_id: int,
    traffic_type: str,
) -> dict:
    _validate_traffic_type(traffic_type)

    direct_duration = await calculate_travel_time(from_world_name, to_world_name)

    lane_edges = await _build_lane_edges(traveling_faction_id, traffic_type)
    graph = build_lane_graph(direct_duration.total_seconds(), from_world_id, to_world_id, lane_edges)

    route = find_fastest_route(graph, from_world_id, to_world_id)
    if route is None:
        return {
            'duration': direct_duration,
            'used_lanes': False,
            'world_path': [from_world_id, to_world_id],
            'saving_seconds': 0.0,
        }

    saving_seconds = max(0.0, direct_duration.total_seconds() - route.total_seconds)

    return {
        'duration': timedelta(seconds=route.total_seconds),
        'used_lanes': route.used_lanes,
        'world_path': route.world_path,
        'saving_seconds': saving_seconds,
    }
