"""Provisional Tagum vehicle mix: defaults, presets and what a mix may change."""
import json
from pathlib import Path

from services.native_scenario_service import configuration_options
from simulation.demand import build_schedule
from simulation.road_network import RoadNetwork
from simulation.scenario_config import CARS_ONLY_MIX, DEFAULTS, TAGUM_PROVISIONAL_MIX, validate_config
from simulation.traffic_engine import TrafficEngine

NETWORK_2J = Path(__file__).resolve().parents[1]/"data"/"networks"/"tagum_network_2j.json"


def test_new_scenarios_default_to_the_tagum_provisional_mix():
    assert DEFAULTS["vehicle_mix"] == TAGUM_PROVISIONAL_MIX == {"motorcycle": .55, "tricycle": .25, "car": .15, "truck": .03, "bus": .02}


def test_mix_changes_classes_but_not_arrival_times_or_routes():
    network = RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8")))
    schedules = [build_schedule(validate_config(DEFAULTS, {"traffic_density": "medium", "vehicle_mix": mix}, network), network, 101, 3600)
                 for mix in (CARS_ONLY_MIX, TAGUM_PROVISIONAL_MIX)]
    cars, tagum = schedules
    assert [(a.time, a.source, a.destination) for a in cars] == [(a.time, a.source, a.destination) for a in tagum]
    assert abs(sum(a.vehicle_type == "motorcycle" for a in tagum)/len(tagum)-0.55) < 0.05


def test_options_offer_both_presets():
    presets = configuration_options()["vehicle_mix_presets"]
    assert presets["tagum_provisional"]["mix"] == TAGUM_PROVISIONAL_MIX and presets["cars_only"]["mix"] == CARS_ONLY_MIX
    assert presets["tagum_provisional"]["label"] == "Tagum (provisional)" and presets["cars_only"]["label"] == "Cars only"


def test_a_saved_custom_mix_is_kept():
    engine = TrafficEngine(seed=1)
    engine.configure(vehicle_mix={"car": 65, "motorcycle": 15, "tricycle": 10, "bus": 5, "truck": 5})
    assert engine.config["vehicle_mix"] == {"car": 65.0, "motorcycle": 15.0, "tricycle": 10.0, "bus": 5.0, "truck": 5.0}
