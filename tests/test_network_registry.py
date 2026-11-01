import json
from pathlib import Path

import pytest

from simulation.network_registry import engine_for_scenario, load_registered_network, registered_networks
from simulation.road_network import load_network


def test_registry_loads_default_and_sites():
    assert load_registered_network(None).fingerprint == load_network().fingerprint
    assert [item["id"] for item in registered_networks()] == ["tagum_network", "tagum_site_a", "tagum_site_b"]
    assert load_registered_network("tagum_site_a").id == "tagum_site_a"
    assert load_registered_network("tagum_site_b").id == "tagum_site_b"


def test_unknown_network_is_refused():
    with pytest.raises(ValueError, match="Unknown network 'nowhere'"):
        load_registered_network("nowhere")


def test_registry_id_must_match_file(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data/networks/tagum_site_a.json"
    (tmp_path / "site.json").write_bytes(source.read_bytes())
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"networks": [{"id": "wrong", "file": "site.json"}]}))
    with pytest.raises(ValueError, match="has id 'tagum_site_a', not 'wrong'"):
        load_registered_network("wrong", registry_path=registry)


def test_scenario_engine_uses_site_network():
    engine = engine_for_scenario({"network_id": "tagum_site_a", "engine_config": {}}, seed=101)
    assert engine.network.id == "tagum_site_a"
