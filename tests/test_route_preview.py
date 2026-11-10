from copy import deepcopy

import pytest

from services.route_preview import RoutePreviewError, preview_route, route_context
from simulation.contraflow import shared_network
from simulation.network_registry import load_registered_network
from simulation.traffic_engine import TrafficEngine


SITE_A, SITE_B = "tagum_site_a", "tagum_site_b"
SOUTH, NORTH, WEST, EAST = ("boundary_0", "boundary_1", "boundary_2", "boundary_3")


def network_source(site=SITE_A):
    return {"kind": "network", "network_id": site}


def arrangement(*lanes, **responses):
    return {"closed_lanes": list(lanes), "closure_responses": responses}


def request(source=None, vehicle_type="car", entry=WEST, destination=NORTH, **fields):
    source = source or network_source()
    return {
        "source": source,
        "vehicle_type": vehicle_type,
        "expected_network_sha256": load_registered_network(source.get("network_id", SITE_A)).fingerprint,
        "entry_id": entry,
        "destination_id": destination,
        **fields,
    }


def scenario(settings, fingerprint=None):
    source = {"kind": "scenario", "scenario_id": 23}
    row = {
        "id": 23, "name": "Saved arrangement", "network_id": SITE_A,
        "network_sha256": fingerprint, "engine_config": settings,
    }

    def load_scenario(scenario_id):
        return row if scenario_id == 23 else None

    return source, load_scenario


def test_entries_use_demand_boundaries_and_class_access():
    network = load_registered_network(SITE_B)
    car = route_context(network_source(SITE_B), "car")
    truck = route_context(network_source(SITE_B), "truck")
    assert {item["id"] for item in car["entries"]} == {"boundary_0", "boundary_1", "boundary_5", "boundary_9"}
    assert {item["id"] for item in truck["entries"]} == {"boundary_0", "boundary_5", "boundary_9"}
    assert "boundary_1" not in {item["id"] for item in truck["destinations"]}
    assert car["network_sha256"] == network.fingerprint
    assert car["geometry"]["network_id"] == network.id
    assert car["network_binding"] == "current_network"


def test_closed_entry_remains_selectable_and_reports_waiting():
    source, loader = scenario(arrangement("road4r", road4r="wait"))
    context = route_context(source, "car", load_scenario=loader)
    assert WEST in {item["id"] for item in context["entries"]}
    result = preview_route(request(source), load_scenario=loader)
    assert result["arrangement_valid"]
    assert result["outcome"] == "waiting_entry"
    assert result["selected"] is None and result["actual_destination_id"] is None
    assert result["original"]["lane_ids"][0] == "road4r"


def test_non_generating_boundary_can_be_returned_as_diversion_exit():
    result = preview_route(request(destination=SOUTH, closure_override=arrangement("road0f")))
    assert result["outcome"] == "alternative_exit"
    assert result["intended_destination_id"] == SOUTH
    assert result["actual_destination_id"] == "boundary_4"
    assert result["selected"]["destination_id"] == "boundary_4"


def test_disallowed_generated_pair_is_rejected():
    with pytest.raises(RoutePreviewError) as error:
        preview_route(request(network_source(SITE_B), entry="boundary_5", destination="boundary_4"))
    assert error.value.status_code == 422


def test_initial_snapshot_applies_zero_time_events_only():
    settings = {
        **arrangement("road1f", road1f="side_street", road2r="nearest_exit", road0f="nearest_exit"),
        "events": [
            {"time": 60, "lane_id": "road0f", "closed": True},
            {"time": 0, "lane_id": "road1f", "closed": False},
            {"time": 0, "lane_id": "road2r", "closed": True, "speed_factor": 0.5},
            {"time": 20, "lane_id": "road2r", "closed": False, "speed_factor": 1},
        ],
    }
    source, loader = scenario(settings)
    before = deepcopy(settings)
    context = route_context(source, "car", load_scenario=loader)
    assert context["initial_closures"] == arrangement("road2r", road2r="nearest_exit")
    assert context["network_binding"] == "current_unpinned"
    assert context["has_later_closure_changes"]
    assert any(notice["code"] == "later_closure_changes" for notice in context["notices"])
    result = preview_route(request(source), load_scenario=loader)
    assert result["effective_closed_lanes"] == ["road2r"]
    assert result["outcome"] == "alternative_exit"
    assert settings == before


