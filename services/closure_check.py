"""Which road pieces have a detour, and whether a chosen set of closures leaves any legal movement (the real routing check)."""
from __future__ import annotations

from simulation.closure_responses import closure_states, scheduled_responses, usual_trips
from simulation.scenario_config import DEFAULTS, normalize_lane_events, validate_config


def closure_report(network, closed_lanes: list[str], events: list[dict] | None = None) -> dict:
    """Preview which usual trips lose their route during each direction's closure."""
    unknown = set(closed_lanes) - network.lanes.keys()
    if unknown:
        raise ValueError(f"Unknown lane: {', '.join(sorted(unknown))}")
    closed = set(closed_lanes)
    states = closure_states(closed, [])
    try:
        events = normalize_lane_events(network, events or [])
        states = closure_states(closed, events)
        validate_config(DEFAULTS, {"closed_lanes": sorted(closed), "events": events}, network)
        message = None
    except ValueError as exc:
        message = str(exc)
    usual = usual_trips(network)
    pieces = {}
    for lane_id in network.lanes:
        choice = scheduled_responses(network, states.values(), lane_id, usual)
        pieces[lane_id] = {
            "has_detour": choice["has_detour"],
            "trips_using": choice["trips_using"],
            "trips_without_route": choice["trips_without_route"],
            "responses": choice["available"],
            "default_response": choice["default"],
        }
    lost = [pair for pair in usual if closed and not network.route(*pair, closed=closed)]
    return {"network_id": network.id, "valid": message is None, "message": message, "pieces": pieces,
            "selection": {"trips": len(usual), "trips_without_route": len(lost)}}
