"""Recorded signal evidence. Never infer a learned controller's fixed cycle."""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from statistics import mean
from pathlib import Path


def summarize_signals(frames, *, step: float, start: float, end: float, junction_id: str | None = None) -> dict:
    segments = []
    first_control = None
    previous = None
    found_junction = junction_id
    for frame in frames:
        time = float(frame.get("time", 0))
        controls = frame.get("junction_controls") or {}
        if not found_junction:
            found_junction = next((key for key, value in controls.items() if value.get("selected_for_rl")), None)
        control = controls.get(found_junction, {})
        if first_control is None and control:
            first_control = dict(control)
        if time < start:
            previous = (time, control)
            continue
        if previous is not None:
            prev_time, prev_control = previous
            a, b = max(start, prev_time), min(end, time)
            if b > a:
                gap = time - prev_time > max(step * 1.5, 0.001)
                phase = str(prev_control.get("phase", "Unavailable"))
                stage = str(prev_control.get("stage", "unknown"))
                if gap or not prev_control:
                    phase, stage = "Unavailable", "unknown"
                elif prev_control.get("mode") != "signalized":
                    phase, stage = "No signal", "unsignalized"
                segment = {"start": a, "end": b, "phase": phase, "stage": stage}
                if segments and segments[-1]["phase"] == phase and segments[-1]["stage"] == stage and abs(segments[-1]["end"] - a) < 1e-6:
                    segments[-1]["end"] = b
                else:
                    segments.append(segment)
        previous = (time, control)
        if time >= end:
            break
    # Missing leading/trailing coverage is shown explicitly, never painted as green.
    if not segments:
        segments = [{"start": start, "end": end, "phase": "Unavailable", "stage": "unknown"}]
    else:
        if segments[0]["start"] > start:
            segments.insert(0, {"start": start, "end": segments[0]["start"], "phase": "Unavailable", "stage": "unknown"})
        if segments[-1]["end"] < end:
            segments.append({"start": segments[-1]["end"], "end": end, "phase": "Unavailable", "stage": "unknown"})
    summaries = []
    for phase in dict.fromkeys(s["phase"] for s in segments if s["stage"] in {"green", "walk", "pedestrian"}):
        runs = []
        total = 0.0
        for i, segment in enumerate(segments):
            if segment["phase"] != phase:
                continue
            duration = segment["end"] - segment["start"]
            total += duration
            # A whole green must have both transitions recorded, with no adjacent recording gap.
            if 0 < i < len(segments) - 1 and segments[i-1]["stage"] != "unknown" and segments[i+1]["stage"] != "unknown":
                runs.append(duration)
        summaries.append({"phase": phase, "total_seconds": round(total, 3), "complete_count": len(runs),
                          "mean_seconds": round(mean(runs), 3) if runs else None,
                          "min_seconds": round(min(runs), 3) if runs else None,
                          "max_seconds": round(max(runs), 3) if runs else None})
    return {"junction_id": found_junction, "start": start, "end": end, "step_seconds": step,
            "settings": first_control or {}, "segments": segments, "phases": summaries,
            "unavailable_seconds": round(sum(s["end"] - s["start"] for s in segments if s["stage"] == "unknown"), 3)}


_TOP_LEVEL_TIME = re.compile(r'^\{[^{\[]*?"time":\s*(-?[0-9][0-9.eE+-]*)\s*[,}]')
_CONTROLS_KEY = re.compile(r'"junction_controls":\s*')
_DECODER = json.JSONDecoder()


def _signal_fields(line: str) -> dict:
    """Parse only a frame's time and junction_controls; parsing every vehicle is most of the cost."""
    time_match = _TOP_LEVEL_TIME.match(line)
    controls_matches = list(_CONTROLS_KEY.finditer(line))
    if time_match is None or len(controls_matches) != 1:
        return json.loads(line)  # anything unusual: the full parse decides
    controls, _ = _DECODER.raw_decode(line, controls_matches[0].end())
    return {"time": float(time_match.group(1)), "junction_controls": controls}


@lru_cache(maxsize=4)
def _read_signals(path: str, mtime_ns: int, size: int, step: float, start: float, end: float, junction_id: str | None) -> dict:
    # Cache only small phase segments/statistics; vehicle frames are streamed then discarded.
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return summarize_signals((_signal_fields(line) for line in stream if line.strip()),
                                 step=step, start=start, end=end, junction_id=junction_id)


def recorded_signals(path: Path, *, step: float, start: float, end: float, junction_id: str | None) -> dict:
    stat = path.stat()
    return _read_signals(str(path.resolve()), stat.st_mtime_ns, stat.st_size, step, start, end, junction_id)
