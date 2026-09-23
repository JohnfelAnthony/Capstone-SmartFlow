import json
import logging
import gzip
import copy
import math
from pathlib import Path

from simulation.road_network import NETWORK_ID as DEFAULT_INTERSECTION_ID

logger = logging.getLogger(__name__)

class TimelinePlaybackEngine:
    """A duck-typed simulation engine that plays back a pre-recorded JSONL timeline."""
    
    def __init__(self, run_id: int, timeline_path: str | None = None):
        self.run_id = run_id
        self.timeline_path = self._resolve_timeline_path(run_id, timeline_path)
        self.manifest_path = self.timeline_path.with_suffix(".manifest.json") if self.timeline_path.suffix == ".jsonl" else Path(str(self.timeline_path).replace(".jsonl.gz", ".manifest.json"))
        self.status = "stopped"
        self.last_error = "None"
        self.last_action = "Idle"
        self.control_mode_label = "Playback Mode"
        self.controller_type = "playback"
        self.controller_provenance = "recorded-playback"
        self.controller_provenance_label = "Recorded Playback"
        self.source_controller_provenance = "unknown"
        self.current_scenario_name = "Recorded Scenario"
        self.intersection_id = DEFAULT_INTERSECTION_ID
        self.traffic_density = "low"
        self.pedestrian_density = "low"
        self.emergency_mode = "disabled"
        self.road_constraint = "None"
        self.seed = 42
        self.simulation_time = 0.0
        self.phase = "ALL_RED"
        self.phase_remaining = 0.0
        self.cycle_count = 0
        self.events = []
        self.step_length = 0.1
        
        self._frames = []
        self._current_frame_idx = 0
        self.duration_limit = 300
        
        manifest = self._load_manifest()
        from simulation.traffic_engine import ENGINE_VERSION
        from simulation.road_network import load_network
        experiment = manifest.get("experiment", {})
        experiment = experiment if isinstance(experiment, dict) else {}
        if experiment.get("engine_version") != ENGINE_VERSION or experiment.get("network_sha256") != load_network().fingerprint:
            self.status = "error"
            self.last_error = "Recording is incompatible with the current native engine/network; generate a new recording."
            return
        controller = manifest.get("controller", {}) if isinstance(manifest, dict) else {}
        if controller:
            self.source_controller_provenance = str(
                controller.get("provenance") or self.source_controller_provenance
            )
        if self.timeline_path.exists():
            try:
                opener = gzip.open if self.timeline_path.suffix == ".gz" else open
                with opener(self.timeline_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            frame = json.loads(line)
                            if not isinstance(frame, dict) or frame.get("engine_version") != ENGINE_VERSION:
                                raise ValueError("Timeline contains an incompatible frame")
                            time = float(frame["time"])
                            step = float(frame["step_length"])
                            if not math.isfinite(time) or not math.isfinite(step) or step <= 0:
                                raise ValueError("Timeline contains invalid time/step values")
                            expected = len(self._frames)*step
                            if abs(time-expected) > 1e-6 or (self._frames and step != self._frames[0]["step_length"]):
                                raise ValueError("Timeline frames must be continuous from time zero")
                            self._frames.append(frame)
                timeline = manifest.get("timeline", {})
                if not self._frames or len(self._frames) != timeline.get("frame_count"):
                    raise ValueError("Timeline is empty or its frame count does not match the manifest")
                if self._frames[-1].get("status") != "completed" or abs(self._frames[-1]["time"]-float(timeline["actual_duration_seconds"])) > 1e-6:
                    raise ValueError("Timeline is incomplete or its duration does not match the manifest")
                self.duration_limit = float(timeline["actual_duration_seconds"])
                self.seed = int(experiment["seed"])
                self._hydrate_from_frame(self._frames[0])
            except Exception as e:
                self._frames.clear()
                self.last_error = f"Failed to load timeline: {e}"
                self.status = "error"
        else:
            self.last_error = f"Timeline not found: {self.timeline_path}"
            self.status = "error"

    @staticmethod
    def _resolve_timeline_path(run_id: int, explicit_timeline_path: str | None) -> Path:
        candidates = []
        if explicit_timeline_path:
            candidates.append(Path(explicit_timeline_path))
        candidates.extend([
            Path(f"assets/generated/timelines/run_{run_id}.jsonl"),
            Path(f"assets/generated/timelines/run_{run_id}.jsonl.gz"),
        ])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _load_manifest(self) -> dict:
        try:
            if self.manifest_path.exists():
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                return manifest if isinstance(manifest, dict) else {}
        except Exception as exc:
            logger.warning("Failed to read timeline manifest %s: %s", self.manifest_path, exc)
        return {}

    def configure(self, **kwargs):
        pass
        
    def configure_from_scenario(self, scenario: dict):
        pass

    def _hydrate_from_frame(self, frame: dict):
        scenario = frame.get("scenario", {})
        dashboard = frame.get("dashboard", {})
        self.current_scenario_name = dashboard.get("current_scenario_name") or self.current_scenario_name
        self.intersection_id = scenario.get("intersection_id", self.intersection_id) or self.intersection_id
        self.traffic_density = scenario.get("traffic_density", self.traffic_density)
        self.pedestrian_density = scenario.get("pedestrian_density", self.pedestrian_density)
        self.emergency_mode = scenario.get("emergency_mode", self.emergency_mode)
        self.road_constraint = scenario.get("road_constraint", self.road_constraint)
        self.simulation_time = float(frame.get("time", self.simulation_time) or 0)
        self.phase = frame.get("phase", self.phase)
        self.phase_remaining = float(frame.get("phase_remaining", self.phase_remaining) or 0)
        self.cycle_count = int(frame.get("cycle_count", self.cycle_count) or 0)
        self.step_length = float(frame.get("step_length", self.step_length) or self.step_length)
        self.events = frame.get("events", [])

    def start(self, duration_limit: int = 300):
        if not self._frames:
            self.status = "error"
            self.last_error = "No timeline frames to play."
            return
            
        self.duration_limit = duration_limit
        self._current_frame_idx = 0
        self._hydrate_from_frame(self._frames[0])
        self.status = "running"
        self.last_action = "Started Playback"
        
    def pause(self):
        if self.status == "running":
            self.status = "paused"
            self.last_action = "Playback paused"
            
    def resume(self):
        if self.status == "paused":
            self.status = "running"
            self.last_action = "Playback resumed"
            
    def stop(self):
        self.status = "stopped"
        self.last_action = "Playback stopped"

    def seek(self, frame_index: int):
        if not self._frames:
            return
        clamped_index = max(0, min(int(frame_index or 0), len(self._frames) - 1))
        self._current_frame_idx = clamped_index
        if self.status in {"completed", "stopped"}:
            self.status = "paused"
        self.last_action = f"Seeked to frame {clamped_index + 1} of {len(self._frames)}"
        self._hydrate_from_frame(self._frames[self._current_frame_idx])
        
    def step(self, num_ticks: int = 1):
        if isinstance(num_ticks, bool) or not isinstance(num_ticks, int) or num_ticks < 0:
            raise ValueError("Tick count must be non-negative")
        if self.status != "running":
            return
            
        self._current_frame_idx += num_ticks
        if self._current_frame_idx >= len(self._frames)-1:
            # Reached end of playback
            self._current_frame_idx = max(0, len(self._frames) - 1)
            self.status = "completed"
            self.last_action = "Playback completed"
        else:
            self.last_action = "Playback advancing"
        self._hydrate_from_frame(self._frames[self._current_frame_idx])

    def _frame_state(self) -> dict:
        if not self._frames:
            return self.to_dict()

        idx = min(self._current_frame_idx, len(self._frames) - 1)
        frame = self._frames[idx]
        state = copy.deepcopy(frame)
        self._hydrate_from_frame(state)
        state["status"] = self.status
        state["playback"] = {
            "frame_index": idx,
            "frame_count": len(self._frames),
            "progress_percent": int((idx / max(1, len(self._frames) - 1)) * 100),
        }
        dashboard = dict(frame.get("dashboard", {}))
        state["dashboard"] = dashboard
        dashboard["last_action"] = self.last_action
        dashboard["last_error"] = self.last_error
        dashboard["control_mode_label"] = self.control_mode_label
        dashboard["controller_provenance"] = self.controller_provenance
        dashboard["controller_provenance_label"] = self.controller_provenance_label
        dashboard["source_controller_provenance"] = self.source_controller_provenance
        dashboard["run_id"] = self.run_id
        dashboard["playback_frame_index"] = idx
        dashboard["playback_frame_count"] = len(self._frames)
        return state
            
    def get_state(self) -> dict:
        return self._frame_state()

    def to_dict(self) -> dict:
        if self._frames:
            return self._frame_state()
        return {
            "time": 0,
            "step_length": self.step_length,
            "status": self.status,
            "phase": self.phase,
            "phase_remaining": self.phase_remaining,
            "cycle_count": self.cycle_count,
            "controller_type": self.controller_type,
            "vehicles": [],
            "vehicle_count": 0,
            "pedestrians": [],
            "pedestrian_count": 0,
            "queues": {},
            "events": [],
            "scenario": {
                "intersection_id": self.intersection_id,
                "traffic_density": self.traffic_density,
                "pedestrian_density": self.pedestrian_density,
                "emergency_mode": self.emergency_mode,
                "road_constraint": self.road_constraint,
            },
            "dashboard": {
                "last_error": self.last_error,
                "last_action": self.last_action,
                "control_mode_label": self.control_mode_label,
                "controller_provenance": self.controller_provenance,
                "controller_provenance_label": self.controller_provenance_label,
                "source_controller_provenance": self.source_controller_provenance,
                "current_scenario_name": self.current_scenario_name,
                "run_id": self.run_id,
            },
            "metrics": {},
            "charts": {},
            "visual": {},
            "traffic_lights": {},
            "playback": {
                "frame_index": 0,
                "frame_count": 0,
                "progress_percent": 0,
            },
        }
