"""One cached metric network shared by the native engine and both renderers."""
from simulation.road_network import NETWORK_ID, load_network


def load_client_visual_network(intersection_id: str | None = None) -> dict:
    if intersection_id not in {None, NETWORK_ID, "tagum_1", "tagum_2", "tagum_3"}:
        raise ValueError("Unknown network")
    return load_network().visual()
