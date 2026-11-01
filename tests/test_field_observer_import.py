"""Reviewed Field Observer revision -> class-preserving scenario demand (plan Task 20, design 0.11).

Fixtures are synthetic: they have a declared empty initial state and invent no field measurements.
"""
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from services.field_observer_import import convert_revision, site_mapping_template
from tests.mixed_traffic_helpers import junction_network

NETWORK = junction_network(arm_length=250.0)
VIDEO_END = 1020.0
FLOW_SPEED = {"speed_mps": 8.33, "source": "synthetic fixture"}
COMMON = {"survey_id": "S1", "intersection_id": "test_cross", "camera_id": "C1", "take_id": "T1", "view_segment_id": "V1"}
EVENT_FIELDS = (*COMMON, "event_id", "episode_id", "event_type", "location_id", "time_s", "frame_pts", "approach_id", "exit_id",
                "crossing_id", "direction", "reviewed_class", "vehicle_subtype", "review_status", "review_method", "reviewer", "note")
COVERAGE_FIELDS = (*COMMON, "event_type", "location_id", "start_s", "end_s", "visibility", "review_method", "reviewer", "note")
BIN_FIELDS = (*COMMON, "start_s", "end_s", "event_type", "location_id", "reviewed_class", "vehicle_subtype", "observed_count", "count",
              "coverage", "review_state", "publication_status")
LOCATION_EVENT = {"arrival_west": "vehicle_arrival", "arrival_north": "vehicle_arrival", "exit_east": "vehicle_discharge",
                  "exit_south": "vehicle_discharge", "crossing_main": "pedestrian_start"}


def mapping(arrival_distance=250.0, speeds=None, **override):
    speed_table = {"west": {"car": FLOW_SPEED, "motorcycle": FLOW_SPEED, "tricycle": FLOW_SPEED},
                   "north": {"car": FLOW_SPEED, "motorcycle": FLOW_SPEED, "tricycle": FLOW_SPEED}} if speeds is None else speeds
    base = {
        "network_id": NETWORK.id, "network_sha256": NETWORK.fingerprint,
        "locations": {
            "arrival_west": {"role": "arrival", "boundary": "w", "approach_id": "west", "distance_from_junction_m": arrival_distance},
            "arrival_north": {"role": "arrival", "boundary": "n", "approach_id": "north", "distance_from_junction_m": arrival_distance},
            "exit_east": {"role": "exit", "boundary": "e", "approach_id": "east", "distance_from_junction_m": 250.0},
            "exit_south": {"role": "exit", "boundary": "s", "approach_id": "south", "distance_from_junction_m": 250.0},
            "crossing_main": {"role": "crossing", "junction": "j"},
        },
        "lead_out_s": 120, "upstream_speed_mps_by_class": speed_table, "movement_conflicts": {},
        "initialization": {"state": "empty", "verified_by": "T", "evidence": "synthetic fixture"},
        "priority_review": None, "class_map": {},
    }
    return {**base, **override}


def event(event_id, kind, location, time_s, *, episode="", cls="car", subtype="", exit_id="", status="accepted"):
    return {**COMMON, "event_id": event_id, "episode_id": episode, "event_type": kind, "location_id": location, "time_s": time_s,
            "frame_pts": "", "approach_id": "", "exit_id": exit_id, "crossing_id": "", "direction": "", "reviewed_class": cls,
            "vehicle_subtype": subtype, "review_status": status, "review_method": "manual", "reviewer": "T", "note": ""}


