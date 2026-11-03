"""Atomic resource mechanics only; these are not traffic-engine tests."""
import itertools
import json
from pathlib import Path
import pytest

from tools.compound_junction_prototype import AtomicClusterReservations, Readiness, route_clusters


READY = Readiness(True, True, True, True)


def test_candidate_route_plans_two_clusters_with_explicit_intermediate_exit():
    path = Path(__file__).resolve().parents[1] / "docs/reports/site-b-frontage-graph-unvalidated.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    route = ["road0_outerr", "road0r", "road3f", "road7f", "road7_outerf"]
    plans = route_clusters(payload, route)
    assert len(plans) == 2
    assert set(plans[0]["junctions"]) == {"frontage_study_left", "frontage_study_right", "tagum_site_b_j"}
    assert plans[0]["entry_lane"] == "road0_outerr" and plans[0]["internal_lanes"] == ["road0r"]
    assert plans[0]["exit_lane"] == plans[1]["entry_lane"] == "road3f"
    assert plans[1]["internal_lanes"] == ["road7f"] and plans[1]["exit_lane"] == "road7_outerf"
    with pytest.raises(ValueError, match="exit lane"):
        route_clusters(payload, route[:2])
    with pytest.raises(ValueError, match="connected"):
        route_clusters(payload, ["road0_outerr", "road7f"])
    with pytest.raises(ValueError, match="unavailable"):
        route_clusters(payload, ["frontage_right_0r"])


def test_candidate_route_rejects_prohibited_turns_and_uturns():
    path = Path(__file__).resolve().parents[1] / "docs/reports/site-b-frontage-graph-unvalidated.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    route = ["road0_outerr", "road0r", "road3f", "road7f", "road7_outerf"]
    payload["prohibited_turns"] = [["road0r", "road3f"]]
    with pytest.raises(ValueError, match="prohibited turn"):
        route_clusters(payload, route)
    payload["prohibited_turns"] = []
    with pytest.raises(ValueError, match="prohibited turn"):
        route_clusters(payload, ["road0_outerf", "road0_outerr"])
    payload["prohibited_turns"] = [["road0r"]]
    with pytest.raises(ValueError, match="Invalid turn restrictions"):
        route_clusters(payload, route)


@pytest.mark.parametrize("checks", [bits for bits in itertools.product((False, True), repeat=4) if not all(bits)])
def test_denied_readiness_reserves_nothing(checks):
    leases = AtomicClusterReservations()
    assert not leases.acquire("car", ("j1", "j2"), "exit", Readiness(*checks))
    assert leases.owner("junction", "j1") is None
    assert leases.owner("junction", "j2") is None
    assert leases.owner("exit", "exit") is None


def test_opposing_requests_are_atomic_and_exit_stays_held_until_rear_clear():
    leases = AtomicClusterReservations()
    assert leases.acquire("bus", ("j1", "j2"), "out", READY)
    assert not leases.acquire("car", ("j2", "j1"), "other", READY)
    assert leases.owner("exit", "other") is None
    assert not leases.release("bus", rear_clear=False)
    assert leases.owner("junction", "j1") == "bus"
    assert leases.release("bus", rear_clear=True)
    assert leases.acquire("car", ("j2", "j1"), "other", READY)


def test_shared_exit_conflicts_without_partially_reserving_new_junction():
    leases = AtomicClusterReservations()
    assert leases.acquire("first", ("a",), "shared", READY)
    assert not leases.acquire("second", ("b",), "shared", READY)
    assert leases.owner("junction", "b") is None
    assert leases.acquire("third", ("b",), "free", READY)
    with pytest.raises(ValueError, match="extended"):
        leases.acquire("first", ("a", "b"), "shared", READY)
    assert not leases.release("missing", rear_clear=True)


def test_invalid_and_ambiguous_inputs_are_rejected():
    leases = AtomicClusterReservations()
    with pytest.raises(ValueError):
        Readiness(True, True, True, None)
    with pytest.raises(ValueError):
        leases.acquire("car", ("j", "j"), "out", READY)
    with pytest.raises(ValueError):
        leases.release("car", rear_clear=1)
