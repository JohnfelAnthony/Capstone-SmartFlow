"""How traffic responds to a closed road: which responses work, validation, the routing rule and the nearest-exit response (engine native-10)."""
import pytest

from services.closure_check import closure_report
from simulation.closure_responses import NEAREST_EXIT, SHARE, SIDE_STREET, SIDE_STREET_ADAPTIVE, WAIT, available_responses
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config
from simulation.traffic_engine import TrafficEngine

A, B = "tagum_site_a", "tagum_site_b"
EAST, NORTH = "boundary_3", "boundary_1"


def offered(site, closed, lane):
    return available_responses(load_registered_network(site), set(closed), lane)["available"]


def test_a_road_next_to_the_loop_offers_the_side_street_sharing_and_the_nearest_exit():
    assert offered(A, ["road2r"], "road2r") == [SIDE_STREET, SIDE_STREET_ADAPTIVE, SHARE, NEAREST_EXIT]
    assert available_responses(load_registered_network(A), {"road2r"}, "road2r")["default"] == SIDE_STREET


def test_closing_a_road_in_both_directions_still_offers_the_side_street_but_not_sharing():
    both = offered(A, ["road2f", "road2r"], "road2r")
    assert SIDE_STREET in both and SHARE not in both


def test_a_wide_road_with_no_detour_offers_sharing_first_and_the_nearest_exit():
    assert offered(A, ["road3f"], "road3f") == [SHARE, NEAREST_EXIT]  # the east exit: nowhere else for its traffic to go
    assert available_responses(load_registered_network(A), {"road3f"}, "road3f")["default"] == SHARE


def test_roads_too_narrow_or_too_short_to_share_do_not_offer_it():
    assert offered(A, ["road6f"], "road6f") == [NEAREST_EXIT] or SHARE not in offered(A, ["road6f"], "road6f")  # the side street is one lane wide
    assert SHARE not in offered(A, ["road4f"], "road4f")  # the 24 m west stub


def test_a_closed_entry_road_offers_waiting_and_sharing_only_where_the_road_can_share():
    assert offered(A, ["road4r"], "road4r") == [WAIT]  # the 24 m west stub is too short to share
    assert offered(A, ["road3r"], "road3r") == [SHARE, WAIT]  # the east entry road


def test_site_b_has_no_detour_so_it_never_offers_avoiding_jams():
    network = load_registered_network(B)
    for lane in network.lanes:
        assert SIDE_STREET_ADAPTIVE not in available_responses(network, {lane}, lane)["available"]


def test_at_site_b_only_sobrecarey_can_share():
    network = load_registered_network(B)
    sharing = {lane for lane in network.lanes if SHARE in available_responses(network, {lane}, lane)["available"]}
    assert sharing == {"road1f", "road1r"}


def test_sharing_is_refused_in_plain_words_where_it_does_not_work_and_a_shared_direction_is_not_counted_as_closed():
    with pytest.raises(ValueError, match="does not work"):
        validate_config(DEFAULTS, {"closed_lanes": ["road6f"], "closure_responses": {"road6f": SHARE}}, load_registered_network(A))
    config = validate_config(DEFAULTS, {"closed_lanes": ["road2r"], "closure_responses": {"road2r": SHARE}}, load_registered_network(A))
    assert config["closure_responses"] == {"road2r": SHARE} and config["routing_mode"] == "static"


@pytest.mark.parametrize("responses,fragment", [
    ({"road3f": SIDE_STREET}, "does not work"),
    ({"road2r": WAIT}, "does not work"),
    ({"road2r": "teleport"}, "Unknown response"),
    ({"road1f": NEAREST_EXIT}, "never closed"),
])
def test_an_unavailable_or_unknown_response_is_refused_in_plain_words(responses, fragment):
    with pytest.raises(ValueError, match=fragment):
        validate_config(DEFAULTS, {"closed_lanes": ["road2r", "road3f"], "closure_responses": responses}, load_registered_network(A))


def test_avoiding_jams_for_one_closure_and_the_plain_side_street_for_another_is_refused():
    with pytest.raises(ValueError, match="whole scenario"):
        validate_config(DEFAULTS, {"closed_lanes": ["road2r", "road2f"], "closure_responses": {"road2r": SIDE_STREET_ADAPTIVE, "road2f": SIDE_STREET}}, load_registered_network(A))


