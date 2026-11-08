"""Every road of a study site is connected (owner's hard requirement, D45): no loose ends, no near-misses, one piece.

Walks the graph of each registered study site. A road may end only at a true network boundary; every other node is a real shared
junction of at least two roads, every road meets its nodes exactly, no road crosses another except at a shared node, and
every lane can both be entered from a boundary and lead to one.
"""
import math
from collections import defaultdict

import pytest

from simulation.network_registry import load_registered_network

SITES = ["tagum_site_a", "tagum_site_b"]
NEAR_MISS_M = 5.0


def roads_at(network):
    touching = defaultdict(list)
    for road in network.payload["roads"]:
        touching[road["source"]].append(road["id"])
        touching[road["target"]].append(road["id"])
    return touching


def reachable(start, next_of):
    seen, frontier = set(start), list(start)
    while frontier:
        for following in next_of(frontier.pop()):
            if following not in seen:
                seen.add(following)
                frontier.append(following)
    return seen


@pytest.mark.parametrize("site", SITES)
def test_every_non_boundary_node_joins_at_least_two_roads(site):
    network = load_registered_network(site)
    touching = roads_at(network)
    for node in network.payload["nodes"]:
        if node.get("boundary"):
            assert len(touching[node["id"]]) >= 1, f"{node['id']} is a boundary with no road"
        else:
            assert len(touching[node["id"]]) >= 2, f"{node['id']} is a loose end: only {touching[node['id']]} reach it"


@pytest.mark.parametrize("site", SITES)
def test_the_network_is_one_connected_piece(site):
    network = load_registered_network(site)
    neighbours = defaultdict(set)
    for road in network.payload["roads"]:
        neighbours[road["source"]].add(road["target"])
        neighbours[road["target"]].add(road["source"])
    first = network.payload["nodes"][0]["id"]
    assert reachable([first], lambda node: neighbours[node]) == set(network.nodes)


@pytest.mark.parametrize("site", SITES)
def test_every_lane_reaches_a_boundary_and_can_be_entered_from_one(site):
    network = load_registered_network(site)
    onward = lambda lane: [other for other in network.outgoing[network.lanes[lane].target] if network.turn_allowed(lane, other)]
    before = defaultdict(list)
    for lane in network.lanes:
        for other in onward(lane):
            before[other].append(lane)
    leaving = {lane for lane, item in network.lanes.items() if item.target in network.boundaries}
    entering = {lane for lane, item in network.lanes.items() if item.source in network.boundaries}
    can_leave = reachable(leaving, lambda lane: before[lane])  # lanes from which some exit lane follows
    can_be_entered = reachable(entering, onward)
    assert not set(network.lanes)-can_leave, f"lanes that lead nowhere: {sorted(set(network.lanes)-can_leave)}"
    assert not set(network.lanes)-can_be_entered, f"lanes no boundary reaches: {sorted(set(network.lanes)-can_be_entered)}"


@pytest.mark.parametrize("site", SITES)
def test_no_near_misses(site):
    network = load_registered_network(site)
    nodes = network.payload["nodes"]
    for index, node in enumerate(nodes):
        for other in nodes[index+1:]:
            if not node.get("boundary") and not other.get("boundary"):
                assert math.dist((node["x"], node["y"]), (other["x"], other["y"])) > 25.0, f"{node['id']} and {other['id']} are almost one junction"
    for road in network.payload["roads"]:
        for node in nodes:
            if node["id"] in (road["source"], road["target"]):
                continue
            nearest = min(point_to_segment((node["x"], node["y"]), a, b) for a, b in zip(road["shape"], road["shape"][1:]))
            assert nearest > NEAR_MISS_M, f"{road['id']} passes {nearest:.1f} m from {node['id']} without joining it"


@pytest.mark.parametrize("site", SITES)
def test_roads_meet_only_at_shared_nodes(site):
    network = load_registered_network(site)
    roads = network.payload["roads"]
    for index, road in enumerate(roads):
        for other in roads[index+1:]:
            if {road["source"], road["target"]} & {other["source"], other["target"]}:
                continue
            for a, b in zip(road["shape"], road["shape"][1:]):
                for c, d in zip(other["shape"], other["shape"][1:]):
                    assert not segments_cross(a, b, c, d), f"{road['id']} crosses {other['id']} with no shared junction"


def point_to_segment(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    share = max(0.0, min(1.0, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/((dx*dx+dy*dy) or 1)))
    return math.hypot(point[0]-a[0]-share*dx, point[1]-a[1]-share*dy)


def segments_cross(a, b, c, d):
    side = lambda p, q, r: (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return side(a, b, c)*side(a, b, d) < 0 and side(c, d, a)*side(c, d, b) < 0
