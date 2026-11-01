"""Resolve saved scenario network identifiers to provisional or default networks."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from simulation.road_network import NETWORK_PATH, RoadNetwork, load_network

REGISTRY_PATH = Path(os.environ.get("SMARTFLOW_NETWORK_REGISTRY_PATH") or
                     Path(__file__).resolve().parents[1] / "data/networks/registry.json")


def _entries(registry_path: Path) -> list[dict]:
    raw = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    entries = raw.get("networks")
    if not isinstance(entries, list):
        raise ValueError("Network registry requires a networks list")
    ids = [entry.get("id") for entry in entries]
    if any(not isinstance(item, str) or not item or item == "tagum_network" for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Network registry ids must be unique and cannot replace the default")
    return entries


@lru_cache(maxsize=32)
def _load_file(path: Path, mtime_ns: int, size: int) -> RoadNetwork:
    return RoadNetwork(json.loads(path.read_text(encoding="utf-8")))


def load_registered_network(network_id: str | None = None, *, registry_path: Path = REGISTRY_PATH) -> RoadNetwork:
    active = load_network()
    if network_id in (None, "tagum_network", active.id):
        return active
    registry_path = Path(registry_path).resolve()
    entry = next((entry for entry in _entries(registry_path) if entry["id"] == network_id), None)
    if entry is None:
        raise ValueError(f"Unknown network '{network_id}'")
    file = entry.get("file")
    if not isinstance(file, str) or Path(file).name != file:
        raise ValueError("Registry network files must be filenames in the registry directory")
    path = registry_path.parent / file
    stat = path.stat()
    network = _load_file(path, stat.st_mtime_ns, stat.st_size)
    if network.id != network_id:
        raise ValueError(f"Registry file {file} has id '{network.id}', not '{network_id}'")
    return network


def registered_networks(registry_path: Path = REGISTRY_PATH) -> list[dict]:
    default = load_network()
    result = [{"id": default.id, "name": default.payload.get("name", default.id), "file": str(NETWORK_PATH),
               "sha256": default.fingerprint, "junctions": len(default.intersections)}]
    for entry in _entries(registry_path):
        network = load_registered_network(entry["id"], registry_path=registry_path)
        result.append({"id": network.id, "name": network.payload.get("name", network.id), "file": entry["file"],
                       "sha256": network.fingerprint, "junctions": len(network.intersections)})
    return result


def engine_for_scenario(scenario: dict, *, seed: int | None = 42, registry_path: Path = REGISTRY_PATH):
    from simulation.traffic_engine import TrafficEngine

    engine = TrafficEngine(seed=seed, network=load_registered_network(scenario.get("network_id"), registry_path=registry_path))
    engine.configure_from_scenario(scenario)
    return engine
