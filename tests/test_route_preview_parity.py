import pytest

from services.route_preview import RoutePreviewError, preview_route
from simulation.network_registry import load_registered_network
from simulation.traffic_engine import TrafficEngine


@pytest.mark.parametrize(("site", "source", "destination", "vehicle_type", "closed", "responses", "mode", "outcome"), [
    ("tagum_site_a", "boundary_2", "boundary_1", "car", [], {}, "static", "unchanged"),
    ("tagum_site_a", "boundary_2", "boundary_1", "car", ["road2r"], {"road2r": "side_street"}, "static", "detour"),
    ("tagum_site_a", "boundary_2", "boundary_1", "car", ["road2r"], {"road2r": "side_street_adaptive"}, "adaptive", "detour"),
    ("tagum_site_a", "boundary_3", "boundary_1", "car", ["road1f"], {"road1f": "nearest_exit"}, "static", "alternative_exit"),
    ("tagum_site_a", "boundary_2", "boundary_1", "car", ["road2r", "road6f"], {}, "static", "no_route"),
    ("tagum_site_a", "boundary_2", "boundary_1", "car", ["road4r"], {"road4r": "wait"}, "static", "waiting_entry"),
    ("tagum_site_a", "boundary_2", "boundary_1", "bus", ["road2r"], {"road2r": "share"}, "static", "unchanged"),
    ("tagum_site_b", "boundary_9", "boundary_1", "motorcycle", ["road1f"], {"road1f": "share"}, "static", "unchanged"),
    ("tagum_site_b", "boundary_9", "boundary_1", "car", ["road9f"], {"road9f": "nearest_exit"}, "static", "detour"),
    ("tagum_site_b", "boundary_9", "boundary_1", "truck", [], {}, "static", "restricted"),
])
def test_preview_matches_disposable_engine_vehicle_arrival(site, source, destination, vehicle_type, closed, responses, mode, outcome):
    network = load_registered_network(site)
    override = {"closed_lanes": closed, "closure_responses": responses}
    payload = {
        "source": {"kind": "network", "network_id": site},
        "expected_network_sha256": network.fingerprint,
        "vehicle_type": vehicle_type, "entry_id": source, "destination_id": destination,
        "closure_override": override,
    }
    engine = TrafficEngine(seed=101, network=network)
    settings = {
        **override, "traffic_density": "none", "pedestrian_density": "none",
        "trips": [{"time": 0, "source": source, "destination": destination, "vehicle_type": vehicle_type}],
    }
    if outcome == "restricted":
        with pytest.raises(ValueError, match="vehicle access"):
            engine.configure(**settings)
        with pytest.raises(RoutePreviewError) as error:
            preview_route(payload)
        assert error.value.status_code == 422
        return

    engine.configure(**settings)
    engine.start(1)
    preview = preview_route(payload)
    assert preview["routing_mode"] == engine.config["routing_mode"] == mode
    assert preview["outcome"] == outcome
    assert engine.requested_vehicles == 1
    if not engine.vehicles:
        assert preview["selected"] is None and preview["actual_destination_id"] is None
        assert len(engine.pending_demand) == 1 and engine.diverted_vehicles == 0
    else:
        vehicle, = engine.vehicles.values()
        assert preview["selected"]["lane_ids"] == vehicle.route
        assert preview["actual_destination_id"] == vehicle.destination
        assert vehicle.diverted == ("nearest_exit" in responses.values())
        assert preview["uses_shared_pavement"] == any(lane[:-1] in engine.shared_roads for lane in vehicle.route)
