"""Reviewed Field Observer counts become scenario demand (D38). The export below is SYNTHETIC: invented events, no field measurement."""
import csv
import hashlib
import io
import json

import pytest

from services.field_observer_counts import import_field_counts

SITE = "tagum_site_a"
COMMON = {"survey_id": "S1", "intersection_id": "site_a", "camera_id": "C1", "take_id": "T1", "view_segment_id": "V1"}
EVENT_FIELDS = (*COMMON, "event_id", "episode_id", "event_type", "location_id", "time_s", "frame_pts", "approach_id", "exit_id",
                "crossing_id", "direction", "reviewed_class", "vehicle_subtype", "review_status", "review_method", "reviewer", "note")
COVERAGE_FIELDS = (*COMMON, "event_type", "location_id", "start_s", "end_s", "visibility", "review_method", "reviewer", "note")
BIN_FIELDS = (*COMMON, "start_s", "end_s", "event_type", "location_id", "reviewed_class", "vehicle_subtype", "observed_count", "count",
              "coverage", "review_state", "publication_status")
LINES = [  # approach_id names the leg the line is on, in the engine's own words
    {"id": "l1", "location_id": "arr_south", "event_type": "vehicle_arrival", "approach_id": "south", "role": "arrival"},
    {"id": "l2", "location_id": "arr_west", "event_type": "vehicle_arrival", "approach_id": "west", "role": "arrival"},
    {"id": "l3", "location_id": "exit_north", "event_type": "vehicle_discharge", "approach_id": "north", "role": "exit"},
    {"id": "l4", "location_id": "exit_east", "event_type": "vehicle_discharge", "approach_id": "east", "role": "exit"},
]
SPAN = 120.0  # two 60 s bins


