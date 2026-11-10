"""Read-only route planning on a start-of-run road arrangement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from services.native_scenario_service import lane_direction, network_display_labels, road_whereabouts
from services.visual_network_service import visual_payload
from simulation.closure_responses import (
    NEAREST_EXIT, RESPONSES, SHARE, SIDE_STREET, SIDE_STREET_ADAPTIVE, WAIT,
    available_responses, closure_states, usual_trips,
)
from simulation.contraflow import eligible_roads, kept_lane, lane_ids
from simulation.network_registry import load_registered_network
from simulation.road_network import RoadNetwork
from simulation.scenario_config import DEFAULTS, normalize_lane_events, object_config
from simulation.traffic_engine import TrafficEngine, VEHICLE_TYPES


BASIS = "initial_arrangement_zero_queue"
ScenarioLoader = Callable[[int], dict | None]


class RoutePreviewError(ValueError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PreviewSource:
    network: RoadNetwork
    label: str
    binding: str
    initial_closures: dict
    slow_lanes: dict
    routing_mode: str
    later_closure_changes: bool
    notices: list[dict]


def _arrangement(network: RoadNetwork, value: object) -> dict:
    if not isinstance(value, dict) or value.keys() != {"closed_lanes", "closure_responses"}:
        raise RoutePreviewError(422, "Supply closed_lanes and closure_responses together to replace the initial arrangement.")
    lanes, responses = value["closed_lanes"], value["closure_responses"]
    if not isinstance(lanes, list) or any(not isinstance(lane, str) or lane not in network.lanes for lane in lanes):
        raise RoutePreviewError(422, "Closure directions must be lane IDs on this network.")
    if len(lanes) != len(set(lanes)):
        raise RoutePreviewError(422, "A closure direction may only be listed once.")
    if not isinstance(responses, dict) or any(lane not in lanes or response not in RESPONSES for lane, response in responses.items()):
        raise RoutePreviewError(422, "Each response must be supported and refer to a listed closure direction.")
    return {"closed_lanes": sorted(lanes), "closure_responses": dict(responses)}


def _resolve_source(source: dict, load_scenario: ScenarioLoader | None) -> PreviewSource:
    scenario = None
    if source.get("kind") == "scenario":
        scenario = load_scenario(source["scenario_id"]) if load_scenario else None
        if scenario is None:
            raise RoutePreviewError(404, "Scenario not found.")
        network_id = scenario.get("network_id")
        if not network_id:
            raise RoutePreviewError(422, "Migrate this scenario to a native network before previewing routes.")
    elif source.get("kind") == "network" and source.get("network_id"):
        network_id = source["network_id"]
    else:
        raise RoutePreviewError(422, "Choose a saved scenario or a registered network.")
    try:
        network = load_registered_network(network_id)
    except FileNotFoundError as exc:
        raise RoutePreviewError(404, "The selected network file is unavailable.") from exc
    except ValueError as exc:
        status = 404 if str(exc).startswith("Unknown network") else 422
        raise RoutePreviewError(status, str(exc)) from exc

    saved_hash = scenario.get("network_sha256") if scenario is not None else None
    if saved_hash and saved_hash != network.fingerprint:
        raise RoutePreviewError(409, "The scenario's network changed since it was saved. Migrate or recreate the scenario before previewing routes.")
    binding = "current_network" if scenario is None else "saved_fingerprint" if saved_hash else "current_unpinned"
    notices = []
    if binding == "current_unpinned":
        notices.append({"code": "current_unpinned", "message": "This scenario has no saved network fingerprint. The preview uses the current network."})

    try:
        settings = object_config(scenario.get("engine_config"), "engine_config") if scenario is not None else {}
        initial_lanes = settings.get("closed_lanes", [])
        if not isinstance(initial_lanes, list) or any(not isinstance(lane, str) or lane not in network.lanes for lane in initial_lanes):
            raise ValueError("The scenario has unknown closure directions.")
        events = normalize_lane_events(network, settings.get("events", []))
        responses = settings.get("closure_responses", {})
        if not isinstance(responses, dict):
            raise ValueError("The scenario's closure responses must be an object.")
        slow_lanes = dict(settings.get("slow_lanes", {}))
    except (TypeError, AttributeError, ValueError) as exc:
        raise RoutePreviewError(422, f"Cannot read the scenario's initial road settings: {exc}") from exc

    closed_at_start = closure_states(initial_lanes, events)[0.0]
    for event in events:
        if event["time"] != 0:
            break
        if event.get("speed_factor") == 1:
            slow_lanes.pop(event["lane_id"], None)
        elif "speed_factor" in event:
            slow_lanes[event["lane_id"]] = event["speed_factor"]
    initial = _arrangement(network, {
        "closed_lanes": sorted(closed_at_start),
        "closure_responses": {lane: choice for lane, choice in responses.items() if lane in closed_at_start},
    })
    later = any(event["time"] > 0 and "closed" in event for event in events)
    if later:
        notices.append({"code": "later_closure_changes", "message": "This preview uses engine time zero. Later scheduled closures and reopenings are not shown."})
    label = str(scenario["name"]) if scenario is not None else network.payload.get("name", network.id)
    return PreviewSource(network, label, binding, initial, slow_lanes, settings.get("routing_mode", DEFAULTS["routing_mode"]), later, notices)


def _choices(network: RoadNetwork, vehicle_type: str) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    if vehicle_type not in VEHICLE_TYPES:
        raise RoutePreviewError(422, "Choose a supported vehicle class.")
    entries = {
        boundary: [lane for lane in network.outgoing[boundary] if network.lane_allows(lane, vehicle_type)]
        for boundary in network.demand_boundaries
    }
    entries = {boundary: lanes for boundary, lanes in entries.items() if lanes}
    pairs = [(entry, destination) for entry, destination in usual_trips(network)
             if entry in entries and network.route(entry, destination, vehicle_type=vehicle_type)]
    return entries, pairs


def _boundary_labels(network: RoadNetwork, road_names: dict, labels: dict) -> dict[str, str]:
    result = {}
    for boundary in network.boundaries:
        lanes = network.outgoing[boundary] + network.incoming[boundary]
        roads = sorted({road_names[lane[:-1]] for lane in lanes})
        result[boundary] = f"{' / '.join(roads)} ({labels[boundary]})" if roads else labels[boundary]
    return result


def route_context(source: dict, vehicle_type: str, *, load_scenario: ScenarioLoader | None = None) -> dict:
    resolved = _resolve_source(source, load_scenario)
    network = resolved.network
    entries, pairs = _choices(network, vehicle_type)
    road_names, labels = network_display_labels(network)
    boundaries = _boundary_labels(network, road_names, labels)
    roads = {road["id"]: road for road in network.payload["roads"]}
    destination_ids = {destination for _, destination in pairs}
    return {
        "source": dict(source), "source_label": resolved.label,
        "network_id": network.id, "network_sha256": network.fingerprint, "network_binding": resolved.binding,
        "geometry": visual_payload(network),
        "entries": [{"id": entry, "label": boundaries[entry], "lane_ids": lanes} for entry, lanes in entries.items()],
        "destinations": [{"id": item, "label": boundaries[item]} for item in network.demand_boundaries if item in destination_ids],
        "eligible_pairs": [{"entry_id": entry, "destination_id": target} for entry, target in pairs],
        "initial_closures": resolved.initial_closures,
        "roads": [{"lane_id": lane_id, "road_id": lane_id[:-1],
                   "label": f"{road_names[lane_id[:-1]]} · {road_whereabouts(network, roads[lane_id[:-1]])}",
                   "direction": lane_direction(lane)}
                  for lane_id, lane in network.lanes.items()],
        "basis": BASIS, "has_later_closure_changes": resolved.later_closure_changes, "notices": resolved.notices,
    }


def _preview_engine(resolved: PreviewSource, arrangement: dict) -> TrafficEngine:
    engine = TrafficEngine(network=resolved.network)
    # Normal configuration validates responses against the base network, then
    # derives the established shared network and opens the shared directions.
    engine.configure(**arrangement, slow_lanes=resolved.slow_lanes, routing_mode=resolved.routing_mode,
                     traffic_density="none", pedestrian_density="none")
    return engine


def _arrival(engine: TrafficEngine, entry: str, destination: str, vehicle_type: str) -> tuple[list[str], bool]:
    costs = engine._travel_costs() if engine.config["routing_mode"] == "adaptive" else None
    return engine.arrival_route(entry, destination, vehicle_type=vehicle_type, costs=costs)


def _path(network: RoadNetwork, lanes: list[str], labels: dict) -> dict | None:
    if not lanes:
        return None
    segments = []
    for index, lane_id in enumerate(lanes):
        if index:
            previous = lanes[index - 1]
            connector = network.connector(previous, lane_id)
            segments.append({"kind": "connector", "from_lane_id": previous, "to_lane_id": lane_id,
                             "points": [{"x": x, "y": y} for x, y in connector]})
        segments.append({"kind": "lane", "lane_id": lane_id,
                         "points": [{"x": x, "y": y} for x, y in network.lanes[lane_id].shape]})
    target = network.lanes[lanes[-1]].target
    return {"lane_ids": lanes, "destination_id": target, "destination_label": labels[target], "segments": segments}


def _response_options(network: RoadNetwork, closed: set[str], blocked_reason: str | None) -> dict:
    usual = usual_trips(network)
    options = {}
    for lane in network.lanes:
        allowed = [] if blocked_reason else available_responses(network, closed, lane, usual)["available"]
        reasons = {
            SIDE_STREET: "A side-street detour must keep every affected usual trip connected to its intended destination.",
            SIDE_STREET_ADAPTIVE: "Avoiding jams requires the same permitted detours as the side-street response.",
            SHARE: ("The opposite direction must be open." if kept_lane(lane) in closed
                    else "This road does not support a two-direction shared-pavement layout."),
            NEAREST_EXIT: "This is an entry direction. Arrivals wait outside instead of diverting from it.",
            WAIT: "Waiting outside is only a response for a closed entry direction.",
        }
        options[lane] = [
            {"value": choice, "enabled": choice in allowed,
             "reason": None if choice in allowed else blocked_reason or reasons[choice]}
            for choice in RESPONSES
        ]
    return options


def _shared_geometry(engine: TrafficEngine) -> list[dict]:
    return [
        {"road_id": road, "kept_lane": kept, "shared_lane": kept_lane(kept),
         "width": engine.network.lanes[kept].width,
         "lanes": {lane: list(engine.network.lanes[lane].shape) for lane in lane_ids(road)}}
        for road, kept in engine.shared_roads.items()
    ]


def preview_route(request: dict, *, load_scenario: ScenarioLoader | None = None) -> dict:
    resolved = _resolve_source(request["source"], load_scenario)
    network = resolved.network
    if request.get("expected_network_sha256") != network.fingerprint:
        raise RoutePreviewError(409, "The base network changed. Reload the Route Planner context and select your trip again.")
    vehicle_type, entry, destination = request["vehicle_type"], request["entry_id"], request["destination_id"]
    entries, pairs = _choices(network, vehicle_type)
    if (entry, destination) not in pairs:
        raise RoutePreviewError(422, "This entry and destination are not a permitted generated trip for the selected vehicle class.")
    arrangement = (_arrangement(network, request["closure_override"]) if "closure_override" in request
                   else resolved.initial_closures)
    closed = set(arrangement["closed_lanes"])
    road_names, labels = network_display_labels(network)
    boundaries = _boundary_labels(network, road_names, labels)
    try:
        original_engine = _preview_engine(resolved, {"closed_lanes": [], "closure_responses": {}})
    except ValueError as exc:
        raise RoutePreviewError(422, str(exc)) from exc
    original, _ = _arrival(original_engine, entry, destination, vehicle_type)
    result = {
        "network_id": network.id, "network_sha256": network.fingerprint, "basis": BASIS,
        "routing_mode": original_engine.config["routing_mode"], "effective_closures": arrangement,
        "original": _path(network, original, boundaries), "selected": None,
        "intended_destination_id": destination, "actual_destination_id": None,
        "shared_roads": [], "uses_shared_pavement": False, "notices": resolved.notices,
    }
    try:
        engine = _preview_engine(resolved, arrangement)
    except ValueError as exc:
        valid_shared = {lane for lane, response in arrangement["closure_responses"].items()
                        if response == SHARE and lane[:-1] in eligible_roads(network) and kept_lane(lane) not in closed}
        blocked_reason = str(exc) if not network.has_legal_movement(closed - valid_shared) else None
        return {**result, "arrangement_valid": False, "outcome": "invalid_arrangement", "reason": str(exc),
                "effective_closed_lanes": sorted(closed), "response_options": _response_options(network, closed, blocked_reason)}

    result.update(arrangement_valid=True, routing_mode=engine.config["routing_mode"],
                  effective_closed_lanes=sorted(engine.closed_lanes), response_options=_response_options(network, closed, None),
                  shared_roads=_shared_geometry(engine))
    if all(lane in engine.closed_lanes for lane in entries[entry]):
        return {**result, "outcome": "waiting_entry", "reason": "The entry is closed, so arrivals wait outside the network."}
    if not any(lane not in engine.closed_lanes and engine._entry_lateral(lane, vehicle_type) is not None for lane in entries[entry]):
        return {**result, "outcome": "no_route", "reason": "No open entry lane can admit the selected vehicle class."}
    lanes, diverting = _arrival(engine, entry, destination, vehicle_type)
    selected = _path(engine.network, lanes, boundaries)
    if not selected:
        return {**result, "outcome": "no_route", "reason": "The engine cannot find a legal route or alternative exit for this trip."}

    if selected["destination_id"] != destination:
        outcome, reason = "alternative_exit", "The engine sends this trip to an open exit selected by routing cost."
    elif diverting:
        outcome, reason = "detour", "The engine chose an open exit by routing cost. It still reaches the intended destination."
    elif lanes != original:
        outcome, reason = "detour", "The route changes and still reaches the intended destination."
    else:
        outcome, reason = "unchanged", "The trip keeps the same road directions."
    uses_shared_pavement = any(lane[:-1] in engine.shared_roads for lane in lanes)
    return {**result, "outcome": outcome, "reason": reason, "selected": selected,
            "actual_destination_id": selected["destination_id"], "uses_shared_pavement": uses_shared_pavement}
