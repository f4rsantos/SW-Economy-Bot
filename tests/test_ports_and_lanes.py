# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest

from services import port_service
from repositories import port_repo
from dtos.ports import Port, PortAccessRule
from utils.lane_pathfinding import LaneEdge, build_lane_graph, find_fastest_route


def test_port_cost_is_flat_per_port():
    costs = port_service.calculate_port_cost()
    assert costs['CM'] == 5_000_000
    assert costs['EL'] == 5_000_000
    assert costs['CS'] == 5_000_000
    assert costs['Alloys'] == 25


def test_lane_cost_is_flat_per_lane():
    costs = port_service.calculate_lane_cost()
    assert costs['CS'] == 10_000_000
    assert costs['Alloys'] == 10


class _FakeConn:
    def transaction(self):
        return _FakeTxCtx()


class _FakeTxCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConnCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_port(port_id, faction_id, world_id, world_name="World", is_active=True):
    return Port(
        id=port_id, faction_id=faction_id, faction_name="Faction",
        world_id=world_id, world_name=world_name, is_active=is_active,
    )


async def test_build_port_allows_multiple_ports_for_same_faction(monkeypatch):
    project_type = megaproject_type_stub()

    async def fake_get_type_by_code(code):
        return project_type

    async def fake_get_port_by_world(faction_id, world_id):
        return None

    charged = []

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        charged.append((faction_id, world_id, resources))

    async def fake_insert_project(conn, faction_id, type_id, world_id):
        return 101

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    from repositories import megaproject_repo

    monkeypatch.setattr(megaproject_repo, "get_type_by_code", fake_get_type_by_code)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(megaproject_repo, "insert_project", fake_insert_project)
    monkeypatch.setattr(port_repo, "get_port_by_world", fake_get_port_by_world)
    monkeypatch.setattr(port_service, "deduct_resources", fake_deduct_resources)

    result_a = await port_service.build_port(faction_id=10, world_id=1, world_name="Alpha")
    result_b = await port_service.build_port(faction_id=10, world_id=2, world_name="Beta")

    assert result_a['project_id'] == 101
    assert result_b['project_id'] == 101
    assert len(charged) == 2


def megaproject_type_stub():
    from repositories import megaproject_repo
    return megaproject_repo.MegaprojectType(
        id=5, code='interplanetary_port', name='Interplanetary Port', description=None,
        is_world_scoped=True, one_per_world=False, one_per_faction=False, has_maintenance=False,
    )


async def test_build_lane_rejects_same_port(monkeypatch):
    with pytest.raises(ValueError, match="two different ports"):
        await port_service.build_lane(faction_id=10, port_a_id=1, port_b_id=1)


async def test_build_lane_succeeds_between_two_owned_ports(monkeypatch):
    port_a = _make_port(1, 10, 100, "Alpha")
    port_b = _make_port(2, 10, 200, "Beta")

    async def fake_get_port_by_id(port_id):
        return port_a if port_id == 1 else port_b

    async def fake_get_lane_between(a, b):
        return None

    async def fake_insert_lane(conn, faction_id, a, b):
        return 55

    charged = []

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        charged.append((faction_id, world_id, resources))

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    from repositories import megaproject_repo

    monkeypatch.setattr(port_repo, "get_port_by_id", fake_get_port_by_id)
    monkeypatch.setattr(port_repo, "get_lane_between", fake_get_lane_between)
    monkeypatch.setattr(port_repo, "insert_lane", fake_insert_lane)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(port_service, "deduct_resources", fake_deduct_resources)

    result = await port_service.build_lane(faction_id=10, port_a_id=1, port_b_id=2)

    assert result['lane_id'] == 55
    assert charged == [(10, None, {'CS': 10_000_000, 'Alloys': 10})]


