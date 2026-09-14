/**
 * SMARTFLOW Three.js Bridge
 * =========================
 * Geometry-first renderer: SUMO exports the road network, this file only
 * visualizes that geometry plus live TraCI entities from Dash.
 */

import {
  RENDERER_STATE_EVENT,
  fetchJsonWithLimit,
  isSupportedThreeRevision,
  sanitizeLiveState,
  sanitizeNetworkPayload,
} from '/assets/render-safety.mjs';

const VISUAL_NETWORK_URL = '/api/visual-network';
const SCENE_FOCUS = Object.freeze({ x: 0, y: 0, z: 0 });
const TARGET_SCENE_SPAN = 82;
const LANE_WIDTH_MULTIPLIER = 3.8;
const VISUAL_BOUNDS_MARGIN = 25;
const TARGET_RENDER_FPS = 30;
const FRAME_INTERVAL_MS = 1000 / TARGET_RENDER_FPS;
const SNAPSHOT_INTERVAL_FALLBACK_MS = 200;
const MAX_THREE_PIXEL_RATIO = 1.25;

let renderer;
let scene;
let camera;
let clock;
let worldRoot;
let staticRoot;
let dynamicRoot;
let initialized = false;
let ready = false;
let disposed = false;
let animFrame = null;
let visualBounds = null;
let worldScale = 0.14;
let sumoOrigin = { x: 528.0, y: 870.0 };

const vehicleRegistry = new Map();
const pedestrianRegistry = new Map();
const signalRegistry = new Map();
let constraintMarker = null;
let lastState = sanitizeLiveState({ status: 'stopped', step_length: 0.1 });
let expectedUpdateIntervalMs = SNAPSHOT_INTERVAL_FALLBACK_MS;
let stateTransitionTime = 0;
let lastSnapshotKey = "";
let lastRenderTime = 0;
let viewportWasVisible = false;
let initObserver = null;

function showRendererMessage(message, isError = false) {
  const loading = document.getElementById('three-loading-msg');
  if (!loading) return;
  loading.style.display = 'flex';
  loading.style.color = isError ? '#fca5a5' : 'var(--text-muted)';
  loading.textContent = message;
}

function handleRendererStateEvent(event) {
  update(event?.detail || {});
}

function snapshotKeyForState(state) {
  return [
    Number(state?.render_ts || 0),
    Number(state?.time || 0),
    String(state?.phase || ""),
    Array.isArray(state?.vehicles) ? state.vehicles.length : 0,
    Array.isArray(state?.pedestrians) ? state.pedestrians.length : 0,
  ].join(":");
}

function resolveExpectedUpdateIntervalMs(nextState, now) {
  if (stateTransitionTime <= 0) return 1000;
  const measuredIntervalMs = Math.max(16, now - stateTransitionTime);
  if (!Number.isFinite(measuredIntervalMs)) return 1000;
  return Math.min(2500, Math.max(200, measuredIntervalMs * 1.05));
}

function isViewportVisible(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return false;
  const computedStyle = window.getComputedStyle(container);
  return computedStyle.display !== 'none' && computedStyle.visibility !== 'hidden';
}

function stopInitObserver() {
  if (initObserver) {
    initObserver.disconnect();
    initObserver = null;
  }
}

function scheduleInitWhenContainerAvailable() {
  if (initialized || initObserver) return;
  if (!document.body) {
    document.addEventListener('DOMContentLoaded', scheduleInitWhenContainerAvailable, { once: true });
    return;
  }

  initObserver = new MutationObserver(() => {
    if (!document.getElementById('three-container')) return;
    init();
    if (initialized) stopInitObserver();
  });
  initObserver.observe(document.body, { childList: true, subtree: true });
}

document.addEventListener(RENDERER_STATE_EVENT, handleRendererStateEvent);

const MATERIALS = {
  ground: 0x9fd36f,
  road: 0x121820,
  roadEdge: 0xf7f8f2,
  sidewalk: 0xf4f2e8,
  crosswalk: 0xffffff,
  laneLine: 0xf5f7fa,
  buildingA: 0x7494b8,
  buildingB: 0xd88b63,
  buildingC: 0x82b37b,
};

const VEHICLE_STYLES = Object.freeze({
  car: { color: 0x4f86f7, width: 0.88, height: 0.42, length: 1.55 },
  suv: { color: 0x8fb56a, width: 0.95, height: 0.5, length: 1.75 },
  taxi: { color: 0xffd23f, width: 0.88, height: 0.42, length: 1.52 },
  pickup: { color: 0xf97316, width: 0.95, height: 0.48, length: 1.9 },
  truck: { color: 0x334155, width: 1.05, height: 0.62, length: 2.45 },
  bus: { color: 0xf8fafc, width: 1.05, height: 0.68, length: 2.7 },
  ambulance: { color: 0xf8fafc, width: 0.98, height: 0.55, length: 1.9 },
});

