"""Manual lane-by-lane counting: one pass per approach over the raw video, merged into one reviewed revision.

Every click records a vehicle class and the exit it took, stamped with VIDEO time. Passes are autosaved JSON files. A pass is
complete only when the reviewer attests it and the playback intervals actually watched span the whole video; gaps are never
filled and incomplete passes are reported, not guessed. The export writes ordinary draft tables and reuses `export_revision`,
so it is the same revision format the detector workflow produces (and SmartFlow's "Import counts from Field Observer" reads).
"""

import bisect
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .core import COMMON, TABLES, export_revision, load_tables, number, read_take, require, write_csv, write_json

# Copied from SmartFlow's registered networks (this tool never imports SmartFlow). Keys are the engine's approach names, which the
# importer requires in lines.json; `street` is the road that leg is on and `end` where the leg leaves the junction.
SITES = {
    "tagum_site_a": {"label": "Site A · Capitol Circumferential Rd × Dalisay Gante Rd",
                     "approaches": {"north": ("Dalisay Gante Road", "north end"), "south": ("Dalisay Gante Road", "south end"),
                                    "west": ("Capitol Circumferential Road", "west end"), "east": ("Capitol Circumferential Road", "east end")}},
    "tagum_site_b": {"label": "Site B · Davao–Agusan National Highway × Sobrecarey / Dao St",
                     "approaches": {"north": ("Sobrecarey Street", "north end"), "south": ("Dao Street", "south end"),
                                    "west": ("Davao-Agusan National Highway", "west end"), "east": ("Davao-Agusan National Highway", "east end")}},
}
VEHICLE_CLASSES = ("car", "motorcycle", "tricycle", "bus", "truck")  # exactly the simulation's five classes
GAP_S = 1.0           # watched intervals closer than this are one interval (playback ticks are ~0.25 s apart)
DEFAULT_BIN_S = 900.0


def site_view(site_id: str) -> dict:
    require(site_id in SITES, "Choose a study site.")
    site = SITES[site_id]
    return {"id": site_id, "label": site["label"], "classes": list(VEHICLE_CLASSES),
            "approaches": [{"id": name, "street": street, "end": end} for name, (street, end) in site["approaches"].items()]}


def _pass_path(directory: Path, approach: str) -> Path:
    return directory / f"pass_{approach}.json"


def load_pass(directory: Path, approach: str) -> dict:
    path = _pass_path(directory, approach)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"approach": approach, "clicks": [], "watched": [], "complete": False, "reviewer": ""}


def save_pass(directory: Path, data: dict) -> None:
    """Atomic replace: a crash leaves the previous complete file, never half a pass."""
    directory.mkdir(parents=True, exist_ok=True)
    path = _pass_path(directory, data["approach"])
    temporary = path.with_suffix(".tmp")
    write_json(temporary, data)
    temporary.replace(path)


def load_site(directory: Path) -> str | None:
    path = directory / "meta.json"
    return json.loads(path.read_text(encoding="utf-8"))["site"] if path.is_file() else None


def set_site(directory: Path, site_id: str) -> None:
    require(site_id in SITES, "Choose a study site.")
    current = load_site(directory)
    require(current in (None, site_id) or not any(load_pass(directory, name)["clicks"] for name in SITES[current]["approaches"]),
            "This recording already has clicks for another site; the approach names would not match.")
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "meta.json", {"site": site_id})


def merge_intervals(intervals: list, gap: float = GAP_S) -> list:
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def spans_video(watched: list, duration: float) -> bool:
    return bool(watched) and watched[0][0] <= GAP_S and watched[-1][1] >= duration - GAP_S and len(watched) == 1


def add_click(directory: Path, site_id: str, duration: float, data: dict) -> dict:
    approach, exit_, vehicle = data.get("approach"), data.get("exit"), data.get("class")
    names = SITES[site_id]["approaches"]
    require(approach in names, "Choose the approach being counted.")
    require(exit_ in names and exit_ != approach, "Choose an exit leg other than the approach the vehicle came from.")
    require(vehicle in VEHICLE_CLASSES, "Choose one of the five vehicle types.")
    moment = number(data.get("time_s"), "video time")
    require(0 <= moment <= duration, "Click time is outside the video.")
    current = load_pass(directory, approach)
    current["clicks"].append({"id": uuid.uuid4().hex[:12], "time_s": moment, "class": vehicle, "exit": exit_,
                              "saved_at": datetime.now(timezone.utc).isoformat()})
    save_pass(directory, current)
    return current


def undo_click(directory: Path, approach: str) -> dict:
    current = load_pass(directory, approach)
    require(bool(current["clicks"]), "Nothing to undo in this pass.")
    current["clicks"].pop()
    save_pass(directory, current)
    return current


def add_watched(directory: Path, approach: str, duration: float, start, end) -> None:
    start, end = number(start, "watched start"), number(end, "watched end")
    require(0 <= start <= end <= duration + 1, "Watched interval is outside the video.")
    current = load_pass(directory, approach)
    current["watched"] = merge_intervals([*current["watched"], [start, min(end, duration)]])
    save_pass(directory, current)


def set_complete(directory: Path, approach: str, duration: float, complete: bool, reviewer: str) -> None:
    current = load_pass(directory, approach)
    if complete:
        require(bool(reviewer.strip()), "Enter the name of the person who counted this approach.")
        require(spans_video(current["watched"], duration),
                "The video has not been played through for this approach without gaps; play the whole video in this pass first.")
    current.update(complete=complete, reviewer=reviewer.strip() if complete else current["reviewer"])
    save_pass(directory, current)