async def test_multiple_lanes_allowed_for_same_faction(monkeypatch):
    port_a = _make_port(1, 10, 100, "Alpha")
    port_b = _make_port(2, 10, 200, "Beta")
    port_c = _make_port(3, 10, 300, "Gamma")

    ports_by_id = {1: port_a, 2: port_b, 3: port_c}

    async def fake_get_port_by_id(port_id):
        return ports_by_id[port_id]

    async def fake_get_lane_between(a, b):
        return None

    call_count = {'n': 0}

    async def fake_insert_lane(conn, faction_id, a, b):
        call_count['n'] += 1
        return call_count['n']

    async def fake_deduct_resources(faction_id, world_id, resources, conn=None):
        return None

    def fake_get_connection():
        return _FakeConnCtx(_FakeConn())

    from repositories import megaproject_repo

    monkeypatch.setattr(port_repo, "get_port_by_id", fake_get_port_by_id)
    monkeypatch.setattr(port_repo, "get_lane_between", fake_get_lane_between)
    monkeypatch.setattr(port_repo, "insert_lane", fake_insert_lane)
    monkeypatch.setattr(megaproject_repo, "get_connection", fake_get_connection)
    monkeypatch.setattr(port_service, "deduct_resources", fake_deduct_resources)

    result_1 = await port_service.build_lane(faction_id=10, port_a_id=1, port_b_id=2)
    result_2 = await port_service.build_lane(faction_id=10, port_a_id=2, port_b_id=3)

    assert result_1['lane_id'] == 1
    assert result_2['lane_id'] == 2


def test_graph_search_prefers_multi_hop_lane_route_over_slower_direct():
    graph = {
        1: [
            LaneEdge(to_world_id=2, duration_seconds=100, is_lane=False),
            LaneEdge(to_world_id=10, duration_seconds=10, is_lane=True),
        ],
        10: [
            LaneEdge(to_world_id=1, duration_seconds=10, is_lane=True),
            LaneEdge(to_world_id=20, duration_seconds=10, is_lane=True),
        ],
        20: [
            LaneEdge(to_world_id=10, duration_seconds=10, is_lane=True),
            LaneEdge(to_world_id=2, duration_seconds=10, is_lane=True),
        ],
        2: [
            LaneEdge(to_world_id=1, duration_seconds=100, is_lane=False),
            LaneEdge(to_world_id=20, duration_seconds=10, is_lane=True),
        ],
    }

    route = find_fastest_route(graph, 1, 2)

    assert route is not None
    assert route.total_seconds == 30
    assert route.world_path == [1, 10, 20, 2]
    assert len(route.lane_hops) == 3


def test_graph_search_only_halves_lane_segments_not_direct_hops():
    graph = {
        1: [
            LaneEdge(to_world_id=2, duration_seconds=10, is_lane=True),
            LaneEdge(to_world_id=3, duration_seconds=100, is_lane=False),
        ],
        2: [LaneEdge(to_world_id=3, duration_seconds=50, is_lane=False)],
        3: [],
    }

    route = find_fastest_route(graph, 1, 3)

    assert route is not None
    assert route.total_seconds == 60
    assert route.world_path == [1, 2, 3]
    assert route.lane_hops == [(1, 2)]


def test_build_lane_graph_adds_direct_edge_alongside_lane_edges():
    lane_edges = {
        1: [LaneEdge(to_world_id=2, duration_seconds=5, is_lane=True)],
        2: [LaneEdge(to_world_id=1, duration_seconds=5, is_lane=True)],
    }

    graph = build_lane_graph(100, 1, 2, lane_edges)

    direct_edges = [e for e in graph[1] if not e.is_lane]
    assert len(direct_edges) == 1
    assert direct_edges[0].duration_seconds == 100
    lane_only_edges = [e for e in graph[1] if e.is_lane]
    assert len(lane_only_edges) == 1


def test_no_route_returns_direct_when_no_lanes_connect_the_pair():
    graph = build_lane_graph(200, 1, 2, {})
    route = find_fastest_route(graph, 1, 2)
    assert route is not None
    assert route.total_seconds == 200
    assert route.used_lanes is False


def test_same_world_returns_zero_duration_route():
    graph = build_lane_graph(0, 5, 5, {})
    route = find_fastest_route(graph, 5, 5)
    assert route is not None
    assert route.total_seconds == 0.0
    assert route.world_path == [5]
    assert route.used_lanes is False


def test_unreachable_world_returns_none():
    graph = {1: [], 2: []}
    route = find_fastest_route(graph, 1, 2)
    assert route is None


def _rule(port_id, faction_id, traffic_type, policy):
    return PortAccessRule(
        id=1, port_id=port_id, faction_id=faction_id, faction_name=None,
        traffic_type=traffic_type, policy=policy,
    )


