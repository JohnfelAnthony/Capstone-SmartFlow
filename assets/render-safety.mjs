const DEFAULT_BOUNDS = Object.freeze({ min_x: -50, min_y: -50, max_x: 50, max_y: 50 });

const MAX_NETWORK_BYTES = 524288;
const MAX_STATE_BYTES = 262144;
const MAX_ABS_COORDINATE = 10000;
const MAX_ROADS = 48;
const MAX_LANES_PER_ROAD = 8;
const MAX_INTERNAL_LANES = 32;
const MAX_AREAS = 24;
const MAX_SIGNALS = 12;
const MAX_SIGNAL_GROUPS = 48;
const MAX_POLYGONS = 64;
const MAX_SHAPE_POINTS = 96;
const MAX_VEHICLES = 160;
const MAX_PEDESTRIANS = 64;
const MAX_TEXT_LENGTH = 48;
const SUPPORTED_THREE_REVISION = "128";
const RENDERER_STATE_EVENT = "smartflow:engine-state";

const SAFE_STATUSES = new Set(["stopped", "running", "paused"]);
const SAFE_SIGNAL_STATES = new Set(["red", "yellow", "green"]);
const SAFE_VEHICLE_TYPES = new Set(["car", "ambulance"]);
const SAFE_SIGNAL_GROUP_KINDS = new Set(["vehicle", "pedestrian"]);
const SAFE_TLS_STATE_CHARACTERS = new Set(["r", "R", "g", "G", "y", "Y", "o", "O", "u", "U", "s", "S", "m", "M"]);

function clampNumber(value, fallback = 0, minimum = -MAX_ABS_COORDINATE, maximum = MAX_ABS_COORDINATE) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return fallback;
  return Math.min(Math.max(numericValue, minimum), maximum);
}

function clampInteger(value, fallback = 0, minimum = 0, maximum = 999) {
  const numericValue = Number.parseInt(value, 10);
  if (!Number.isFinite(numericValue)) return fallback;
  return Math.min(Math.max(numericValue, minimum), maximum);
}

function sanitizeText(value, fallback = "", maxLength = MAX_TEXT_LENGTH) {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  if (!text) return fallback;
  return text.slice(0, maxLength);
}

function sanitizeBoolean(value) {
  return value === true;
}

