"""Single-take evidence registration, manual tables and immutable exports."""

import csv
import hashlib
import json
import math
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .media import probe_video

CLASSES = ("car", "motorcycle", "tricycle", "jeepney", "bus", "truck", "bicycle",
           "other", "unknown")
EVENT_TYPES = ("vehicle_arrival", "vehicle_movement", "vehicle_discharge",
               "pedestrian_arrival", "pedestrian_start", "pedestrian_complete")
STATUSES = ("proposed", "accepted", "corrected", "rejected", "uncertain")
ACCEPTED = {"accepted", "corrected"}
COMMON = ("survey_id", "intersection_id", "camera_id", "take_id", "view_segment_id")
TABLES = {
    "events.csv": (*COMMON, "event_id", "episode_id", "event_type", "location_id", "time_s",
                   "frame_pts", "approach_id", "exit_id", "crossing_id", "direction",
                   "reviewed_class", "vehicle_subtype", "review_status", "review_method",
                   "reviewer", "note"),
    "coverage.csv": (*COMMON, "event_type", "location_id", "start_s", "end_s", "visibility",
                     "review_method", "reviewer", "note"),
    "signal_changes.csv": (*COMMON, "signal_event_id", "time_s", "frame_pts", "signal_head_id",
                           "movement_group", "indication", "source", "review_status", "reviewer", "note"),
    "queue_samples.csv": (*COMMON, "sample_id", "time_s", "frame_pts", "approach_id", "queue_count",
                          "visibility", "review_status", "reviewer", "note"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, columns, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def number(value, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: expected a number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label}: must be finite.")
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def identifier(value: str, label: str) -> str:
    require(isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value)),
            f"{label}: use 1–80 letters, digits, underscores or hyphens.")
    return value


def create_take(video: Path, destination: Path, *, survey_id: str, intersection_id: str,
                take_id: str, start: str | None, collector: str, clock_note: str,
                source_kind: str) -> dict:
    video, destination = video.resolve(), destination.resolve()
    require(video.is_file(), "Source video does not exist.")
    require(not destination.exists(), "Destination already exists; use a new take directory.")
    for value, label in ((survey_id, "survey_id"), (intersection_id, "intersection_id"), (take_id, "take_id")):
        identifier(value, label)
    started = datetime.fromisoformat(start) if start else None
    require(started is None or started.utcoffset() is not None, "Start must include its UTC offset, for example +08:00.")
    require(bool(collector.strip()) and bool(clock_note.strip()), "Collector and clock-check note are required.")
    require(source_kind in {"observed", "synthetic"}, "Choose observed or synthetic source_kind explicitly.")
    original_hash = sha256(video)
    media = probe_video(video)
    require(not media["timestamp_issues"], "Unusable video timestamps: " + "; ".join(media["timestamp_issues"][:5]))
    require(sha256(video) == original_hash, "Video changed while registration was running.")
    frames = media.pop("frames")
    require(media["decoded_duration_s"] > 0, "Video has no measurable duration.")
    context = dict(zip(COMMON, (survey_id, intersection_id, "PHONE_01", take_id, take_id)))
    manifest = {"schema_version": 1, "tool_version": __version__, **context,
                "collection_start": started.isoformat() if started else None,
                "collection_clock_status": "declared" if started else "unknown",
                "collector": collector.strip(),
                "clock_note": clock_note.strip(), "source_kind": source_kind,
                "source_path": str(video), "source_sha256": original_hash,
                "source_bytes": video.stat().st_size, "media": media,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "scope": "one stationary take; manual observations; provisional evidence"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".field-observer-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "take"
        stage.mkdir()
        write_csv(stage / "frames.csv", ("frame_index", "frame_pts", "time_base", "time_s"), frames)
        manifest["frames_sha256"] = sha256(stage / "frames.csv")
        write_json(stage / "manifest.json", manifest)
        (stage / "draft").mkdir()
        for filename, columns in TABLES.items():
            write_csv(stage / "draft" / filename, columns, [])
        (stage / "revisions").mkdir()
        stage.rename(destination)
    return manifest


def read_take(take: Path, verify_video: bool = True) -> tuple[dict, dict[int, float]]:
    manifest = read_json(take / "manifest.json")
    require(manifest.get("schema_version") == 1, "Unsupported manifest version.")
    require(manifest.get("camera_id") == "PHONE_01", "This release accepts one camera, PHONE_01.")
    require(sha256(take / "frames.csv") == manifest["frames_sha256"], "Frame index changed; register a new take.")
    if verify_video:
        source = Path(manifest["source_path"])
        require(source.is_file(), "Original recording is missing; restore it to its registered path.")
        require(sha256(source) == manifest["source_sha256"], "Original recording changed; register a new take.")
    with (take / "frames.csv").open(newline="", encoding="utf-8") as stream:
        frames = {int(row["frame_pts"]): float(row["time_s"]) for row in csv.DictReader(stream)}
    return manifest, frames


def nearest_frame(take: Path, seconds: float) -> dict:
    manifest, frames = read_take(take, verify_video=False)
    require(0 <= seconds <= manifest["media"]["last_frame_time_s"], "Requested time is outside recorded frame times.")
    pts = min(frames, key=lambda item: abs(frames[item] - seconds))
    return {**{key: manifest[key] for key in COMMON}, "frame_pts": pts, "time_s": frames[pts]}


def load_tables(take: Path) -> dict:
    tables = {}
    for filename, columns in TABLES.items():
        with (take / "draft" / filename).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == list(columns), f"{filename}: header must match the generated template.")
            rows = []
            for line, row in enumerate(reader, 2):
                require(None not in row and None not in row.values(), f"{filename}:{line}: wrong column count.")
                rows.append({key: value.strip() for key, value in row.items()})
            tables[filename] = rows
    return tables