def vehicle(episode, arrival_s, exit_s, *, cls="car", subtype="", source="arrival_west", destination="exit_east"):
    rows = [event(f"{episode}-a", "vehicle_arrival", source, arrival_s, episode=episode, cls=cls, subtype=subtype)]
    if exit_s is not None:
        rows.append(event(f"{episode}-x", "vehicle_discharge", destination, exit_s, episode=episode, cls=cls, subtype=subtype))
    return rows


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(tmp_path, events, *, coverage_until=None, blank_bins=(), unresolved_bins=(), queue_rows=None):
    """A revision folder. coverage_until overrides how far a location's complete coverage runs (default the whole video)."""
    folder = tmp_path / "revision"
    folder.mkdir()
    until = {location: VIDEO_END for location in LOCATION_EVENT} | (coverage_until or {})
    write_csv(folder / "events.csv", EVENT_FIELDS, events)
    write_csv(folder / "coverage.csv", COVERAGE_FIELDS, [
        {**COMMON, "event_type": LOCATION_EVENT[location], "location_id": location, "start_s": 0, "end_s": end,
         "visibility": "complete", "review_method": "manual", "reviewer": "T", "note": ""} for location, end in until.items()])
    bins = []
    for location, kind in LOCATION_EVENT.items():
        for left, right in ((0.0, 900.0), (900.0, VIDEO_END)):
            blank = any(item[0] == location and item[1] <= left < item[2] for item in blank_bins)
            unresolved = any(item[0] == location and item[1] <= left < item[2] for item in unresolved_bins)
            bins.append({**COMMON, "start_s": left, "end_s": right, "event_type": kind, "location_id": location, "reviewed_class": "car",
                         "vehicle_subtype": "", "observed_count": 0, "count": "" if blank or unresolved else 0,
                         "coverage": "incomplete" if blank else "complete", "review_state": "unresolved" if unresolved else "manual_review_recorded",
                         "publication_status": "provisional"})
    write_csv(folder / "reviewed_bins.csv", BIN_FIELDS, bins)
    write_csv(folder / "queue_samples.csv", ("sample_id", "time_s"), queue_rows or [])
    (folder / "lines.json").write_text(json.dumps({"schema_version": 1, "lines": [{"id": f"line_{name}", "location_id": name} for name in LOCATION_EVENT]}))
    names = ("events.csv", "coverage.csv", "reviewed_bins.csv", "lines.json", "queue_samples.csv")
    (folder / "manifest.json").write_text(json.dumps({**COMMON, "revision": "r000001", "artifact_sha256": {name: sha(folder / name) for name in names}}))
    return folder


def rows_of(result):
    return list(csv.DictReader(io.StringIO(result["trips_csv"])))


def convert(folder, mapping_=None, *, origin_s=0, start_s=0, end_s=900):
    return convert_revision(folder, mapping_ or mapping(), NETWORK, origin_s=origin_s, start_s=start_s, end_s=end_s)


def test_accepted_movements_become_trips_with_class_and_boundaries(tmp_path):
    result = convert(build(tmp_path, vehicle("e1", 12.4, 20.0, cls="motorcycle")))
    assert rows_of(result)[0] == {"time_s": "12.4", "source": "w", "destination": "e", "vehicle_type": "motorcycle"}
    assert result["summary"]["by_class"] == {"motorcycle": 1}
    assert result["summary"]["by_movement"] == {"w->e": 1}


def test_arrival_times_move_back_by_the_boundary_to_line_travel_time(tmp_path):
    # Line 50 m from the junction on a 250 m approach at 8.33 m/s: shift 200 / 8.33 = 24.0 s.
    result = convert(build(tmp_path, vehicle("e1", 60.0, 90.0)), mapping(arrival_distance=50.0))
    assert rows_of(result)[0]["time_s"] == "36.0"


def test_early_measurement_arrival_is_imported_as_lead_in(tmp_path):
    result = convert(build(tmp_path, vehicle("e1", 125.0, 150.0)), mapping(arrival_distance=50.0), start_s=120, end_s=1020 - 120)
    assert rows_of(result)[0]["time_s"] == "101.0"
    assert result["timing"]["measurement_start_s"] == 120.0
    assert result["summary"]["demand_by_period"]["lead_in"] == 1


def test_lead_in_arrival_before_the_origin_is_refused_not_clipped(tmp_path):
    # Observed at 5 s with a 24 s shift enters the boundary at -19 s: it is already on the approach at origin 0.
    with pytest.raises(ValueError, match="INSUFFICIENT_INITIAL_STATE.*1 vehicle"):
        convert(build(tmp_path, vehicle("e1", 5.0, 30.0)), mapping(arrival_distance=50.0))


def test_missing_initial_state_evidence_is_refused(tmp_path):
    with pytest.raises(ValueError, match="INSUFFICIENT_INITIAL_STATE"):
        convert(build(tmp_path, vehicle("e1", 12.4, 20.0)), mapping(initialization=None))


def test_a_vehicle_on_the_approach_at_the_origin_is_refused(tmp_path):
    # Arrived before origin 60 and still leaves after it: not an empty start.
    with pytest.raises(ValueError, match="INSUFFICIENT_INITIAL_STATE"):
        convert(build(tmp_path, vehicle("e1", 30.0, 90.0)), origin_s=60, start_s=60, end_s=900)


def test_shifted_post_window_arrival_is_kept_as_boundary_demand(tmp_path):
    # Observed 910 s, shift 24 s: boundary time 886 s is before the end at 900 s.
    result = convert(build(tmp_path, vehicle("e1", 910.0, 940.0)), mapping(arrival_distance=50.0))
    assert rows_of(result)[0]["time_s"] == "886.0"
    assert result["summary"]["demand_by_period"]["measurement"] == 1


