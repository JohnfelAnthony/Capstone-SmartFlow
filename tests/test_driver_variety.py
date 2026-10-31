"""Class driving parameters and seeded per-vehicle driver variety."""
import random
import statistics

from simulation.mixed_traffic import CLASS_DRIVING, DriverProfile, DrivingParameters, sample_driver
from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import fill_queue, hold_green, junction_network, started_engine


def test_class_table_matches_the_design():
    assert CLASS_DRIVING == {
        "car": DrivingParameters(1.2, 2.0, 1.5, 0.5), "motorcycle": DrivingParameters(0.8, 1.0, 2.0, 1.0),
        "tricycle": DrivingParameters(1.2, 1.5, 1.0, 0.6), "bus": DrivingParameters(1.5, 2.5, 0.8, 0.3),
        "truck": DrivingParameters(1.5, 2.5, 0.8, 0.3)}


def test_scale_zero_gives_the_class_values():
    assert sample_driver("car", random.Random(1), 0.0) == DriverProfile(1.0, 1.2, 2.0, 1.5, 0.5)


def test_variation_stays_inside_its_bounds():
    rng = random.Random(4)
    profiles = [sample_driver("motorcycle", rng, 1.0) for _ in range(2000)]
    assert all(0.8 <= p.speed_multiplier <= 1.2 and 0.56-1e-9 <= p.time_headway <= 1.12+1e-9 for p in profiles)
    assert abs(statistics.fmean(p.speed_multiplier for p in profiles)-1) < 0.01
    assert len({p.time_headway for p in profiles}) > 100


def test_every_draw_uses_exactly_two_gaussians_whatever_the_scale():
    for scale in (0.0, 1.0):
        rng = random.Random(9)
        sample_driver("bus", rng, scale)
        reference = random.Random(9)
        reference.gauss(0, 1), reference.gauss(0, 1)
        assert rng.random() == reference.random()


def tagum_engine(seed, scale=1.0, ticks=600):
    engine = TrafficEngine(seed=seed)
    engine.configure(traffic_density="medium", vehicle_mix=dict(TAGUM_PROVISIONAL_MIX))
    engine.driver_variation_scale = scale
    engine.start(600)
    engine.step(ticks)
    return engine


def test_same_seed_gives_the_same_drivers():
    runs = [sorted((v.id, v.speed_factor, v.time_headway) for v in tagum_engine(5).vehicles.values()) for _ in range(2)]
    assert runs[0] and runs[0] == runs[1]
    assert len({headway for _, _, headway in runs[0]}) > 1


def test_driver_variety_does_not_touch_the_arrival_schedule():
    off, on = tagum_engine(5, scale=0.0, ticks=0), tagum_engine(5, scale=1.0, ticks=0)
    assert off.demand_fingerprint == on.demand_fingerprint and off.arrivals == on.arrivals


def standstill_gaps(engine, vehicles):
    queue = sorted(vehicles, key=lambda vehicle: vehicle.position)
    assert all(vehicle.speed <= 0.1 and vehicle.connector is None for vehicle in queue)
    return [front.position-front.length/2-(rear.position+rear.length/2) for rear, front in zip(queue, queue[1:])]


def test_motorcycles_stand_closer_than_cars():
    gaps = {}
    for vehicle_type in ("motorcycle", "car"):
        engine = started_engine(junction_network())
        hold_green(engine, "j", "north")
        gaps[vehicle_type] = standstill_gaps(engine, fill_queue(engine, ["wf", "er"], vehicle_type, 5))
    assert len(gaps["motorcycle"]) == 4 and all(gap < 1.2 for gap in gaps["motorcycle"]), gaps
    assert len(gaps["car"]) == 4 and all(gap > 1.9 for gap in gaps["car"]), gaps