function init() {
  const T = window.THREE;
  if (!isSupportedThreeRevision(T)) {
    console.warn('[SmartFlow] THREE unavailable or unsupported');
    showRendererMessage('3D renderer unavailable.', true);
    return false;
  }

  const container = document.getElementById('three-container');
  if (!container) {
    scheduleInitWhenContainerAvailable();
    return false;
  }
  if (!isViewportVisible('three-container')) return false;
  stopInitObserver();

  if (initialized) {
    if (renderer?.domElement && !container.contains(renderer.domElement)) {
      container.appendChild(renderer.domElement);
      onResize();
    }
    return true;
  }

  disposed = false;
  initialized = true;

  const width = container.clientWidth || 900;
  const height = container.clientHeight || 520;

  renderer = new T.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_THREE_PIXEL_RATIO));
  renderer.setSize(width, height);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;
  renderer.setClearColor(0xb9e3a4);
  if (T.SRGBColorSpace) renderer.outputColorSpace = T.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  scene = new T.Scene();
  scene.background = new T.Color(0xb9e3a4);
  scene.fog = new T.Fog(0xb9e3a4, 95, 190);

  camera = new T.PerspectiveCamera(34, width / Math.max(height, 1), 0.1, 500);
  camera.position.set(46, 54, 46);
  camera.lookAt(SCENE_FOCUS.x, SCENE_FOCUS.y, SCENE_FOCUS.z);

  worldRoot = new T.Group();
  staticRoot = new T.Group();
  dynamicRoot = new T.Group();
  worldRoot.add(staticRoot, dynamicRoot);
  scene.add(worldRoot);

  setupLights();
  buildBaseScene();

  clock = new T.Clock();
  window.addEventListener('resize', onResize);
  onResize();
  loop();

  loadVisualNetwork()
    .then(network => {
      buildRoadsFromNetwork(network);
      buildContextAssets(network);
      syncAllFromState(lastState);
      const loading = document.getElementById('three-loading-msg');
      if (loading) loading.style.display = 'none';
      ready = true;
    })
    .catch(error => {
      console.warn('[SmartFlow] Failed to load visual network:', error);
      showRendererMessage('3D map unavailable.', true);
      ready = true;
    });

  return true;
}

function setupLights() {
  const T = window.THREE;
  scene.add(new T.HemisphereLight(0xffffff, 0x79a95d, 0.85));

  const sun = new T.DirectionalLight(0xfff4d6, 1.25);
  sun.position.set(58, 88, 42);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -80;
  sun.shadow.camera.right = 80;
  sun.shadow.camera.top = 80;
  sun.shadow.camera.bottom = -80;
  sun.shadow.bias = -0.001;
  scene.add(sun);
}