def csv_text(fields, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def event(event_id, kind, location, time_s, *, episode, cls="car", subtype="", status="accepted"):
    return {**COMMON, "event_id": event_id, "episode_id": episode, "event_type": kind, "location_id": location, "time_s": time_s, "frame_pts": "",
            "approach_id": "", "exit_id": "", "crossing_id": "", "direction": "", "reviewed_class": cls, "vehicle_subtype": subtype,
            "review_status": status, "review_method": "manual", "reviewer": "T", "note": ""}


def vehicle(name, arrive_s, source, sink, exit_s=None, **kind):
    arrival = event(f"{name}-a", "vehicle_arrival", f"arr_{source}", arrive_s, episode=name, **kind)
    leave = event(f"{name}-x", "vehicle_discharge", f"exit_{sink}", exit_s if exit_s is not None else arrive_s + 8, episode=name, **kind)
    return [arrival, leave]


def export(vehicles, *, blank=None, incomplete_coverage=None, lines=None):
    """The five files of a revision. Bin counts come from the accepted events, so the export is consistent unless a test breaks it."""
    events = [row for group in vehicles for row in group]
    classes = sorted({(row["reviewed_class"], row["vehicle_subtype"]) for row in events} | {("car", "")})
    bins = []
    for location, kind in (("arr_south", "vehicle_arrival"), ("arr_west", "vehicle_arrival"), ("exit_north", "vehicle_discharge"), ("exit_east", "vehicle_discharge")):
        for left in (0.0, 60.0):
            for cls, subtype in classes:
                count = sum(row["location_id"] == location and row["reviewed_class"] == cls and row["vehicle_subtype"] == subtype
                            and left <= float(row["time_s"]) < left + 60 for row in events)
                missing = blank == (location, left)
                bins.append({**COMMON, "start_s": left, "end_s": left + 60, "event_type": kind, "location_id": location, "reviewed_class": cls,
                             "vehicle_subtype": subtype, "observed_count": count, "count": "" if missing else count,
                             "coverage": "incomplete" if missing else "complete", "review_state": "manual_review_recorded", "publication_status": "provisional"})
    coverage = [{**COMMON, "event_type": kind, "location_id": location, "start_s": 0, "end_s": incomplete_coverage.get(location, SPAN) if incomplete_coverage else SPAN,
                 "visibility": "complete", "review_method": "manual", "reviewer": "T", "note": ""}
                for location, kind in (("arr_south", "vehicle_arrival"), ("arr_west", "vehicle_arrival"), ("exit_north", "vehicle_discharge"), ("exit_east", "vehicle_discharge"))]
    files = {"events.csv": csv_text(EVENT_FIELDS, events), "coverage.csv": csv_text(COVERAGE_FIELDS, coverage), "reviewed_bins.csv": csv_text(BIN_FIELDS, bins),
             "lines.json": json.dumps({"schema_version": 1, "take_id": "T1", "lines": lines or LINES})}
    manifest = {**COMMON, "revision": "r000001", "bin_seconds": 60, "artifact_sha256": {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in files.items()}
                | {"quality_report.json": "0" * 64}}  # a real manifest also lists files that are not uploaded
    return {**files, "manifest.json": json.dumps(manifest)}


def run(files, config=None):
    return import_field_counts(files=files, network_id=SITE, engine_config=config or {})


def windows(result):
    return result["engine_config"]["demand_windows"]


def test_counts_per_class_approach_and_turn_become_rates_in_the_exports_time_bins():
    vehicles = [vehicle("a", 5, "south", "north"), vehicle("b", 20, "south", "north"), vehicle("c", 30, "south", "east", cls="motorcycle"),
                vehicle("d", 70, "west", "east", cls="truck", exit_s=80)]
    result = run(export(vehicles))
    rows = {(w["start"], w["end"], w["vehicle_type"], w["od"][0]["source"], w["od"][0]["destination"]): w["vehicles_per_hour"] for w in windows(result)}
    # south = boundary_0 and north = boundary_1 and so on, rates are count / bin length in vehicles per hour
    assert rows == {(0.0, 60.0, "car", "boundary_0", "boundary_1"): 120.0, (0.0, 60.0, "motorcycle", "boundary_0", "boundary_3"): 60.0,
                    (60.0, 120.0, "truck", "boundary_2", "boundary_3"): 60.0}
    config = result["engine_config"]
    assert config["traffic_density"] == "none" and config["trips"] == [] and config["demand_source"]["kind"] == "field_counts"
    assert "not calibrated or validated" in config["demand_source"]["description"]
    summary = result["summary"]
    assert summary["vehicles"] == 4 and summary["bins"] == 2 and summary["bin_seconds"] == 60.0
    assert summary["by_approach_class"] == {"south": {"car": 2, "motorcycle": 1}, "west": {"truck": 1}}
    assert summary["turns"] == {"south to north": 2, "south to east": 1, "west to east": 1}


def test_the_other_scenario_settings_survive_the_import():
    result = run(export([vehicle("a", 5, "south", "north")]), {"pedestrian_density": "low", "green_seconds": 20.0})
    assert result["engine_config"]["pedestrian_density"] == "low" and result["engine_config"]["green_seconds"] == 20.0


def test_a_blank_reviewed_bin_is_refused_by_name_never_read_as_zero():
    with pytest.raises(ValueError, match=r"arr_west 60.*120 s.*no reviewed count"):
        run(export([vehicle("a", 5, "south", "north")], blank=("arr_west", 60.0)))


def test_incomplete_coverage_is_refused():
    with pytest.raises(ValueError, match="exit_east coverage ends at 90"):
        run(export([vehicle("a", 5, "south", "north")], incomplete_coverage={"exit_east": 90.0}))


def test_a_changed_file_is_refused():
    files = export([vehicle("a", 5, "south", "north")])
    files["events.csv"] = files["events.csv"].replace("car", "bus", 1)
    with pytest.raises(ValueError, match="events.csv changed since this revision was exported"):
        run(files)


def test_a_missing_file_is_refused_naming_it():
    files = export([vehicle("a", 5, "south", "north")])
    del files["lines.json"]
    with pytest.raises(ValueError, match="lines.json"):
        run(files)


def test_an_approach_that_is_not_one_of_the_sites_is_refused_with_the_valid_names():
    lines = [{**line, "approach_id": "A1"} if line["location_id"] == "arr_south" else line for line in LINES]
    with pytest.raises(ValueError, match="'A1'.*east, north, south, west"):
        run(export([vehicle("a", 5, "south", "north")], lines=lines))


def test_a_vehicle_with_no_reviewed_exit_is_refused_unless_it_arrived_in_the_last_minute():
    lost = vehicle("lost", 30, "south", "north")[:1]
    with pytest.raises(ValueError, match="1 vehicle.*no reviewed exit"):
        run(export([lost]))
    late = vehicle("late", 100, "south", "north")[:1]  # arrived 20 s before the footage ended: it may simply not have left yet
    result = run(export([vehicle("a", 5, "south", "north"), late]))
    assert result["summary"]["vehicles"] == 1 and result["summary"]["not_counted_at_the_end"] == 1


def test_a_u_turn_is_refused():
    lines = [{**line, "approach_id": "north"} if line["location_id"] == "arr_west" else line for line in LINES]  # arriving on the leg it leaves by
    with pytest.raises(ValueError, match="north to north"):
        run(export([vehicle("u", 10, "west", "north")], lines=lines))


def test_pedicab_and_jeepney_use_a_flagged_mapping_and_other_classes_are_listed_not_simulated():
    vehicles = [vehicle("p", 5, "south", "north", cls="tricycle", subtype="pedicab"), vehicle("j", 10, "south", "north", cls="jeepney"),
                vehicle("b", 15, "south", "north", cls="bicycle"), vehicle("t", 20, "south", "north", cls="tricycle", subtype="bao_bao")]
    result = run(export(vehicles))
    assert {w["vehicle_type"] for w in windows(result)} == {"tricycle", "bus"}
    mapping = {item["field_class"]: item for item in result["summary"]["class_mapping"]}
    assert (mapping["tricycle/pedicab"]["engine_class"], mapping["tricycle/pedicab"]["pending_team_decision"]) == ("tricycle", True)
    assert (mapping["jeepney"]["engine_class"], mapping["jeepney"]["pending_team_decision"]) == ("bus", True)
    assert mapping["tricycle/bao_bao"]["pending_team_decision"] is False
    assert result["summary"]["not_simulated"] == {"bicycle": 1}
    assert result["summary"]["vehicles"] == 3


def test_the_site_must_be_a_study_site():
    with pytest.raises(ValueError, match="study site"):
        import_field_counts(files=export([vehicle("a", 5, "south", "north")]), network_id="tagum_network", engine_config={})


def test_the_scenarios_api_returns_the_summary_and_refuses_a_bad_export_in_plain_words(tmp_path, monkeypatch):
    import os
    os.environ.setdefault("SMARTFLOW_SECRET_KEY", "field-counts-test-only")
    from fastapi.testclient import TestClient
    import config
    from backend.main import app
    from backend.simulation_runtime import simulation_runtime
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "counts.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_PASSWORD", "CountsAdmin42!")
    with TestClient(app) as client:
        simulation_runtime.reset(force=True)
        assert client.post("/api/auth/login", json={"username": "admin", "password": "CountsAdmin42!"}).status_code == 200
        good = client.post("/api/scenarios/field-observer-counts", json={"network_id": SITE, "engine_config": {}, "files": export([vehicle("a", 5, "south", "north")])})
        assert good.status_code == 200, good.text
        assert good.json()["summary"]["vehicles"] == 1 and good.json()["engine_config"]["demand_source"]["kind"] == "field_counts"
        bad = client.post("/api/scenarios/field-observer-counts", json={"network_id": SITE, "engine_config": {}, "files": export([vehicle("a", 5, "south", "north")], blank=("arr_west", 60.0))})
        assert bad.status_code == 422 and "no reviewed count" in bad.json()["detail"]
        simulation_runtime.reset(force=True)


def test_the_imported_demand_runs_in_the_engine_and_is_reproducible():
    from simulation.network_registry import engine_for_scenario
    config = run(export([vehicle(f"a{n}", 2 + 3*n, "south", "north") for n in range(15)]))["engine_config"]
    totals = []
    for _ in range(2):
        engine = engine_for_scenario({"network_id": SITE, "engine_config": config}, seed=101)
        engine.start(240)
        engine.step(2400)
        totals.append((engine._last_metrics["total_vehicles_spawned"], engine._last_metrics["throughput"]))
    assert totals[0] == totals[1] and totals[0][0] > 0