def validate(take: Path) -> tuple[dict, dict, dict]:
    manifest, frames = read_take(take)
    tables = load_tables(take)
    end = manifest["media"]["decoded_duration_s"]
    episodes = {}
    accepted_events = []
    episode_classes = {}
    ranges = {}
    for filename, rows in tables.items():
        ids = set()
        for line, row in enumerate(rows, 2):
            label = f"{filename}:{line}"
            for key in COMMON:
                require(row[key] == manifest[key], f"{label}: {key} does not match this take.")
            if filename == "coverage.csv":
                require(row["event_type"] in EVENT_TYPES and bool(row["location_id"]), f"{label}: unknown event type or missing location.")
                start, stop = number(row["start_s"], label), number(row["end_s"], label)
                require(0 <= start < stop <= end + 1e-6, f"{label}: coverage must be inside the recorded interval.")
                require(row["visibility"] in {"complete", "partial", "unseen"}, f"{label}: invalid visibility.")
                require(row["review_method"] in {"manual_count", "individual_review"} and bool(row["reviewer"]),
                        f"{label}: manual coverage review and reviewer are required; automatic acceptance is not implemented.")
                key = (row["event_type"], row["location_id"])
                prior = ranges.setdefault(key, [])
                require(all(stop <= left or start >= right for left, right, _ in prior), f"{label}: overlapping coverage.")
                prior.append((start, stop, row["visibility"]))
                continue
            id_column = {"events.csv": "event_id", "signal_changes.csv": "signal_event_id", "queue_samples.csv": "sample_id"}[filename]
            require(bool(row[id_column]) and row[id_column] not in ids, f"{label}: missing or duplicate record ID.")
            ids.add(row[id_column])
            require(row["review_status"] in STATUSES, f"{label}: invalid review status.")
            accepted = row["review_status"] in ACCEPTED
            require(not accepted or bool(row["reviewer"]), f"{label}: accepted/corrected records need a reviewer.")
            require(row["review_status"] != "corrected" or bool(row["note"]), f"{label}: correction needs a note.")
            seconds = number(row["time_s"], label)
            require(0 <= seconds < end + 1e-6, f"{label}: time is outside this recording.")
            observer_log = filename == "signal_changes.csv" and row["source"] == "observer_log"
            if observer_log:
                require(bool(row["note"]), f"{label}: identify the clock-aligned observer log in note.")
                require(not accepted or manifest["collection_clock_status"] == "declared",
                        f"{label}: resolve the collection clock before accepting a companion observer log.")
            else:
                try:
                    pts = int(row["frame_pts"])
                except ValueError as exc:
                    raise ValueError(f"{label}: frame_pts must identify a decoded source frame.") from exc
                require(pts in frames and abs(frames[pts] - seconds) <= 1e-6,
                        f"{label}: time_s and frame_pts must match frames.csv; use the frame command.")
            if filename == "events.csv":
                kind = row["event_type"]
                require(kind in EVENT_TYPES and bool(row["location_id"]) and bool(row["episode_id"]), f"{label}: missing event/episode/location identity.")
                pending_proposal = row["review_method"] == "automatic_proposal" and not accepted
                require(pending_proposal or row["review_method"] in {"manual_count", "individual_review", "corrected"},
                        f"{label}: automatic/sample-audited acceptance is not implemented.")
                vehicle = kind.startswith("vehicle_")
                require((row["reviewed_class"] in CLASSES) if vehicle else row["reviewed_class"] == "person",
                        f"{label}: invalid vehicle/person category.")
                require(not row["vehicle_subtype"] or row["reviewed_class"] == "tricycle", f"{label}: this release supports subtype only for tricycles.")
                if accepted:
                    identity = (row["reviewed_class"], row["vehicle_subtype"], row["crossing_id"] if not vehicle else "")
                    require(episode_classes.setdefault(row["episode_id"], identity) == identity,
                            f"{label}: episode class/subtype/crossing changed between events.")
                    require(bool(row["approach_id"] if vehicle else row["crossing_id"]), f"{label}: missing approach/crossing ID.")
                    require(kind != "vehicle_movement" or bool(row["exit_id"]), f"{label}: a completed movement requires its visible exit.")
                    key = (row["episode_id"], kind, row["location_id"])
                    require(key not in episodes, f"{label}: duplicate accepted episode/event at this location.")
                    episodes[key] = seconds
                    accepted_events.append(row)
            elif filename == "signal_changes.csv":
                require(bool(row["signal_head_id"]) and bool(row["movement_group"]), f"{label}: signal head and controlled group required.")
                require(row["source"] in {"video", "observer_log"}, f"{label}: invalid signal source.")
                require(row["indication"] in {"red", "yellow", "green", "red_arrow", "yellow_arrow", "green_arrow", "walk", "dont_walk", "flashing", "unknown"}, f"{label}: invalid signal indication.")
            else:
                require(bool(row["approach_id"]), f"{label}: queue approach required.")
                require(row["visibility"] in {"complete", "lower_bound", "unknown"}, f"{label}: invalid queue visibility.")
                if row["visibility"] == "unknown":
                    require(row["queue_count"] == "", f"{label}: unknown queue must be blank, not zero.")
                else:
                    require(bool(re.fullmatch(r"[0-9]+", row["queue_count"])), f"{label}: queue count must be a nonnegative integer.")
    for row in accepted_events:
        key = (row["event_type"], row["location_id"])
        moment = float(row["time_s"])
        require(any(left <= moment < right and visibility != "unseen" for left, right, visibility in ranges.get(key, [])),
                f"Event {row['event_id']}: no visible declared coverage at its time/location.")
    # A pedestrian episode cannot end before it starts. Missing starts/arrivals
    # remain incomplete; no waiting time is imputed for them.
    pedestrian_episodes = {}
    for row in accepted_events:
        if row["event_type"].startswith("pedestrian_"):
            key = (row["episode_id"], row["crossing_id"])
            episode = pedestrian_episodes.setdefault(key, {})
            require(row["event_type"] not in episode, f"Episode {key}: duplicate pedestrian stage.")
            episode[row["event_type"]] = float(row["time_s"])
    for key, episode in pedestrian_episodes.items():
        times = [episode[kind] for kind in EVENT_TYPES[3:] if kind in episode]
        require(times == sorted(times), f"Episode {key}: pedestrian stages are out of time order.")
    summary = {"publication_status": "provisional", "gate_a": "not_implemented_no_automatic_acceptance",
               "gate_b": "independent_field_audit_not_recorded", "field_accuracy_verified": False,
               "source_kind": manifest["source_kind"], "accepted_event_count": len(accepted_events),
               "collection_clock_status": manifest["collection_clock_status"],
               "row_counts": {name: len(rows) for name, rows in tables.items()},
               "event_review_statuses": dict(Counter(row["review_status"] for row in tables["events.csv"])),
               "note": "Checks establish table consistency and source identity, not field accuracy or calibration."}
    return manifest, tables, summary


