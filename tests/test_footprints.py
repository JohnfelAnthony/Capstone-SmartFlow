"""Footprint geometry and run fingerprints used by the mixed-traffic checks."""
import itertools
import json
import math
import random
from pathlib import Path

from simulation.footprints import longitudinal_digest, overlapping_pairs, record_rectangle, rectangle, rectangles_overlap, state_digest
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine

NETWORK_2J = Path(__file__).resolve().parents[1]/"data"/"networks"/"tagum_network_2j.json"


def test_side_by_side_rectangles_with_a_gap_do_not_overlap():
    assert not rectangles_overlap(rectangle(0, 0, 0.0, 4.5, 1.8), rectangle(0, -1.6, 0.0, 2.0, 0.8))


def test_rectangles_overlapping_by_ten_centimetres_are_detected():
    assert rectangles_overlap(rectangle(0, 0, 0.0, 4.5, 1.8), rectangle(4.4, 0, 0.0, 4.5, 1.8))


def test_rotated_rectangles_use_true_geometry():
    assert not rectangles_overlap(rectangle(0, 0, 0.0, 4.5, 1.8), rectangle(0, 3.35, math.pi/2, 4.5, 1.8))


def test_overlapping_pairs_reads_engine_records():
    records = [{"id": "a", "x": 0, "y": 0, "angle": 90, "length": 4.5, "width": 1.8},
               {"id": "b", "x": 1, "y": 0, "angle": 90, "length": 4.5, "width": 1.8},
               {"id": "c", "x": 50, "y": 0, "angle": 90, "length": 4.5, "width": 1.8}]
    assert overlapping_pairs(records) == [("a", "b")]


def test_overlapping_pairs_matches_a_full_pairwise_check():
    rng = random.Random(3)
    records = [{"id": f"v{index}", "x": rng.uniform(0, 60), "y": rng.uniform(0, 60), "angle": rng.uniform(0, 360),
                "length": rng.uniform(2, 10), "width": rng.uniform(0.8, 2.5)} for index in range(200)]
    expected = sorted(tuple(sorted((a["id"], b["id"]))) for a, b in itertools.combinations(records, 2)
                      if rectangles_overlap(record_rectangle(a), record_rectangle(b)))
    assert expected and overlapping_pairs(records) == expected


def test_only_the_state_digest_sees_sideways_state():
    network = RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8")))
    engines = []
    for _ in range(2):
        engine = TrafficEngine(seed=101, network=network)
        engine.configure(traffic_density="medium", vehicle_mix={"car": 1.0})
        engine.start(600)
        engine.step(100)
        engines.append(engine)
    a, b = engines
    assert b.vehicles
    setattr(next(iter(b.vehicles.values())), "lateral", 0.5)
    t = a.simulation_time
    assert state_digest(a, t) != state_digest(b, t)
    assert longitudinal_digest(a, t) == longitudinal_digest(b, t)