function buildBaseScene() {
  const T = window.THREE;
  const ground = new T.Mesh(
    new T.PlaneGeometry(150, 150),
    new T.MeshStandardMaterial({ color: MATERIALS.ground, roughness: 0.96 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.04;
  ground.receiveShadow = true;
  staticRoot.add(ground);
}

async function loadVisualNetwork() {
  const rawNetwork = await fetchJsonWithLimit(VISUAL_NETWORK_URL, 'Visual network');
  return sanitizeNetworkPayload(rawNetwork);
}

function configureTransform(bounds) {
  visualBounds = bounds;
  const spanX = Math.max(bounds.max_x - bounds.min_x, 1);
  const spanY = Math.max(bounds.max_y - bounds.min_y, 1);
  worldScale = TARGET_SCENE_SPAN / Math.max(spanX, spanY);
  sumoOrigin = {
    x: (bounds.min_x + bounds.max_x) / 2,
    y: (bounds.min_y + bounds.max_y) / 2,
  };
}

function buildRoadsFromNetwork(network) {
  configureTransform(network.bounds);
  const T = window.THREE;

  const roadShoulder = new T.MeshStandardMaterial({ color: MATERIALS.roadEdge, roughness: 0.92 });
  const roadMaterial = new T.MeshStandardMaterial({ color: MATERIALS.road, roughness: 0.88 });
  const sidewalkMaterial = new T.MeshStandardMaterial({ color: MATERIALS.sidewalk, roughness: 0.95 });
  const laneLineMaterial = new T.MeshStandardMaterial({ color: MATERIALS.laneLine, roughness: 0.55 });

  staticRoot.add(createIntersectionPad(network));

  for (const road of network.roads || []) {
    for (const lane of road.lanes || []) {
      const isSidewalk = isPedestrianOnlyLane(lane);
      const width = lane.width * worldScale * LANE_WIDTH_MULTIPLIER;
      if (!isSidewalk) {
        staticRoot.add(createLaneStrip(lane.shape, width + 0.48, roadShoulder, 0.005));
      }
      staticRoot.add(createLaneStrip(lane.shape, width, isSidewalk ? sidewalkMaterial : roadMaterial, isSidewalk ? 0.018 : 0.028));
      if (!isSidewalk) {
        staticRoot.add(createDashedLaneLine(lane.shape, laneLineMaterial));
      }
    }
  }

  for (const walkingArea of network.walking_areas || []) {
    for (const lane of walkingArea.lanes || []) {
      staticRoot.add(createWalkingArea(lane));
    }
  }

  for (const crossing of network.crossings || []) {
    for (const lane of crossing.lanes || []) {
      staticRoot.add(createCrosswalk(lane));
    }
  }

  for (const signal of network.signals || []) {
    const mesh = createTrafficSignalMesh(signal);
    signalRegistry.set(signal.id, mesh);
    staticRoot.add(mesh.group);
  }
}

function buildFallbackScene() {
  visualBounds = { min_x: 268, min_y: 610, max_x: 788, max_y: 1130 };
  const network = {
    bounds: visualBounds,
    roads: [
      { lanes: [{ width: 3.2, shape: [{ x: 310, y: 870 }, { x: 746, y: 870 }] }] },
      { lanes: [{ width: 3.2, shape: [{ x: 528, y: 1110 }, { x: 528, y: 650 }] }] },
    ],
    crossings: [],
    walking_areas: [],
    signals: [],
  };
  buildRoadsFromNetwork(network);
}

function buildContextAssets(network) {
  const T = window.THREE;
  const bounds = network.bounds;
  const placements = [
    { x: bounds.min_x + 45, y: bounds.max_y - 48, color: MATERIALS.buildingA, w: 8.5, h: 5.2, d: 6.5 },
    { x: bounds.max_x - 62, y: bounds.max_y - 58, color: MATERIALS.buildingB, w: 9.5, h: 3.6, d: 7.4 },
    { x: bounds.max_x - 70, y: bounds.min_y + 55, color: MATERIALS.buildingC, w: 8.0, h: 4.4, d: 8.0 },
  ];

  for (const placement of placements) {
    const group = new T.Group();
    const base = toScenePoint(placement.x, placement.y, 0);
    const footprintScale = worldScale * 5.2;
    const body = new T.Mesh(
      new T.BoxGeometry(placement.w * footprintScale, placement.h, placement.d * footprintScale),
      new T.MeshStandardMaterial({ color: placement.color, roughness: 0.82 }),
    );
    body.position.y = placement.h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const roof = new T.Mesh(
      new T.BoxGeometry(placement.w * footprintScale * 1.08, 0.18, placement.d * footprintScale * 1.08),
      new T.MeshStandardMaterial({ color: 0x3f4652, roughness: 0.8 }),
    );
    roof.position.y = placement.h + 0.12;
    roof.castShadow = true;
    group.add(roof);

    group.position.copy(base);
    staticRoot.add(group);
  }
}

function createIntersectionPad(network) {
  const T = window.THREE;
  const center = averageSignalPosition(network.signals || []);
  const mesh = new T.Mesh(
    new T.CircleGeometry(5.2, 32),
    new T.MeshStandardMaterial({ color: MATERIALS.road, roughness: 0.88 }),
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.copy(toScenePoint(center.x, center.y, 0.032));
  mesh.receiveShadow = true;
  return mesh;
}

function averageSignalPosition(signals) {
  if (!signals.length) return { x: sumoOrigin.x, y: sumoOrigin.y };
  const total = signals.reduce((acc, signal) => ({
    x: acc.x + Number(signal.x || 0),
    y: acc.y + Number(signal.y || 0),
  }), { x: 0, y: 0 });
  return { x: total.x / signals.length, y: total.y / signals.length };
}

function isPedestrianOnlyLane(lane) {
  const allow = lane.allow || '';
  const disallow = lane.disallow || '';
  return allow.includes('pedestrian') && !disallow.includes('pedestrian');
}

function createLaneStrip(points, width, material, yOffset = 0.02) {
  const T = window.THREE;
  const group = new T.Group();
  if (!points || points.length < 2) return group;

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = toScenePoint(points[index].x, points[index].y, yOffset);
    const end = toScenePoint(points[index + 1].x, points[index + 1].y, yOffset);
    const strip = createSegmentStrip(start, end, width, material);
    if (strip) group.add(strip);
  }

  return group;
}

function createSegmentStrip(start, end, width, material) {
  const T = window.THREE;
  const delta = new T.Vector3().subVectors(end, start);
  const length = delta.length();
  if (length < 0.001) return null;

  const center = new T.Vector3().addVectors(start, end).multiplyScalar(0.5);
  const strip = new T.Mesh(new T.PlaneGeometry(width, length + 0.08), material);
  strip.rotation.x = -Math.PI / 2;
  strip.rotation.y = Math.atan2(delta.x, delta.z);
  strip.position.copy(center);
  strip.receiveShadow = true;
  return strip;
}

function createDashedLaneLine(points, material) {
  const T = window.THREE;
  const group = new T.Group();
  if (!points || points.length < 2) return group;

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = toScenePoint(points[index].x, points[index].y, 0.052);
    const end = toScenePoint(points[index + 1].x, points[index + 1].y, 0.052);
    const delta = new T.Vector3().subVectors(end, start);
    const length = delta.length();
    if (length < 0.3) continue;

    const dashCount = Math.max(1, Math.floor(length / 2.6));
    for (let dash = 0; dash < dashCount; dash += 1) {
      const t = (dash + 0.5) / dashCount;
      const position = new T.Vector3().lerpVectors(start, end, t);
      const marker = new T.Mesh(new T.PlaneGeometry(0.08, Math.min(1.2, length / dashCount * 0.55)), material);
      marker.rotation.x = -Math.PI / 2;
      marker.rotation.y = Math.atan2(delta.x, delta.z);
      marker.position.copy(position);
      marker.receiveShadow = true;
      group.add(marker);
    }
  }

  return group;
}

function createWalkingArea(lane) {
  const T = window.THREE;
  const material = new T.MeshStandardMaterial({
    color: MATERIALS.sidewalk,
    roughness: 0.95,
    transparent: true,
    opacity: 0.96,
  });

  if ((lane.shape || []).length >= 4) {
    return createPolygonMesh(lane.shape, material, 0.038);
  }

  return createLaneStrip(lane.shape, lane.width * worldScale * LANE_WIDTH_MULTIPLIER, material, 0.038);
}

function createCrosswalk(lane) {
  const T = window.THREE;
  const group = new T.Group();
  const points = lane.shape || [];
  if (points.length < 2) return group;

  const start = toScenePoint(points[0].x, points[0].y, 0.062);
  const end = toScenePoint(points[points.length - 1].x, points[points.length - 1].y, 0.062);
  const delta = new T.Vector3().subVectors(end, start);
  const length = delta.length();
  if (length < 0.1) return group;

  const material = new T.MeshStandardMaterial({ color: MATERIALS.crosswalk, roughness: 0.48 });
  const stripeCount = Math.max(4, Math.floor(length / 0.35));
  const stripeLength = Math.max(0.9, lane.width * worldScale * LANE_WIDTH_MULTIPLIER * 0.72);

  for (let index = 0; index < stripeCount; index += 1) {
    const t = (index + 0.5) / stripeCount;
    const position = new T.Vector3().lerpVectors(start, end, t);
    const stripe = new T.Mesh(new T.PlaneGeometry(0.2, stripeLength), material);
    stripe.rotation.x = -Math.PI / 2;
    stripe.rotation.y = Math.atan2(delta.x, delta.z);
    stripe.position.copy(position);
    stripe.receiveShadow = true;
    group.add(stripe);
  }

  return group;
}

function createPolygonMesh(points, material, yOffset) {
  const T = window.THREE;
  const shape = new T.Shape();

  points.forEach((point, index) => {
    const scenePoint = toScenePoint(point.x, point.y);
    const shapeX = scenePoint.x;
    const shapeY = -scenePoint.z;
    if (index === 0) {
      shape.moveTo(shapeX, shapeY);
    } else {
      shape.lineTo(shapeX, shapeY);
    }
  });
  shape.closePath();

  const mesh = new T.Mesh(new T.ShapeGeometry(shape), material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = yOffset;
  mesh.receiveShadow = true;
  return mesh;
}

function createTrafficSignalMesh(signal) {
  const T = window.THREE;
  const group = new T.Group();
  group.position.copy(toScenePoint(signal.x, signal.y, 0.04));

  const poleMaterial = new T.MeshStandardMaterial({ color: 0x475569, roughness: 0.75 });
  const housingMaterial = new T.MeshStandardMaterial({ color: 0x18212d, roughness: 0.65 });

  const pole = new T.Mesh(new T.CylinderGeometry(0.05, 0.07, 1.9, 10), poleMaterial);
  pole.position.y = 0.95;
  pole.castShadow = true;
  group.add(pole);

  const arm = new T.Mesh(new T.BoxGeometry(0.08, 0.08, 0.75), poleMaterial);
  arm.position.set(0, 1.72, 0.36);
  arm.castShadow = true;
  group.add(arm);

  const housing = new T.Mesh(new T.BoxGeometry(0.26, 0.58, 0.18), housingMaterial);
  housing.position.set(0, 1.54, 0.72);
  housing.castShadow = true;
  group.add(housing);

  const red = createLamp(0xff3b30, 0, 1.72, 0.84);
  const yellow = createLamp(0xffcc00, 0, 1.54, 0.84);
  const green = createLamp(0x22c55e, 0, 1.36, 0.84);
  group.add(red, yellow, green);

  const kind = signal.kind || 'major';
  return { id: signal.id, kind, group, red, yellow, green };
}

function createLamp(color, x, y, z) {
  const T = window.THREE;
  const lamp = new T.Mesh(
    new T.SphereGeometry(0.075, 12, 12),
    new T.MeshStandardMaterial({ color, emissive: 0x000000, roughness: 0.28 }),
  );
  lamp.position.set(x, y, z);
  return lamp;
}

function createVehicleMesh(entity) {
  const T = window.THREE;
  const style = VEHICLE_STYLES[entity.visual_type] || VEHICLE_STYLES.car;
  const group = new T.Group();
  
  // Inner group to hold the mesh so we can offset it relative to the front bumper
  const meshGroup = new T.Group();
  // If +Z is the front, shifting by -length/2 aligns the +Z edge (bumper) with Z=0
  meshGroup.position.z = -style.length / 2;
  group.add(meshGroup);

  const body = new T.Mesh(
    new T.BoxGeometry(style.width, style.height, style.length),
    new T.MeshStandardMaterial({ color: entity.emergency ? 0xf8fafc : style.color, roughness: 0.42, metalness: 0.12 }),
  );
  body.position.y = style.height / 2 + 0.08;
  body.castShadow = true;
  meshGroup.add(body);

  const cabin = new T.Mesh(
    new T.BoxGeometry(style.width * 0.72, style.height * 0.62, style.length * 0.42),
    new T.MeshStandardMaterial({ color: 0xc7e8ff, roughness: 0.18, transparent: true, opacity: 0.9 }),
  );
  cabin.position.set(0, style.height + 0.12, -style.length * 0.03);
  cabin.castShadow = true;
  meshGroup.add(cabin);

  addVehicleWheels(meshGroup, style);

  if (entity.emergency || entity.visual_type === 'ambulance') {
    const stripe = new T.Mesh(
      new T.BoxGeometry(style.width + 0.03, 0.04, style.length * 0.72),
      new T.MeshStandardMaterial({ color: 0xef4444, emissive: 0x220000 }),
    );
    stripe.position.set(0, style.height + 0.16, 0);
    meshGroup.add(stripe);

    const lightLeft = new T.Mesh(new T.BoxGeometry(0.12, 0.06, 0.12), new T.MeshStandardMaterial({ color: 0xef4444, emissive: 0x550000 }));
    const lightRight = new T.Mesh(new T.BoxGeometry(0.12, 0.06, 0.12), new T.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x002244 }));
    lightLeft.position.set(-0.15, style.height + 0.36, -0.08);
    lightRight.position.set(0.15, style.height + 0.36, 0.08);
    meshGroup.add(lightLeft, lightRight);
    group.userData.emergencyLightLeft = lightLeft;
    group.userData.emergencyLightRight = lightRight;
  }

  return group;
}

function addVehicleWheels(group, style) {
  const T = window.THREE;
  const wheelMaterial = new T.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.65 });
  const zOffset = style.length * 0.34;
  const xOffset = style.width * 0.53;
  for (const x of [-xOffset, xOffset]) {
    for (const z of [-zOffset, zOffset]) {
      const wheel = new T.Mesh(new T.CylinderGeometry(0.12, 0.12, 0.08, 12), wheelMaterial);
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, 0.16, z);
      wheel.castShadow = true;
      group.add(wheel);
    }
  }
}

