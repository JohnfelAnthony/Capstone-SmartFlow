"""Desktop-owned background jobs for the existing independent site validator."""
from __future__ import annotations

import json
import hashlib
import math
import csv
import io
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import database
from services.reviewed_revision_store import revision_path
from services.reviewed_revision_store import _long_path
from services.field_observer_import import convert_revision
from services.site_validation import criteria_sha256, run_validation, validate_criteria, validation_gate
from services.workload_admission import workload_admission
from simulation.network_registry import load_registered_network

JOB_ID = re.compile(r"[0-9a-f]{32}\Z")


def _same_converted_demand(config: dict, converted: dict) -> bool:
    """Check explicit demand, not just user-editable provenance labels."""
    vehicles = [{"time": float(row["time_s"]), "source": row["source"], "destination": row["destination"],
                 "vehicle_type": row["vehicle_type"]} for row in csv.DictReader(io.StringIO(converted["trips_csv"]))]
    pedestrians = []
    if converted["pedestrian_counts_csv"]:
        for row in csv.DictReader(io.StringIO(converted["pedestrian_counts_csv"])):
            start, end, count = float(row["start_s"]), float(row["end_s"]), int(row["count"])
            pedestrians.extend({"time": round(start + (index + .5) * (end - start) / count, 6), "junction": row["junction"]}
                               for index in range(count))
    vehicle_key = lambda item: (float(item["time"]), item["source"], item["destination"], item["vehicle_type"])
    pedestrian_key = lambda item: (float(item["time"]), item["junction"])
    return (not config.get("demand_windows") and sorted(config.get("trips") or [], key=vehicle_key) == sorted(vehicles, key=vehicle_key)
            and sorted(config.get("pedestrian_trips") or [], key=pedestrian_key) == sorted(pedestrians, key=pedestrian_key))


