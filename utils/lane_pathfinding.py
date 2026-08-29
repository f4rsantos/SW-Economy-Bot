# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LANE_SPEED_MULTIPLIER = 2.0


@dataclass(frozen=True, slots=True)
class LaneEdge:
    to_world_id: int
    duration_seconds: float
    is_lane: bool
    port_world_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class RouteResult:
    total_seconds: float
    world_path: List[int]
    lane_hops: List[Tuple[int, int]]

    @property
    def used_lanes(self) -> bool:
        return len(self.lane_hops) > 0


def build_lane_graph(
    direct_duration_seconds: float,
    from_world_id: int,
    to_world_id: int,
    lane_edges: Dict[int, List[LaneEdge]],
) -> Dict[int, List[LaneEdge]]:
    graph: Dict[int, List[LaneEdge]] = {
        world_id: list(edges) for world_id, edges in lane_edges.items()
    }
    graph.setdefault(from_world_id, [])
    graph.setdefault(to_world_id, [])
    graph[from_world_id] = graph[from_world_id] + [
        LaneEdge(to_world_id=to_world_id, duration_seconds=direct_duration_seconds, is_lane=False)
    ]
    graph[to_world_id] = graph[to_world_id] + [
        LaneEdge(to_world_id=from_world_id, duration_seconds=direct_duration_seconds, is_lane=False)
    ]
    return graph


def find_fastest_route(
    graph: Dict[int, List[LaneEdge]],
    from_world_id: int,
    to_world_id: int,
) -> Optional[RouteResult]:
    if from_world_id == to_world_id:
        return RouteResult(total_seconds=0.0, world_path=[from_world_id], lane_hops=[])

    best_cost: Dict[int, float] = {from_world_id: 0.0}
    previous: Dict[int, Tuple[int, bool]] = {}
    visited: set = set()
    heap: List[Tuple[float, int]] = [(0.0, from_world_id)]

    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == to_world_id:
            break

        for edge in graph.get(node, []):
            neighbor = edge.to_world_id
            if neighbor in visited:
                continue
            new_cost = cost + edge.duration_seconds
            if new_cost < best_cost.get(neighbor, float("inf")):
                best_cost[neighbor] = new_cost
                previous[neighbor] = (node, edge.is_lane)
                heapq.heappush(heap, (new_cost, neighbor))

    if to_world_id not in best_cost:
        return None

    path = [to_world_id]
    lane_hops: List[Tuple[int, int]] = []
    node = to_world_id
    while node != from_world_id:
        prev_node, was_lane = previous[node]
        if was_lane:
            lane_hops.append((prev_node, node))
        path.append(prev_node)
        node = prev_node
    path.reverse()
    lane_hops.reverse()

    return RouteResult(
        total_seconds=best_cost[to_world_id],
        world_path=path,
        lane_hops=lane_hops,
    )