function createPedestrianMesh() {
  const T = window.THREE;
  const group = new T.Group();

  const torso = new T.Mesh(
    new T.BoxGeometry(0.22, 0.52, 0.16),
    new T.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.65 }),
  );
  torso.position.y = 0.53;
  torso.castShadow = true;
  group.add(torso);

  const head = new T.Mesh(
    new T.SphereGeometry(0.12, 12, 12),
    new T.MeshStandardMaterial({ color: 0xf2c2a0, roughness: 0.5 }),
  );
  head.position.y = 0.89;
  head.castShadow = true;
  group.add(head);

  const legMaterial = new T.MeshStandardMaterial({ color: 0x111827, roughness: 0.7 });
  for (const x of [-0.06, 0.06]) {
    const leg = new T.Mesh(new T.BoxGeometry(0.055, 0.34, 0.06), legMaterial);
    leg.position.set(x, 0.18, 0);
    group.add(leg);
  }

  return group;
}

function createConstraintMesh() {
  const T = window.THREE;
  const group = new T.Group();
  const material = new T.MeshStandardMaterial({
    color: 0xff3344,
    emissive: 0x550000,
    roughness: 0.35,
  });

  const barA = new T.Mesh(new T.BoxGeometry(2.4, 0.16, 0.18), material);
  const barB = new T.Mesh(new T.BoxGeometry(2.4, 0.16, 0.18), material);
  barA.rotation.y = Math.PI / 4;
  barB.rotation.y = -Math.PI / 4;
  barA.position.y = 0.32;
  barB.position.y = 0.32;
  group.add(barA, barB);
  return group;
}

