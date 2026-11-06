"""Rehearse the whole study workflow against a SCRATCH server and database, on a SYNTHETIC Field Observer export.

    import counts -> scenario -> short train -> evaluate -> record -> Compare Runs -> report -> backup and restore,
    plus one live run for each closure response.

Everything it creates is labelled SYNTHETIC; it makes no field measurement and proves only that the pieces fit together.
Development seeds only (11 for training, 101 for held-out evaluation and recordings); the training is two short episodes.
Never point it at the owner's database: it refuses a server whose scenario list does not look like a scratch database
unless --allow-existing is given.

    python tools/rehearse_workflow.py --api http://127.0.0.1:18063 --password <admin password> --out docs/reports/stage5-2026-11-07
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sqlite3
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.movement_counts import approach_boundaries  # noqa: E402
from simulation.closure_responses import NEAREST_EXIT, SHARE, SIDE_STREET, SIDE_STREET_ADAPTIVE  # noqa: E402
from simulation.network_registry import load_registered_network  # noqa: E402

SPAN, BIN = 960, 60
SYNTHETIC = "SYNTHETIC"
# Field class, subtype, weight: includes a pedicab and a jeepney (the two flagged mappings) and a bicycle (not simulated).
CLASSES = [("car", "", .15), ("motorcycle", "", .45), ("tricycle", "bao_bao", .17), ("tricycle", "pedicab", .03), ("bus", "", .03),
           ("truck", "", .04), ("jeepney", "", .10), ("bicycle", "", .03)]
COMMON = {"survey_id": "S1", "intersection_id": "rehearsal", "camera_id": "C1", "take_id": "T1", "view_segment_id": "V1"}
EVENT_FIELDS = (*COMMON, "event_id", "episode_id", "event_type", "location_id", "time_s", "frame_pts", "approach_id", "exit_id", "crossing_id",
                "direction", "reviewed_class", "vehicle_subtype", "review_status", "review_method", "reviewer", "note")
COVERAGE_FIELDS = (*COMMON, "event_type", "location_id", "start_s", "end_s", "visibility", "review_method", "reviewer", "note")
BIN_FIELDS = (*COMMON, "start_s", "end_s", "event_type", "location_id", "reviewed_class", "vehicle_subtype", "observed_count", "count",
              "coverage", "review_state", "publication_status")


def table(fields, rows) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def synthetic_export(site: str, seed: int, vehicles_per_minute: float) -> dict[str, str]:
    """The five files of a reviewed revision, invented: a seeded stream of vehicles per approach, each with an arrival and a reviewed exit."""
    import hashlib
    rng = random.Random(seed)
    approaches = sorted(approach_boundaries(load_registered_network(site)))
    events = []
    for number in range(round(vehicles_per_minute*SPAN/60)):
        origin = rng.choice(approaches)
        destination = rng.choice([name for name in approaches if name != origin])
        field_class, subtype, _ = rng.choices(CLASSES, [weight for *_, weight in CLASSES])[0]
        arrive = round(rng.uniform(0, SPAN-30), 1)
        for kind, place, moment in (("vehicle_arrival", f"arr_{origin}", arrive), ("vehicle_discharge", f"exit_{destination}", arrive+rng.uniform(6, 20))):
            events.append({**COMMON, "event_id": f"v{number}-{kind[8]}", "episode_id": f"v{number}", "event_type": kind, "location_id": place, "time_s": round(moment, 1),
                           "frame_pts": "", "approach_id": "", "exit_id": "", "crossing_id": "", "direction": "", "reviewed_class": field_class,
                           "vehicle_subtype": subtype, "review_status": "accepted", "review_method": "manual", "reviewer": SYNTHETIC, "note": SYNTHETIC})
    lines = ([(f"arr_{name}", "vehicle_arrival", name, "arrival") for name in approaches] + [(f"exit_{name}", "vehicle_discharge", name, "exit") for name in approaches])
    classes = sorted({(row["reviewed_class"], row["vehicle_subtype"]) for row in events})
    bins = []
    for location, kind, _, _ in lines:
        for left in range(0, SPAN, BIN):
            for field_class, subtype in classes:
                count = sum(row["location_id"] == location and row["reviewed_class"] == field_class and row["vehicle_subtype"] == subtype
                            and left <= row["time_s"] < left+BIN for row in events)
                bins.append({**COMMON, "start_s": left, "end_s": left+BIN, "event_type": kind, "location_id": location, "reviewed_class": field_class,
                             "vehicle_subtype": subtype, "observed_count": count, "count": count, "coverage": "complete",
                             "review_state": "manual_review_recorded", "publication_status": "provisional"})
    coverage = [{**COMMON, "event_type": kind, "location_id": location, "start_s": 0, "end_s": SPAN, "visibility": "complete", "review_method": "manual",
                 "reviewer": SYNTHETIC, "note": SYNTHETIC} for location, kind, _, _ in lines]
    files = {"events.csv": table(EVENT_FIELDS, events), "coverage.csv": table(COVERAGE_FIELDS, coverage), "reviewed_bins.csv": table(BIN_FIELDS, bins),
             "lines.json": json.dumps({"schema_version": 1, "take_id": "T1", "lines": [
                 {"id": f"l{index}", "location_id": place, "event_type": kind, "approach_id": name, "role": role} for index, (place, kind, name, role) in enumerate(lines)]})}
    manifest = {**COMMON, "revision": f"synthetic-{seed}", "bin_seconds": BIN, "artifact_sha256": {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in files.items()}}
    return {**files, "manifest.json": json.dumps(manifest)}


class Rehearsal:
    def __init__(self, api: str, password: str, out: Path):
        self.client = httpx.Client(base_url=api, timeout=900)
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.log: list[dict] = []
        login = self.client.post("/api/auth/login", json={"username": "admin", "password": password})
        login.raise_for_status()

    def step(self, name: str, **facts):
        print(f"[{name}] " + "; ".join(f"{key}={value}" for key, value in facts.items()), flush=True)
        self.log.append({"step": name, **facts})

    def call(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = self.client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
        return response

    def wait(self, label: str, ready, timeout=900, every=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = ready()
            if value:
                return value
            time.sleep(every)
        raise TimeoutError(f"{label} did not finish in {timeout}s")

    # --- 1. import counts -> scenario
    def import_and_save(self, site: str, label: str, seed: int, per_minute: float) -> dict:
        files = synthetic_export(site, seed, per_minute)
        imported = self.call("POST", "/api/scenarios/field-observer-counts", json={"network_id": site, "engine_config": {"pedestrian_density": "none"}, "files": files}).json()
        summary = imported["summary"]
        pending = [item["field_class"] for item in summary["class_mapping"] if item["pending_team_decision"]]
        saved = self.call("POST", "/api/scenarios", json={"name": f"REHEARSAL {label} ({SYNTHETIC})", "network_id": site, "engine_config": imported["engine_config"],
                                                          "description": f"{SYNTHETIC} Field Observer export for a rehearsal; not a measurement. Scenario-based, demand from field counts, not calibrated or validated."}).json()
        self.step("import-and-save", site=site, scenario_id=saved["id"], vehicles=summary["vehicles"], vehicles_per_hour=summary["vehicles_per_hour"],
                  rate_note=summary["rate_note"], flagged_mappings=pending, not_simulated=summary["not_simulated"])
        return saved

    # --- 2. short train (+ the held-out evaluation the job runs)
    def train(self, train_id: int, holdout_id: int) -> int:
        settings = {"scenario_id": train_id, "evaluation_scenario_id": holdout_id, "episodes": 2, "warmup_seconds": 0, "evaluation_seconds": 20,
                    "decision_interval_seconds": 5, "minimum_green_hold_seconds": 10, "checkpoint_every": 0, "seeds": "11", "evaluation_seeds": "101"}
        job = self.call("POST", "/api/rl/jobs", json={"algorithms": ["ql"], "settings": settings}).json()["job_id"]
        status = self.wait("training job", lambda: (lambda s: s if s["job"] and s["job"]["id"] == job and s["job"]["status"] in {"completed", "failed", "stopped", "error"} else None)(
            self.call("GET", "/api/rl/status", params={"job_id": job}).json()))
        self.step("train", job_id=job, status=status["job"]["status"], message=status["job"]["message"], progress=status["job"]["progress_percent"])
        if status["job"]["status"] != "completed":
            raise RuntimeError("training job did not complete: " + "\n".join(line["text"] for line in status["log_lines"][-15:]))
        models = [model for model in status["models"] if model["compatible"]]
        model = max(models, key=lambda item: item["id"])
        self.step("model", model_id=model["id"], algorithm=model["algorithm"], junction=model["controlled_junction"], network=model.get("network_id"))
        return model["id"]

    # --- 3. record -> compare
    def record(self, scenario_id: int, control_mode: str, seed: int, seconds: int) -> int:
        run = self.call("POST", "/api/simulation/timelines", json={"scenario_id": scenario_id, "duration_seconds": seconds, "seed": seed, "control_mode": control_mode}).json()["run"]["id"]
        self.wait(f"recording {control_mode}", lambda: self.call("GET", f"/api/runs/{run}").json()["status"] in {"completed", "error"}, every=1.0)
        record = self.call("GET", f"/api/runs/{run}").json()
        if record["status"] != "completed":
            raise RuntimeError(f"recording {control_mode} failed: {record.get('notes')}")
        return run

    def compare(self, scenario_id: int, model_id: int) -> list[int]:
        seconds, seed = 60, 101
        runs = {mode: self.record(scenario_id, mode, seed, seconds) for mode in ("no-signal", "fixed-time", f"ql:{model_id}")}
        compatible = {option["run"]["id"] for option in self.call("GET", "/api/compare/compatible-runs", params={"left_run_id": runs["fixed-time"]}).json()["runs"]}
        pair = self.call("GET", "/api/compare/pair", params={"left_run_id": runs["fixed-time"], "right_run_id": runs["no-signal"]}).json()
        first = pair["left"]["frames"][0]
        self.step("compare", runs=runs, compatible_with_fixed_time=sorted(compatible), comparison_type=pair["comparison_type"], frames=len(pair["left"]["frames"]),
                  first_frame_time=first["time"], first_frame_vehicles=first["vehicle_count"], duration=pair["left"]["option"]["timeline"]["actual_duration_seconds"], warnings=pair["warnings"])
        if not {runs["no-signal"], runs[f"ql:{model_id}"]} <= compatible:
            raise RuntimeError("the three recordings are not mutually compatible in Compare Runs")
        if first["time"] != 0.0 or first["vehicle_count"] <= 0:
            raise RuntimeError("a recording does not open on traffic at clock 0")
        return list(runs.values())

    # --- 4. report
    def report(self, run_ids: list[int]):
        text = self.call("POST", "/api/reports/export", json={"run_ids": run_ids, "format": "csv"}).text
        (self.out / "rehearsal-report.csv").write_text(text, encoding="utf-8", newline="")
        rows = list(csv.DictReader(io.StringIO(text)))
        columns = list(rows[0])
        wanted = ["Stalled Vehicles At Run End", "Measurement Start Seconds", "Measurement Duration Seconds"]
        self.step("report", rows=len(rows), has_columns={name: name in columns for name in wanted},
                  measurement_start=[row["Measurement Start Seconds"] for row in rows], stalled=[row["Stalled Vehicles At Run End"] for row in rows])
        if not all(name in columns for name in wanted):
            raise RuntimeError("the report lacks a column")

    # --- 5. a live run for each closure response (Site A, west entry road2r closed for the whole run)
    def live_responses(self, site: str, base_config: dict):
        results = {}
        for response in (SIDE_STREET, SIDE_STREET_ADAPTIVE, SHARE, NEAREST_EXIT):
            config = {**base_config, "closed_lanes": ["road2r"], "closure_responses": {"road2r": response}}
            made = self.call("POST", "/api/scenarios", json={"name": f"REHEARSAL closure {response} ({SYNTHETIC})", "network_id": site, "engine_config": config}).json()
            started = self.call("POST", "/api/simulation/start", json={"scenario_id": made["id"], "duration_seconds": 20, "seed": 101, "control_mode": "fixed-time"}).json()["simulation"]
            self.call("POST", "/api/simulation/speed", json={"speed_multiplier": 4.0})
            first = started["state"]
            final = self.wait(f"live run {response}", lambda: (lambda s: s if s["status"] in {"completed", "error", "stopped"} else None)(self.call("GET", "/api/simulation/state").json()), timeout=120, every=1.0)
            metrics = final["state"]["metrics"]
            results[response] = {"first_frame_time": first["time"], "first_frame_vehicles": first["vehicle_count"], "status": final["status"], "final_time": final["state"]["time"],
                                 "diverted": metrics.get("diverted_vehicles"), "held": metrics.get("closure_held_vehicles"), "stalled": metrics.get("stalled_vehicles"),
                                 "shared_roads": len(final["state"].get("visual", {}).get("shared_roads", []) or [])}
            self.call("POST", "/api/simulation/reset")
        self.step("live-responses", site=site, results=results)
        return results

    # --- 6. backup and restore
    def backup(self, db_path: Path | None):
        before = self.counts(db_path)
        created = self.call("POST", "/api/admin/backups").json()
        restored = self.call("POST", f"/api/admin/backups/{created['backup']['id']}/restore").json()
        self.step("backup-restore", backup=created["backup"]["filename"], size_bytes=created["backup"]["size_bytes"], restore_path=restored["restore_path"], message=restored["message"], live_counts=before)
        stage = Path(restored["restore_path"])
        databases = sorted(stage.rglob("*.db"))
        if databases:
            after = self.counts(databases[0])
            self.step("restored-counts", database=str(databases[0]), counts=after)
            if after != before:
                raise RuntimeError(f"the restored copy differs from the live database: {before} vs {after}")

    @staticmethod
    def counts(path: Path | None):
        if path is None:
            return None
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            scenarios = dict(connection.execute("SELECT network_id, COUNT(*) FROM scenarios GROUP BY network_id").fetchall())
            return {"scenarios_by_site": scenarios, "runs": connection.execute("SELECT COUNT(*) FROM simulation_runs").fetchone()[0],
                    "models": connection.execute("SELECT COUNT(*) FROM rl_models").fetchone()[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--db", type=Path, help="the scratch server's database file, to compare before and after the restore")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    rehearsal = Rehearsal(args.api, args.password, args.out)
    existing = [scenario["name"] for scenario in rehearsal.call("GET", "/api/scenarios").json()["scenarios"] if not scenario["name"].startswith("REHEARSAL")]
    if len(existing) > 3 and not args.allow_existing:
        raise SystemExit(f"This server has {len(existing)} scenarios that are not rehearsal ones; it does not look like a scratch database. Use --allow-existing to go on.")
    rehearsal.step("start", note=f"{SYNTHETIC} rehearsal; development seeds only; short training")
    site_a, site_b = "tagum_site_a", "tagum_site_b"
    a_train = rehearsal.import_and_save(site_a, "Site A counts", 1, 14)
    a_hold = rehearsal.import_and_save(site_a, "Site A held-out counts", 2, 12)
    rehearsal.import_and_save(site_b, "Site B counts", 3, 12)
    model_id = rehearsal.train(a_train["id"], a_hold["id"])
    runs = rehearsal.compare(a_train["id"], model_id)
    rehearsal.report(runs)
    rehearsal.live_responses(site_a, {**a_train["engine_config"], "warmup_seconds": 30})
    rehearsal.backup(args.db)
    (args.out / "rehearsal-log.json").write_text(json.dumps(rehearsal.log, indent=2), encoding="utf-8")
    print("Rehearsal finished.")


if __name__ == "__main__":
    main()
