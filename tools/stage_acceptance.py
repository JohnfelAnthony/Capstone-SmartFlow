"""Acceptance for Site A and Site B (synthetic demand, provisional geometry): every case and seed through tools.mixed_traffic_report.run_case.

Each finished run is appended as one JSON line, so a long batch can be read while it runs. A new --out file is required.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SMARTFLOW_SECRET_KEY", "stage-acceptance")

SITE_A = [f"siteA-static-{density}-{control}{suffix}" for density in ("medium", "high") for control in ("nosignal", "fixed") for suffix in ("", "-closure")]
SITE_A += [f"siteA-static-medium-{control}-{closure}" for control in ("nosignal", "fixed") for closure in ("road1-closed", "road2-closed", "side-street-closed")]
SITE_B = [f"siteB-{density}-{control}" for density in ("medium", "high") for control in ("nosignal", "fixed")]
SITE_B += [f"siteB-static-medium-{control}-{closure}" for control in ("nosignal", "fixed") for closure in ("road1-closed", "road2-closed")]
# Zero at every seed and case is the target for these; a count above 0 in any run fails the acceptance.
ZERO_TARGETS = ("max_overlapping_pairs", "max_stuck_junction_vehicles", "max_stalled_vehicles", "max_gridlock_seconds", "final_vehicle_conservation_error")


def run(job: tuple) -> dict:
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    from tools.mixed_traffic_report import case_options, run_case
    name, seed, seconds = job
    network, density, _, options = case_options(name)
    result = run_case(network, density, dict(TAGUM_PROVISIONAL_MIX), seconds, seed, **options)
    return {"case": name, "seed": seed, "seconds": seconds, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds", default="101,102,103,104,105,106,107,108")
    parser.add_argument("--extra-seeds", default=None, help="seeds for the added closure cases (road1, road2, side street); default --seeds")
    parser.add_argument("--seconds", type=float, default=1800.0)
    parser.add_argument("--workers", type=int, default=7)
    parser.add_argument("--sites", default="A,B")
    parser.add_argument("--heavy-seeds", default=None, help="seeds for the high-traffic no-signal cases, which take hours each (default: --seeds)")
    parser.add_argument("--skip-done", type=Path, action="append", default=[], help="earlier --out files whose (case, seed) pairs are not run again")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; choose a new path to preserve prior evidence")
    names = (SITE_B if "B" in args.sites else []) + (SITE_A if "A" in args.sites else [])
    done = {(row["case"], row["seed"]) for path in args.skip_done for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    def seeds_for(name: str) -> str:
        if args.extra_seeds and any(tag in name for tag in ("road1-closed", "road2-closed", "side-street-closed")):
            return args.extra_seeds
        return args.heavy_seeds if args.heavy_seeds and "high-nosignal" in name else args.seeds
    jobs = [(name, int(seed), args.seconds) for name in names for seed in seeds_for(name).split(",") if (name, int(seed)) not in done]
    jobs.sort(key=lambda job: ("high-nosignal" not in job[0], not job[0].startswith("siteB"), "high" not in job[0]))  # longest first
    with ProcessPoolExecutor(args.workers) as pool, args.out.open("w", encoding="utf-8") as out:
        futures = [pool.submit(run, job) for job in jobs]
        for result in (future.result() for future in as_completed(futures)):
            out.write(json.dumps(result)+"\n")
            out.flush()
            bad = {key: result[key] for key in ZERO_TARGETS if result.get(key)}
            print(f'{result["case"]} seed {result["seed"]}: completed {result["completed"]}{" TARGET MISSED " + json.dumps(bad) if bad else ""}', file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