function toScenePoint(x, y, yOffset = 0) {
  const T = window.THREE;
  return new T.Vector3(
    (Number(x) - sumoOrigin.x) * worldScale,
    yOffset,
    -(Number(y) - sumoOrigin.y) * worldScale,
  );
}

function rotationFromSumoAngle(angleDegrees) {
  const T = window.THREE;
  return T.MathUtils.degToRad(180 - Number(angleDegrees || 0));
}

function bezierInterpolate3D(p0, r0, p3, r3, t) {
  const dx = p3.x - p0.x;
  const dz = p3.z - p0.z;
  const d = Math.sqrt(dx * dx + dz * dz);
  const m = d * 0.4;
  
  const p1x = p0.x + Math.sin(r0) * m;
  const p1z = p0.z + Math.cos(r0) * m;
  const p2x = p3.x - Math.sin(r3) * m;
  const p2z = p3.z - Math.cos(r3) * m;
  
  const u = 1 - t;
  const tt = t * t;
  const uu = u * u;
  const uuu = uu * u;
  const ttt = tt * t;

  return {
    x: uuu * p0.x + 3 * uu * t * p1x + 3 * u * tt * p2x + ttt * p3.x,
    y: p0.y + (p3.y - p0.y) * t, // linear for vertical
    z: uuu * p0.z + 3 * uu * t * p1z + 3 * u * tt * p2z + ttt * p3.z
  };
}

