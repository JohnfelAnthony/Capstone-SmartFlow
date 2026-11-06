"""Shared-lane closure ("contraflow"), hypothetical: when one direction of a road is closed, its traffic moves onto half of the opposite
direction's pavement, so that pavement carries one lane each way. No road is added and no network file changes: a derived network is built
at run time in which the road's centre line is moved half its width toward the open pavement and each direction keeps half the width. Lane
ids, nodes and junction topology are the same, so routing, signals and the RL observation see the same lanes. It assumes cones, signs and
usually an enforcer; neither study site has an enforcer today, and the widths are provisional.

Eligible: a two-way road at least MIN_WIDTH_M wide per direction (room for a lane each way) and MIN_LENGTH_M long. Not the narrow side streets,
not a one-way carriageway (a divided highway needs crossover paths through its median openings, which are not built).
"""
from __future__ import annotations

import copy
import math
from functools import lru_cache

from .road_network import RoadNetwork, length, sample, width_per_direction

MIN_WIDTH_M = 6.0
MIN_LENGTH_M = 60.0
TAPER_M = 25.0  # the moved centre line eases back onto the original over this distance at each junction
STEP_M = 5.0


def lane_ids(road_id: str) -> tuple[str, str]:
    return f"{road_id}f", f"{road_id}r"


def road_of(lane_id: str) -> str:
    return lane_id[:-1]


def kept_lane(lane_id: str) -> str:
    """The lane that keeps its own pavement when `lane_id` is the closed, shared direction."""
    forward, reverse = lane_ids(road_of(lane_id))
    return reverse if lane_id == forward else forward


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value*value*(3-2*value)


def shifted_shape(shape: list, toward_right: bool, shift: float, taper: float = TAPER_M) -> list:
    """The centre line moved `shift` metres to its right (or left) along its middle, easing back to the original at both ends."""
    total = length(shape)
    taper = min(taper, 0.4*total)
    positions = sorted({0.0, total, *(index*STEP_M for index in range(1, int(total/STEP_M))), taper, total-taper})
    points = []
    for position in positions:
        x, y, heading = sample(shape, position)
        offset = (1 if toward_right else -1)*shift*_smoothstep(min(position, total-position)/taper)
        points.append((x+math.sin(heading)*offset, y-math.cos(heading)*offset))
    points[0], points[-1] = tuple(shape[0]), tuple(shape[-1])
    return points


def _eligible_road(road: dict) -> bool:
    return not road.get("oneway") and width_per_direction(road) >= MIN_WIDTH_M and length([tuple(point) for point in road["shape"]]) >= MIN_LENGTH_M


def derive(network: RoadNetwork, active: dict[str, str]) -> RoadNetwork:
    """The network with each road in `active` (road id to the lane that keeps its own pavement) shared. Raises ValueError if it cannot be built."""
    payload = copy.deepcopy(network.payload)
    roads = {road["id"]: road for road in payload["roads"]}
    for road_id, kept in active.items():
        road = roads.get(road_id)
        if road is None or not _eligible_road(road) or kept not in lane_ids(road_id):
            raise ValueError(f"Road {road_id} cannot share its pavement")
        width = width_per_direction(road)
        # The forward lane drives on the right of the road's shape, the reverse lane on its left.
        moved = shifted_shape([tuple(point) for point in road["shape"]], kept.endswith("f"), width/2)
        road["shape"] = [[round(x, 3), round(y, 3)] for x, y in moved]
        road["width_per_direction_m"] = width/2
        road["osm_tags"] = {**(road.get("osm_tags") or {}), "lanes": "2"}
    derived = RoadNetwork(payload)
    if any(abs(derived.clearance[node]-network.clearance[node]) > 1e-9 for node in network.clearance):
        raise ValueError("Sharing this road would move the stop lines of its junctions")
    return derived


_NETWORKS: dict[int, RoadNetwork] = {}


@lru_cache(maxsize=256)
def _derived(network_id: int, fingerprint: str, active: tuple) -> RoadNetwork:
    return derive(_NETWORKS[network_id], dict(active))


def shared_network(network: RoadNetwork, active: dict[str, str]) -> RoadNetwork:
    """`derive`, cached per base network and set of shared roads (every engine on the network reuses it)."""
    if not active:
        return network
    _NETWORKS[id(network)] = network
    return _derived(id(network), network.fingerprint, tuple(sorted(active.items())))


@lru_cache(maxsize=64)
def _eligible(network_id: int, fingerprint: str) -> frozenset:
    network = _NETWORKS[network_id]
    roads = set()
    for road in network.payload["roads"]:
        if not _eligible_road(road):
            continue
        try:
            for kept in lane_ids(road["id"]):
                derive(network, {road["id"]: kept})
        except ValueError:
            continue
        roads.add(road["id"])
    return frozenset(roads)


def eligible_roads(network: RoadNetwork) -> frozenset:
    """Road ids whose closed direction can share the opposite pavement."""
    _NETWORKS[id(network)] = network
    return _eligible(id(network), network.fingerprint)


def strip_geometry(network: RoadNetwork, shared_lane: str) -> dict:
    """What to draw for a shared road: both lanes' centre lines and their width, taken from the derived network."""
    derived = shared_network(network, {road_of(shared_lane): kept_lane(shared_lane)})
    lanes = {lane: [[round(x, 2), round(y, 2)] for x, y in derived.lanes[lane].shape] for lane in lane_ids(road_of(shared_lane))}
    return {"road_id": road_of(shared_lane), "shared_lane": shared_lane, "kept_lane": kept_lane(shared_lane), "width": derived.lanes[shared_lane].width, "lanes": lanes}
