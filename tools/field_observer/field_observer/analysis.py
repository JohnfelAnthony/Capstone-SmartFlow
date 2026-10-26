"""Offline proposal runs. Raw detector evidence never becomes an accepted count."""

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .core import COMMON, TABLES, load_tables, read_json, read_take, require, sha256, write_csv, write_json
from .detector import TrafficDetector
from .lines import LineCounter, validate_config
from .media import display_frames

TRACK_COLUMNS = ("frame_pts", "time_s", "track_id", "detected_class_id", "detected_class",
                 "confidence", "x1", "y1", "x2", "y2")
PROPOSAL_COLUMNS = (*TABLES["events.csv"], "line_id", "track_id", "detected_class_id", "detected_class", "confidence")


class AnalysisCancelled(Exception):
    """A GUI cancellation leaves an explicitly interrupted evidence run."""


def analyze(take: Path, config_path: Path, destination: Path, weights: Path, *,
            confidence: float = 0.35, device: str = "auto", detector_factory=TrafficDetector, progress=None,
            on_frame=None, cancelled=None) -> dict:
    require(not destination.exists(), "Analysis destination already exists; choose a new run directory.")
    manifest, indexed = read_take(take)
    config = read_json(config_path)
    validate_config(config, manifest)
    detector = detector_factory(weights, confidence, device)
    counter = LineCounter(config)
    run_id = "A" + uuid.uuid4().hex[:12]
    destination.mkdir(parents=True)
    run = {"schema_version": 1, "tool_version": __version__, "run_id": run_id,
           "status": "incomplete", "publication_status": "proposals_only", "field_accuracy_verified": False,
           **{key: manifest[key] for key in COMMON}, "source_kind": manifest["source_kind"],
           "source_sha256": manifest["source_sha256"], "source_manifest_sha256": sha256(take / "manifest.json"),
           "started_at": datetime.now(timezone.utc).isoformat(), "detector": detector.provenance,
           "event_time_rule": "first stable frame beyond the line; no interpolated event timestamp",
           "limitations": ["No dedicated tricycle/jeepney model; review missed and misclassified vehicles.",
                           "People crossing lines are candidates; exclude riders and sidewalk traffic.",
                           "Track fragmentation or ID switches can miss or duplicate events.",
                           "No automatic turns, signal phases, queues, waiting times or coverage certification."]}
    write_json(destination / "run.json", run)
    write_json(destination / "lines.json", config)
    seen = 0
    event_count = 0
    first_time = None
    previous_time = None
    try:
        with (destination / "tracks.csv").open("w", newline="", encoding="utf-8") as tracks_file, \
             (destination / "proposals.csv").open("w", newline="", encoding="utf-8") as proposals_file, \
             (destination / "events_for_review.csv").open("w", newline="", encoding="utf-8") as events_file:
            tracks_writer = csv.DictWriter(tracks_file, fieldnames=TRACK_COLUMNS)
            proposals_writer = csv.DictWriter(proposals_file, fieldnames=PROPOSAL_COLUMNS)
            events_writer = csv.DictWriter(events_file, fieldnames=TABLES["events.csv"])
            for writer in (tracks_writer, proposals_writer, events_writer):
                writer.writeheader()
            for pts, absolute, picture in display_frames(Path(manifest["source_path"]), config["rotation_clockwise"]):
                if cancelled and cancelled():
                    raise AnalysisCancelled("Analysis cancelled by the operator.")
                first_time = absolute if first_time is None else first_time
                seconds = float(absolute - first_time)
                require(pts in indexed and abs(indexed[pts] - seconds) <= 1e-6,
                        "Decoded timestamps no longer match the registered source.")
                require(previous_time is None or seconds > previous_time, "Decoded timestamps must strictly increase.")
                require(picture.size == (config["width"], config["height"]), "Decoded image dimensions changed.")
                previous_time = seconds
                detections = detector.update(picture, seconds)
                new_events = []
                for track in detections:
                    tracks_writer.writerow({"frame_pts": pts, "time_s": seconds, **track})
                    if not track["track_id"]:
                        continue
                    for line in counter.update(track, seconds):
                        event_count += 1
                        event = {key: "" for key in TABLES["events.csv"]}
                        event.update({key: manifest[key] for key in COMMON})
                        event.update(event_id=f"{run_id}_E{event_count:06d}", episode_id=f"{run_id}_{track['track_id']}",
                                     event_type=line["event_type"], location_id=line["location_id"], time_s=seconds,
                                     frame_pts=pts, approach_id=line.get("approach_id", ""), crossing_id=line.get("crossing_id", ""),
                                     direction=line["direction"], reviewed_class="person" if track["detected_class"] == "person" else "unknown",
                                     review_status="proposed", review_method="automatic_proposal",
                                     note=f"Unreviewed {run_id}; detector suggested {track['detected_class']}; line {line['id']}.")
                        events_writer.writerow(event)
                        proposal = {**event, "line_id": line["id"],
                                    **{key: track[key] for key in ("track_id", "detected_class_id", "detected_class", "confidence")}}
                        proposals_writer.writerow(proposal)
                        new_events.append(proposal)
                seen += 1
                if on_frame:
                    on_frame(picture, pts, seconds, detections, new_events, seen)
                if progress and seen % 100 == 0:
                    progress(seen, seconds, event_count)
        if cancelled and cancelled():
            raise AnalysisCancelled("Analysis cancelled by the operator.")
        require(seen == len(indexed), "Analysis ended before all registered frames were processed.")
        require(sha256(Path(manifest["source_path"])) == manifest["source_sha256"], "Original video changed during analysis.")
        require(sha256(take / "manifest.json") == run["source_manifest_sha256"], "Take manifest changed during analysis.")
        require(sha256(take / "frames.csv") == manifest["frames_sha256"], "Frame index changed during analysis.")
        artifacts = ("lines.json", "tracks.csv", "proposals.csv", "events_for_review.csv")
        run.update(status="complete", decoded_frames=seen, proposal_count=event_count,
                   completed_at=datetime.now(timezone.utc).isoformat(),
                   artifact_sha256={name: sha256(destination / name) for name in artifacts})
    except BaseException as exc:
        run.update(status="interrupted" if isinstance(exc, (KeyboardInterrupt, AnalysisCancelled)) else "failed",
                   decoded_frames=seen, proposal_count=event_count, error=str(exc))
        write_json(destination / "run.json", run)
        raise
    write_json(destination / "run.json", run)
    return {"analysis_path": str(destination.resolve()), **run}


