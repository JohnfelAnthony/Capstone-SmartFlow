"""CSV headers and explicitly synthetic examples for the loaded network."""
import csv
import io

from services.observed_data_import import SCHEMAS
from simulation.road_network import load_network


def observation_template(kind: str, *, example: bool = False, network=None) -> dict:
    if kind not in SCHEMAS:
        raise ValueError("Choose trips, od_counts, turn_counts, or pedestrian_counts.")
    network = network or load_network()
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SCHEMAS[kind], lineterminator="\n")
    writer.writeheader()
    if example:
        row = _example(kind, network)
        writer.writerow(row)
    label = "synthetic_example" if example else "blank_template"
    return {"filename": f"smartflow_{kind}_{label}.csv", "csv_text": stream.getvalue(),
            "network_id": network.id, "network_sha256": network.fingerprint, "synthetic_example": example}


def _example(kind, network):
    if kind == "pedestrian_counts":
        return {"start_s": 0, "end_s": 60, "junction": network.intersections[0], "count": 2}
    for source in sorted(network.boundaries):
        for destination in sorted(network.boundaries):
            if source == destination:
                continue
            route = network.route(source, destination)
            if not route:
                continue
            if kind == "trips":
                return {"time_s": 1, "source": source, "destination": destination, "vehicle_type": "car"}
            row = {"start_s": 0, "end_s": 60, "source": source, "destination": destination, "count": 2}
            if kind == "od_counts":
                return row
            for incoming, outgoing in zip(route, route[1:]):
                junction = network.lanes[incoming].target
                valid_turn = (junction in network.intersections and network.lanes[outgoing].source == junction
                              and network.turn_allowed(incoming, outgoing))
                if valid_turn:
                    return {**row, "junction": junction, "from_lane": incoming, "to_lane": outgoing}
    raise ValueError("The loaded network has no connected example for this schema. Download a blank template and supply valid network IDs.")
