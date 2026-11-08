"""One metric network shared by the native engine and both renderers."""
from simulation.network_registry import load_registered_network, load_registered_network_revision
from simulation.road_network import RoadNetwork
from services.native_scenario_service import network_display_labels


def load_client_visual_network(network_id: str | None = None) -> dict:
    return _visual_payload(load_registered_network(network_id))


def load_recorded_visual_network(network_id: str | None, fingerprint: str | None, embedded: dict | None) -> dict:
    if not fingerprint:
        raise ValueError("Recording has no network fingerprint")
    if embedded is not None:
        network = RoadNetwork(embedded)
        if network.fingerprint != fingerprint:
            raise ValueError("Embedded network does not match the recording fingerprint")
    else:
        network = load_registered_network_revision(network_id, fingerprint)
    return _visual_payload(network)


def _visual_payload(network: RoadNetwork) -> dict:
    visual = network.visual()
    _, node_labels = network_display_labels(network)
    visual["junctions"] = [{**junction, "label": node_labels[junction["id"]]}
                           for junction in visual["junctions"]]
    return visual