def test_vehicle_and_pedestrian_demand_share_the_origin(tmp_path):
    events = vehicle("e1", 200.0, 230.0) + [event("p1", "pedestrian_start", "crossing_main", 100.0, cls="person")]
    result = convert(build(tmp_path, events), origin_s=30, start_s=150, end_s=1000 - 100)
    assert rows_of(result)[0]["time_s"] == "170.0"
    assert [(r["start_s"], r["end_s"], r["count"]) for r in csv.DictReader(io.StringIO(result["pedestrian_counts_csv"]))] == [("60", "120", "1")]
    assert result["timing"] == {"origin_s": 30.0, "measurement_start_s": 120.0, "measurement_duration_s": 750.0, "demand_end_s": 990.0}


def test_an_arrival_line_outside_the_modelled_approach_is_refused(tmp_path):
    with pytest.raises(ValueError, match="arrival_north is 400 m from the junction; the modelled approach is 250 m"):
        convert(build(tmp_path, vehicle("e1", 12.4, 20.0)), _with_distance(mapping(), "arrival_north", 400.0))


def test_exits_after_the_window_are_found_in_the_lead_out(tmp_path):
    result = convert(build(tmp_path, vehicle("e1", 890.0, 950.0)))
    assert result["summary"]["trips"] == 1


def test_missing_lead_out_coverage_is_refused(tmp_path):
    folder = build(tmp_path, vehicle("e1", 12.4, 20.0), coverage_until={"exit_east": 900.0})
    with pytest.raises(ValueError, match="exit_east coverage ends at 900 s; the lead-out needs it until 1020 s"):
        convert(folder)


def test_excluded_classes_are_reported_not_hidden(tmp_path):
    events = vehicle("e1", 10.0, 40.0, cls="tricycle", subtype="pedicab") + vehicle("e2", 20.0, 50.0, cls="tricycle", subtype="pedicab") + vehicle("e3", 30.0, 60.0)
    result = convert(build(tmp_path, events), mapping(class_map={"tricycle/pedicab": "exclude"}))
    assert result["summary"]["excluded_by_class"] == {"tricycle/pedicab": 2}
    assert result["summary"]["trips"] == 1


def test_an_unmapped_class_with_vehicles_is_refused(tmp_path):
    with pytest.raises(ValueError, match=r"tricycle/pedicab.*1 vehicle.*class_map"):
        convert(build(tmp_path, vehicle("e1", 10.0, 40.0, cls="tricycle", subtype="pedicab")))


def test_provenance_names_the_reviewed_video(tmp_path):
    folder = build(tmp_path, vehicle("e1", 12.4, 20.0))
    provenance = convert(folder)["provenance"]
    assert set(provenance) == {"survey_id", "take_id", "revision", "manifest_sha256", "reviewed_bins_sha256", "origin_s", "window",
                               "measurement_start_s", "demand_end_s", "lead_out_s", "initialization", "upstream_time_assumptions", "mapping_sha256"}
    assert provenance["manifest_sha256"] == sha(folder / "manifest.json")
    assert provenance["reviewed_bins_sha256"] == sha(folder / "reviewed_bins.csv")
    assert provenance["window"] == [0.0, 900.0]


def test_incomplete_coverage_in_the_window_is_refused(tmp_path):
    folder = build(tmp_path, vehicle("e1", 12.4, 20.0), blank_bins=[("arrival_north", 0.0, 900.0)])
    with pytest.raises(ValueError, match="arrival_north.*0–900 s.*incomplete"):
        convert(folder)


def test_unresolved_events_in_the_window_are_refused(tmp_path):
    folder = build(tmp_path, vehicle("e1", 12.4, 20.0), unresolved_bins=[("arrival_west", 0.0, 900.0)])
    with pytest.raises(ValueError, match="arrival_west.*0–900 s.*incomplete"):
        convert(folder)


def test_arrivals_without_an_exit_are_refused_by_count(tmp_path):
    events = vehicle("e1", 10.0, None) + vehicle("e2", 20.0, None) + vehicle("e3", 30.0, None) + vehicle("e4", 40.0, 70.0)
    with pytest.raises(ValueError, match="3 arrivals have no exit"):
        convert(build(tmp_path, events))


def test_follow_up_arrivals_without_an_exit_are_disclosed_not_imported(tmp_path):
    result = convert(build(tmp_path, vehicle("e1", 10.0, 40.0) + vehicle("e2", 950.0, None)))
    assert result["summary"]["trips"] == 1
    assert result["summary"]["follow_up_arrivals_without_exit"] == 1
    assert result["summary"]["travel_time_follow_up"] == "insufficient"


