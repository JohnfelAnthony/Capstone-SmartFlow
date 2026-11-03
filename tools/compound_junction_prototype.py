"""Research-only atomic reservation primitive for nearby junctions.

This is not wired into TrafficEngine and does not perform geometry, signal,
pedestrian, exit-storage or dynamic safety checks. It cannot certify
deadlock freedom or fairness. All readiness flags must come from an eventual
validated engine implementation; the caller must not guess them.
"""
from __future__ import annotations

from dataclasses import dataclass

from tools.close_junction_analysis import analyze as analyze_close_junctions


def route_clusters(payload: dict, lane_ids: list[str]) -> list[dict]:
    """Map a complete directed draft route to candidate compound clusters.

    This uses raw topology because the proposed short links do not pass the
    native parser. It enforces the native no-U-turn and explicit prohibition
    rules, but performs no signal, storage or physical clearance check.
    """
    if not isinstance(lane_ids, list) or not lane_ids or any(not isinstance(lane, str) for lane in lane_ids):
        raise ValueError("A nonempty sequence of lane IDs is required")
    lanes = {}
    for road in payload["roads"]:
        generated = [(road["id"] + "f", road["source"], road["target"])]
        if not road.get("oneway"):
            generated.append((road["id"] + "r", road["target"], road["source"]))
        for lane_id, source, target in generated:
            if lane_id in lanes:
                raise ValueError("Ambiguous generated lane ID")
            lanes[lane_id] = (source, target)
    if any(lane not in lanes for lane in lane_ids):
        raise ValueError("Route references an unavailable directed lane")
    if any(lanes[a][1] != lanes[b][0] for a, b in zip(lane_ids, lane_ids[1:])):
        raise ValueError("Route lanes are not connected in travel direction")
    raw_restrictions = payload.get("prohibited_turns", [])
    if not isinstance(raw_restrictions, list) or any(
            not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(lane, str) for lane in pair)
            for pair in raw_restrictions):
        raise ValueError("Invalid turn restrictions in candidate network")
    restrictions = {tuple(pair) for pair in raw_restrictions}
    for incoming, outgoing in zip(lane_ids, lane_ids[1:]):
        if lanes[incoming][0] == lanes[outgoing][1] or (incoming, outgoing) in restrictions:
            raise ValueError(f"Route contains a prohibited turn: {incoming} to {outgoing}")
    groups = analyze_close_junctions(payload)["candidate_groups"]
    by_node = {node: tuple(group) for group in groups for node in group}
    if lanes[lane_ids[0]][0] in by_node:
        raise ValueError("Route starts inside a candidate cluster; entry must be planned upstream")
    result, index = [], 0
    while index < len(lane_ids):
        entry = lane_ids[index]
        source, target = lanes[entry]
        cluster = by_node.get(target)
        if cluster is None or source in cluster:
            index += 1
            continue
        traversed, internal = [target], []
        cursor = index + 1
        while cursor < len(lane_ids) and lanes[lane_ids[cursor]][1] in cluster:
            internal.append(lane_ids[cursor])
            traversed.append(lanes[lane_ids[cursor]][1])
            cursor += 1
        if cursor >= len(lane_ids):
            raise ValueError("A cluster route must include an exit lane for downstream storage")
        result.append({"junctions": list(cluster), "entry_lane": entry, "internal_lanes": internal,
                       "traversed_junctions": traversed, "exit_lane": lane_ids[cursor]})
        index = cursor
    return result


@dataclass(frozen=True)
class Readiness:
    signals_ready: bool
    exit_storage_available: bool
    crossing_clear: bool
    path_clear: bool

    def __post_init__(self):
        if any(type(value) is not bool for value in vars(self).values()):
            raise ValueError("Readiness checks must be explicit booleans")

    @property
    def ready(self):
        return all(vars(self).values())


class AtomicClusterReservations:
    """Reserve an entire declared junction cluster and its exit as one lease.

    A denied request leaves all resources untouched. The owner may not add or
    change resources after acquisition, avoiding partial extension. The caller
    must report actual rear clearance; a timeout never releases a moving body.
    """

    def __init__(self):
        self._resources = {}
        self._leases = {}

    def acquire(self, vehicle_id: str, junctions: tuple[str, ...], exit_lane: str, readiness: Readiness) -> bool:
        if not isinstance(vehicle_id, str) or not vehicle_id or not isinstance(exit_lane, str) or not exit_lane:
            raise ValueError("Vehicle and exit lane IDs are required")
        if not isinstance(junctions, tuple) or not junctions or any(not isinstance(node, str) or not node for node in junctions):
            raise ValueError("A nonempty tuple of junction IDs is required")
        if len(set(junctions)) != len(junctions) or not isinstance(readiness, Readiness):
            raise ValueError("Junction IDs must be unique and readiness explicit")
        resources = frozenset([*(('junction', node) for node in junctions), ('exit', exit_lane)])
        previous = self._leases.get(vehicle_id)
        if previous is not None:
            if previous != resources:
                raise ValueError("An existing lease cannot be extended or changed")
            return True
        if not readiness.ready or any(resource in self._resources for resource in resources):
            return False
        self._leases[vehicle_id] = resources
        for resource in resources:
            self._resources[resource] = vehicle_id
        return True

    def release(self, vehicle_id: str, *, rear_clear: bool) -> bool:
        if type(rear_clear) is not bool:
            raise ValueError("Rear-clear state must be an explicit boolean")
        resources = self._leases.get(vehicle_id)
        if resources is None or not rear_clear:
            return False
        for resource in resources:
            del self._resources[resource]
        del self._leases[vehicle_id]
        return True

    def owner(self, kind: str, resource_id: str):
        return self._resources.get((kind, resource_id))
