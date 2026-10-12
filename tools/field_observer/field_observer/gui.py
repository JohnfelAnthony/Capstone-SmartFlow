"""Loopback-only GUI with one background job and file-based evidence per recording."""

import csv
import json
import re
import secrets
import threading
import time
import uuid
import webbrowser
import zipfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .analysis import AnalysisCancelled, analyze, use_proposals
from .core import (CLASSES, COMMON, TABLES, create_take, export_revision, identifier, load_tables,
                   nearest_frame, number, read_json, read_take, require, sha256, write_csv, write_json)
from .demo import DemoDetector, create_demo
from .detector import TrafficDetector
from .lines import validate_config
from .media import display_frames
from .preview import PreviewWriter, annotate, jpeg_bytes

BUSY = {"uploading", "indexing", "loading", "analyzing", "stopping", "exporting"}


class ObserverGUI:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.project = self.take = self.run = self.revision = None
        self.manifest = self.config = None
        self.demo = False
        self.image = b""
        self.version = 0
        self.status = "empty"
        self.message = "Choose a recording, or try the scripted demo."
        self.frame_number = 0
        self.seconds = 0.
        self.counts = Counter()
        self.name = ""

    def idle(self):
        require(self.status not in BUSY, "Wait for the current operation, or stop analysis first.")

    def update(self, **values):
        with self.lock:
            for key, value in values.items():
                setattr(self, key, value)
            self.version += 1

    def saved(self):
        rows = []
        for path in sorted(self.root.glob("p*"), reverse=True):
            if (path / "ui.json").is_file() and (path / "take/manifest.json").is_file():
                try:
                    meta = read_json(path / "ui.json")
                    rows.append({"id": path.name, "name": meta["name"], "demo": meta["demo"]})
                except (OSError, ValueError, KeyError):
                    continue
        return rows

    def state(self):
        with self.lock:
            return {"status": self.status, "message": self.message, "version": self.version,
                    "name": self.name, "demo": self.demo, "seconds": self.seconds,
                    "frame_number": self.frame_number, "config": self.config,
                    "duration": self.manifest["media"]["decoded_duration_s"] if self.manifest else 0,
                    "counts": [{"line": key[0], "kind": key[1], "class": key[2], "count": value}
                               for key, value in self.counts.items()],
                    "has_replay": bool(self.run and (self.run / "preview.mp4").exists() and self.status == "complete"),
                    "has_export": bool(self.revision), "project_id": self.project.name if self.project else None,
                    "output_folder": str(self.project) if self.project else ""}

    def background(self, function):
        def wrapped():
            try:
                function()
            except AnalysisCancelled:
                self.update(status="cancelled", message="Stopped. Partial output is preserved; start a new analysis to retry.")
            except Exception as exc:
                self.update(status="error", message=str(exc))
        self.thread = threading.Thread(target=wrapped, daemon=True)
        self.thread.start()

    def new_project(self, metadata, demo=False):
        with self.lock:
            self.idle()
            for key in ("survey_id", "intersection_id"):
                identifier(metadata.get(key, ""), key)
            require(bool(metadata.get("collector", "").strip()), "Enter the researcher's name.")
            require(metadata.get("source_kind") in ("observed", "synthetic"), "Choose the source type.")
            project = self.root / ("p" + uuid.uuid4().hex)
            project.mkdir()
            self.project, self.take, self.run, self.revision = project, project / "take", None, None
            self.manifest = self.config = None
            self.image = b""
            self.counts = Counter()
            self.name, self.demo = metadata["name"], demo
            self.seconds, self.frame_number = 0., 0
            self.cancel.clear()
            self.update(status="uploading", message="Saving the recording locally...")
            write_json(project / "ui.json", {"name": self.name, "demo": demo, "latest_run": None})
            return project

    def register(self, source, metadata):
        self.update(status="indexing", message="Reading the original frame timestamps. Long recordings take longer.")
        self.manifest = create_take(source, self.take, survey_id=metadata["survey_id"],
                                    intersection_id=metadata["intersection_id"], take_id=self.project.name,
                                    start=metadata.get("start") or None, collector=metadata["collector"],
                                    clock_note=metadata.get("clock_note") or "Collection clock not verified in GUI",
                                    source_kind=metadata["source_kind"])
        self.configure(0)
        if self.demo:
            self.config["lines"] = [
                dict(id="VEHICLES_IN", event_type="vehicle_arrival", location_id="N_APPROACH", approach_id="N", crossing_id="",
                     a=[140, 240], b=[490, 240], direction="negative_to_positive"),
                dict(id="PEOPLE_START", event_type="pedestrian_start", location_id="CROSS_N", approach_id="", crossing_id="C_N",
                     a=[520, 240], b=[630, 240], direction="negative_to_positive")]
        self.update(status="ready", message="Draw a counting line, then start analysis." if not self.demo else
                    "Scripted demo loaded. Start analysis to see example boxes and counts; these are not AI results.")

    def configure(self, rotation):
        require(rotation in (0, 90, 180, 270), "Choose a supported rotation.")
        generator = display_frames(Path(self.manifest["source_path"]), rotation)
        try:
            _, _, picture = next(generator)
        finally:
            generator.close()
        width, height = picture.size
        self.config = {"schema_version": 1, "take_id": self.manifest["take_id"], "source_sha256": self.manifest["source_sha256"],
                       "coordinate_space": "display_pixels", "rotation_clockwise": rotation,
                       "width": width, "height": height, "deadband_px": min(4, min(width, height) / 10),
                       "max_gap_s": .5, "lines": []}
        picture.thumbnail((960, 960))
        self.update(image=jpeg_bytes(picture), seconds=0., frame_number=0)

    def open_project(self, project_id):
        with self.lock:
            self.idle()
            require(bool(re.fullmatch(r"p[0-9a-f]{32}", project_id)), "Invalid saved recording ID.")
            project = self.root / project_id
            meta = read_json(project / "ui.json")
            manifest, _ = read_take(project / "take")
            self.project, self.take, self.manifest = project, project / "take", manifest
            self.name, self.demo = meta["name"], bool(meta["demo"])
            self.run = self.revision = None
            self.counts = Counter()
            self.configure(0)
            latest = meta.get("latest_run")
            if latest and re.fullmatch(r"analysis_[0-9a-f]{12}", latest):
                run = project / latest
                if read_json(run / "run.json").get("status") == "complete" and (run / "preview.mp4").is_file():
                    self.run, self.config = run, read_json(run / "lines.json")
                    for event in self.proposals():
                        self.counts[(event["line_id"], event["event_type"], event["detected_class"])] += 1
            self.update(status="complete" if self.run else "ready", message="Saved recording opened.")

    def start_analysis(self, supplied_config, confidence):
        with self.lock:
            self.idle()
            require(self.manifest is not None, "Choose a recording first.")
            require(not load_tables(self.take)["events.csv"],
                    "This recording already has a review draft. Preserve it and upload a new take for a different analysis.")
            validate_config(supplied_config, self.manifest)
            require(.1 <= number(confidence, "confidence") <= .9, "Confidence must be between 0.1 and 0.9.")
            self.config = supplied_config
            self.run = self.project / ("analysis_" + uuid.uuid4().hex[:12])
            config_path = self.project / "pending-lines.json"
            write_json(config_path, self.config)
            self.cancel.clear()
            self.counts = Counter()
            self.revision = None
            self.update(status="loading", message="Loading the detector. CPU startup may take a little while.", frame_number=0, seconds=0.)
        def work():
            writer = None
            last_preview = 0.
            def frame(picture, pts, seconds, detections, events, frame_number):
                nonlocal writer, last_preview
                if writer is None:
                    writer = PreviewWriter(self.run / "preview.mp4")
                annotated = annotate(picture, detections, self.config, seconds, self.demo)
                writer.append(annotated, seconds)
                with self.lock:
                    for event in events:
                        self.counts[(event["line_id"], event["event_type"], event["detected_class"])] += 1
                now = time.monotonic()
                if now - last_preview >= .15 or events:
                    self.update(status="stopping" if self.cancel.is_set() else "analyzing", message="Processing frames locally...",
                                seconds=seconds, frame_number=frame_number, image=jpeg_bytes(annotated))
                    last_preview = now
            try:
                result = analyze(self.take, config_path, self.run, Path(__file__).resolve().parents[1] / ".cache/models/rf-detr-small.pth",
                                 confidence=float(confidence), detector_factory=DemoDetector if self.demo else TrafficDetector,
                                 on_frame=frame, cancelled=self.cancel.is_set)
            finally:
                if writer:
                    writer.close()
            if self.cancel.is_set():
                raise AnalysisCancelled("Stopped before the review handoff.")
            use_proposals(self.take, self.run)
            write_json(self.run / "preview.json", {"source_sha256": self.manifest["source_sha256"],
                       "preview_sha256": sha256(self.run / "preview.mp4"), "role": "annotated visual aid; original remains authoritative"})
            write_json(self.project / "ui.json", {"name": self.name, "demo": self.demo, "latest_run": self.run.name})
            self.update(status="complete", message="Analysis complete. Play the annotated video and review every proposed event.",
                        frame_number=result["decoded_frames"], seconds=self.manifest["media"]["last_frame_time_s"])
        self.background(work)

    def proposals(self):
        if not self.run or not (self.run / "proposals.csv").exists():
            return []
        with (self.run / "proposals.csv").open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def events(self):
        with self.lock:
            if not self.take or self.status in BUSY:
                return {"events": [], "proposals": [], "coverage": []}
            tables = load_tables(self.take)
            return {"events": tables["events.csv"], "coverage": tables["coverage.csv"], "proposals": self.proposals()}

    def save_draft(self, name, rows):
        temporary = self.take / "draft" / (name + ".tmp")
        write_csv(temporary, TABLES[name], rows)
        temporary.replace(self.take / "draft" / name)

    def review(self, data):
        with self.lock:
            self.idle()
            require(self.run is not None and read_json(self.run / "run.json")["status"] == "complete", "Finish analysis first.")
            rows = load_tables(self.take)["events.csv"]
            require(bool(data.get("reviewer", "").strip()), "A reviewer name is required.")
            existing = next((row for row in rows if row["event_id"] == data.get("event_id")), None)
            row = dict(existing) if existing else {key: "" for key in TABLES["events.csv"]}
            if existing is None:
                require(not data.get("event_id"), "Event not found.")
                line = next((line for line in self.config["lines"] if line["id"] == data.get("line_id")), None)
                require(line is not None, "Choose the line for this missed event.")
                timing = nearest_frame(self.take, number(data["time_s"], "event time"))
                row.update({key: self.manifest[key] for key in COMMON}, event_id="M" + uuid.uuid4().hex[:12],
                           event_type=line["event_type"], location_id=line["location_id"],
                           approach_id=line.get("approach_id", ""), crossing_id=line.get("crossing_id", ""),
                           direction=line["direction"], frame_pts=timing["frame_pts"], time_s=timing["time_s"])
            elif "time_s" in data:
                timing = nearest_frame(self.take, number(data["time_s"], "event time"))
                row.update(frame_pts=timing["frame_pts"], time_s=timing["time_s"])
            status = data.get("review_status")
            require(status in ("accepted", "corrected", "rejected", "uncertain"), "Choose a review decision.")
            category = data.get("reviewed_class")
            is_vehicle = row["event_type"].startswith("vehicle_")
            require(category in CLASSES if is_vehicle else category == "person", "Choose the correct vehicle/person class.")
            subtype = data.get("vehicle_subtype", "") if category == "tricycle" else ""
            require(subtype in ("", "tagum_passenger_tricycle"), "Unknown tricycle subtype.")
            require(status != "corrected" or bool(data.get("note", "").strip()), "Describe the correction in the note.")
            episode = data.get("episode_id", "").strip() or row.get("episode_id") or row["event_id"]
            identifier(episode, "episode_id")
            row.update(reviewed_class=category, vehicle_subtype=subtype, review_status=status, episode_id=episode,
                       review_method="individual_review" if existing else "manual_count", reviewer=data["reviewer"].strip(),
                       note=data.get("note", "").strip())
            rows = [row if item["event_id"] == row["event_id"] else item for item in rows] if existing else [*rows, row]
            self.save_draft("events.csv", rows)
            self.update(message="Review saved. The original detector proposals are preserved.")

    def coverage(self, data):
        with self.lock:
            self.idle()
            require(self.config is not None, "Choose a recording first.")
            line = next((line for line in self.config["lines"] if line["id"] == data.get("line_id")), None)
            require(line is not None, "Choose the line covered by this review.")
            start, end = number(data["start_s"], "start"), number(data["end_s"], "end")
            require(0 <= start < end <= self.manifest["media"]["decoded_duration_s"] + 1e-6, "Coverage interval is outside this recording.")
            visibility = data.get("visibility")
            require(visibility in ("complete", "partial", "unseen"), "Choose visibility.")
            require(visibility != "complete" or data.get("full_pass") is True, "Complete coverage requires a full review including missed objects.")
            require(bool(data.get("reviewer", "").strip()), "Enter a reviewer.")
            rows = load_tables(self.take)["coverage.csv"]
            # Saving the same interval updates it; different overlapping intervals are rejected.
            same = lambda row: row["event_type"] == line["event_type"] and row["location_id"] == line["location_id"]
            rows = [row for row in rows if not (same(row) and float(row["start_s"]) == start and float(row["end_s"]) == end)]
            require(all(not same(row) or end <= float(row["start_s"]) or start >= float(row["end_s"]) for row in rows),
                    "This interval overlaps existing coverage for the line.")
            row = {key: "" for key in TABLES["coverage.csv"]}
            row.update({key: self.manifest[key] for key in COMMON}, event_type=line["event_type"], location_id=line["location_id"],
                       start_s=start, end_s=end, visibility=visibility, review_method="manual_count", reviewer=data["reviewer"], note=data.get("note", ""))
            self.save_draft("coverage.csv", [*rows, row])
            self.update(message="Coverage saved. Export will check all accepted events against it.")


class GUIHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


def make_server(root: Path, port=0):
    service = ObserverGUI(root)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def json_response(self, value, status=200):
            payload = json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def local_request(self):
            port = self.server.server_port
            require(self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}"), "This app accepts local requests only.")

        def file_response(self, path, content_type, attachment=None):
            require(path.is_file(), "File is not ready.")
            size = path.stat().st_size
            start, end = 0, size - 1
            requested = self.headers.get("Range")
            if requested:
                match = re.fullmatch(r"bytes=(\d+)-(\d*)", requested)
                if not match or int(match[1]) >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                start = int(match[1])
                end = min(int(match[2]) if match[2] else end, end)
                require(start <= end, "Invalid byte range.")
            self.send_response(206 if requested else 200)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if requested:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if attachment:
                self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
            self.end_headers()
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)

        def do_GET(self):
            try:
                self.local_request()
                route = urlparse(self.path).path
                if route == "/":
                    html = Path(__file__).with_name("gui.html").read_text(encoding="utf-8").replace("__TOKEN__", token).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(html)
                elif route == "/api/state":
                    self.json_response(service.state())
                elif route == "/api/saved":
                    self.json_response(service.saved())
                elif route == "/api/events":
                    self.json_response(service.events())
                elif route == "/api/image":
                    with service.lock:
                        data = service.image
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif route == "/api/replay":
                    require(service.status == "complete" and service.run is not None, "Finish analysis before playback.")
                    self.file_response(service.run / "preview.mp4", "video/mp4")
                elif route == "/api/original":
                    require(service.manifest is not None, "Choose a recording first.")
                    source = Path(service.manifest["source_path"])
                    media_type = "video/mp4" if source.suffix.lower() in (".mp4", ".m4v", ".mov") else "application/octet-stream"
                    self.file_response(source, media_type)
                elif route == "/api/export.zip":
                    require(service.revision is not None, "Export a reviewed revision first.")
                    self.file_response(service.revision.parent / (service.revision.name + ".zip"), "application/zip", "field-observations.zip")
                else:
                    self.json_response({"error": "Not found"}, 404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.json_response({"error": str(exc)}, 400)

        def do_POST(self):
            try:
                self.local_request()
                require(secrets.compare_digest(self.headers.get("X-Observer-Token", ""), token), "Refresh the app before making changes.")
                expected_origin = f"http://{self.headers['Host']}"
                require(self.headers.get("Origin", expected_origin) == expected_origin, "Cross-site requests are not accepted.")
                route = urlparse(self.path)
                length = int(self.headers.get("Content-Length", "0"))
                if route.path == "/api/upload":
                    require(0 < length <= 8 * 1024 ** 3, "Choose a video smaller than 8 GB.")
                    metadata = {key: values[0] for key, values in parse_qs(route.query).items()}
                    suffix = Path(metadata.get("name", "")).suffix.lower()
                    require(suffix in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts"), "Unsupported video filename extension.")
                    project = service.new_project(metadata)
                    source = project / ("source" + suffix)
                    try:
                        with source.open("xb") as stream:
                            remaining = length
                            while remaining:
                                block = self.rfile.read(min(1024 * 1024, remaining))
                                require(bool(block), "Upload ended early; choose the recording again.")
                                stream.write(block)
                                remaining -= len(block)
                        service.background(lambda: service.register(source, metadata))
                    except Exception as exc:
                        service.update(status="error", message=str(exc))
                        raise
                else:
                    require(0 < length <= 2 * 1024 * 1024, "Request is too large or empty.")
                    data = json.loads(self.rfile.read(length))
                    require(isinstance(data, dict), "Expected an object.")
                    if route.path == "/api/demo":
                        metadata = dict(name="Scripted visual demo", survey_id="SYNTHETIC", intersection_id="DEMO", collector="Demo",
                                        source_kind="synthetic", clock_note="Scripted software demo, not a field observation")
                        project = service.new_project(metadata, demo=True)
                        def demo_job():
                            source = project / "source.mp4"
                            create_demo(source)
                            service.register(source, metadata)
                        service.background(demo_job)
                    elif route.path == "/api/open":
                        service.open_project(data["id"])
                    elif route.path == "/api/rotate":
                        with service.lock:
                            service.idle()
                            require(service.manifest is not None and service.run is None, "Rotate before starting analysis.")
                            service.configure(data["rotation"])
                    elif route.path == "/api/analyze":
                        service.start_analysis(data["config"], data.get("confidence", .35))
                    elif route.path == "/api/stop":
                        with service.lock:
                            require(service.status in ("loading", "analyzing", "stopping"), "No analysis is running.")
                            service.cancel.set()
                            service.update(status="stopping", message="Stopping after the current frame/model load finishes...")
                    elif route.path == "/api/review":
                        service.review(data)
                    elif route.path == "/api/coverage":
                        service.coverage(data)
                    elif route.path == "/api/export":
                        with service.lock:
                            service.idle()
                            require(service.status == "complete", "Finish analysis before export.")
                            service.update(status="exporting", message="Checking observations and saving a provisional revision...")
                        def export_job():
                            try:
                                revision = export_revision(service.take, data.get("reviewer", ""), data.get("note", ""))
                                with zipfile.ZipFile(revision.parent / (revision.name + ".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
                                    for item in revision.iterdir():
                                        archive.write(item, item.name)
                                service.update(revision=revision, status="complete", message="Provisional revision saved. Download the ZIP below.")
                            except (ValueError, OSError) as exc:
                                service.update(status="complete", message=f"Export needs attention: {exc}")
                        service.background(export_job)
                    else:
                        raise ValueError("Unknown action.")
                self.json_response({"ok": True})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.json_response({"error": str(exc)}, 400)

    server = GUIHTTPServer(("127.0.0.1", port), Handler)
    server.observer = service
    return server


def serve(root=None, port=0, open_browser=True):
    root = root or Path(__file__).resolve().parents[3] / "data/generated/field_observer_gui"
    server = make_server(root, port)
    address = f"http://127.0.0.1:{server.server_port}"
    print(f"Field Observer: {address}\nKeep this window open while using the app. Close it to stop.", flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.observer.cancel.set()
    finally:
        server.server_close()
