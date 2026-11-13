"""Runs with no closure stay identical to what the previous engine (`native-8`) produced for the same seed.

The digests were recorded from commit c42ba78 before the closure work and re-run on `native-9` and `native-10`; they match. A change here
means traffic changed without a closure, which needs its own engine bump. The single-junction Site A is the kept copy under
data/networks/history, because the installed Site A now has the West-North loop. Seed 101, 120 s, provisional Tagum mix.

The two no-signal rows were re-pinned on 2026-11-12 for the negotiated no-signal rule at the study junction (owner-approved
design, docs/superpowers/specs/2026-11-12-negotiated-no-signal-design.md). It changes only no-signal runs and is recorded in each
run's control metadata (`no_signal_behaviour`), so the engine version and the RL contract stay `native-14`; the fixed-time and
routing rows are unchanged. On 2026-11-13 the conservative rule was made explicit (a vehicle not yet inside crosses every path) and the
entry check was made faster with the same answers; both rows still match their 2026-11-12 values.
"""
import json
from pathlib import Path

import pytest

from simulation.footprints import state_digest
from simulation.road_network import RoadNetwork
from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
from simulation.traffic_engine import TrafficEngine

NETWORKS = Path(__file__).resolve().parents[1]/"data"/"networks"
NATIVE_8_DIGESTS = {
    ("history/tagum_site_a_single_junction.json", "high", "fixed"): "56bcd0fa913f644f",
    ("history/tagum_site_a_single_junction.json", "high", "nosignal"): "254208f195862e6e",
    ("tagum_site_b_pre_sobrecarey_access.json", "high", "fixed"): "dbe1d481cfbb4884",
    ("tagum_site_b_pre_sobrecarey_access.json", "high", "nosignal"): "49c8171ac9835016",
    ("tagum_network.json", "medium", "fixed"): "3fe956f18578a291",
    ("tagum_network.json", "medium", "static"): "7209b4f79c0c88d2",
}


@pytest.mark.parametrize("filename, density, control", NATIVE_8_DIGESTS)
def test_traffic_without_closures_matches_native_8(filename, density, control):
    network = RoadNetwork(json.loads((NETWORKS/filename).read_text(encoding="utf-8")))
    engine = TrafficEngine(seed=101, network=network)
    engine.configure(traffic_density=density, pedestrian_density="low", vehicle_mix=TAGUM_PROVISIONAL_MIX,
                     **({"routing_mode": "static"} if control == "static" else {}))
    if control == "nosignal":
        engine.enable_no_signal_control()
    engine.start(120)
    assert state_digest(engine, 120.0)[:16] == NATIVE_8_DIGESTS[(filename, density, control)]