def test_is_traffic_allowed_owner_always_allowed():
    rules = [_rule(1, 20, port_service.TRAFFIC_TRANSFERS, port_service.POLICY_DENY)]
    assert port_service.is_traffic_allowed(rules, 10, 10, port_service.TRAFFIC_TRANSFERS) is True


def test_is_traffic_allowed_specific_deny_blocks_faction():
    rules = [_rule(1, 20, port_service.TRAFFIC_UNITS, port_service.POLICY_DENY)]
    assert port_service.is_traffic_allowed(rules, 10, 20, port_service.TRAFFIC_UNITS) is False


def test_is_traffic_allowed_default_policy_applies_to_others():
    rules = [_rule(1, None, port_service.TRAFFIC_UNITS, port_service.POLICY_DENY)]
    assert port_service.is_traffic_allowed(rules, 10, 99, port_service.TRAFFIC_UNITS) is False


def test_is_traffic_allowed_specific_allow_overrides_default_deny():
    rules = [
        _rule(1, None, port_service.TRAFFIC_UNITS, port_service.POLICY_DENY),
        _rule(1, 20, port_service.TRAFFIC_UNITS, port_service.POLICY_ALLOW),
    ]
    assert port_service.is_traffic_allowed(rules, 10, 20, port_service.TRAFFIC_UNITS) is True


def test_is_traffic_allowed_no_rules_defaults_to_allowed():
    assert port_service.is_traffic_allowed([], 10, 20, port_service.TRAFFIC_TRANSFERS) is True


def test_transfers_vs_units_distinction_is_independent():
    rules = [_rule(1, 20, port_service.TRAFFIC_TRANSFERS, port_service.POLICY_ALLOW)]
    assert port_service.is_traffic_allowed(rules, 10, 20, port_service.TRAFFIC_TRANSFERS) is True
    assert port_service.is_traffic_allowed(rules, 10, 20, port_service.TRAFFIC_UNITS) is True


def test_transfers_vs_units_distinction_deny_only_blocks_that_type():
    rules = [_rule(1, 20, port_service.TRAFFIC_UNITS, port_service.POLICY_DENY)]
    assert port_service.is_traffic_allowed(rules, 10, 20, port_service.TRAFFIC_TRANSFERS) is True
    assert port_service.is_traffic_allowed(rules, 10, 20, port_service.TRAFFIC_UNITS) is False


async def test_calculate_best_route_excludes_denied_lane_from_graph(monkeypatch):
    port_a = _make_port(1, 30, 100, "Alpha")
    port_b = _make_port(2, 30, 200, "Beta")

    async def fake_get_all_active_ports():
        return [port_a, port_b]

    from dtos.ports import PortLane

    lane = PortLane(
        id=1, faction_id=30, port_a_id=1, port_b_id=2,
        world_a_id=100, world_b_id=200, world_a_name="Alpha", world_b_name="Beta",
    )

    async def fake_get_all_active_lanes():
        return [lane]

    deny_rule = _rule(1, 99, port_service.TRAFFIC_UNITS, port_service.POLICY_DENY)

    async def fake_get_all_rules_for_ports(port_ids):
        return [deny_rule]

    from datetime import timedelta as _td

    async def fake_calculate_travel_time(from_name, to_name, current_time=None):
        return _td(hours=10)

    monkeypatch.setattr(port_repo, "get_all_active_ports", fake_get_all_active_ports)
    monkeypatch.setattr(port_repo, "get_all_active_lanes", fake_get_all_active_lanes)
    monkeypatch.setattr(port_repo, "get_all_rules_for_ports", fake_get_all_rules_for_ports)
    monkeypatch.setattr(port_service, "calculate_travel_time", fake_calculate_travel_time)

    result_denied = await port_service.calculate_best_route(100, "Alpha", 200, "Beta", 99, port_service.TRAFFIC_UNITS)
    assert result_denied['used_lanes'] is False
    assert result_denied['duration'].total_seconds() == _td(hours=10).total_seconds()

    result_allowed = await port_service.calculate_best_route(100, "Alpha", 200, "Beta", 30, port_service.TRAFFIC_UNITS)
    assert result_allowed['used_lanes'] is True
    assert result_allowed['duration'].total_seconds() == _td(hours=5).total_seconds()
