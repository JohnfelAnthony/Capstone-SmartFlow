"""A Field Observer manual-count export (four hand-counted approach passes) imports as scenario demand. SYNTHETIC: invented clicks, no field measurement.

The export is made by the tool's own code (tools/field_observer), not hand-written, so this checks the real file format against the real importer.
"""
import csv
import io
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "field_observer"
sys.path.insert(0, str(TOOL))
from field_observer import manual_count  # noqa: E402  (the tool is a separate package; it never imports SmartFlow)
from field_observer.core import TABLES, sha256, write_csv, write_json  # noqa: E402

from services.field_observer_counts import import_field_counts  # noqa: E402

FPS, FRAMES = 10, 600
DURATION = FRAMES / FPS


def fabricated_take(root: Path) -> Path:
    take = root / "take"
    (take / "draft").mkdir(parents=True)
    (take / "revisions").mkdir()
    source = root / "source.mp4"
    source.write_bytes(b"synthetic stand-in, never decoded")
    write_csv(take / "frames.csv", ("frame_index", "frame_pts", "time_base", "time_s"),
              [{"frame_index": i, "frame_pts": i * 100, "time_base": "1/1000", "time_s": i / FPS} for i in range(FRAMES)])
    write_json(take / "manifest.json", {
        "schema_version": 1, "tool_version": "test", "survey_id": "S1", "intersection_id": "site", "camera_id": "PHONE_01", "take_id": "T1",
        "view_segment_id": "T1", "collection_start": None, "collection_clock_status": "unknown", "collector": "T", "clock_note": "test",
        "source_kind": "synthetic", "source_path": str(source), "source_sha256": sha256(source), "source_bytes": source.stat().st_size,
        "frames_sha256": sha256(take / "frames.csv"),
        "media": {"width": 640, "height": 360, "decoded_duration_s": DURATION, "last_frame_time_s": (FRAMES - 1) / FPS}})
    for name, columns in TABLES.items():
        write_csv(take / "draft" / name, columns, [])
    return take


def manual_export(tmp_path: Path, site: str, plan: dict) -> dict:
    """Run four complete passes and return the revision's files as the importer receives them."""
    take, directory = fabricated_take(tmp_path), tmp_path / "manual_count"
    manual_count.set_site(directory, site)
    for approach in manual_count.SITES[site]["approaches"]:
        for moment, exit_, vehicle in plan.get(approach, []):
            manual_count.add_click(directory, site, DURATION, {"approach": approach, "exit": exit_, "class": vehicle, "time_s": moment})
        manual_count.add_watched(directory, approach, DURATION, 0, DURATION)
        manual_count.set_complete(directory, approach, DURATION, True, "Counter")
    revision = manual_count.export_manual(take, directory, "Reviewer", "Synthetic hand count", bin_seconds=30)
    names = ("manifest.json", "events.csv", "coverage.csv", "reviewed_bins.csv", "lines.json")
    return {name: (revision / name).read_bytes().decode("utf-8") for name in names}


PLAN = {"south": [(3, "north", "car"), (10, "north", "car"), (31, "east", "motorcycle"), (41, "west", "tricycle")],
        "west": [(12, "east", "truck"), (50, "east", "bus")],
        "north": [(40, "south", "car")],
        "east": [(55, "west", "motorcycle")]}


@pytest.mark.parametrize("site", ["tagum_site_a", "tagum_site_b"])
def test_a_manual_count_export_imports_with_the_right_movements_per_class(tmp_path, site):
    files = manual_export(tmp_path, site, PLAN)
    result = import_field_counts(files=files, network_id=site, engine_config={})
    summary = result["summary"]
    assert summary["vehicles"] == 8
    assert summary["span_seconds"] == DURATION and summary["bin_seconds"] == 30
    assert summary["by_approach_class"] == {"south": {"car": 2, "motorcycle": 1, "tricycle": 1}, "west": {"bus": 1, "truck": 1},
                                           "north": {"car": 1}, "east": {"motorcycle": 1}}
    assert summary["turns"] == {"south to north": 2, "south to east": 1, "south to west": 1, "west to east": 2,
                                "north to south": 1, "east to west": 1}
    assert summary["not_counted_at_the_end"] == 0 and summary["not_simulated"] == {}
    windows = result["engine_config"]["demand_windows"]
    assert {(w["label"], w["vehicle_type"]): w["vehicles_per_hour"] for w in windows}[("south to north car", "car")] == pytest.approx(2 * 3600 / DURATION)
    assert result["engine_config"]["demand_source"]["kind"] == "field_counts"


def test_an_exported_manual_count_has_manual_review_throughout(tmp_path):
    files = manual_export(tmp_path, "tagum_site_a", PLAN)
    rows = list(csv.DictReader(io.StringIO(files["events.csv"], newline="")))
    assert rows and {row["review_method"] for row in rows} == {"manual_count"}