def summary(directory: Path, site_id: str, duration: float) -> dict:
    passes = []
    for name in SITES[site_id]["approaches"]:
        current = load_pass(directory, name)
        tally = {}
        for click in current["clicks"]:
            tally[f"{click['exit']}|{click['class']}"] = tally.get(f"{click['exit']}|{click['class']}", 0) + 1
        passes.append({"approach": name, "count": len(current["clicks"]), "tally": tally, "watched": current["watched"],
                       "watched_s": round(sum(end - start for start, end in current["watched"]), 2),
                       "spans_video": spans_video(current["watched"], duration), "complete": current["complete"],
                       "reviewer": current["reviewer"], "recent": current["clicks"][-8:][::-1]})
    return {"site": site_view(site_id), "passes": passes, "duration": duration,
            "can_export": all(item["complete"] and item["spans_video"] for item in passes)}


def _lines_config(manifest: dict, site_id: str) -> dict:
    """lines.json for the revision. Nothing was drawn: every line has a nominal segment, flagged as such."""
    width, height = manifest["media"]["width"], manifest["media"]["height"]
    names = list(SITES[site_id]["approaches"])
    lines = []
    for index, role in enumerate(("arrival", "exit")):
        for offset, name in enumerate(names):
            row = (index * len(names) + offset + 1) * height / (2 * len(names) + 1)
            lines.append({"id": f"{name}_{role}", "event_type": "vehicle_arrival" if role == "arrival" else "vehicle_discharge",
                          "location_id": f"{name}_{role}", "approach_id": name, "crossing_id": "", "role": role,
                          "direction": "negative_to_positive", "a": [0, round(row)], "b": [width - 1, round(row)],
                          "geometry": "nominal_not_drawn"})
    return {"schema_version": 1, "take_id": manifest["take_id"], "source_sha256": manifest["source_sha256"],
            "coordinate_space": "display_pixels", "rotation_clockwise": 0, "width": width, "height": height,
            "deadband_px": min(4, min(width, height) / 10), "max_gap_s": .5, "counting_method": "manual_click", "lines": lines}


def export_manual(take: Path, directory: Path, reviewer: str, note: str, bin_seconds: float = DEFAULT_BIN_S) -> Path:
    """Merge the four complete passes into draft tables, then export through the tool's ordinary revision writer."""
    site_id = load_site(directory)
    require(site_id is not None, "Choose the study site first.")
    manifest, frames = read_take(take, verify_video=False)
    duration = manifest["media"]["decoded_duration_s"]
    report = summary(directory, site_id, duration)
    incomplete = [item["approach"] for item in report["passes"] if not (item["complete"] and item["spans_video"])]
    require(not incomplete, "Every approach needs a complete pass over the whole video before export. Not complete: " + ", ".join(incomplete) + ".")
    marker = directory / "draft_written"
    tables = load_tables(take)
    require(marker.exists() or not (tables["events.csv"] or tables["coverage.csv"]),
            "This recording already has a detector review draft; manual counts need a recording with an empty draft.")
    times = sorted(frames.values())

    def snapped(moment):  # the nearest decoded frame, as the validation requires time_s to equal a frames.csv time
        position = bisect.bisect_left(times, moment)
        return min(times[max(0, position - 1):position + 1], key=lambda value: abs(value - moment))

    pts_of = {time_s: pts for pts, time_s in frames.items()}
    context = {key: manifest[key] for key in COMMON}
    events, coverage = [], []
    reviewers = ", ".join(sorted({item["reviewer"] for item in report["passes"]}))  # an exit line is counted by every pass
    for item in report["passes"]:
        name = item["approach"]
        current = load_pass(directory, name)
        for click in current["clicks"]:
            moment = snapped(click["time_s"])
            base = {**context, "episode_id": f"MC_{click['id']}", "time_s": moment, "frame_pts": pts_of[moment],
                    "direction": "negative_to_positive", "reviewed_class": click["class"], "vehicle_subtype": "",
                    "review_status": "accepted", "review_method": "manual_count", "reviewer": current["reviewer"]}
            events.append({**base, "event_id": f"MA_{click['id']}", "event_type": "vehicle_arrival", "location_id": f"{name}_arrival",
                           "approach_id": name, "exit_id": f"{click['exit']}_exit", "crossing_id": "",
                           "note": f"manual count, pass {name}; exit chosen by the counter"})
            events.append({**base, "event_id": f"MX_{click['id']}", "event_type": "vehicle_discharge", "location_id": f"{click['exit']}_exit",
                           "approach_id": name, "exit_id": f"{click['exit']}_exit", "crossing_id": "",
                           "note": "manual count: exit recorded at the click time, not an observed crossing time"})
        for location, kind, who in ((f"{name}_arrival", "vehicle_arrival", current["reviewer"]), (f"{name}_exit", "vehicle_discharge", reviewers)):
            coverage.append({**context, "event_type": kind, "location_id": location, "start_s": 0, "end_s": duration, "visibility": "complete",
                             "review_method": "manual_count", "reviewer": who,
                             "note": "pass attested complete; playback watched without gaps"})
    events.sort(key=lambda row: (row["time_s"], row["event_id"]))
    write_csv(take / "draft" / "events.csv", TABLES["events.csv"], events)
    write_csv(take / "draft" / "coverage.csv", TABLES["coverage.csv"], coverage)
    marker.write_text("manual_count owns draft/events.csv and draft/coverage.csv\n", encoding="utf-8")
    return export_revision(take, reviewer, note, bin_seconds, lines=_lines_config(manifest, site_id))
