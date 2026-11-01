"""Signalized and all-way-stop behaviour stays what `native-6` released (and `native-7` keeps).

The digests were recorded from the pre-two-site code (commit 51880ab). A change here means existing runs and
models would behave differently under the same engine label, so it needs the coordinated `native-7` bump.
"""
import pytest

from simulation.footprints import state_digest
from tests.mixed_traffic_helpers import busy_engine, junction_network

PRE_TWO_SITE_DIGESTS = {
    ("signalized", 101): "c20b1bbea8e1f66e",
    ("all_way_stop", 101): "b7911d0d197d562b",
}


@pytest.mark.parametrize("mode, seed", PRE_TWO_SITE_DIGESTS)
def test_existing_junction_modes_match_the_native_6_release(mode, seed):
    plans = {} if mode == "signalized" else {"signal_plans": {"j": {"mode": mode}}}
    engine = busy_engine(junction_network(), seed=seed, density="medium", **plans)
    assert state_digest(engine, 400.0)[:16] == PRE_TWO_SITE_DIGESTS[(mode, seed)]