function isInsideVisualBounds(entity) {
  if (!visualBounds) return false;
  const x = Number(entity.x);
  const y = Number(entity.y);
  return (
    x >= visualBounds.min_x - VISUAL_BOUNDS_MARGIN &&
    x <= visualBounds.max_x + VISUAL_BOUNDS_MARGIN &&
    y >= visualBounds.min_y - VISUAL_BOUNDS_MARGIN &&
    y <= visualBounds.max_y + VISUAL_BOUNDS_MARGIN
  );
}

function upsertVehicle(entity) {
  let entry = vehicleRegistry.get(entity.id);
  const visualType = entity.emergency ? 'ambulance' : entity.visual_type;
  const shouldRebuild = entry && (entry.visualType !== visualType || entry.emergency !== Boolean(entity.emergency));

  if (shouldRebuild) {
    dynamicRoot.remove(entry.group);
    vehicleRegistry.delete(entity.id);
    entry = null;
  }

  if (!entry) {
    const group = createVehicleMesh({ ...entity, visual_type: visualType });
    group.position.copy(toScenePoint(entity.x, entity.y, 0.08));
    group.rotation.y = rotationFromSumoAngle(entity.angle);
    dynamicRoot.add(group);
    entry = {
      id: entity.id,
      group,
      visualType,
      emergency: Boolean(entity.emergency),
      targetPosition: toScenePoint(entity.x, entity.y, 0.08),
      targetRotation: rotationFromSumoAngle(entity.angle),
      startPosition: toScenePoint(entity.x, entity.y, 0.08),
      startRotation: rotationFromSumoAngle(entity.angle),
    };
    vehicleRegistry.set(entity.id, entry);
  } else {
    entry.startPosition = entry.group.position.clone();
    entry.startRotation = entry.group.rotation.y;
  }

  entry.targetPosition = toScenePoint(entity.x, entity.y, 0.08);
  entry.targetRotation = rotationFromSumoAngle(entity.angle);
}

