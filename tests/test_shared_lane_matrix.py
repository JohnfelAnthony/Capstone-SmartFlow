import json
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from tools import shared_lane_matrix


@pytest.mark.parametrize("overlaps", [0, 1])
def test_matrix_exit_status_reports_safety_failures_and_preserves_all_results(monkeypatch, tmp_path, overlaps):
    out = tmp_path / "matrix.jsonl"

    def run(job):
        site, lane, control, seed, _ = job
        clean = {"completed": 1, "max_stalled_vehicles": 0, "max_stuck_junction_vehicles": 0, "conservation_error": 0}
        return {
            "site": site, "shared_lane": lane, "control": control, "seed": seed,
            "shared": {**clean, "max_overlapping_pairs": overlaps if seed == 101 else 0},
            "no_closure": {**clean, "max_overlapping_pairs": None},
        }

    monkeypatch.setattr(shared_lane_matrix, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(shared_lane_matrix, "run", run)
    monkeypatch.setattr(sys, "argv", ["shared_lane_matrix", "--out", str(out), "--cases", "0",
                                     "--controls", "no-signal", "--seeds-a", "101,102"])
    assert shared_lane_matrix.main() == overlaps
    rows = {row["seed"]: row for row in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
    assert rows[101]["missed_targets"] == ({"shared": {"max_overlapping_pairs": 1}} if overlaps else {})
    assert rows[102]["missed_targets"] == {}
    assert rows[101]["no_closure"]["max_overlapping_pairs"] is None
