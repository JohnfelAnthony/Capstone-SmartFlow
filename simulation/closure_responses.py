"""How traffic may respond to a closed road, and which responses really work for a given selection (the real routing check).

Responses, stored per closed lane in `engine_config.closure_responses`:
- side_street: vehicles whose usual route is cut take the detour that exists (what a closure has always done).
- side_street_adaptive: the same, and every vehicle also reroutes around congestion. Routing is network-wide, so it applies to the whole scenario.
- share: the closed direction's traffic moves onto half of the opposite pavement, one lane each way (hypothetical, see simulation/contraflow.py).
- nearest_exit: vehicles whose route would use the closed road go to the nearest open exit instead, even where a detour exists.
- wait: demand that would enter on a closed entry road waits until it reopens (the vehicles have not entered yet).
"""
from __future__ import annotations

from collections.abc import Collection, Iterable

SIDE_STREET, SIDE_STREET_ADAPTIVE, SHARE, NEAREST_EXIT, WAIT = "side_street", "side_street_adaptive", "share", "nearest_exit", "wait"
RESPONSES = (SIDE_STREET, SIDE_STREET_ADAPTIVE, SHARE, NEAREST_EXIT, WAIT)
LABELS = {SIDE_STREET: "Use the side street", SIDE_STREET_ADAPTIVE: "Use the side street and avoid jams", SHARE: "Share the other side (hypothetical)",
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


def closure_states(closed_lanes: Iterable[str], events: list[dict]) -> dict[float, frozenset[str]]:
    """Snapshot the closed directions after all validated events at each time."""
    closed = set(closed_lanes)
    states = {0.0: frozenset(closed)}
    for event in events:
        if "closed" in event:
            (closed.add if event["closed"] else closed.discard)(event["lane_id"])
            states[event["time"]] = frozenset(closed)
    return states


def available_responses(network, closed: set, lane_id: str, trips: dict | None = None) -> dict:
    """Responses for a single closure state."""
    return scheduled_responses(network, [frozenset(closed)], lane_id, trips)


def scheduled_responses(network, states: Collection[frozenset[str]], lane_id: str, trips: dict | None = None) -> dict:
    """Report routes and responses that work whenever this direction is closed."""
    trips = usual_trips(network) if trips is None else trips
    using = [pair for pair, route in trips.items() if lane_id in route]
    # For a direction the user has not picked yet, preview closing it for the whole run.
    active = {closed for closed in states if lane_id in closed}
    if not active:
        active = {closed | {lane_id} for closed in states}
    unreachable = sum(any(not network.route(*pair, closed=closed) for closed in active) for pair in using)
    kind = lane_kind(network, lane_id)
    has_detour = unreachable == 0 and kind != "entry"
    options = []
    if has_detour:
        options += [SIDE_STREET, SIDE_STREET_ADAPTIVE]
    # Sharing can still be draining after an event. Keep the opposite direction
    # available throughout the schedule rather than assuming an instant switch.
    if _can_share(network, set().union(*states), lane_id):
        options.append(SHARE)
    options.append(WAIT if kind == "entry" else NEAREST_EXIT)
    return {
        "available": options, "default": options[0], "has_detour": has_detour,
        "trips_using": len(using), "trips_without_route": unreachable,
    }


def _can_share(network, closed: set, lane_id: str) -> bool:
    """A wide enough two-way road whose opposite direction is open: the closed direction can use half of that pavement."""
    from .contraflow import eligible_roads, kept_lane, road_of
    return road_of(lane_id) in eligible_roads(network) and kept_lane(lane_id) not in closed


def check_responses(network, responses: dict, states: Collection[frozenset[str]]) -> None:
    """Refuse, in plain words, a response that is unknown, set for a road that is never closed, not available for it, or mixed in a way that conflicts."""
    if not isinstance(responses, dict) or any(not isinstance(lane, str) or not isinstance(choice, str) for lane, choice in responses.items()):
        raise ValueError("closure_responses must map each closed road to a response")
    if not responses:
        return
    closed_ever = set().union(*states)
    trips = usual_trips(network)
    for lane_id, choice in responses.items():
        if lane_id not in closed_ever:
            raise ValueError(f"A response is set for a road that is never closed ({lane_id}).")
        if choice not in RESPONSES:
            raise ValueError(f"Unknown response '{choice}' for a closed road.")
        offered = scheduled_responses(network, states, lane_id, trips)["available"]
        if choice not in offered:
            names = ", ".join(LABELS[item].lower() for item in offered)
            raise ValueError(f"'{LABELS[choice]}' does not work for this closed road ({lane_id}); choose one of: {names}.")
    if SIDE_STREET in responses.values() and SIDE_STREET_ADAPTIVE in responses.values():
        raise ValueError("Avoiding jams applies to the whole scenario: choose 'Use the side street and avoid jams' for every closure that uses a side street, or for none.")
