"""Which road pieces have a detour, and whether a chosen set of closures leaves any legal movement (the real routing check)."""
from __future__ import annotations

from simulation.scenario_config import DEFAULTS, validate_config


def closure_report(network, closed_lanes: list[str]) -> dict:
    """Per lane: how many entry-to-exit trips normally use it and how many would have no route if only it were closed.

    `has_detour` is False when any such trip would lose every route, which is always the case for an entry road (nothing
    can start there) and for an exit with no other way round. The selection is checked as a whole by `validate_config`.
    """
    unknown = set(closed_lanes) - network.lanes.keys()
    if unknown:
        raise ValueError(f"Unknown lane: {', '.join(sorted(unknown))}")
    entries = [node for node in network.boundaries if network.outgoing[node]]
    exits = [node for node in network.boundaries if network.incoming[node]]
    usual = {(source, target): network.route(source, target) for source in entries for target in exits if source != target}
    usual = {pair: route for pair, route in usual.items() if route}
    pieces = {}
    for lane_id in network.lanes:
        using = [pair for pair, route in usual.items() if lane_id in route]
        unreachable = [pair for pair in using if not network.route(*pair, closed={lane_id})]
        pieces[lane_id] = {"has_detour": not unreachable, "trips_using": len(using), "trips_without_route": len(unreachable)}
    closed = set(closed_lanes)
    try:
        validate_config(DEFAULTS, {"closed_lanes": sorted(closed)}, network)
        message = None
    except ValueError as exc:
        message = str(exc)
    lost = [pair for pair in usual if closed and not network.route(*pair, closed=closed)]
    return {"network_id": network.id, "valid": message is None, "message": message, "pieces": pieces,
            "selection": {"trips": len(usual), "trips_without_route": len(lost)}}
