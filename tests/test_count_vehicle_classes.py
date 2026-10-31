import pytest

from services import observed_data_import as importer
from services.observation_identity import normalized_observation_identity
from simulation.road_network import load_network


def test_count_import_preserves_class_and_legacy_car_default(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "IMPORT_DIRECTORY", tmp_path)
    network = load_network()
    source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                               if a != b and network.route(a, b))
    header = "start_s,end_s,source,destination,count"
    row = f"0,10,{source},{destination},2"
    options = dict(kind="od_counts", source_description="Synthetic class test", collected_on="2026-01-01")
    legacy = importer.import_observations(csv_text=f"{header}\n{row}\n", **options)
    buses = importer.import_observations(csv_text=f"{header},vehicle_type\n{row},bus\n", **options)
    assert [trip["vehicle_type"] for trip in legacy["engine_config"]["trips"]] == ["car", "car"]
    assert [trip["vehicle_type"] for trip in buses["engine_config"]["trips"]] == ["bus", "bus"]
    assert normalized_observation_identity("od_counts", f"{header}\n{row}\n")["normalized_sha256"] == \
        normalized_observation_identity("od_counts", f"{header},vehicle_type\n{row},car\n")["normalized_sha256"]
    route = network.route(source, destination)
    from_lane, to_lane = next((a, b) for a, b in zip(route, route[1:])
                              if network.lanes[a].target in network.intersections)
    junction = network.lanes[from_lane].target
    turns = ("start_s,end_s,source,destination,junction,from_lane,to_lane,count,vehicle_type\n"
             f"0,10,{source},{destination},{junction},{from_lane},{to_lane},2,truck\n")
    result = importer.import_observations(csv_text=turns, **{**options, "kind": "turn_counts"})
    assert [trip["vehicle_type"] for trip in result["engine_config"]["trips"]] == ["truck", "truck"]
    with pytest.raises(ValueError, match="vehicle_type is not supported"):
        importer.import_observations(csv_text=f"{header},vehicle_type\n{row},pedicab\n", **options)
