"""Shared-lane closure in the engine (hypothetical): the closed direction's traffic uses half of the opposite pavement while the closure lasts.

Site A's west piece: road2r runs from the west junction to the study junction, road2f the other way. Closing road2r with the response
"share" moves its traffic onto the road2f pavement, one lane each way; the lanes are drained of vehicles before the road is changed.
"""
from simulation.contraflow import lane_ids
from simulation.footprints import overlapping_pairs
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.scenario_config import TAGUM_PROVISIONAL_MIX

WEST, EAST = "boundary_2", "boundary_3"
WINDOW = [{"time": 40.0, "lane_id": "road2r", "closed": True}, {"time": 300.0, "lane_id": "road2r", "closed": False}]


def trip(time, source, destination, kind="car"):
    return {"time": time, "source": source, "destination": destination, "vehicle_type": kind}


def build(*, share=True, events=None, closed=None, trips=(), density="none", seconds=500):
    config = {"traffic_density": density, "pedestrian_density": "none", "trips": list(trips), "vehicle_mix": dict(TAGUM_PROVISIONAL_MIX)}
    config.update({"events": events} if events is not None else {"closed_lanes": closed or []})
    if share:
        config["closure_responses"] = {"road2r": "share"}
    engine = engine_for_scenario({"network_id": "tagum_site_a", "engine_config": config}, seed=7)
    engine.driver_variation_scale = 0
    engine.start(seconds)
    return engine


def run_until(engine, seconds):
    engine.step(int(round((seconds-engine.simulation_time)/0.1)))


def test_both_directions_keep_flowing_while_the_pavement_is_shared():
    trips = [trip(60+10*index, WEST, EAST) for index in range(6)] + [trip(65+10*index, EAST, WEST) for index in range(6)]  # early enough for the ~710 m crossing to finish while the pavement is shared
    engine = build(events=WINDOW, trips=trips)
    base = engine.base_network
    run_until(engine, 200)
    metrics = engine._last_metrics
    assert engine.network is not base and metrics["shared_lane_roads"] == 1
    assert [engine.network.lanes[lane].width for lane in lane_ids("road2")] == [base.lanes["road2r"].width/2]*2
    run_until(engine, 290)
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["diverted_vehicles"], metrics["closure_held_vehicles"], metrics["unfinished_vehicles"]) == (12, 0, 0, 0)
    assert "road2r" not in engine.closed_lanes  # the shared direction is not closed: it carries traffic


def test_the_road_goes_back_to_normal_when_the_closure_ends():
    engine = build(events=WINDOW, trips=[trip(310, WEST, EAST), trip(315, EAST, WEST)])
    run_until(engine, 450)
    base = engine.base_network
    assert engine.network is base and engine._last_metrics["shared_lane_roads"] == 0
    assert engine._last_metrics["throughput"] == 2 and engine.closed_lanes == set()


def test_the_road_changes_only_once_every_vehicle_on_its_two_lanes_has_left():
    trips = [trip(second, WEST, EAST) for second in range(10, 40, 4)] + [trip(second, EAST, WEST) for second in range(12, 40, 4)]
    engine = build(events=WINDOW, trips=trips)
    base, swapped_at = engine.base_network, None
    while engine.simulation_time < 120:
        engine.step(1)
        if swapped_at is None and engine.network is not base:
            swapped_at = engine.simulation_time
            on_the_road = [vehicle.id for vehicle in engine.vehicles.values() if vehicle.route[0] in ("road2r", "road2f")]
            heading_in = [vehicle.id for vehicle in engine.vehicles.values() if len(vehicle.route) > 1 and vehicle.route[1] in ("road2r", "road2f") and vehicle.connector is not None]
            assert on_the_road == [] and heading_in == []
    assert swapped_at is not None and swapped_at >= 40


def test_a_closure_from_the_start_shares_at_once():
    engine = build(closed=["road2r"])
    assert engine.network is not engine.base_network and engine._last_metrics["shared_lane_roads"] == 1 and "road2r" not in engine.closed_lanes


def test_without_the_response_the_closure_works_as_it_always_did():
    engine = build(share=False, events=WINDOW, trips=[trip(100, WEST, EAST)])
    run_until(engine, 200)
    assert engine.network is engine.base_network and "road2r" in engine.closed_lanes and engine._last_metrics["shared_lane_roads"] == 0


def test_two_busy_directions_on_one_pavement_never_overlap():
    engine = build(events=[{"time": 100.0, "lane_id": "road2r", "closed": True}, {"time": 400.0, "lane_id": "road2r", "closed": False}], density="medium", seconds=500)
    base = engine.base_network
    shared_seen = False
    while engine.simulation_time < 480:
        engine.step(1)
        shared_seen = shared_seen or engine.network is not base
        assert not overlapping_pairs(engine.vehicle_records()), f"overlap at {engine.simulation_time}s"
    assert shared_seen and engine._last_metrics["stalled_vehicles"] == 0


def test_the_derived_network_does_not_change_what_the_base_network_is():
    base = load_registered_network("tagum_site_a")
    fingerprint = base.fingerprint
    build(events=WINDOW)
    assert load_registered_network("tagum_site_a").fingerprint == fingerprint


def test_a_scenario_saved_with_a_shared_closure_from_the_start_records_the_base_networks_fingerprint_and_runs_again():
    import database
    base = load_registered_network("tagum_site_a")
    saved = database.validated_native_scenario("tagum_site_a", {"closed_lanes": ["road2r"], "closure_responses": {"road2r": "share"}})
    assert saved["network_sha256"] == base.fingerprint
    import json
    scenario = {"network_id": "tagum_site_a", "network_sha256": saved["network_sha256"], "engine_config": json.loads(saved["engine_config"])}
    engine = engine_for_scenario(scenario, seed=3)  # raises when the saved fingerprint does not match the network
    engine.configure_from_scenario(scenario)  # and again on an engine that is already sharing
    assert engine.base_network.fingerprint == base.fingerprint and engine.network is not engine.base_network


def test_the_live_frame_sent_to_the_map_carries_the_shared_road_and_stays_unchanged_when_nothing_is_shared():
    from services.render_frame_service import build_render_frame
    sharing = build(closed=["road2r"])
    shared = build_render_frame(sharing.to_dict())["visual"]["shared_roads"]
    assert [(road["road_id"], road["shared_lane"], road["kept_lane"]) for road in shared] == [("road2", "road2r", "road2f")]
    assert "shared_roads" not in build_render_frame(build(share=False).to_dict())["visual"]
