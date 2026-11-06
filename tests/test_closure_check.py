import pytest

from services.closure_check import closure_report
from tests.mixed_traffic_helpers import junction_network


def test_an_exit_road_with_no_way_round_has_no_detour():
    pieces = closure_report(junction_network(), [])["pieces"]
    assert {key: pieces["er"][key] for key in ("has_detour", "trips_using", "trips_without_route")} == {"has_detour": False, "trips_using": 3, "trips_without_route": 3}
    assert pieces["er"]["responses"] == ["nearest_exit"]


def test_an_entry_road_has_no_detour_and_a_road_used_by_nobody_says_so():
    pieces = closure_report(junction_network(), [])["pieces"]
    assert pieces["wf"]["has_detour"] is False and pieces["wf"]["trips_using"] == 3


def test_the_selection_is_checked_as_a_whole_with_a_plain_message():
    report = closure_report(junction_network(), ["wf", "wr", "ef", "er", "nf", "nr"])
    assert report["valid"] is False and "no legal movement" in report["message"]
    ok = closure_report(junction_network(), ["wr"])
    assert ok["valid"] is True and ok["message"] is None
    assert ok["selection"] == {"trips": 12, "trips_without_route": 3}


def test_unknown_lane_is_refused():
    with pytest.raises(ValueError, match="Unknown lane"):
        closure_report(junction_network(), ["nope"])


def test_options_describe_each_lane_for_the_closure_picker():
    from services.native_scenario_service import configuration_options
    lanes = {lane["id"]: lane for lane in configuration_options("tagum_site_a")["lanes"]}
    entries = [lane for lane in lanes.values() if lane["kind"] == "entry"]
    assert len(entries) == 4 and all(lane["road_id"] == lane["id"][:-1] for lane in lanes.values())
    assert {lane["direction"] for lane in lanes.values()} <= {"northbound", "southbound", "eastbound", "westbound"}


def test_closure_check_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    import backend.main as main
    monkeypatch.setattr(main, "require_any_permission", lambda user, permissions: None)
    main.app.dependency_overrides[main.require_current_user] = lambda: {"id": 1}
    try:
        client = TestClient(main.app)
        report = client.post("/api/networks/tagum_site_a/closure-check", json={"closed_lanes": []}).json()
        assert report["valid"] is True and "road0f" in report["pieces"]
        assert client.post("/api/networks/missing/closure-check", json={"closed_lanes": []}).status_code == 422
        assert client.post("/api/networks/tagum_site_a/closure-check", json={"closed_lanes": ["nope"]}).status_code == 422
    finally:
        main.app.dependency_overrides.pop(main.require_current_user, None)


def test_timed_closures_are_checked_with_the_selection():
    events = [{"time": 50, "lane_id": lane, "closed": True} for lane in ("er", "nr", "sr", "wr")]
    report = closure_report(junction_network(), [], events)
    assert report["valid"] is False and "at 50 s" in report["message"]


def test_options_say_where_each_road_piece_lies():
    from services.native_scenario_service import configuration_options
    where = {lane["road_id"]: lane["where"] for lane in configuration_options("tagum_site_a")["lanes"]}
    assert where["road2"].startswith("west, 0–226") and where["road4"].startswith("west, 226–2")