def make_bins(manifest: dict, tables: dict, bin_seconds: float) -> list[dict]:
    require(math.isfinite(bin_seconds) and bin_seconds >= 1, "Bin size must be at least one second.")
    end = manifest["media"]["decoded_duration_s"]
    scopes = sorted({(row["event_type"], row["location_id"]) for row in tables["coverage.csv"]})
    output = []
    for kind, location in scopes:
        events = [row for row in tables["events.csv"] if row["event_type"] == kind and row["location_id"] == location and row["review_status"] in ACCEPTED]
        coverage = [row for row in tables["coverage.csv"] if row["event_type"] == kind and row["location_id"] == location]
        unresolved = [row for row in tables["events.csv"] if row["event_type"] == kind and row["location_id"] == location and row["review_status"] in {"proposed", "uncertain"}]
        categories = {(label, "") for label in (CLASSES if kind.startswith("vehicle_") else ("person",))}
        categories.update((row["reviewed_class"], row["vehicle_subtype"]) for row in events)
        for index in range(math.ceil(end / bin_seconds)):
            left, right = index * bin_seconds, min((index + 1) * bin_seconds, end)
            full = sum(max(0, min(right, float(row["end_s"])) - max(left, float(row["start_s"])))
                       for row in coverage if row["visibility"] == "complete")
            complete = abs(full - (right - left)) < 1e-6
            reviewed = not any(left <= float(row["time_s"]) < right for row in unresolved)
            for label, subtype in sorted(categories):
                count = sum(left <= float(row["time_s"]) < right and row["reviewed_class"] == label and row["vehicle_subtype"] == subtype for row in events)
                output.append({**{key: manifest[key] for key in COMMON}, "start_s": left, "end_s": right,
                               "event_type": kind, "location_id": location, "reviewed_class": label,
                               "vehicle_subtype": subtype, "observed_count": count,
                               "count": count if complete and reviewed else "", "coverage": "complete" if complete else "incomplete",
                               "review_state": "manual_review_recorded" if reviewed else "unresolved",
                               "publication_status": "provisional"})
    return output