function upsertPedestrian(entity) {
  let entry = pedestrianRegistry.get(entity.id);
  if (!entry) {
    const group = createPedestrianMesh();
    group.position.copy(toScenePoint(entity.x, entity.y, 0.07));
    dynamicRoot.add(group);
    entry = {
      id: entity.id,
      group,
      targetPosition: toScenePoint(entity.x, entity.y, 0.07),
      targetRotation: 0,
      startPosition: toScenePoint(entity.x, entity.y, 0.07),
      startRotation: 0,
    };
    pedestrianRegistry.set(entity.id, entry);
  } else {
    entry.startPosition = entry.group.position.clone();
    entry.startRotation = entry.group.rotation.y;
  }

  const nextPosition = toScenePoint(entity.x, entity.y, 0.07);
  const deltaX = nextPosition.x - entry.group.position.x;
  const deltaZ = nextPosition.z - entry.group.position.z;
  if (Math.abs(deltaX) > 0.001 || Math.abs(deltaZ) > 0.001) {
    entry.targetRotation = Math.atan2(deltaX, deltaZ);
  }
  entry.targetPosition = nextPosition;
}

function syncVehiclesFromState(vehicles) {
  const activeIds = new Set();
  if (!visualBounds) return;

  for (const vehicle of vehicles || []) {
    if (!isInsideVisualBounds(vehicle)) continue;
    activeIds.add(vehicle.id);
    upsertVehicle(vehicle);
  }

  for (const [id, entry] of vehicleRegistry.entries()) {
    if (!activeIds.has(id)) {
      dynamicRoot.remove(entry.group);
      vehicleRegistry.delete(id);
    }
  }
}

function syncPedestriansFromState(pedestrians) {
  const activeIds = new Set();
  if (!visualBounds) return;

  for (const pedestrian of pedestrians || []) {
    if (!isInsideVisualBounds(pedestrian)) continue;
    activeIds.add(pedestrian.id);
    upsertPedestrian(pedestrian);
  }

  for (const [id, entry] of pedestrianRegistry.entries()) {
    if (!activeIds.has(id)) {
      dynamicRoot.remove(entry.group);
      pedestrianRegistry.delete(id);
    }
  }
}

function syncConstraintMarkerFromState(visual) {
  const marker = visual?.constraint_marker;
  if (!marker?.active || !isInsideVisualBounds(marker)) {
    if (constraintMarker) {
      dynamicRoot.remove(constraintMarker);
      constraintMarker = null;
    }
    return;
  }

  if (!constraintMarker) {
    constraintMarker = createConstraintMesh();
    dynamicRoot.add(constraintMarker);
  }
  constraintMarker.position.copy(toScenePoint(marker.x, marker.y, 0.18));
}

function syncSignalsFromState(state) {
  const nsState = state?.ns_state || 'red';
  const ewState = state?.ew_state || 'red';
  for (const signal of signalRegistry.values()) {
    const displayState = signal.kind === 'major' ? nsState : ewState;
    setSignalLampState(signal, displayState);
  }
}

function setSignalLampState(signal, state) {
  const active = String(state || 'red').toLowerCase();
  signal.red.material.emissive.setHex(active === 'red' ? 0x7f1d1d : 0x000000);
  signal.yellow.material.emissive.setHex(active === 'yellow' ? 0x7c5f00 : 0x000000);
  signal.green.material.emissive.setHex(active === 'green' ? 0x14532d : 0x000000);
}

function syncAllFromState(state) {
  if (!staticRoot || !dynamicRoot) return;
  syncVehiclesFromState(state.vehicles || []);
  syncPedestriansFromState(state.pedestrians || []);
  syncConstraintMarkerFromState(state.visual || {});
  syncSignalsFromState(state);
}

function clearDynamicState() {
  for (const entry of vehicleRegistry.values()) dynamicRoot.remove(entry.group);
  vehicleRegistry.clear();

  for (const entry of pedestrianRegistry.values()) dynamicRoot.remove(entry.group);
  pedestrianRegistry.clear();

  if (constraintMarker) {
    dynamicRoot.remove(constraintMarker);
    constraintMarker = null;
  }
}

