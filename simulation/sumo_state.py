from typing import Iterable


def canonical_signal_states(phase: str) -> tuple[str, str]:
    if phase == "NS_GREEN":
        return "green", "red"
    if phase == "NS_YELLOW":
        return "yellow", "red"
    if phase in {"WEST_GREEN", "EAST_GREEN", "EW_GREEN"}:
        return "red", "green"
    if phase in {"WEST_YELLOW", "EAST_YELLOW", "EW_YELLOW"}:
        return "red", "yellow"
    return "red", "red"


def _vehicle_visual_type(vehicle_id: str, emergency: bool) -> str:
    if emergency:
        return "ambulance"
    return "car"


def vehicle_snapshot(connection, vehicle_ids: Iterable[str], limit: int, emergency_ids: set[str] | None = None) -> list[dict]:
    snapshot = []
    emergency_ids = emergency_ids or set()
    for vehicle_id in list(vehicle_ids)[:limit]:
        x, y = connection.vehicle.getPosition(vehicle_id)
        emergency = vehicle_id in emergency_ids
        speed = connection.vehicle.getSpeed(vehicle_id)
        snapshot.append({
            "id": vehicle_id,
            "type": "vehicle",
            "x": round(x, 2),
            "y": round(y, 2),
            "speed": round(speed, 2),
            "angle": round(connection.vehicle.getAngle(vehicle_id), 2),
            "edge_id": connection.vehicle.getRoadID(vehicle_id),
            "lane_id": connection.vehicle.getLaneID(vehicle_id),
            "lane_position": round(connection.vehicle.getLanePosition(vehicle_id), 2),
            "length": round(connection.vehicle.getLength(vehicle_id), 2),
            "width": round(connection.vehicle.getWidth(vehicle_id), 2),
            "wait_time": round(connection.vehicle.getAccumulatedWaitingTime(vehicle_id), 1),
            "stopped": speed <= 0.1,
            "state": "active",
            "visual_type": _vehicle_visual_type(vehicle_id, emergency),
            "emergency": emergency,
        })
    return snapshot


def pedestrian_snapshot(connection, person_ids: Iterable[str], limit: int) -> list[dict]:
    snapshot = []
    for person_id in list(person_ids)[:limit]:
        x, y = connection.person.getPosition(person_id)
        speed = connection.person.getSpeed(person_id)
        snapshot.append({
            "id": person_id,
            "type": "pedestrian",
            "x": round(x, 2),
            "y": round(y, 2),
            "speed": round(speed, 2),
            "edge_id": connection.person.getRoadID(person_id),
            "lane_id": connection.person.getLaneID(person_id),
            "stopped": speed <= 0.05,
            "state": "active",
            "visual_type": "pedestrian",
        })
    return snapshot


def build_state_payload(
    *,
    status: str,
    simulation_time: float,
    phase: str,
    phase_remaining: float,
    cycle_count: int,
    controller_type: str,
    vehicles: list[dict],
    pedestrians: list[dict],
    metrics: dict,
    events: list[dict],
    scenario: dict,
    dashboard: dict,
    charts: dict,
    visual: dict,
    traffic_lights: dict,
    step_length: float,
) -> dict:
    return {
        "time": round(simulation_time, 1),
        "step_length": round(step_length, 3),
        "status": status,
        "phase": phase,
        "phase_remaining": round(max(phase_remaining, 0.0), 1),
        "cycle_count": cycle_count,
        "controller_type": controller_type,
        "vehicles": vehicles,
        "vehicle_count": len(vehicles) if metrics.get("active_vehicle_count") is None else metrics["active_vehicle_count"],
        "pedestrians": pedestrians,
        "pedestrian_count": len(pedestrians) if metrics.get("active_pedestrian_count") is None else metrics["active_pedestrian_count"],
        "queues": metrics.get("queue_by_approach", {}),
        "metrics": {
            key: value
            for key, value in metrics.items()
            if key not in {"active_vehicle_count", "active_pedestrian_count", "queue_by_approach"}
        },
        "events": events,
        "scenario": scenario,
        "dashboard": dashboard,
        "charts": charts,
        "visual": visual,
        "traffic_lights": traffic_lights,
    }