class DesktopValidationJobs:
    def __init__(self, study_root: Path):
        self.root = Path(study_root).resolve()
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}
        raw_directory = self.root / "data" / "validation-jobs"
        if raw_directory.is_symlink() or not raw_directory.resolve().is_relative_to(self.root):
            raise ValueError("Validation job storage must remain inside desktop data")
        self.directory = Path(_long_path(raw_directory))
        self.directory.mkdir(parents=True, exist_ok=True)
        self._load()

    def _save(self, job: dict) -> None:
        if not JOB_ID.fullmatch(job["id"]):
            raise ValueError("Invalid validation job ID")
        temporary = self.directory / f".job-{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(job, stream, sort_keys=True, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / f"{job['id']}.json")
        finally:
            temporary.unlink(missing_ok=True)

    def _load(self) -> None:
        for path in sorted(self.directory.glob("*.json")):
            if not JOB_ID.fullmatch(path.stem):
                continue
            try:
                if path.is_symlink() or path.stat().st_size > 5 * 1024 * 1024:
                    raise ValueError("Unsafe or oversized validation-job record")
                job = json.loads(path.read_text(encoding="utf-8"))
                if (not isinstance(job, dict) or job.get("id") != path.stem or
                        job.get("status") not in {"running", "completed", "failed", "interrupted"}):
                    raise ValueError("Invalid validation-job record")
                if job["status"] == "running":
                    job.update(status="interrupted", result=None,
                               error="The backend stopped before this job recorded completion. Check saved reports before retrying.")
                    self._save(job)
                self.jobs[path.stem] = job
            except (OSError, ValueError, TypeError) as exc:
                self.jobs[path.stem] = {"id": path.stem, "status": "failed", "site": "Unknown site", "purpose": "unknown",
                                        "result": None, "error": f"Job record could not be read or reconciled: {exc}"}

    def start(self, *, scenario_id: int, revision_id: str, purpose: str, origin_s: float, start_s: float, end_s: float) -> dict:
        if purpose not in {"calibration", "validation"}:
            raise ValueError("Purpose must be calibration or validation")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (origin_s, start_s, end_s)) or not 0 <= origin_s <= start_s < end_s:
            raise ValueError("Require 0 <= origin <= start < end")
        scenario = database.get_scenario_by_id(scenario_id)
        if not scenario:
            raise ValueError("Scenario not found")
        site = scenario.get("network_id")
        if site not in {"tagum_site_a", "tagum_site_b"}:
            raise ValueError("Select a scenario for Site A or Site B")
        config = scenario.get("engine_config")
        config = json.loads(config) if isinstance(config, str) else config
        if not isinstance(config, dict):
            raise ValueError("Scenario settings are invalid")
        if purpose == "validation" and (config.get("demand_source") or {}).get("kind") != "observed":
            raise ValueError("Independent field validation requires observed demand; synthetic scenarios cannot open the gate")
        sites = self.root / "data" / "sites"
        mapping = json.loads((sites / f"{site}_mapping.json").read_text(encoding="utf-8"))
        all_criteria = json.loads((sites / "validation_criteria.json").read_text(encoding="utf-8"))
        if not isinstance(all_criteria, dict):
            raise ValueError("Validation criteria must be an object")
        criteria = validate_criteria((all_criteria.get("sites") or {}).get(site))
        ledger_path = sites / f"{site}_ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else None
        if not isinstance(mapping, dict) or mapping.get("network_id") != site:
            raise ValueError("Site mapping does not match the selected scenario")
        if purpose == "validation":
            if not isinstance(ledger, dict) or not isinstance(ledger.get("held_out"), dict) or not ledger["held_out"].get("recording"):
                raise ValueError("Independent validation needs a ledger naming the held-out recording and freeze/access history")
            held_out_hash = ledger["held_out"].get("manifest_sha256")
            identity = {"criteria_sha256": criteria_sha256(criteria), "revision_manifest_sha256": held_out_hash}
            preliminary = validation_gate({"purpose": "validation", "status": "PASS", "identity": identity}, identity, ledger)
            if not preliminary["open"]:
                raise ValueError("Independent validation cannot start: " + "; ".join(preliminary["reasons"]))
        revision = revision_path(self.root, revision_id)
        if purpose == "validation":
            actual_manifest = hashlib.sha256((revision / "manifest.json").read_bytes()).hexdigest()
            if actual_manifest != held_out_hash:
                raise ValueError("The selected reviewed revision is not the nominated held-out recording")
            source = config.get("demand_source") or {}
            datasets = source.get("datasets") or []
            mapping_hash = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if (config.get("traffic_density") != "none" or config.get("pedestrian_density") != "none" or not datasets or
                    any(not isinstance(item, dict) or item.get("kind") != "observed" or
                        (item.get("provenance") or {}).get("manifest_sha256") != actual_manifest or
                        (item.get("provenance") or {}).get("mapping_sha256") != mapping_hash or
                        (item.get("provenance") or {}).get("window") != [start_s, end_s] or
                        (item.get("provenance") or {}).get("origin_s") != origin_s for item in datasets)):
                raise ValueError("The scenario demand must come entirely from this reviewed revision, mapping and video window")
            network = load_registered_network(site)
            converted = convert_revision(revision, mapping, network, origin_s=origin_s, start_s=start_s, end_s=end_s)
            if not _same_converted_demand(config, converted):
                raise ValueError("The scenario demand differs from the reviewed conversion; create a fresh scenario")
        lease = workload_admission.acquire("site validation")
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "status": "running", "site": site, "purpose": purpose, "result": None, "error": None,
               "scenario_id": scenario_id, "revision_id": revision_id, "started_at": datetime.now(timezone.utc).isoformat(),
               "window": {"origin_s": origin_s, "start_s": start_s, "end_s": end_s}}
        try:
            with self.lock:
                self._save(job)
                self.jobs[job_id] = job
        except BaseException:
            workload_admission.release(lease)
            raise

        def execute():
            try:
                report, path = run_validation(scenario=scenario, revision_dir=revision, mapping=mapping, criteria=criteria,
                                              purpose=purpose, origin_s=origin_s, start_s=start_s, end_s=end_s,
                                              reports_dir=self.root / "docs" / "reports", ledger=ledger)
                result = {"report_id": report["report_id"], "report_file": path.name, "status": report["status"],
                          "gate": report["gate"], "decision": report["decision"]}
                with self.lock:
                    job.update(status="completed", result=result)
                    try:
                        self._save(job)
                    except (OSError, ValueError, TypeError):
                        job["persistence_warning"] = "Report was written, but the job status could not be saved. Check saved reports after restart."
            except Exception as exc:
                with self.lock:
                    job.update(status="failed", error=str(exc) or type(exc).__name__)
                    try:
                        self._save(job)
                    except (OSError, ValueError, TypeError):
                        job["persistence_warning"] = "The failed job status could not be saved. Check saved reports after restart."
            finally:
                workload_admission.release(lease)

        try:
            threading.Thread(target=execute, name=f"site-validation-{job_id[:8]}", daemon=True).start()
        except BaseException:
            workload_admission.release(lease)
            with self.lock:
                job.update(status="failed", error="Validation worker could not start.")
                try:
                    self._save(job)
                except (OSError, ValueError, TypeError):
                    job["persistence_warning"] = "The failed job status could not be saved."
            raise
        return dict(job)

    def get(self, job_id: str) -> dict | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job is not None else None

    def list(self) -> list[dict]:
        with self.lock:
            return sorted((dict(job) for job in self.jobs.values()), key=lambda job: job.get("started_at", ""), reverse=True)
