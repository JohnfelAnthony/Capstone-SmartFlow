from services.field_observer_import import site_mapping_template
from simulation.network_registry import load_registered_network


def test_mapping_template_lists_boundary_roads_without_inventing_field_data():
    network = load_registered_network("tagum_site_a")
    template = site_mapping_template(network)
    assert template["network_id"] == network.id
    assert template["network_sha256"] == network.fingerprint
    assert {item["boundary"] for item in template["boundaries"]} == set(network.boundaries)
    assert all(item["road_name"] and item["length_m"] > 0 for item in template["boundaries"])
    assert template["locations"] == {}
    assert template["lead_out_s"] is None
    assert "tricycle/pedicab" not in template["class_map"]
