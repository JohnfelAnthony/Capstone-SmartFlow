"""One metric network shared by the native engine and both renderers."""
from simulation.road_network import load_network
from services.native_scenario_service import network_display_labels


def load_client_visual_network(network_id: str | None = None) -> dict:
    network = load_network()
    if network_id not in {None, network.id}:
        raise ValueError("Unknown network")
    visual = network.visual()
    _, node_labels = network_display_labels(network)
    visual["junctions"] = [{**junction, "label": node_labels[junction["id"]]}
                           for junction in visual["junctions"]]
    return visual
