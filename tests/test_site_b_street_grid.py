"""Site B with the owner's painted side streets (D45): the core is kept, every street joins at a junction, and side streets stay empty unless a detour needs them."""
import json
import math
from pathlib import Path

import pytest

from services.movement_counts import approach_boundaries
from simulation.closure_responses import usual_trips
from simulation.footprints import overlapping_pairs
from simulation.network_registry import load_registered_network
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine
from tools.site_b_measured_layout import build_measured_site_b
from tools.site_b_street_grid import build_site_b_street_grid

ROOT = Path(__file__).resolve().parents[1]/"data"/"networks"
INSTALLED = json.loads((ROOT/"tagum_site_b.json").read_text(encoding="utf-8"))
MEASURED = json.loads((ROOT/"tagum_site_b_pre_street_grid.json").read_text(encoding="utf-8"))
NETWORK = RoadNetwork(INSTALLED)
STUDY = "tagum_site_b_j"
ENDS = {"boundary_0": "Dao Street", "boundary_1": "Sobrecarey Street", "boundary_4": "Davao-Agusan National Highway", "boundary_5": "Davao-Agusan National Highway",
        "boundary_8": "Davao-Agusan National Highway", "boundary_9": "Davao-Agusan National Highway"}


def test_generator_reproduces_the_installed_network():
    assert build_site_b_street_grid() == INSTALLED


def test_the_previous_revision_is_listed_and_loads():
    entry = next(item for item in json.loads((ROOT/"registry.json").read_text(encoding="utf-8"))["networks"] if item["id"] == "tagum_site_b")
    listed = {item["file"]: item["sha256"] for item in entry["revision_history"]}
    assert listed["tagum_site_b_pre_street_grid.json"] == RoadNetwork(MEASURED).fingerprint != NETWORK.fingerprint
    assert entry["file"] == "tagum_site_b.json"


def test_the_measured_core_is_kept():
    """Same study and neighbouring junctions, ten original road ids, islands, sheds and site features; only what a new junction crosses is cut."""
    nodes, core_nodes = {node["id"]: node for node in INSTALLED["nodes"]}, {node["id"]: node for node in MEASURED["nodes"]}
    for node_id in (STUDY, "1115349256"):
        assert nodes[node_id] == core_nodes[node_id]
    assert INSTALLED["nodes"][0]["id"] == STUDY and NETWORK.intersections[0] == STUDY
    assert [road["id"] for road in INSTALLED["roads"][:10]] == [road["id"] for road in MEASURED["roads"]]
    assert {road["id"]: road["name"] for road in INSTALLED["roads"][:10]} == {road["id"]: road["name"] for road in MEASURED["roads"]}
    installed_features = {feature["id"]: feature for feature in INSTALLED["site_features"]}
    for feature in MEASURED["site_features"]:
        assert installed_features.get(feature["id"], feature) == feature or feature["kind"] == "street_light"
    assert {feature["id"] for feature in MEASURED["site_features"] if feature["kind"] != "street_light"} <= set(installed_features)
    lights = lambda payload: {feature["id"] for feature in payload["site_features"] if feature["kind"] == "street_light"}
    assert lights(MEASURED)-lights(INSTALLED) == {"light_2"}  # the one lamp that stood where the north-west street now joins
    assert {"Citi Hardware", "Jollibee"} <= {feature.get("label") for feature in INSTALLED["site_features"]}
    changed = {island["id"] for island in MEASURED["islands"] if island not in INSTALLED["islands"]}
    assert changed == {"median_sw_far", "median_gap_tip", "median_sw_near", "side_nw_far", "side_se_far", "side_nw_beyond_2"}  # only what the three new highway junctions cross is cut


def test_the_core_is_rebuilt_unchanged_without_the_grid():
    assert build_measured_site_b(json.loads((ROOT/"history"/"tagum_site_b_osm_corridor.json").read_text(encoding="utf-8"))) == MEASURED


def test_study_junction_stays_first_and_the_only_signal_and_new_junctions_are_first_come():
    engine = TrafficEngine(network=NETWORK)
    modes = {node: signal.mode for node, signal in engine.signals.items()}
    assert modes.pop(STUDY) == "signalized" and engine.controlled_junction == STUDY
    assert set(modes.values()) == {"first_come"} and len(modes) == 9
    new_junctions = [node for node in INSTALLED["nodes"] if node["id"].startswith("tagum_site_b_j") and node["id"] != STUDY]
    assert len(new_junctions) == 8 and all(node["generated_demand"] is False and node["default_control_mode"] == "first_come" for node in new_junctions)
    assert NETWORK.pedestrian_junctions == [STUDY, "1115349256"]  # as before; the new junctions draw no crosswalks


def test_only_the_highway_sobrecarey_and_dao_ends_remain_and_each_takes_generated_traffic():
    names = {node["id"]: next(road["name"] for road in INSTALLED["roads"] if node["id"] in (road["source"], road["target"])) for node in INSTALLED["nodes"] if node.get("boundary")}
    assert names == ENDS
    assert NETWORK.boundaries == NETWORK.demand_boundaries == list(ENDS)


def test_new_roads_are_unnamed_minor_side_streets_and_the_main_roads_are_not():
    for road in INSTALLED["roads"]:
        main = road["name"] in {"Davao-Agusan National Highway", "Dao Street", "Sobrecarey Street"}
        assert bool(road.get("minor")) == (not main), road["id"]
        assert main or road["name"] in {"Unnamed road", "Acacia Street", "Bonifacio Street"}
    new = [road for road in INSTALLED["roads"][10:] if road.get("minor")]
    assert len(new) == 4 and all(road["name"] == "Unnamed road" for road in new)