function sanitizePoint(rawPoint) {
  if (!rawPoint || typeof rawPoint !== "object") return null;
  const x = clampNumber(rawPoint.x, Number.NaN);
  const y = clampNumber(rawPoint.y, Number.NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function sanitizeShape(rawShape, minimumPoints = 2, maximumPoints = MAX_SHAPE_POINTS) {
  if (!Array.isArray(rawShape)) return [];
  const points = [];
  for (const rawPoint of rawShape.slice(0, maximumPoints)) {
    const point = sanitizePoint(rawPoint);
    if (!point) continue;
    const previousPoint = points[points.length - 1];
    if (!previousPoint || previousPoint.x !== point.x || previousPoint.y !== point.y) {
      points.push(point);
    }
  }
  return points.length >= minimumPoints ? points : [];
}

function sanitizeBounds(rawBounds) {
  if (!rawBounds || typeof rawBounds !== "object") return { ...DEFAULT_BOUNDS };
  let minX = clampNumber(rawBounds.min_x, DEFAULT_BOUNDS.min_x);
  let minY = clampNumber(rawBounds.min_y, DEFAULT_BOUNDS.min_y);
  let maxX = clampNumber(rawBounds.max_x, DEFAULT_BOUNDS.max_x);
  let maxY = clampNumber(rawBounds.max_y, DEFAULT_BOUNDS.max_y);
  if (minX >= maxX) [minX, maxX] = [DEFAULT_BOUNDS.min_x, DEFAULT_BOUNDS.max_x];
  if (minY >= maxY) [minY, maxY] = [DEFAULT_BOUNDS.min_y, DEFAULT_BOUNDS.max_y];
  return { min_x: minX, min_y: minY, max_x: maxX, max_y: maxY };
}

function sanitizeLane(rawLane) {
  if (!rawLane || typeof rawLane !== "object") return null;
  const shape = sanitizeShape(rawLane.shape, 2);
  if (!shape.length) return null;
  return {
    id: sanitizeText(rawLane.id, `lane-${clampInteger(rawLane.index, 0, 0, 32)}`),
    index: clampInteger(rawLane.index, 0, 0, 32),
    width: clampNumber(rawLane.width, 3.2, 0.5, 16),
    allow: sanitizeText(rawLane.allow),
    disallow: sanitizeText(rawLane.disallow),
    shape,
  };
}

function sanitizeRoad(rawRoad, index) {
  if (!rawRoad || typeof rawRoad !== "object") return null;
  const lanes = (Array.isArray(rawRoad.lanes) ? rawRoad.lanes : [])
    .slice(0, MAX_LANES_PER_ROAD)
    .map(sanitizeLane)
    .filter(Boolean);
  if (!lanes.length) return null;
  const shape = sanitizeShape(rawRoad.shape, 2) || lanes[0].shape;
  return {
    index,
    function: sanitizeText(rawRoad.function, "normal"),
    toward_intersection: sanitizeBoolean(rawRoad.toward_intersection),
    away_from_intersection: sanitizeBoolean(rawRoad.away_from_intersection),
    shape,
    lanes,
  };
}

function sanitizeRoadCollection(rawCollection, limit) {
  if (!Array.isArray(rawCollection)) return [];
  return rawCollection.slice(0, limit).map(sanitizeRoad).filter(Boolean);
}

function averageShapeCenter(shape) {
  if (!shape.length) return { x: 0, y: 0 };
  const total = shape.reduce((accumulator, point) => ({
    x: accumulator.x + point.x,
    y: accumulator.y + point.y,
  }), { x: 0, y: 0 });
  return { x: total.x / shape.length, y: total.y / shape.length };
}

function sanitizeSignal(rawSignal, index) {
  if (!rawSignal || typeof rawSignal !== "object") return null;
  const shape = sanitizeShape(rawSignal.shape, 3);
  const center = averageShapeCenter(shape);
  return {
    id: sanitizeText(rawSignal.id, `signal-${index}`),
    kind: index === 0 ? "major" : sanitizeText(rawSignal.kind, "minor"),
    x: clampNumber(rawSignal.x, center.x),
    y: clampNumber(rawSignal.y, center.y),
    shape,
  };
}

function sanitizeSignalGroup(rawGroup, index) {
  if (!rawGroup || typeof rawGroup !== "object") return null;
  const stopLine = sanitizeShape(rawGroup.stop_line, 2, 2);
  const anchor = sanitizePoint(rawGroup.anchor);
  const linkIndices = Array.isArray(rawGroup.link_indices)
    ? rawGroup.link_indices.slice(0, 8).map((value) => clampInteger(value, 0, 0, 64))
    : [];
  if (!stopLine.length || !anchor || !linkIndices.length) return null;

  const kind = sanitizeText(rawGroup.kind, "vehicle");
  return {
    id: sanitizeText(rawGroup.id, `signal-group-${index}`),
    signal_id: sanitizeText(rawGroup.signal_id, "signal-0"),
    lane_id: sanitizeText(rawGroup.lane_id, "lane-0"),
    from_edge_id: sanitizeText(rawGroup.from_edge_id),
    kind: SAFE_SIGNAL_GROUP_KINDS.has(kind) ? kind : "vehicle",
    width: clampNumber(rawGroup.width, 3.2, 0.5, 16),
    heading: clampNumber(rawGroup.heading, 0, -360, 360),
    anchor,
    stop_line: stopLine,
    link_indices: linkIndices,
    via_lane_ids: (Array.isArray(rawGroup.via_lane_ids) ? rawGroup.via_lane_ids : [])
      .slice(0, 8)
      .map((value) => sanitizeText(value))
      .filter(Boolean),
  };
}

function sanitizePolygon(rawPolygon, index) {
  if (!rawPolygon || typeof rawPolygon !== "object") return null;
  const shape = sanitizeShape(rawPolygon.shape, 3, MAX_SHAPE_POINTS);
  if (!shape.length) return null;
  return {
    id: sanitizeText(rawPolygon.id, `poly-${index}`),
    color: sanitizeText(rawPolygon.color, "#808080"),
    fill: sanitizeBoolean(rawPolygon.fill),
    layer: clampNumber(rawPolygon.layer, 0, -100, 100),
    shape,
  };
}

function sanitizePolygons(rawPolygons) {
  if (!Array.isArray(rawPolygons)) return [];
  return rawPolygons
    .slice(0, MAX_POLYGONS)
    .map(sanitizePolygon)
    .filter(Boolean);
}

function sanitizeTrafficLightEntry(rawEntry) {
  if (!rawEntry || typeof rawEntry !== "object") return null;
  const phase = sanitizeText(rawEntry.phase, "ALL_RED");
  const rawState = sanitizeText(rawEntry.state, "");
  const state = Array.from(rawState)
    .filter((value) => SAFE_TLS_STATE_CHARACTERS.has(value))
    .join("")
    .slice(0, 64);
  if (!state) return null;
  return { phase, state };
}

function sanitizeTrafficLights(rawTrafficLights) {
  if (!rawTrafficLights || typeof rawTrafficLights !== "object") return {};
  const sanitized = {};
  for (const [signalId, rawEntry] of Object.entries(rawTrafficLights)) {
    const safeSignalId = sanitizeText(signalId);
    const safeEntry = sanitizeTrafficLightEntry(rawEntry);
    if (safeSignalId && safeEntry) {
      sanitized[safeSignalId] = safeEntry;
    }
  }
  return sanitized;
}

function sanitizeConstraintMarker(rawMarker) {
  if (!rawMarker || typeof rawMarker !== "object" || rawMarker.active !== true) {
    return { active: false };
  }
  const x = clampNumber(rawMarker.x, Number.NaN);
  const y = clampNumber(rawMarker.y, Number.NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return { active: false };
  }
  return { active: true, x, y };
}

function sanitizeVehicle(rawVehicle, index) {
  if (!rawVehicle || typeof rawVehicle !== "object") return null;
  const x = clampNumber(rawVehicle.x, Number.NaN);
  const y = clampNumber(rawVehicle.y, Number.NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const visualType = sanitizeText(rawVehicle.visual_type, "car");
  return {
    id: sanitizeText(rawVehicle.id, `vehicle-${index}`),
    x,
    y,
    angle: clampNumber(rawVehicle.angle, 0, -720, 720),
    speed: clampNumber(rawVehicle.speed, 0, 0, 80),
    lane_id: sanitizeText(rawVehicle.lane_id),
    lane_position: clampNumber(rawVehicle.lane_position, 0, 0, MAX_ABS_COORDINATE),
    length: clampNumber(rawVehicle.length, 4.5, 1.5, 16),
    width: clampNumber(rawVehicle.width, 1.8, 0.8, 4),
    stopped: sanitizeBoolean(rawVehicle.stopped),
    visual_type: SAFE_VEHICLE_TYPES.has(visualType) ? visualType : "car",
    emergency: sanitizeBoolean(rawVehicle.emergency),
  };
}

function sanitizePedestrian(rawPedestrian, index) {
  if (!rawPedestrian || typeof rawPedestrian !== "object") return null;
  const x = clampNumber(rawPedestrian.x, Number.NaN);
  const y = clampNumber(rawPedestrian.y, Number.NaN);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return {
    id: sanitizeText(rawPedestrian.id, `pedestrian-${index}`),
    x,
    y,
    speed: clampNumber(rawPedestrian.speed, 0, 0, 10),
    lane_id: sanitizeText(rawPedestrian.lane_id),
    stopped: sanitizeBoolean(rawPedestrian.stopped),
  };
}

async function fetchJsonWithLimit(url, label, maxBytes = MAX_NETWORK_BYTES) {
  const response = await fetch(url, { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) {
    throw new Error(`${label} request failed with ${response.status}`);
  }
  const text = await response.text();
  if (text.length > maxBytes) {
    throw new Error(`${label} payload exceeded ${maxBytes} bytes`);
  }
  return JSON.parse(text);
}

function sanitizeNetworkPayload(rawNetwork) {
  if (!rawNetwork || typeof rawNetwork !== "object") {
    return {
      version: 1,
      bounds: { ...DEFAULT_BOUNDS },
      roads: [],
      internal_lanes: [],
      crossings: [],
      walking_areas: [],
      signals: [],
      signal_groups: [],
      polygons: [],
      source_net: "",
      scope: { mode: "" },
    };
  }
  const scope = rawNetwork.scope && typeof rawNetwork.scope === "object" ? rawNetwork.scope : {};
  return {
    version: 1,
    source_net: sanitizeText(rawNetwork.source_net, ""),
    scope: {
      mode: sanitizeText(scope.mode, ""),
    },
    bounds: sanitizeBounds(rawNetwork.bounds),
    roads: sanitizeRoadCollection(rawNetwork.roads, MAX_ROADS),
    internal_lanes: sanitizeRoadCollection(rawNetwork.internal_lanes, MAX_INTERNAL_LANES),
    crossings: sanitizeRoadCollection(rawNetwork.crossings, MAX_AREAS),
    walking_areas: sanitizeRoadCollection(rawNetwork.walking_areas, MAX_AREAS),
    signals: (Array.isArray(rawNetwork.signals) ? rawNetwork.signals : [])
      .slice(0, MAX_SIGNALS)
      .map(sanitizeSignal)
      .filter(Boolean),
    signal_groups: (Array.isArray(rawNetwork.signal_groups) ? rawNetwork.signal_groups : [])
      .slice(0, MAX_SIGNAL_GROUPS)
      .map(sanitizeSignalGroup)
      .filter(Boolean),
    polygons: sanitizePolygons(rawNetwork.polygons),
  };
}

function sanitizeLiveState(rawState) {
  if (!rawState || typeof rawState !== "object") {
    return {
      status: "stopped",
      step_length: 0.1,
      flow_state: "IDLE",
      render_mode: "idle",
      intersection_id: "tagum_1",
      playback: { active: false, frame_index: 0, frame_count: 0 },
      ns_state: "red",
      ew_state: "red",
      vehicles: [],
      pedestrians: [],
      visual: { constraint_marker: { active: false } },
      traffic_lights: {},
    };
  }

  const status = sanitizeText(rawState.status, "stopped");
  const nsState = sanitizeText(rawState.ns_state, "red").toLowerCase();
  const ewState = sanitizeText(rawState.ew_state, "red").toLowerCase();
  const playback = rawState.playback && typeof rawState.playback === "object"
    ? {
        active: rawState.playback.active === true,
        frame_index: clampInteger(rawState.playback.frame_index, 0, 0, 1000000),
        frame_count: clampInteger(rawState.playback.frame_count, 0, 0, 1000000),
      }
    : { active: false, frame_index: 0, frame_count: 0 };

  return {
    render_ts: clampNumber(rawState.render_ts, 0, 0, 1000000000000),
    status: SAFE_STATUSES.has(status) ? status : "stopped",
    step_length: clampNumber(rawState.step_length, 0.1, 0.01, 5),
    flow_state: sanitizeText(rawState.flow_state, "IDLE", 24),
    render_mode: sanitizeText(rawState.render_mode, "idle", 24).toLowerCase(),
    intersection_id: sanitizeText(rawState.intersection_id, "tagum_1", 24).toLowerCase(),
    playback,
    ns_state: SAFE_SIGNAL_STATES.has(nsState) ? nsState : "red",
    ew_state: SAFE_SIGNAL_STATES.has(ewState) ? ewState : "red",
    phase: sanitizeText(rawState.phase),
    time: clampNumber(rawState.time, 0, 0, 86400),
    vehicles: (Array.isArray(rawState.vehicles) ? rawState.vehicles : [])
      .slice(0, MAX_VEHICLES)
      .map(sanitizeVehicle)
      .filter(Boolean),
    pedestrians: (Array.isArray(rawState.pedestrians) ? rawState.pedestrians : [])
      .slice(0, MAX_PEDESTRIANS)
      .map(sanitizePedestrian)
      .filter(Boolean),
    visual: {
      constraint_marker: sanitizeConstraintMarker(rawState.visual?.constraint_marker),
    },
    traffic_lights: sanitizeTrafficLights(rawState.traffic_lights),
  };
}

function isSupportedThreeRevision(threeNamespace) {
  return Boolean(threeNamespace) && String(threeNamespace.REVISION || "") === SUPPORTED_THREE_REVISION;
}

export {
  MAX_NETWORK_BYTES,
  MAX_STATE_BYTES,
  RENDERER_STATE_EVENT,
  SUPPORTED_THREE_REVISION,
  fetchJsonWithLimit,
  isSupportedThreeRevision,
  sanitizeLiveState,
  sanitizeNetworkPayload,
};
