"""Each approach of a study site's junction as the boundary nodes its traffic enters and leaves by."""
from __future__ import annotations

import math

from simulation.scenario_config import is_study_site


def _heading(lane, at_start: bool) -> float:
    a, b = lane.shape[:2] if at_start else lane.shape[-2:]
    return math.atan2(b[1]-a[1], b[0]-a[0])


def _turn(first: float, second: float) -> float:
    return abs((first-second+math.pi) % (2*math.pi)-math.pi)


def _leg_boundary(network, lane, upstream: bool) -> str:
    """The boundary node a leg reaches, going straight on through any neighboring junction."""
    node = lane.source if upstream else lane.target
    while not network.nodes[node].get("boundary"):
        if upstream:
            candidates = [network.lanes[other] for other in network.incoming[node] if network.turn_allowed(other, lane.id)]
            lane = min(candidates, key=lambda other: _turn(_heading(other, False), _heading(lane, True)))
            node = lane.source
        else:
            candidates = [network.lanes[other] for other in network.outgoing[node] if network.turn_allowed(lane.id, other)]
            lane = min(candidates, key=lambda other: _turn(_heading(lane, False), _heading(other, True)))
            node = lane.target
    return node


def approach_boundaries(network) -> dict[str, tuple[str, str]]:
    """Each approach of the study junction (the network's first) as its (entry boundary, exit boundary)."""
    if not is_study_site(network.id):
        raise ValueError("Movement counts need a study site")
    junction = network.intersections[0]
    outgoing = [network.lanes[lane_id] for lane_id in network.outgoing[junction]]
    result, used = {}, set()
    for lane_id in network.incoming[junction]:
        incoming = network.lanes[lane_id]
        # A split carriageway leaves on a different road, so the leg's exit is the lane running back the way the entry came.
        backward = _heading(incoming, False)+math.pi
        exit_lane = min(outgoing, key=lambda lane: _turn(_heading(lane, True), backward))
        if exit_lane.id in used:
            raise ValueError("Two approaches match one exit; the site needs an explicit approach mapping")
        used.add(exit_lane.id)
        result[incoming.approach] = (_leg_boundary(network, incoming, True), _leg_boundary(network, exit_lane, False))
    return result