def test_the_sobrecarey_ban_covers_every_lane_of_the_street():
    sobrecarey = {f"{road['id']}{direction}" for road in INSTALLED["roads"] if road["name"] == "Sobrecarey Street" for direction in "fr"}
    assert len(sobrecarey) == 6 and set(NETWORK.lane_vehicle_restrictions) == sobrecarey
    assert all(restricted == frozenset({"bus", "truck"}) for restricted in NETWORK.lane_vehicle_restrictions.values())


def test_the_neighbouring_junction_keeps_its_bonifacio_kerb_rule_and_no_u_turn_through_an_opening():
    assert set(NETWORK.entry_kerb_vehicle_types) == {"road9f", "road19f"}  # the new entry lane, and the lane on to the neighbouring junction
    assert NETWORK.lanes["road19f"].source == "boundary_9" and NETWORK.lanes["road9f"].target == "1115349256"
    for entry, exit_ in (("road14f", "road15f"), ("road19f", "road20f"), ("road5f", "road4f"), ("road9f", "road8f")):  # boundary_5 to boundary_4 and boundary_9 to boundary_8, and as before at the two old junctions
        assert not NETWORK.turn_allowed(entry, exit_)


def test_a_street_meets_the_highway_only_on_its_median_centre_line():
    for node, clearance in (("tagum_site_b_j2", 16.0), ("tagum_site_b_j4", 16.0), ("tagum_site_b_j7", 28.0)):  # Osmeña leaves at about 38 degrees, so its stop lines stand further back
        assert NETWORK.clearance[node] == clearance
        highway = [road for road in INSTALLED["roads"] if node in (road["source"], road["target"]) and road["name"] == "Davao-Agusan National Highway"]
        assert len(highway) == 4


def test_the_field_counts_still_match_every_approach_to_a_boundary_through_the_grid():
    assert approach_boundaries(NETWORK) == {"south": ("boundary_0", "boundary_0"), "north": ("boundary_1", "boundary_1"), "east": ("boundary_9", "boundary_8"), "west": ("boundary_5", "boundary_4")}


def test_with_nothing_closed_generated_trips_never_use_a_side_street():
    """The two highway ends are a U-turn apart, so only a loop round the grid joins them: not a generated trip."""
    assert NETWORK.side_street_only_pairs == {("boundary_5", "boundary_4"), ("boundary_9", "boundary_8")}
    pairs = [(a, b) for a in NETWORK.demand_boundaries for b in NETWORK.demand_boundaries if a != b and NETWORK.outgoing[a] and NETWORK.incoming[b]]
    served = [pair for pair in pairs if pair not in NETWORK.side_street_only_pairs]
    assert len(served) == 12
    for source, target in served:
        assert not set(NETWORK.route(source, target)) & NETWORK.minor_lanes, (source, target)
    assert not any(pair in NETWORK.side_street_only_pairs for pair in usual_trips(NETWORK))


def test_a_closure_on_sobrecarey_sends_the_highway_traffic_round_by_the_grid():
    trip = NETWORK.route("boundary_9", "boundary_1")
    assert not set(trip) & NETWORK.minor_lanes and "road1f" in trip
    detour = NETWORK.route("boundary_9", "boundary_1", closed={"road1f"})
    assert detour and "road1f" not in detour and set(detour) & NETWORK.minor_lanes
    engine = TrafficEngine(seed=7, network=NETWORK)
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static", closed_lanes=["road1f"],
                     trips=[{"time": 1, "source": "boundary_9", "destination": "boundary_1", "vehicle_type": "car"}])
    engine.driver_variation_scale = 0
    engine.start(300)
    engine.step(3000)
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["unfinished_vehicles"], metrics["diverted_vehicles"]) == (1, 0, 0)
    assert not overlapping_pairs(engine.vehicle_records())


def test_a_closure_on_dao_can_be_left_by_the_loop_through_the_median_opening():
    detour = NETWORK.route("boundary_5", "boundary_0", closed={"road0f"})
    assert detour and "road0f" not in detour and set(detour) & NETWORK.minor_lanes


def test_traffic_with_no_closure_never_enters_a_side_street():
    engine = load_engine("medium")
    side = NETWORK.minor_lanes
    for _ in range(1800):
        engine.step(1)
        assert not [vehicle.id for vehicle in engine.vehicles.values() if vehicle.route[0] in side]
    assert engine._last_metrics["vehicle_conservation_error"] == 0


def load_engine(density):
    from services.native_controller import apply_controller
    from simulation.network_registry import engine_for_scenario
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    engine = engine_for_scenario({"network_id": "tagum_site_b", "engine_config": {"traffic_density": density, "pedestrian_density": "low", "vehicle_mix": dict(TAGUM_PROVISIONAL_MIX)}}, seed=101)
    apply_controller(engine, "no-signal")
    engine.start(180)
    return engine


def test_a_bend_is_a_25_m_arc():
    """Each new side street's bends are drawn as arcs: no corner of more than 6 degrees remains in its shape."""
    for road in (road for road in INSTALLED["roads"][10:] if road.get("minor")):
        headings = [math.atan2(b[1]-a[1], b[0]-a[0]) for a, b in zip(road["shape"], road["shape"][1:])]
        turns = [abs((second-first+math.pi) % (2*math.pi)-math.pi) for first, second in zip(headings, headings[1:])]
        assert math.degrees(max(turns, default=0)) <= 6.0, road["id"]
