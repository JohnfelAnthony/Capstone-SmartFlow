import json
from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork

NETWORKS = Path(__file__).resolve().parents[1] / "data" / "networks"


@pytest.mark.parametrize("filename,network_id,streets", [
    ("tagum_site_a.json", "tagum_site_a", {"Capitol Circumferential Road", "Dalisay Gante Road"}),
    ("tagum_site_b.json", "tagum_site_b", {"Davao-Agusan National Highway", "Sobrecarey Street", "Dao Street"}),
])
def test_site_network_has_a_study_junction_with_four_approaches(filename, network_id, streets):
    payload = json.loads((NETWORKS / filename).read_text(encoding="utf-8"))
    network = RoadNetwork(payload)
    assert network.id == network_id
    assert len(network.intersections) == (10 if network_id == "tagum_site_b" else 13)  # the study junction first, then the street grid: Site A around the public market (D41), Site B the owner's painted streets and the neighbouring junction (D45)
    assert sorted(network.lanes[lane].approach for lane in network.incoming[network.intersections[0]]) == ["east", "north", "south", "west"]
    assert streets <= {road["name"] for road in payload["roads"]}
    assert payload["source"]["provider"] == "OpenStreetMap"
    assert any("field" in text.lower() for text in payload["source"]["assumptions"])