def test_empty_override_clears_initial_closures_without_mutating_schedule():
    settings = {**arrangement("road2r", road2r="nearest_exit"),
                "events": [{"time": 20, "lane_id": "road2r", "closed": False}]}
    source, loader = scenario(settings)
    before = deepcopy(settings)
    result = preview_route(request(source, closure_override=arrangement()), load_scenario=loader)
    assert result["outcome"] == "unchanged"
    assert result["effective_closures"] == arrangement()
    assert settings == before
    assert route_context(source, "car", load_scenario=loader)["initial_closures"] == arrangement(
        "road2r", road2r="nearest_exit",
    )


def test_shared_paths_match_derived_network_and_keep_base_fingerprint(monkeypatch):
    def unexpected(*_args, **_kwargs):
        pytest.fail("Preview must not start or step a simulation")

    monkeypatch.setattr(TrafficEngine, "start", unexpected)
    monkeypatch.setattr(TrafficEngine, "step", unexpected)
    network = load_registered_network(SITE_A)
    base = deepcopy(network.payload)
    result = preview_route(request(closure_override=arrangement("road2r", road2r="share")))
    assert result["network_sha256"] == network.fingerprint
    assert result["effective_closed_lanes"] == []
    assert result["outcome"] == "unchanged" and result["uses_shared_pavement"]
    original, selected = result["original"], result["selected"]
    assert original["lane_ids"] == selected["lane_ids"]
    assert original["segments"] != selected["segments"]
    derived = shared_network(network, {"road2": "road2f"})
    assert result["shared_roads"][0]["shared_lane"] == "road2r"
    assert result["shared_roads"][0]["kept_lane"] == "road2f"
    assert result["shared_roads"][0]["width"] == derived.lanes["road2r"].width
    segment = next(item for item in selected["segments"] if item.get("lane_id") == "road2r")
    assert segment["points"] == [{"x": x, "y": y} for x, y in derived.lanes["road2r"].shape]
    assert any(item["kind"] == "connector" for item in selected["segments"])
    assert network.payload == base


def test_no_route_and_invalid_arrangement_are_distinct():
    unreachable = preview_route(request(closure_override=arrangement("road2r", "road6f")))
    assert unreachable["arrangement_valid"] and unreachable["outcome"] == "no_route"
    assert unreachable["selected"] is None
    network = load_registered_network(SITE_A)
    blocked = preview_route(request(closure_override=arrangement(*network.lanes)))
    assert not blocked["arrangement_valid"] and blocked["outcome"] == "invalid_arrangement"
    assert blocked["selected"] is None and blocked["original"]
    assert all(not option["enabled"] for options in blocked["response_options"].values() for option in options)


def test_stale_saved_fingerprint_is_refused():
    source, loader = scenario({}, "0" * 64)
    with pytest.raises(RoutePreviewError, match="network") as error:
        route_context(source, "car", load_scenario=loader)
    assert error.value.status_code == 409


@pytest.mark.parametrize("override", [
    None,
    arrangement("road2r", "road2r"),
    arrangement("unknown"),
    arrangement(road2r="share"),
    arrangement("road2r", road2r="unknown"),
])
def test_preview_rejects_malformed_closure_overrides(override):
    with pytest.raises(RoutePreviewError) as error:
        preview_route(request(closure_override=override))
    assert error.value.status_code == 422


def test_incompatible_saved_response_is_reported_and_can_be_changed_temporarily():
    source, loader = scenario(arrangement("road6f", road6f="share"))
    result = preview_route(request(source), load_scenario=loader)
    assert result["outcome"] == "invalid_arrangement" and result["selected"] is None
    choices = {choice["value"]: choice for choice in result["response_options"]["road6f"]}
    assert not choices["share"]["enabled"] and choices["share"]["reason"]
    assert choices["nearest_exit"]["enabled"]
    corrected = preview_route(request(source, closure_override=arrangement("road6f", road6f="nearest_exit")),
                              load_scenario=loader)
    assert corrected["arrangement_valid"]
