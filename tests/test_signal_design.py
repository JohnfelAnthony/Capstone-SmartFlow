import pytest

from simulation.signal_design import flows_from_counts, plan_from_result, saturation_from_network, webster_plan

SAT = dict.fromkeys(("north", "south", "east", "west"), 1800)
PHASES = [["north", "south"], ["east", "west"]]


def test_two_phase_worked_example():
    result = webster_plan(PHASES, {"north": 900, "south": 720, "east": 540, "west": 450}, SAT)
    assert (result.cycle_seconds, result.phase_greens, result.lost_time_seconds) == (70, [39, 23], 6)


def test_walk_phase_worked_example():
    result = webster_plan([*PHASES, "pedestrian"], {"north": 540, "south": 450, "east": 360, "west": 270}, SAT, pedestrian_green_seconds=10)
    assert (result.cycle_seconds, result.phase_greens, result.lost_time_seconds) == (61, [25.4, 16.6, 10], 17)


def test_oversaturation_and_bad_input_are_refused():
    with pytest.raises(ValueError, match="Total flow ratio Y must be below 1"):
        webster_plan(PHASES, {"north": 1170, "south": 0, "east": 720, "west": 0}, SAT)
    with pytest.raises(ValueError):
        webster_plan(PHASES, {"north": -1}, SAT)
    with pytest.raises(ValueError, match="belong to a vehicle phase"):
        webster_plan(PHASES, {"north": 10, "typo": 50}, SAT)


def test_zero_demand_and_green_clamps_are_reported():
    result = webster_plan([*PHASES, "pedestrian"], dict.fromkeys(SAT, 0), SAT, pedestrian_green_seconds=10)
    assert result.cycle_seconds == 39 and result.phase_greens == [10, 10, 10]
    assert "No vehicle demand; every phase gets its minimum green" in result.warnings
    result = webster_plan(PHASES, {"north": 1440, "south": 0, "east": 90, "west": 0}, SAT)
    assert result.webster_cycle_seconds == 94 and result.cycle_seconds == 78 and result.phase_greens == [60, 10]


def test_flows_apply_provisional_class_factors():
    assert flows_from_counts({"north": {"car": 100, "motorcycle": 200, "bus": 10}}) == {"north": 220}


def test_plans_require_walk_and_check_vehicle_maximum_red():
    result = webster_plan(PHASES, dict.fromkeys(SAT, 90), SAT)
    with pytest.raises(ValueError, match="needs a walk phase"):
        plan_from_result(result, {})
    result = webster_plan([*PHASES, "pedestrian"], {"north": 540, "south": 450, "east": 360, "west": 270}, SAT, pedestrian_green_seconds=10)
    with pytest.raises(ValueError, match="shorter than this plan's own fixed-time red"):
        plan_from_result(result, {"maximum_red_seconds": 40})
    assert plan_from_result(result, {})["phase_greens"] == [25.4, 16.6, 10]


def test_saturation_is_based_on_approach_width():
    from tests.mixed_traffic_helpers import junction_network
    network = junction_network()
    expected = {network.lanes[lane].approach: network.lanes[lane].width / 3.3 * 1800
                for lane in network.incoming["j"]}
    assert saturation_from_network(network, "j") == expected


def test_cli_calculates_provisional_site_plan(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    counts = tmp_path / "counts.json"
    counts.write_text(json.dumps({"north": {"car": 100}}), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "tools/design_signal_plan.py", "--network-id", "tagum_site_a",
                             "--counts", str(counts)], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["network_id"] == "tagum_site_a"
    assert output["result"]["assumptions"]["provisional"] is True
    assert "pedestrian" in output["plan"]["phase_order"]