function stepDynamicEntities(dt) {
  const now = performance.now();
  let progress = expectedUpdateIntervalMs > 0 ? (now - stateTransitionTime) / expectedUpdateIntervalMs : 1;
  if (progress > 1) progress = 1;

  for (const entry of vehicleRegistry.values()) {
    if (entry.startPosition) {
      const curvedPos = bezierInterpolate3D(
        entry.startPosition, entry.startRotation,
        entry.targetPosition, entry.targetRotation,
        progress
      );
      entry.group.position.set(curvedPos.x, curvedPos.y, curvedPos.z);
      
      const delta = entry.targetRotation - entry.startRotation;
      let targetRot = entry.targetRotation;
      if (delta > Math.PI) targetRot -= Math.PI * 2;
      else if (delta < -Math.PI) targetRot += Math.PI * 2;
      
      entry.group.rotation.y = entry.startRotation + (targetRot - entry.startRotation) * progress;
    }

    const lightLeft = entry.group.userData.emergencyLightLeft;
    const lightRight = entry.group.userData.emergencyLightRight;
    if (lightLeft && lightRight) {
      const pulse = Math.sin((now / 1000) * 12);
      lightLeft.visible = pulse >= 0;
      lightRight.visible = pulse < 0;
    }
  }

  for (const entry of pedestrianRegistry.values()) {
    if (entry.startPosition) {
      entry.group.position.lerpVectors(entry.startPosition, entry.targetPosition, progress);
      entry.group.position.y = entry.targetPosition.y + Math.abs(Math.sin((now / 1000) * 8)) * 0.035;
      
      const delta = entry.targetRotation - entry.startRotation;
      let targetRot = entry.targetRotation;
      if (delta > Math.PI) targetRot -= Math.PI * 2;
      else if (delta < -Math.PI) targetRot += Math.PI * 2;
      
      entry.group.rotation.y = entry.startRotation + (targetRot - entry.startRotation) * progress;
    }
  }
}

function loop() {
  if (disposed) return;
  animFrame = requestAnimationFrame(loop);

  const now = performance.now();
  const dt = Math.min(clock?.getDelta?.() || 0.016, 0.1);
  const isVisible = isViewportVisible('three-container');
  if (!isVisible) {
    viewportWasVisible = false;
    return;
  }

  if (!viewportWasVisible) {
    viewportWasVisible = true;
    lastRenderTime = 0;
  }

  if (now - lastRenderTime < FRAME_INTERVAL_MS) {
    return;
  }

  const state = lastState;
  if (state.status === 'stopped') {
    clearDynamicState();
  } else {
    stepDynamicEntities(state.status === 'paused' ? 0 : dt);
  }

  syncSignalsFromState(state);
  renderer?.render(scene, camera);
  lastRenderTime = now;
}

function onResize() {
  const container = document.getElementById('three-container');
  if (!container || !renderer || !camera) return;
  const width = container.clientWidth || 900;
  const height = container.clientHeight || 520;
  renderer.setSize(width, height);
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
}

function update(state) {
  const nextState = sanitizeLiveState(state);
  if (!init()) {
    lastState = nextState;
    return;
  }
  const snapshotKey = snapshotKeyForState(nextState);
  if (snapshotKey && snapshotKey === lastSnapshotKey) {
    return;
  }
  
  const now = performance.now();
  lastState = nextState;
  expectedUpdateIntervalMs = resolveExpectedUpdateIntervalMs(nextState, now);
  stateTransitionTime = now;
  lastSnapshotKey = snapshotKey;
  
  syncAllFromState(lastState);
}

function dispose() {
  disposed = true;
  if (animFrame) cancelAnimationFrame(animFrame);
  window.removeEventListener('resize', onResize);
  clearDynamicState();
  signalRegistry.clear();
  if (renderer) {
    renderer.dispose();
    if (renderer.domElement?.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement);
    }
  }
  initialized = false;
  ready = false;
  stopInitObserver();
  lastState = sanitizeLiveState({ status: 'stopped', step_length: 0.1 });
  expectedUpdateIntervalMs = SNAPSHOT_INTERVAL_FALLBACK_MS;
  stateTransitionTime = 0;
  lastSnapshotKey = "";
  lastRenderTime = 0;
  viewportWasVisible = false;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (!init()) scheduleInitWhenContainerAvailable();
  });
} else {
  if (!init()) scheduleInitWhenContainerAvailable();
}
