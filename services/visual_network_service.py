"""One metric network shared by the native engine and both renderers."""
from simulation.road_network import NETWORK_ID, load_network


def load_client_visual_network(intersection_id: str | None = None) -> dict:
    network = load_network()
    legacy_ids = {"tagum_1", "tagum_2", "tagum_3"} if network.id == NETWORK_ID else set()
    if intersection_id not in {None, network.id, *legacy_ids}:
        raise ValueError("Unknown network")
    return network.visual()