def test_a_study_site_run_is_static_unless_a_closure_chose_to_avoid_jams():
    network = load_registered_network(A)
    assert validate_config(DEFAULTS, {"routing_mode": "adaptive"}, network)["routing_mode"] == "static"
    assert validate_config(DEFAULTS, {"routing_mode": "adaptive", "closed_lanes": ["road2r"]}, network)["routing_mode"] == "static"
    chosen = validate_config(DEFAULTS, {"closed_lanes": ["road2r"], "closure_responses": {"road2r": SIDE_STREET_ADAPTIVE}}, network)
    assert chosen["routing_mode"] == "adaptive"
    timed = validate_config(DEFAULTS, {"events": [{"time": 30, "lane_id": "road2r", "closed": True}], "closure_responses": {"road2r": SIDE_STREET_ADAPTIVE}}, network)
    assert timed["routing_mode"] == "adaptive"


def test_the_five_junction_network_keeps_whatever_routing_it_is_given():
    network = load_registered_network("tagum_network")
    assert validate_config(DEFAULTS, {"routing_mode": "adaptive"}, network)["routing_mode"] == "adaptive"
    assert validate_config(DEFAULTS, {"routing_mode": "static"}, network)["routing_mode"] == "static"


def test_a_saved_scenario_with_closures_and_no_recorded_response_behaves_as_before():
    config = validate_config(DEFAULTS, {"closed_lanes": ["road2r"]}, load_registered_network(A))
    assert config["closure_responses"] == {} and config["routing_mode"] == "static"


def run_east_to_north(response, *, seconds=400, events=None):
    """An east-to-north trip normally goes straight through the study junction (road1f). With road1f closed the loop is a detour (road2f, road6f);
    the nearest open exit from the study junction is another one (west or south)."""
    scenario = {"network_id": A, "engine_config": {"traffic_density": "none", "pedestrian_density": "none", "closure_responses": {"road1f": response},
                                                   "trips": [{"time": 1, "source": EAST, "destination": NORTH, "vehicle_type": "car"}],
                                                   **({"events": events} if events else {"closed_lanes": ["road1f"]})}}
    engine = engine_for_scenario(scenario, seed=7)
    engine.driver_variation_scale = 0
    engine.start(seconds)
    engine.step(seconds*10)
    return engine._last_metrics


def test_the_side_street_response_takes_the_loop():
    metrics = run_east_to_north(SIDE_STREET)
    assert (metrics["throughput"], metrics["diverted_vehicles"], metrics["lanes"]["road6f"]["exits"]) == (1, 0, 1)


def test_the_nearest_exit_response_diverts_even_where_the_loop_exists():
    metrics = run_east_to_north(NEAREST_EXIT)
    assert (metrics["throughput"], metrics["diverted_vehicles"], metrics["lanes"]["road6f"]["exits"]) == (1, 1, 0)


def test_the_nearest_exit_response_also_diverts_a_vehicle_already_underway_when_the_road_closes():
    events = [{"time": 3, "lane_id": "road1f", "closed": True}]
    metrics = run_east_to_north(NEAREST_EXIT, events=events)
    assert metrics["diverted_vehicles"] == 1 and metrics["lanes"]["road6f"]["exits"] == 0
    assert run_east_to_north(SIDE_STREET, events=events)["lanes"]["road6f"]["exits"] == 1


def test_the_closure_check_lists_the_responses_for_each_piece_and_the_one_to_preselect():
    report = closure_report(load_registered_network(A), ["road2r"])
    piece = report["pieces"]["road2r"]
    assert piece["responses"] == [SIDE_STREET, SIDE_STREET_ADAPTIVE, SHARE, NEAREST_EXIT] and piece["default_response"] == SIDE_STREET
    assert report["pieces"]["road4r"]["responses"] == [WAIT]


def test_site_validation_stays_static_even_for_a_scenario_that_chose_to_avoid_jams():
    from services.site_simulation import validation_engine
    scenario = {"network_id": A, "engine_config": {"closed_lanes": ["road2r"], "closure_responses": {"road2r": SIDE_STREET_ADAPTIVE}}}
    assert engine_for_scenario(scenario, seed=1).config["routing_mode"] == "adaptive"  # training and evaluation follow the saved choice
    engine = validation_engine(scenario, 1)
    assert engine.config["routing_mode"] == "static" and engine.config["closure_responses"] == {"road2r": SIDE_STREET}


def test_training_follows_the_scenarios_saved_choice():
    from simulation.rl_env import SmartFlowRLEnv
    scenario = {"network_id": A, "engine_config": {"traffic_density": "low", "closed_lanes": ["road2r"], "closure_responses": {"road2r": SIDE_STREET_ADAPTIVE}}}
    env = SmartFlowRLEnv(scenario=scenario, seed=11, warmup_seconds=0, evaluation_seconds=5)
    env.reset(seed=11)
    assert env.engine.config["routing_mode"] == "adaptive"
    env.close()