def use_proposals(take: Path, analysis: Path) -> dict:
    """Explicitly seed an EMPTY draft. Never append a second run or replace edits."""
    manifest, _ = read_take(take)
    run = read_json(analysis / "run.json")
    require(run.get("status") == "complete", "Only a complete analysis can seed review.")
    require(run.get("source_manifest_sha256") == sha256(take / "manifest.json") and
            run.get("source_sha256") == manifest["source_sha256"], "Analysis belongs to a different take or source.")
    names = {"lines.json", "tracks.csv", "proposals.csv", "events_for_review.csv"}
    require(set(run.get("artifact_sha256", {})) == names, "Analysis artifact inventory is invalid.")
    for name in names:
        require(sha256(analysis / name) == run["artifact_sha256"][name], f"Analysis artifact changed: {name}.")
    tables = load_tables(take)
    require(not tables["events.csv"], "Draft events are not empty; preserve existing review instead of merging another run.")
    with (analysis / "events_for_review.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == list(TABLES["events.csv"]), "Unexpected proposal event columns.")
        rows = list(reader)
    require(all(row["review_status"] == "proposed" and row["review_method"] == "automatic_proposal" for row in rows),
            "Analysis must contain only unreviewed proposals.")
    write_csv(take / "draft" / "events.csv", TABLES["events.csv"], rows)
    return {"draft_events": len(rows), "review_status": "proposed", "analysis_path": str(analysis.resolve()),
            "next": "Review against the entire video, add misses, set classes and coverage, then check/export."}