def test_a_changed_revision_file_is_refused(tmp_path):
    folder = build(tmp_path, vehicle("e1", 12.4, 20.0))
    (folder / "events.csv").write_text((folder / "events.csv").read_text() + "\n")
    with pytest.raises(ValueError, match="events.csv.*changed"):
        convert(folder)


def test_a_mapping_for_another_network_is_refused(tmp_path):
    with pytest.raises(ValueError, match="network"):
        convert(build(tmp_path, vehicle("e1", 12.4, 20.0)), mapping(network_sha256="other"))


def test_a_missing_upstream_speed_is_refused_when_the_line_is_not_at_the_boundary(tmp_path):
    with pytest.raises(ValueError, match="upstream speed.*west.*car"):
        convert(build(tmp_path, vehicle("e1", 60.0, 90.0)), mapping(arrival_distance=50.0, speeds={}))


def test_lead_out_shorter_than_two_minutes_is_refused(tmp_path):
    with pytest.raises(ValueError, match="lead_out_s"):
        convert(build(tmp_path, vehicle("e1", 12.4, 20.0)), mapping(lead_out_s=60))


def test_pedestrian_starts_become_60_s_pedestrian_counts(tmp_path):
    events = [event(f"p{index}", "pedestrian_start", "crossing_main", time_s, cls="person") for index, time_s in enumerate((10.0, 50.0, 70.0))]
    result = convert(build(tmp_path, events + vehicle("e1", 12.4, 20.0)))
    rows = list(csv.DictReader(io.StringIO(result["pedestrian_counts_csv"])))
    assert [(r["start_s"], r["end_s"], r["count"]) for r in rows] == [("0", "60", "2"), ("60", "120", "1")]
    assert rows[0]["junction"] == "j"


def test_result_imports_through_the_existing_importer(tmp_path, monkeypatch):
    import services.observed_data_import as importer
    from simulation.network_registry import load_registered_network
    monkeypatch.setattr(importer, "IMPORT_DIRECTORY", tmp_path / "imports")
    site = load_registered_network("tagum_site_a")
    template = site_mapping_template(site)
    west, east = [item for item in template["boundaries"] if item["road_name"] == "Capitol Circumferential Road"][:2]
    site_mapping = {**template, "lead_out_s": 120, "initialization": mapping()["initialization"],
                    "locations": {"arrival_west": {"role": "arrival", "boundary": west["boundary"], "approach_id": "west", "distance_from_junction_m": west["length_m"]},
                                  "exit_east": {"role": "exit", "boundary": east["boundary"], "approach_id": "east", "distance_from_junction_m": east["length_m"]}}}
    folder = build(tmp_path, vehicle("e1", 12.4, 20.0) + vehicle("e2", 30.0, 60.0, cls="bus"))
    result = convert_revision(folder, site_mapping, site, origin_s=0, start_s=0, end_s=900)
    imported = importer.import_observations(kind="trips", csv_text=result["trips_csv"], source_description="synthetic converter test",
                                            collected_on="2026-10-30", network_id="tagum_site_a", provenance=result["provenance"])
    trips = imported["engine_config"]["trips"]
    assert sorted(trip["vehicle_type"] for trip in trips) == ["bus", "car"]
    assert imported["engine_config"]["demand_source"]["datasets"][0]["provenance"] == result["provenance"]


def test_count_imports_keep_the_vehicle_type(monkeypatch, tmp_path):
    import services.observed_data_import as importer
    monkeypatch.setattr(importer, "IMPORT_DIRECTORY", tmp_path / "imports")
    base = "start_s,end_s,source,destination,count"
    legacy = importer.import_observations(kind="od_counts", csv_text=f"{base}\n0,60,boundary_1,boundary_2,2\n", source_description="legacy", collected_on="2026-10-30")
    typed = importer.import_observations(kind="od_counts", csv_text=f"{base},vehicle_type\n0,60,boundary_1,boundary_2,2,bus\n", source_description="typed", collected_on="2026-10-30")
    assert {trip["vehicle_type"] for trip in legacy["engine_config"]["trips"]} == {"car"}
    assert {trip["vehicle_type"] for trip in typed["engine_config"]["trips"]} == {"bus"}


def _with_distance(mapping_, location, distance):
    mapping_["locations"][location] = {**mapping_["locations"][location], "distance_from_junction_m": distance}
    return mapping_