def export_revision(take: Path, reviewer: str, note: str, bin_seconds: float = 900) -> Path:
    require(bool(reviewer.strip()) and bool(note.strip()), "Export reviewer and review note are required.")
    manifest, tables, summary = validate(take)
    bins = make_bins(manifest, tables, bin_seconds)
    revisions = take / "revisions"
    existing = sorted(path for path in revisions.iterdir() if re.fullmatch(r"r[0-9]{6}", path.name))
    number_ = int(existing[-1].name[1:]) + 1 if existing else 1
    destination = revisions / f"r{number_:06d}"
    require(not destination.exists(), "Revision already exists.")
    previous = existing[-1] if existing else None
    if previous:
        old_manifest = read_json(previous / "manifest.json")
        for filename, expected in old_manifest["artifact_sha256"].items():
            require(Path(filename).name == filename, "Invalid file reference in previous revision.")
            require(sha256(previous / filename) == expected, f"Previous revision changed: {filename}.")
    previous_hashes = {name: sha256(previous / name) for name in TABLES} if previous else {}
    with tempfile.TemporaryDirectory(prefix=".export-", dir=revisions) as temporary:
        stage = Path(temporary) / "revision"
        stage.mkdir()
        for name, rows in tables.items():
            write_csv(stage / name, TABLES[name], rows)
        bin_columns = (*COMMON, "start_s", "end_s", "event_type", "location_id", "reviewed_class",
                       "vehicle_subtype", "observed_count", "count", "coverage", "review_state", "publication_status")
        write_csv(stage / "reviewed_bins.csv", bin_columns, bins)
        write_json(stage / "quality_report.json", summary)
        record = {"reviewer": reviewer.strip(), "note": note.strip(),
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "previous_revision": previous.name if previous else None,
                  "previous_table_sha256": previous_hashes,
                  "table_sha256": {name: sha256(stage / name) for name in TABLES},
                  "source_manifest_sha256": sha256(take / "manifest.json")}
        write_json(stage / "review_record.json", record)
        write_json(stage / "manifest.json", {**manifest, "revision": destination.name,
                   "bin_seconds": bin_seconds, "publication_status": "provisional",
                   "artifact_sha256": {path.name: sha256(path) for path in stage.iterdir()}})
        stage.rename(destination)
    return destination
