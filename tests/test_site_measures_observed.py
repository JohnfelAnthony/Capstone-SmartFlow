"""Observed measures from a reviewed Field Observer revision (plan Task 26). Synthetic fixtures only."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from services import site_validation as sv

COMMON = {"survey_id": "S1", "intersection_id": "test_cross", "camera_id": "C1", "take_id": "T1", "view_segment_id": "V1"}
EVENT_FIELDS = ("event_id", "episode_id", "event_type", "location_id", "time_s", "exit_id", "reviewed_class", "vehicle_subtype", "review_status")
COVERAGE_FIELDS = ("event_type", "location_id", "start_s", "end_s", "visibility")
BIN_FIELDS = ("start_s", "end_s", "event_type", "location_id", "count")
QUEUE_FIELDS = ("sample_id", "time_s", "approach_id", "queue_count", "visibility", "review_status")
PAIR_FIELDS = ("pair_id", "movement_a", "movement_b", "priority_time_a_s", "priority_time_b_s", "entry_time_a_s", "entry_time_b_s",
               "readiness_of_earlier", "blocked_reason", "visibility", "reviewer", "note")
START, END, LEAD_OUT = 100.0, 1000.0, 120.0
KINDS = {"arrival_west": "vehicle_arrival", "arrival_north": "vehicle_arrival", "stop_west": "vehicle_discharge", "stop_north": "vehicle_discharge",
         "exit_east": "vehicle_discharge", "exit_south": "vehicle_discharge"}
MAPPING = {"locations": {
    "arrival_west": {"role": "arrival", "boundary": "w", "approach_id": "west", "distance_from_junction_m": 100.0},
    "arrival_north": {"role": "arrival", "boundary": "n", "approach_id": "north", "distance_from_junction_m": 100.0},
    "stop_west": {"role": "stopline", "boundary": "w", "approach_id": "west"},
    "stop_north": {"role": "stopline", "boundary": "n", "approach_id": "north"},
    "exit_east": {"role": "exit", "boundary": "e"}, "exit_south": {"role": "exit", "boundary": "s"}},
    "lead_out_s": LEAD_OUT, "movement_conflicts": {"identity": "v1", "pairs": [["w->e", "n->s"], ["w->s", "n->e"]]}}
CRITERIA = {"queue_sample_interval_s": 30.0, "discharge_bin_s": 300.0, "pair_window_s": 10.0, "tie_tolerance_s": 0.5,
            "approaches": ["w", "n"], "min_samples": {"queue": 1, "discharge": 1, "travel_time": 1}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def row(fields, **values):
    return {name: values.get(name, "") for name in fields}


def event(event_id, kind, location, time_s, episode="", exit_id="", status="accepted"):
    return row(EVENT_FIELDS, event_id=event_id, episode_id=episode, event_type=kind, location_id=location, time_s=time_s, exit_id=exit_id,
               reviewed_class="car", review_status=status)


def trip(episode, arrive, exit_, source="arrival_west", destination="exit_east"):
    items = [event(f"{episode}a", "vehicle_arrival", source, arrive, episode)]
    if exit_ is not None:
        items.append(event(f"{episode}x", "vehicle_discharge", destination, exit_, episode))
    return items


def pair(pair_id, ma, mb, pa, pb, ea, eb, readiness="ready", visibility="complete", reason=""):
    return row(PAIR_FIELDS, pair_id=pair_id, movement_a=ma, movement_b=mb, priority_time_a_s=pa, priority_time_b_s=pb, entry_time_a_s=ea,
               entry_time_b_s=eb, readiness_of_earlier=readiness, blocked_reason=reason, visibility=visibility, reviewer="T")


def build(tmp_path, events=(), queue=(), pairs=None, coverage_end=None, blank_bins=()):
    folder = tmp_path / "revision"
    folder.mkdir()
    until = {name: END + LEAD_OUT for name in KINDS} | (coverage_end or {})
    write_csv(folder / "events.csv", EVENT_FIELDS, events)
    write_csv(folder / "coverage.csv", COVERAGE_FIELDS, [row(COVERAGE_FIELDS, event_type=KINDS[name], location_id=name, start_s=0, end_s=end, visibility="complete") for name, end in until.items()])
    write_csv(folder / "reviewed_bins.csv", BIN_FIELDS, [row(BIN_FIELDS, start_s=0.0, end_s=END + LEAD_OUT, event_type=KINDS[name], location_id=name, count="" if name in blank_bins else 0) for name in KINDS])
    write_csv(folder / "queue_samples.csv", QUEUE_FIELDS, queue)
    names = ["events.csv", "coverage.csv", "reviewed_bins.csv", "queue_samples.csv", "lines.json"]
    (folder / "lines.json").write_text("{}")
    if pairs is not None:
        write_csv(folder / "priority_review.csv", PAIR_FIELDS, pairs)
        names.append("priority_review.csv")
    (folder / "manifest.json").write_text(json.dumps({**COMMON, "revision": "r000001", "artifact_sha256": {name: sha(folder / name) for name in names}}))
    return folder


def observed(folder, criteria=None):
    return sv.observed_measures(folder, MAPPING, start_s=START, end_s=END, criteria=criteria or CRITERIA)


def sample(sample_id, time_s, approach, count, visibility="complete"):
    return row(QUEUE_FIELDS, sample_id=sample_id, time_s=time_s, approach_id=approach, queue_count=count if visibility != "unknown" else "",
               visibility=visibility, review_status="accepted")


def test_queue_is_the_mean_of_complete_samples_at_the_shared_instants(tmp_path):
    queue = [sample("1", 100.0, "west", 2), sample("2", 130.0, "west", 4), sample("3", 160.0, "west", 9, "lower_bound"),
             sample("4", 190.0, "west", 6), sample("5", 145.0, "west", 99), sample("6", 100.0, "north", 1), sample("7", 130.0, "north", 3, "unknown")]
    result = observed(build(tmp_path, queue=queue))["queue"]
    assert result["w"] == {"value": 4.0, "samples": 3, "excluded": {"incomplete_visibility": 1, "off_instant": 1}}
    assert result["n"]["value"] == 1.0 and result["n"]["samples"] == 1


def test_an_approach_without_samples_has_no_value_not_zero(tmp_path):
    result = observed(build(tmp_path, queue=[sample("1", 100.0, "west", 2)]))["queue"]
    assert result["n"]["value"] is None and result["n"]["samples"] == 0


def test_discharge_counts_stop_line_crossings_per_bin_and_flags_incomplete_bins(tmp_path):
    events = [event(str(index), "vehicle_discharge", "stop_west", time_s) for index, time_s in enumerate((110.0, 250.0, 399.0, 401.0, 700.0))]
    result = observed(build(tmp_path, events=events, coverage_end={"stop_north": 700.0}))["discharge"]
    assert {key: item["value"] for key, item in result["w"].items()} == {"0": 3, "1": 1, "2": 1}
    assert all(item["complete"] for item in result["w"].values())
    assert [result["n"][key]["complete"] for key in ("0", "1", "2")] == [True, True, False]


def test_a_blank_reviewed_bin_makes_discharge_incomplete(tmp_path):
    result = observed(build(tmp_path, blank_bins=("stop_west",)))["discharge"]
    assert not any(item["complete"] for item in result["w"].values())


def test_travel_time_follows_the_arrival_cohort_to_the_exit_and_reports_unfinished(tmp_path):
    events = trip("a", 150.0, 170.0) + trip("b", 200.0, 240.0) + trip("c", 990.0, 1050.0) + trip("d", 400.0, None) + trip("e", 50.0, 90.0)
    result = observed(build(tmp_path, events=events))["travel_time"]
    assert (result["count"], result["unfinished"], result["complete"]) == (3, 1, True)
    assert result["mean"] == pytest.approx((20 + 40 + 60) / 3) and result["median"] == 40.0


def test_travel_time_is_incomplete_when_exit_coverage_stops_early(tmp_path):
    assert observed(build(tmp_path, events=trip("a", 150.0, 170.0), coverage_end={"exit_east": 900.0}))["travel_time"]["complete"] is False


def test_arrival_order_share_counts_eligible_pairs_and_reports_each_exclusion(tmp_path):
    pairs = [
        pair("p1", "w->e", "n->s", 200.0, 203.0, 205.0, 209.0),                       # earlier entered first: respected
        pair("p2", "w->e", "n->s", 300.0, 304.0, 309.0, 306.0),                       # later entered first, earlier ready: violation
        pair("p3", "w->e", "n->s", 400.0, 402.0, 405.0, 410.0),                       # respected
        pair("p4", "w->e", "w->s", 500.0, 503.0, 505.0, 509.0),                       # same approach: not competing movements
        pair("p5", "w->s", "n->s", 600.0, 603.0, 605.0, 609.0),                       # reviewed table does not list this pair
        pair("p6", "w->e", "n->s", 700.0, 700.3, 705.0, 709.0),                       # priority tie
        pair("p7", "w->e", "n->s", 800.0, 830.0, 835.0, 840.0),                       # beyond the pair window
        pair("p8", "w->e", "n->s", 850.0, 853.0, 860.0, 855.0, readiness="blocked", reason="exit full"),
        pair("p9", "w->e", "n->s", 870.0, 873.0, 880.0, 876.0, readiness="unknown"),
        pair("p10", "w->e", "n->s", 880.0, 883.0, 890.0, 886.0, visibility="partial"),
        pair("p11", "w->e", "n->s", 900.0, 903.0, 910.0, 910.0),                       # unresolved entry tie
        pair("p12", "w->e", "n->s", 920.0, 925.0, 922.0, 922.4),                       # later vehicle not yet in the zone when the first entered
    ]
    result = observed(build(tmp_path, pairs=pairs))["arrival_order"]
    assert (result["eligible"], result["respected"]) == (3, 2)
    assert result["share"] == pytest.approx(2 / 3)
    assert result["excluded"] == {"nonconflicting": 2, "tied": 2, "noncompeting": 2, "blocked_earlier": 1, "unknown_readiness": 1, "unobservable": 1}


def test_no_priority_review_means_no_arrival_order_evidence(tmp_path):
    result = observed(build(tmp_path))["arrival_order"]
    assert (result["eligible"], result["share"]) == (0, None)


def test_a_changed_priority_review_is_refused_by_hash(tmp_path):
    folder = build(tmp_path, pairs=[pair("p1", "w->e", "n->s", 200.0, 203.0, 205.0, 209.0)])
    (folder / "priority_review.csv").write_text("tampered")
    with pytest.raises(ValueError, match="priority_review.csv.*changed"):
        observed(folder)
