"""How traffic may respond to a closed road, and which responses really work for a given selection (the real routing check).

Responses, stored per closed lane in `engine_config.closure_responses`:
- side_street: vehicles whose usual route is cut take the detour that exists (what a closure has always done).
- side_street_adaptive: the same, and every vehicle also reroutes around congestion. Routing is network-wide, so it applies to the whole scenario.
- nearest_exit: vehicles whose route would use the closed road go to the nearest open exit instead, even where a detour exists.
- wait: demand that would enter on a closed entry road waits until it reopens (the vehicles have not entered yet).
(A fifth, sharing the opposite side of the road, arrives with the shared-lane closure.)
"""
from __future__ import annotations

SIDE_STREET, SIDE_STREET_ADAPTIVE, NEAREST_EXIT, WAIT = "side_street", "side_street_adaptive", "nearest_exit", "wait"
RESPONSES = (SIDE_STREET, SIDE_STREET_ADAPTIVE, NEAREST_EXIT, WAIT)
LABELS = {SIDE_STREET: "Use the side street", SIDE_STREET_ADAPTIVE: "Use the side street and avoid jams",
          NEAREST_EXIT: "Send to the nearest open exit", WAIT: "Vehicles wait until it reopens"}


def usual_trips(network) -> dict:
    """Entry-to-exit trips and the lanes each normally uses, with nothing closed."""
    entries = [node for node in network.boundaries if network.outgoing[node]]
    exits = [node for node in network.boundaries if network.incoming[node]]
    trips = {(source, target): network.route(source, target) for source in entries for target in exits if source != target}
    return {pair: route for pair, route in trips.items() if route}


def lane_kind(network, lane_id: str) -> str:
    lane = network.lanes[lane_id]
    return "entry" if lane.source in network.boundaries else "exit" if lane.target in network.boundaries else "link"


def available_responses(network, closed: set, lane_id: str, trips: dict | None = None) -> dict:
    """The responses that work for `lane_id` when every lane in `closed` (which includes it) is closed, and the one to preselect."""
    trips = usual_trips(network) if trips is None else trips
    using = [pair for pair, route in trips.items() if lane_id in route]
    has_detour = all(network.route(*pair, closed=closed) for pair in using)
    kind = lane_kind(network, lane_id)
    options = []
    if has_detour and kind != "entry":
        options += [SIDE_STREET, SIDE_STREET_ADAPTIVE]
    if kind != "entry":
        options.append(NEAREST_EXIT)
    if kind == "entry":
        options.append(WAIT)
    return {"available": options, "default": options[0], "has_detour": has_detour and kind != "entry"}


def check_responses(network, responses: dict, closed_ever: set) -> None:
    """Refuse, in plain words, a response that is unknown, set for a road that is never closed, not available for it, or mixed in a way that conflicts."""
    if not isinstance(responses, dict) or any(not isinstance(lane, str) or not isinstance(choice, str) for lane, choice in responses.items()):
        raise ValueError("closure_responses must map each closed road to a response")
    trips = usual_trips(network) if responses else {}
    for lane_id, choice in responses.items():
        if lane_id not in closed_ever:
            raise ValueError(f"A response is set for a road that is never closed ({lane_id}).")
        if choice not in RESPONSES:
            raise ValueError(f"Unknown response '{choice}' for a closed road.")
        offered = available_responses(network, closed_ever, lane_id, trips)["available"]
        if choice not in offered:
            names = ", ".join(LABELS[item].lower() for item in offered)
            raise ValueError(f"'{LABELS[choice]}' does not work for this closed road ({lane_id}); choose one of: {names}.")
    if SIDE_STREET in responses.values() and SIDE_STREET_ADAPTIVE in responses.values():
        raise ValueError("Avoiding jams applies to the whole scenario: choose 'Use the side street and avoid jams' for every closure that uses a side street, or for none.")
