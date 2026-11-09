"""Prepare the owner's selected Site A records for the next installer, without building it."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from desktop.starter_content import METRIC_COLUMNS, STARTER_ID, file_digest, verify_content


def read_only(path: Path):
    connection = sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def prepare(web_root: Path, ql_database: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Choose an empty output location. The existing payload is at {output}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        closing(read_only(web_root / "data" / "smartflow.db")) as web,
        closing(read_only(ql_database)) as ql,
        TemporaryDirectory(prefix="starter-", dir=output.parent) as temporary,
    ):
        payload = Path(temporary) / "payload"
        payload.mkdir()
        scenario = web.execute(
            "SELECT network_id, network_sha256, engine_config FROM scenarios WHERE id = 41"
        ).fetchone()
        catalog = {"id": STARTER_ID, "scenario": dict(scenario), "models": {}, "runs": {}}
        model_digests = {}
        for algorithm, model_id in (("ql", 26), ("dql", 27)):
            row = web.execute("SELECT algorithm, checkpoint_path FROM rl_models WHERE id = ?", (model_id,)).fetchone()
            if not row or row["algorithm"] != algorithm:
                raise ValueError(f"Expected web model #{model_id} ({algorithm}).")
            source = web_root / row["checkpoint_path"]
            catalog["models"][algorithm] = source.name
            model_digests[algorithm] = file_digest(source)
            shutil.copyfile(source, payload / source.name)
            if algorithm == "dql":
                metadata = source.with_suffix(".metadata.json")
                shutil.copyfile(metadata, payload / metadata.name)

        signatures = []
        for algorithm, connection, source_run, notes in (
            ("fixed-time", web, 230, "Original web recording #230."),
            ("ql", ql, 1, "New QL recording matched to web runs #230 and #231."),
            ("dql", web, 231, "Original web recording #231."),
        ):
            row = connection.execute("SELECT * FROM simulation_runs WHERE id = ?", (source_run,)).fetchone()
            if not row or (row["status"], row["control_mode"], row["seed"], row["duration_seconds"]) != (
                "completed", algorithm, 101, 300.0
            ):
                raise ValueError(f"The {algorithm} run is missing or has different settings.")
            timeline = Path(row["timeline_path"])
            if not timeline.name.endswith(".jsonl.gz"):
                raise ValueError("Expected the compressed recording.")
            manifest = json.loads(timeline.with_name(timeline.name.removesuffix(".jsonl.gz") + ".manifest.json").read_text(encoding="utf-8"))
            experiment = manifest["experiment"]
            signatures.append(tuple(experiment[key] for key in (
                "engine_version", "network_sha256", "seed", "duration_seconds", "measurement_start", "demand_sha256", "config"
            )))
            if experiment["network_sha256"] != scenario["network_sha256"] or experiment["config"] != json.loads(scenario["engine_config"]):
                raise ValueError(f"The {algorithm} recording does not match the saved Site A scenario.")
            if model_digests.get(algorithm) != (experiment.get("policy") or {}).get("sha256"):
                raise ValueError(f"The {algorithm} recording does not match its selected model.")
            metrics = connection.execute("SELECT * FROM run_metrics WHERE run_id = ? ORDER BY id DESC LIMIT 1", (source_run,)).fetchone()
            catalog["runs"][algorithm] = {key: row[key] for key in ("seed", "start_time", "end_time", "duration_seconds")}
            catalog["runs"][algorithm]["notes"] = notes
            catalog["runs"][algorithm]["metrics"] = {key: metrics[key] for key in METRIC_COLUMNS}
            shutil.copyfile(timeline, payload / f"{algorithm}.jsonl.gz")
            manifest["artifacts"] = {
                "timeline_path_canonical": f"{algorithm}.jsonl.gz",
                "compression": manifest["artifacts"]["compression"],
            }
            (payload / f"{algorithm}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        if any(signature != signatures[0] for signature in signatures[1:]):
            raise ValueError("The recordings do not use matched inputs.")
        catalog["sha256"] = {path.name: file_digest(path) for path in sorted(payload.iterdir())}
        (payload / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        verify_content(payload)
        payload.rename(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-root", type=Path, required=True)
    parser.add_argument("--ql-database", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("tmp/desktop-starter-content"))
    args = parser.parse_args()
    prepare(args.web_root.resolve(), args.ql_database, args.output.resolve())
    print(f"Starter content ready at {args.output.resolve()}")


if __name__ == "__main__":
    main()
