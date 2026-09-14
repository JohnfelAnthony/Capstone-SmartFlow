/**
 * SMARTFLOW 2D Canvas Renderer
 * ===============================
 * High-fidelity SUMO GUI-style 2D map view of the SMARTFLOW intersection.
 * Draws filled road polygons, zebra crosswalks, SUMO-style signals,
 * and accurately scaled dynamic entities.
 *
 * Exports SmartFlowCanvas2D { init, update, dispose, isReady }
 */

import {
  RENDERER_STATE_EVENT,
  fetchJsonWithLimit,
  sanitizeLiveState,
  sanitizeNetworkPayload,
} from '/assets/render-safety.mjs';

const VISUAL_NETWORK_URL = '/api/visual-network';
const RENDER_STREAM_URL = '/api/render-stream';
const TARGET_RENDER_FPS = 30;
const FRAME_INTERVAL_MS = 1000 / TARGET_RENDER_FPS;
const SNAPSHOT_INTERVAL_FALLBACK_MS = 200;
const PLAYBACK_EXPECTED_UPDATE_MIN_MS = 40;
const PLAYBACK_EXPECTED_UPDATE_MAX_MS = 250;
const MAX_CANVAS_DPR = 1.25;
const MAX_PREDICTION_MS = 260;
const LIVE_EXPECTED_UPDATE_MIN_MS = 120;
const LIVE_EXPECTED_UPDATE_MAX_MS = 280;
const LIVE_LATE_FRAME_CARRY_MS = 90;
const LIVE_SAME_LANE_PREDICTION_MS = 80;
const STREAM_FALLBACK_GRACE_MS = 900;

// ── Colour palette (SUMO GUI Theme) ────────────
const C = {
  bg:          '#2e8b00',  // SUMO green grass
  road:        '#333333',  // Dark asphalt
  sidewalk:    '#999999',  // Grey concrete
  crosswalk:   '#ffffff',  // White zebra stripes
  laneLine:    '#ffffff',  // White dashed lane dividers
  edgeLine:    '#cccccc',  // Light grey curbs/edges
  internalLane:'#3e3e3e',  // Internal junction connectors
  signalRed:   '#ff0000',  // Vivid red
  signalGreen: '#00ff00',  // Vivid green
  signalYellow:'#ffd84d',  // Vivid yellow
  signalOff:   '#333333',  // Off/dark
  vehicle:     '#ffd700',  // SUMO yellow
  emsWhite:    '#ffffff',  // Ambulance body
  emsCross:    '#00ff00',  // Ambulance green cross
  emsRed:      '#ff0000',  // Flasher
  emsBlue:     '#0000ff',  // Flasher
  pedestrian:  '#ff8c00',  // SUMO orange dots
  constraint:  '#ff0000',  // Closure marker
};

const CAR_PALETTE = [
  '#ffd21f',
  '#f97316',
  '#ef4444',
  '#22c55e',
  '#38bdf8',
  '#2563eb',
  '#f8fafc',
  '#a3a3a3',
];



function hashStringToIndex(value, modulo) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % modulo;
}

function getVehicleColor(vehicleId) {
  if (!vehicleId) return C.vehicle;
  return CAR_PALETTE[hashStringToIndex(vehicleId, CAR_PALETTE.length)];
}

// ── Module state ─────────────────────────────────────────────────
let canvas = null;
let ctx = null;
let network = null;
let initialized = false;
let ready = false;
let disposed = false;
let animFrameId = null;
let needsRedraw = true;
let bgCanvas = null;          // offscreen canvas for static geometry
let laneGeometryById = new Map();
let previousState = null;
let stateTransitionTime = 0;
let expectedUpdateIntervalMs = SNAPSHOT_INTERVAL_FALLBACK_MS;
let lastSnapshotKey = '';
let previousVehiclesById = new Map();
let previousPedestriansById = new Map();
let lastDrawTime = 0;
let viewportWasVisible = false;
let playbackWarmStartUntil = 0;
let currentState = sanitizeLiveState({ status: 'stopped', step_length: 0.1 });
let currentNetworkIntersectionId = '';
let pendingNetworkIntersectionId = '';
let networkLoadPromise = null;
let initObserver = null;
let renderStream = null;
let renderStreamActiveUntil = 0;
let lastStreamSequence = -1;

// Coordinate transform
const T = { scale: 1, ox: 0, oy: 0, cw: 640, ch: 480 };

// ── Helpers ──────────────────────────────────────────────────────
function toPixel(sx, sy) {
  // SUMO +Y is Up. Canvas +Y is Down.
  return {
    x: Number(sx) * T.scale + T.ox,
    y: -Number(sy) * T.scale + T.oy,
  };
}

function configureTransform(networkData, cw, ch) {
  // We want a zoomed-in view of the intersection, not the full bounds.
  // We use the signal junction shape as the center, plus a margin.
  let min_x = 0, max_x = 0, min_y = 0, max_y = 0;
  let hasJunction = false;

  if (networkData.signals && networkData.signals.length > 0 && networkData.signals[0].shape) {
    const shape = networkData.signals[0].shape;
    min_x = Math.min(...shape.map(p => p.x));
    max_x = Math.max(...shape.map(p => p.x));
    min_y = Math.min(...shape.map(p => p.y));
    max_y = Math.max(...shape.map(p => p.y));
    hasJunction = true;
  }

  if (hasJunction) {
    // Add margin for the zoomed-in view
    const margin = 15;
    min_x -= margin;
    max_x += margin;
    min_y -= margin;
    max_y += margin;
  } else {
    // Fallback to network bounds if no junction found
    const b = networkData.bounds || { min_x: -50, min_y: -50, max_x: 50, max_y: 50 };
    min_x = b.min_x;
    max_x = b.max_x;
    min_y = b.min_y;
    max_y = b.max_y;
  }

  const spanX = Math.max(max_x - min_x, 1);
  const spanY = Math.max(max_y - min_y, 1);
  const pad = 0.90; // 90% of canvas
  
  // Calculate scale to fit the tight bounds into the canvas
  const s = Math.min((cw * pad) / spanX, (ch * pad) / spanY);
  T.scale = s;
  
  // Center the view. Remember Y is flipped.
  // If SUMO bounds are min_y to max_y, the visual center is (min_y + max_y)/2
  // After flip, the center in canvas coords (before translation) is - (min_y + max_y)/2 * scale
  const centerX = (min_x + max_x) / 2;
  const centerY = (min_y + max_y) / 2;
  
  T.ox = cw / 2 - centerX * s;
  T.oy = ch / 2 - (-centerY * s); 
  
  T.cw = cw;
  T.ch = ch;
  
  // Camera bounds stay tight around the junction, while dynamic clipping uses
  // the exported visual scope so vehicles do not vanish on visible approaches.
  T.viewBounds = { min_x, max_x, min_y, max_y };
  T.dynamicBounds = networkData.bounds || T.viewBounds;
}

function isInsideBounds(sx, sy) {
  const b = T.dynamicBounds || T.viewBounds;
  if (!b) return true;
  // Add a small buffer so cars don't pop in/out instantly
  const buffer = 10;
  return (
    sx >= b.min_x - buffer && sx <= b.max_x + buffer &&
    sy >= b.min_y - buffer && sy <= b.max_y + buffer
  );
}

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function lerp(start, end, progress) {
  return start + (end - start) * progress;
}

function toSumoAngle(dx, dy, fallbackAngle = 0) {
  if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
    return fallbackAngle;
  }
  return (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360;
}

function unwrapAngle(startAngle, endAngle) {
  let safeStartAngle = Number(startAngle || 0);
  const safeEndAngle = Number(endAngle || 0);
  if (safeEndAngle - safeStartAngle > 180) safeStartAngle += 360;
  else if (safeStartAngle - safeEndAngle > 180) safeStartAngle -= 360;
  return safeStartAngle;
}

function bezierInterpolate(p0x, p0y, a0, p3x, p3y, a3, t) {
  const rad0 = a0 * Math.PI / 180;
  const rad3 = a3 * Math.PI / 180;
  const dx = p3x - p0x;
  const dy = p3y - p0y;
  const d = Math.sqrt(dx * dx + dy * dy);
  const m = d * 0.4;
  
  const p1x = p0x + Math.sin(rad0) * m;
  const p1y = p0y + Math.cos(rad0) * m;
  const p2x = p3x - Math.sin(rad3) * m;
  const p2y = p3y - Math.cos(rad3) * m;
  
  const u = 1 - t;
  const tt = t * t;
  const uu = u * u;
  const uuu = uu * u;
  const ttt = tt * t;

  return {
    x: uuu * p0x + 3 * uu * t * p1x + 3 * u * tt * p2x + ttt * p3x,
    y: uuu * p0y + 3 * uu * t * p1y + 3 * u * tt * p2y + ttt * p3y
  };
}

function buildLaneGeometry(lane) {
  const shape = lane?.shape || [];
  if (!Array.isArray(shape) || shape.length < 2) return null;
  const segments = [];
  let totalLength = 0;

  for (let i = 1; i < shape.length; i++) {
    const start = shape[i - 1];
    const end = shape[i];
    const dx = Number(end.x) - Number(start.x);
    const dy = Number(end.y) - Number(start.y);
    const length = Math.hypot(dx, dy);
    if (length <= 1e-6) continue;
    segments.push({
      start,
      end,
      dx,
      dy,
      length,
      startOffset: totalLength,
      endOffset: totalLength + length,
      heading: toSumoAngle(dx, dy),
    });
    totalLength += length;
  }

  if (!segments.length) return null;
  const clipStartPosition = Number(lane?.clip_start_position);
  const clipEndPosition = Number(lane?.clip_end_position);
  const sourceLength = Number(lane?.source_length);
  return {
    shape,
    segments,
    totalLength,
    clipStartPosition: Number.isFinite(clipStartPosition) ? clipStartPosition : 0,
    clipEndPosition: Number.isFinite(clipEndPosition) && clipEndPosition > 0
      ? clipEndPosition
      : totalLength,
    sourceLength: Number.isFinite(sourceLength) && sourceLength > 0
      ? sourceLength
      : totalLength,
  };
}

function registerLaneGeometry(lane) {
  if (!lane?.id) return;
  const geometry = buildLaneGeometry(lane);
  if (geometry) {
    laneGeometryById.set(lane.id, geometry);
  }
}

function buildLaneGeometryCache(networkData) {
  laneGeometryById = new Map();
  for (const roadCollection of [
    networkData.roads || [],
    networkData.internal_lanes || [],
    networkData.crossings || [],
    networkData.walking_areas || [],
  ]) {
    for (const road of roadCollection) {
      for (const lane of road.lanes || []) {
        registerLaneGeometry(lane);
      }
    }
  }
}

function sampleLanePoint(laneId, lanePosition, fallbackX, fallbackY, fallbackAngle = 0) {
  const geometry = laneGeometryById.get(laneId);
  if (!geometry) {
    return { x: Number(fallbackX), y: Number(fallbackY), angle: Number(fallbackAngle || 0) };
  }

  const rawLanePosition = Number(lanePosition);
  if (!Number.isFinite(rawLanePosition)) {
    return { x: Number(fallbackX), y: Number(fallbackY), angle: Number(fallbackAngle || 0), projected: false };
  }

  const clipStartPosition = Number(geometry.clipStartPosition || 0);
  const clipEndPosition = Number(geometry.clipEndPosition || geometry.totalLength);
  const clipTolerance = 0.35;
  if (
    rawLanePosition < clipStartPosition - clipTolerance ||
    rawLanePosition > clipEndPosition + clipTolerance
  ) {
    return { x: Number(fallbackX), y: Number(fallbackY), angle: Number(fallbackAngle || 0), projected: false };
  }

  const visualLanePosition = clamp(rawLanePosition - clipStartPosition, 0, geometry.totalLength);
  const segment = geometry.segments.find((candidate) => visualLanePosition <= candidate.endOffset)
    || geometry.segments[geometry.segments.length - 1];
  const segmentProgress = segment.length > 0
    ? (visualLanePosition - segment.startOffset) / segment.length
    : 0;
  return {
    x: lerp(Number(segment.start.x), Number(segment.end.x), segmentProgress),
    y: lerp(Number(segment.start.y), Number(segment.end.y), segmentProgress),
    angle: segment.heading ?? Number(fallbackAngle || 0),
    projected: true,
  };
}

function snapshotKeyForState(state) {
  const renderTimestamp = Number(state?.render_ts || 0);
  const simTime = Number(state?.time || 0);
  const phase = String(state?.phase || '');
  const intersectionId = String(state?.intersection_id || '');
  const playbackFrameIndex = Number(state?.playback?.frame_index || 0);
  const vehicleCount = Array.isArray(state?.vehicles) ? state.vehicles.length : 0;
  const pedestrianCount = Array.isArray(state?.pedestrians) ? state.pedestrians.length : 0;
  return `${renderTimestamp}:${simTime}:${phase}:${intersectionId}:${playbackFrameIndex}:${vehicleCount}:${pedestrianCount}`;
}

function isPlaybackState(state) {
  return state?.playback?.active === true || state?.flow_state === 'PLAYING_BACK';
}

function isLiveState(state) {
  return state?.render_mode === 'live' || state?.flow_state === 'LIVE_RUNNING';
}

function resolvePlaybackUpdateIntervalMs(nextState, previousLiveState = null) {
  const currentTime = Number(nextState?.time || 0);
  const previousTime = Number(previousLiveState?.time || 0);
  const frameDeltaMs = previousLiveState ? Math.max(0, (currentTime - previousTime) * 1000) : 0;
  const stepLengthMs = Math.max(1, Number(nextState?.step_length || 0.1) * 1000);
  const expectedMs = frameDeltaMs > 0 ? frameDeltaMs : stepLengthMs;
  if (!Number.isFinite(expectedMs) || expectedMs <= 0) {
    return SNAPSHOT_INTERVAL_FALLBACK_MS;
  }
  return clamp(expectedMs, PLAYBACK_EXPECTED_UPDATE_MIN_MS, PLAYBACK_EXPECTED_UPDATE_MAX_MS);
}

function resolveExpectedUpdateIntervalMs(nextState, now, previousLiveState = null) {
  if (isPlaybackState(nextState)) {
    return resolvePlaybackUpdateIntervalMs(nextState, previousLiveState);
  }
  if (stateTransitionTime <= 0) return 1000;
  const measuredIntervalMs = Math.max(16, now - stateTransitionTime);
  if (!Number.isFinite(measuredIntervalMs)) return 1000;
  if (isLiveState(nextState)) {
    return clamp(measuredIntervalMs * 1.03, LIVE_EXPECTED_UPDATE_MIN_MS, LIVE_EXPECTED_UPDATE_MAX_MS);
  }
  return clamp(measuredIntervalMs * 1.10, 200, 2500);
}

function getCanvasDpr() {
  return Math.min(window.devicePixelRatio || 1, MAX_CANVAS_DPR);
}

function isViewportVisible(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return false;
  const computedStyle = window.getComputedStyle(container);
  return computedStyle.display !== 'none' && computedStyle.visibility !== 'hidden';
}

function isDashboardPath() {
  const normalizedPath = String(window.location?.pathname || '').replace(/\/$/, '') || '/';
  return normalizedPath === '/dashboard';
}

function isRenderStreamFresh() {
  return Date.now() < renderStreamActiveUntil;
}

function stopRenderStream() {
  if (renderStream) {
    renderStream.close();
    renderStream = null;
  }
  renderStreamActiveUntil = 0;
  lastStreamSequence = -1;
}

function startRenderStream() {
  if (renderStream || !window.EventSource || !isDashboardPath()) return;

  renderStream = new EventSource(RENDER_STREAM_URL);
  renderStream.addEventListener('frame', (event) => {
    try {
      const frame = JSON.parse(event.data || '{}');
      const sequence = Number(frame.sequence ?? -1);
      if (Number.isFinite(sequence) && sequence <= lastStreamSequence) return;
      if (Number.isFinite(sequence)) lastStreamSequence = sequence;
      renderStreamActiveUntil = Date.now() + STREAM_FALLBACK_GRACE_MS;
      update(frame);
    } catch (error) {
      console.warn('[SmartFlow2D] Render stream frame rejected:', error);
    }
  });
  renderStream.onerror = () => {
    renderStreamActiveUntil = 0;
    if (!isDashboardPath()) stopRenderStream();
  };
}

function setLoadingMessageVisible(isVisible) {
  const loading = document.getElementById('canvas-loading-msg');
  if (loading) {
    loading.style.display = isVisible ? 'flex' : 'none';
  }
}

function buildVisualNetworkUrl(intersectionId = '') {
  const normalizedIntersectionId = String(intersectionId || '').trim().toLowerCase();
  if (!normalizedIntersectionId) return VISUAL_NETWORK_URL;
  return `${VISUAL_NETWORK_URL}?intersection_id=${encodeURIComponent(normalizedIntersectionId)}`;
}

function predictVehiclePose(vehicle, predictionMs, fallbackX, fallbackY, fallbackAngle = 0) {
  const speed = Number(vehicle?.speed || 0);
  if (!Number.isFinite(speed) || speed <= 0.05 || vehicle?.stopped) {
    return {
      x: Number(fallbackX),
      y: Number(fallbackY),
      angle: Number(fallbackAngle || 0),
    };
  }

  const predictionSeconds = clamp(predictionMs, 0, MAX_PREDICTION_MS) / 1000;
  const radians = Number(fallbackAngle || 0) * Math.PI / 180;
  // SUMO angle 0 is North (+Y). Wait! toPixel converts y based on sumoOrigin.
  // In SUMO coordinates:
  // dx = sin(radians) * distance
  // dy = cos(radians) * distance
  const distance = speed * predictionSeconds;
  return {
    x: Number(fallbackX) + (Math.sin(radians) * distance),
    y: Number(fallbackY) + (Math.cos(radians) * distance),
    angle: Number(fallbackAngle || 0),
  };
}

function predictVehicleOnLane(vehicle, predictionMs, fallbackX, fallbackY, fallbackAngle = 0) {
  const laneId = String(vehicle?.lane_id || '');
  if (!laneId) {
    return {
      x: Number(fallbackX),
      y: Number(fallbackY),
      angle: Number(fallbackAngle || 0),
    };
  }

  const speed = Number(vehicle?.speed || 0);
  const lanePosition = Number(vehicle?.lane_position);
  if (!Number.isFinite(speed) || speed <= 0.05 || !Number.isFinite(lanePosition) || vehicle?.stopped) {
    return {
      x: Number(fallbackX),
      y: Number(fallbackY),
      angle: Number(fallbackAngle || 0),
    };
  }

  const projectedLanePosition = lanePosition + (speed * (clamp(predictionMs, 0, LIVE_LATE_FRAME_CARRY_MS) / 1000));
  return sampleLanePoint(laneId, projectedLanePosition, fallbackX, fallbackY, fallbackAngle);
}



// ── Geometry Generators ──────────────────────────────────────────

/**
 * Given a polyline (array of {x,y}) and a width, generate a closed polygon
 * representing the thick lane surface.
 */
function expandLaneToPolygon(shape, width) {
  if (!shape || shape.length < 2) return [];
  const halfWidth = width / 2;
  const leftEdge = [];
  const rightEdge = [];
  
  for (let i = 0; i < shape.length; i++) {
    let dx, dy;
    if (i === 0) {
      dx = shape[1].x - shape[0].x;
      dy = shape[1].y - shape[0].y;
    } else if (i === shape.length - 1) {
      dx = shape[i].x - shape[i - 1].x;
      dy = shape[i].y - shape[i - 1].y;
    } else {
      // Average the direction of the two adjacent segments
      const dx1 = shape[i].x - shape[i-1].x;
      const dy1 = shape[i].y - shape[i-1].y;
      const dx2 = shape[i+1].x - shape[i].x;
      const dy2 = shape[i+1].y - shape[i].y;
      
      const len1 = Math.sqrt(dx1*dx1 + dy1*dy1);
      const len2 = Math.sqrt(dx2*dx2 + dy2*dy2);
      
      dx = (dx1/len1 + dx2/len2);
      dy = (dy1/len1 + dy2/len2);
    }
    
    const len = Math.sqrt(dx*dx + dy*dy);
    if (len === 0) continue;
    
    // Normal vector
    const nx = -dy / len;
    const ny = dx / len;
    
    leftEdge.push({
      x: shape[i].x + nx * halfWidth,
      y: shape[i].y + ny * halfWidth
    });
    
    // Right edge is built in reverse later to form a loop
    rightEdge.unshift({
      x: shape[i].x - nx * halfWidth,
      y: shape[i].y - ny * halfWidth
    });
  }
  
  return leftEdge.concat(rightEdge);
}

// ── Drawing Primitives ───────────────────────────────────────────

function drawPolygon(ctxToUse, shape, fillColor, strokeColor = null, lineWidth = 1) {
  if (!shape || shape.length < 3) return;
  ctxToUse.beginPath();
  const p0 = toPixel(shape[0].x, shape[0].y);
  ctxToUse.moveTo(p0.x, p0.y);
  for (let i = 1; i < shape.length; i++) {
    const p = toPixel(shape[i].x, shape[i].y);
    ctxToUse.lineTo(p.x, p.y);
  }
  ctxToUse.closePath();
  if (fillColor) {
    ctxToUse.fillStyle = fillColor;
    ctxToUse.fill();
  }
  if (strokeColor) {
    ctxToUse.strokeStyle = strokeColor;
    ctxToUse.lineWidth = lineWidth;
    ctxToUse.stroke();
  }
}

function drawPolyline(ctxToUse, shape, color, width, isDashed = false) {
  if (!shape || shape.length < 2) return;
  ctxToUse.beginPath();
  const p0 = toPixel(shape[0].x, shape[0].y);
  ctxToUse.moveTo(p0.x, p0.y);
  for (let i = 1; i < shape.length; i++) {
    const p = toPixel(shape[i].x, shape[i].y);
    ctxToUse.lineTo(p.x, p.y);
  }
  ctxToUse.strokeStyle = color;
  ctxToUse.lineWidth = width;
  ctxToUse.lineCap = 'butt';
  ctxToUse.lineJoin = 'miter';
  if (isDashed) {
    ctxToUse.setLineDash([T.scale * 2, T.scale * 2]); // roughly 2m dashes
  } else {
    ctxToUse.setLineDash([]);
  }
  ctxToUse.stroke();
  ctxToUse.setLineDash([]); // Reset
}

// ── Static Resource Drawing ──────────────────────────────────────

function drawCrosswalk(ctxToUse, lane) {
  const shape = lane.shape || [];
  if (shape.length < 2) return;
  
  const width = lane.width || 4;
  const p1 = toPixel(shape[0].x, shape[0].y);
  const p2 = toPixel(shape[shape.length - 1].x, shape[shape.length - 1].y);
  
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const pixelLen = Math.sqrt(dx * dx + dy * dy);
  if (pixelLen < 1) return;
  
  // Calculate physical length in SUMO coords for spacing
  const sumodx = shape[shape.length-1].x - shape[0].x;
  const sumody = shape[shape.length-1].y - shape[0].y;
  const sumoLen = Math.sqrt(sumodx*sumodx + sumody*sumody);
  
  // SUMO zebra stripes: white bars parallel to lane direction
  const barWidthSumo = 0.5; // 0.5m wide white bars
  const gapSumo = 0.5;      // 0.5m gaps
  
  const count = Math.floor(sumoLen / (barWidthSumo + gapSumo));
  const pixelWidth = width * T.scale;
  const pixelBarWidth = barWidthSumo * T.scale;
  
  ctxToUse.fillStyle = C.crosswalk;
  for (let i = 0; i < count; i++) {
    // Start slightly offset so we don't draw exactly on the edge
    const t = ((i * (barWidthSumo + gapSumo)) + (barWidthSumo/2)) / sumoLen;
    if (t > 1) break;
    
    const cx = p1.x + dx * t;
    const cy = p1.y + dy * t;
    
    ctxToUse.save();
    ctxToUse.translate(cx, cy);
    ctxToUse.rotate(Math.atan2(dy, dx));
    // Draw a bar across the width of the crossing
    ctxToUse.fillRect(-pixelBarWidth/2, -pixelWidth/2, pixelBarWidth, pixelWidth);
    ctxToUse.restore();
  }
}

// Helper to extrapolate the ends of external roads visually off-screen
function extrapolateLaneShape(shape, road, distance = 1000) {
  if (!shape || shape.length < 2) return shape;
  const newShape = [...shape];
  
  if (road.toward_intersection) {
    const p0 = shape[0], p1 = shape[1];
    const dx = p0.x - p1.x, dy = p0.y - p1.y;
    const len = Math.hypot(dx, dy);
    if (len > 0) {
      newShape[0] = { x: p0.x + (dx/len)*distance, y: p0.y + (dy/len)*distance };
    }
  }
  if (road.away_from_intersection) {
    const pN = shape[shape.length - 1], pN_1 = shape[shape.length - 2];
    const dx = pN.x - pN_1.x, dy = pN.y - pN_1.y;
    const len = Math.hypot(dx, dy);
    if (len > 0) {
      newShape[shape.length - 1] = { x: pN.x + (dx/len)*distance, y: pN.y + (dy/len)*distance };
    }
  }
  return newShape;
}

// ── Draw static geometry to offscreen canvas ─────────────────────
function isTagum1Network() {
  const sourceNet = String(network?.source_net || '').toLowerCase();
  const scopeMode = String(network?.scope?.mode || '').toLowerCase();
  const intersectionId = String(currentNetworkIntersectionId || currentState?.intersection_id || '').toLowerCase();
  return (
    intersectionId === 'tagum_1' ||
    sourceNet.includes('tagum1') ||
    scopeMode.includes('tagum_j1')
  );
}

function drawPolygons(ctxToUse) {
  for (const poly of network.polygons || []) {
    if (!poly.shape || poly.shape.length < 3) continue;
    
    // Base shadow
    ctxToUse.save();
    const pixelTransform = toPixel(0, 0); // we use scale
    ctxToUse.translate(T.scale * 0.45, T.scale * 0.55);
    drawPolygon(ctxToUse, poly.shape, 'rgba(9, 18, 24, 0.24)', null);
    ctxToUse.restore();

    // Building body
    let color = poly.color;
    if (!color || color === '#808080' || color === 'red') {
      // Pick a random nice color based on id hash if it's default
      const palette = ['#526b7a', '#7a8f55', '#9b7352', '#a26455', '#1f5f7a', '#8b6f9f', '#4b6b5a', '#8c7d55'];
      color = palette[hashStringToIndex(poly.id, palette.length)];
    }
    drawPolygon(ctxToUse, poly.shape, color, 'rgba(8, 18, 24, 0.55)', Math.max(1, T.scale * 0.08));

    // Calculate centroid for roof shrinking
    let cx = 0, cy = 0, minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const p of poly.shape) { 
      cx += p.x; cy += p.y; 
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }
    cx /= poly.shape.length;
    cy /= poly.shape.length;

    // Shrink towards centroid for roof effect
    const roofScale = 0.82;
    const roofShape = poly.shape.map(p => ({
      x: cx + (p.x - cx) * roofScale,
      y: cy + (p.y - cy) * roofScale
    }));

    // Draw roof darkening
    drawPolygon(ctxToUse, roofShape, 'rgba(0, 0, 0, 0.35)', 'rgba(255, 255, 255, 0.16)', Math.max(1, T.scale * 0.06));

    // Draw procedural windows/skylights
    ctxToUse.save();
    // Draw a subtle "elevator shaft" or HVAC unit near the centroid to break up the flat roof
    const centerPixel = toPixel(cx, cy);
    ctxToUse.translate(centerPixel.x, centerPixel.y);
    let dx = poly.shape[1].x - poly.shape[0].x;
    let dy = poly.shape[1].y - poly.shape[0].y;
    ctxToUse.rotate(-Math.atan2(dy, dx));
    
    ctxToUse.fillStyle = 'rgba(18, 30, 38, 0.4)';
    const shaftW = 3.0 * T.scale;
    const shaftH = 2.0 * T.scale;
    if (Math.abs(maxX - minX) > 5 && Math.abs(maxY - minY) > 5) {
       ctxToUse.fillRect(-shaftW/2, -shaftH/2, shaftW, shaftH);
       ctxToUse.fillStyle = 'rgba(255, 255, 255, 0.06)';
       ctxToUse.fillRect(-shaftW/2 + 0.5*T.scale, -shaftH/2 - 1.5*T.scale, 1.5*T.scale, 1.2*T.scale);
    }
    ctxToUse.restore();
  }
}

function buildStaticLayer() {
  if (!network || !ctx) return;

  const cw = T.cw;
  const ch = T.ch;
  buildLaneGeometryCache(network);

  bgCanvas = document.createElement('canvas');
  bgCanvas.width = cw;
  bgCanvas.height = ch;
  const bg = bgCanvas.getContext('2d');

  // Background - SUMO green grass
  bg.fillStyle = C.bg;
  bg.fillRect(0, 0, cw, ch);
  drawPolygons(bg);

  // --- Roads & Sidewalks ---
  for (const road of network.roads || []) {
    // Process sidewalks first (drawn underneath so roads cover inner edges cleanly)
    for (const lane of road.lanes || []) {
      const isPed = String(lane.allow || '').includes('pedestrian');
      if (isPed) {
        const extShape = extrapolateLaneShape(lane.shape, road);
        const poly = expandLaneToPolygon(extShape, lane.width || 2.0);
        drawPolygon(bg, poly, C.sidewalk, C.edgeLine, 1.5);
      }
    }
    
    // Process vehicle lanes
    let prevVehLaneShape = null;
    for (const lane of road.lanes || []) {
      const isPed = String(lane.allow || '').includes('pedestrian');
      if (!isPed) {
        // Draw filled road surface
        const extShape = extrapolateLaneShape(lane.shape, road);
        const poly = expandLaneToPolygon(extShape, lane.width || 3.2);
        drawPolygon(bg, poly, C.road, null);
        
        // Draw lane separator if there was a previous vehicle lane
        // SUMO draws dashed white lines between lanes flowing in the same direction
        if (prevVehLaneShape) {
          // Calculate the midpoint line between the two lane centerlines
          const sepShape = [];
          const minLen = Math.min(extShape.length, prevVehLaneShape.length);
          for (let i = 0; i < minLen; i++) {
            sepShape.push({
              x: (extShape[i].x + prevVehLaneShape[i].x) / 2,
              y: (extShape[i].y + prevVehLaneShape[i].y) / 2
            });
          }
          drawPolyline(bg, sepShape, C.laneLine, Math.max(1, T.scale * 0.15), true);
        }
        prevVehLaneShape = extShape;
      }
    }
  }

  // --- Internal Junction Lanes ---
  for (const road of network.internal_lanes || []) {
    for (const lane of road.lanes || []) {
      const isPed = String(lane.allow || '').includes('pedestrian');
      const width = lane.width || (isPed ? 2.0 : 3.0);
      const poly = expandLaneToPolygon(lane.shape, width);
      drawPolygon(bg, poly, isPed ? C.sidewalk : C.internalLane, null);
    }
  }

  // --- Junction Fill ---
  const signals = network.signals || [];
  if (signals.length > 0 && signals[0].shape) {
    drawPolygon(bg, signals[0].shape, C.road, null);
  }

  // --- Walking Areas ---
  for (const area of network.walking_areas || []) {
    for (const lane of area.lanes || []) {
      drawPolygon(bg, lane.shape, C.sidewalk, C.edgeLine, 1.5);
    }
  }

  // --- Crosswalks ---
  for (const crossing of network.crossings || []) {
    for (const lane of crossing.lanes || []) {
      drawCrosswalk(bg, lane);
    }
  }
}

// ── Dynamic Resource Drawing ──────────────────────────────────────

function drawRoundedRect(ctxToUse, x, y, width, height, radius) {
  const r = Math.min(radius, Math.abs(width) / 2, Math.abs(height) / 2);
  ctxToUse.beginPath();
  ctxToUse.moveTo(x + r, y);
  ctxToUse.lineTo(x + width - r, y);
  ctxToUse.quadraticCurveTo(x + width, y, x + width, y + r);
  ctxToUse.lineTo(x + width, y + height - r);
  ctxToUse.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctxToUse.lineTo(x + r, y + height);
  ctxToUse.quadraticCurveTo(x, y + height, x, y + height - r);
  ctxToUse.lineTo(x, y + r);
  ctxToUse.quadraticCurveTo(x, y, x + r, y);
  ctxToUse.closePath();
}

function drawVehicle(ctxToUse, x, y, sumoAngle, visualType, isEmergency, flashState, lengthMeters = 4.5, widthMeters = 1.8, vehicleId = '') {
  const p = toPixel(x, y);
  // SUMO angle is clockwise from North. Canvas angle is clockwise from East.
  // Wait, SUMO angle: 0 = North, 90 = East.
  // Canvas angle: 0 = East, 90 = South (since +Y is down).
  // So: Angle mapping: canvasAngle = SUMO_Angle - 90 deg.
  // Let's verify: SUMO 0 (N) -> canvas -90 (Up). Correct since canvas -Y is Up.
  // SUMO 90 (E) -> canvas 0 (Right). Correct.
  // SUMO 180 (S) -> canvas 90 (Down). Correct since canvas +Y is Down.
  const angleRad = (sumoAngle - 90) * Math.PI / 180;
  
  const effectiveLengthMeters = Math.max(3.6, Number(lengthMeters || 4.5));
  const effectiveWidthMeters = Math.max(1.4, Number(widthMeters || 1.8));
  const vLen = effectiveLengthMeters * T.scale;
  const vWid = effectiveWidthMeters * T.scale;
  
  ctxToUse.save();
  ctxToUse.translate(p.x, p.y);
  ctxToUse.rotate(angleRad);
  
  if (isEmergency || visualType === 'ambulance') {
    // Ambulance
    ctxToUse.fillStyle = C.emsWhite;
    ctxToUse.fillRect(-vLen, -vWid/2, vLen, vWid);
    
    // Green Cross on roof
    ctxToUse.fillStyle = C.emsCross;
    const cW = vWid * 0.4;
    const cH = cW * 0.3;
    const cx = -vLen / 2; // Center of vehicle
    ctxToUse.fillRect(cx - cH/2, -cW/2, cH, cW);
    ctxToUse.fillRect(cx - cW/2, -cH/2, cW, cH);
    
    // Lightbar flashing
    const lbW = vWid * 0.8;
    const lbH = vLen * 0.15;
    const lbX = -vLen * 0.25; // near front
    ctxToUse.fillStyle = flashState ? C.emsRed : C.emsBlue;
    ctxToUse.fillRect(lbX - lbH/2, -lbW/2, lbH, lbW);
    
  } else {
    // Standard car: SUMO position is the front bumper, so the nose stays at x=0.
    const bodyTop = -vWid * 0.5;
    const bodyBottom = vWid * 0.5;
    const rearX = -vLen;
    const noseX = 0;
    const shoulderX = -vLen * 0.18;
    const tailInset = Math.max(1.2, vWid * 0.12);
    const noseInset = Math.max(1.4, vWid * 0.18);

    ctxToUse.beginPath();
    ctxToUse.moveTo(rearX + tailInset, bodyTop);
    ctxToUse.lineTo(shoulderX, bodyTop);
    ctxToUse.quadraticCurveTo(noseX - noseInset, bodyTop, noseX, -vWid * 0.2);
    ctxToUse.lineTo(noseX, vWid * 0.2);
    ctxToUse.quadraticCurveTo(noseX - noseInset, bodyBottom, shoulderX, bodyBottom);
    ctxToUse.lineTo(rearX + tailInset, bodyBottom);
    ctxToUse.quadraticCurveTo(rearX, bodyBottom, rearX, bodyBottom - tailInset);
    ctxToUse.lineTo(rearX, bodyTop + tailInset);
    ctxToUse.quadraticCurveTo(rearX, bodyTop, rearX + tailInset, bodyTop);
    ctxToUse.closePath();
    ctxToUse.fillStyle = getVehicleColor(vehicleId);
    ctxToUse.fill();
    ctxToUse.lineWidth = Math.max(1, T.scale * 0.12);
    ctxToUse.strokeStyle = 'rgba(82, 61, 0, 0.75)';
    ctxToUse.stroke();

    const wheelRadius = Math.max(1.1, vWid * 0.13);
    ctxToUse.fillStyle = 'rgba(20,20,20,0.86)';
    for (const wheelX of [-vLen * 0.78, -vLen * 0.26]) {
      ctxToUse.beginPath();
      ctxToUse.arc(wheelX, bodyTop + wheelRadius * 0.35, wheelRadius, 0, Math.PI * 2);
      ctxToUse.arc(wheelX, bodyBottom - wheelRadius * 0.35, wheelRadius, 0, Math.PI * 2);
      ctxToUse.fill();
    }

    const glassColor = 'rgba(26, 50, 70, 0.72)';
    ctxToUse.fillStyle = glassColor;
    drawRoundedRect(ctxToUse, -vLen * 0.36, -vWid * 0.36, vLen * 0.16, vWid * 0.72, Math.max(1, vWid * 0.1));
    ctxToUse.fill();
    drawRoundedRect(ctxToUse, -vLen * 0.64, -vWid * 0.32, vLen * 0.16, vWid * 0.64, Math.max(1, vWid * 0.1));
    ctxToUse.fill();

    ctxToUse.fillStyle = 'rgba(255,255,190,0.85)';
    ctxToUse.fillRect(-vLen * 0.05, -vWid * 0.28, Math.max(1, vLen * 0.035), vWid * 0.18);
    ctxToUse.fillRect(-vLen * 0.05, vWid * 0.1, Math.max(1, vLen * 0.035), vWid * 0.18);
  }
  
  ctxToUse.restore();
}

function drawPedestrian(ctxToUse, x, y) {
  const p = toPixel(x, y);
  const r = 0.5 * T.scale; // 0.5m radius
  ctxToUse.fillStyle = C.pedestrian;
  ctxToUse.beginPath();
  ctxToUse.arc(p.x, p.y, r, 0, Math.PI * 2);
  ctxToUse.fill();
}

function drawSignalBar(ctxToUse, lane, color) {
  if (!lane.shape || lane.shape.length < 2) return;
  // Signal is at the END of the lane
  const p1Sumo = lane.shape[lane.shape.length - 2];
  const p2Sumo = lane.shape[lane.shape.length - 1];
  
  const p1 = toPixel(p1Sumo.x, p1Sumo.y);
  const p2 = toPixel(p2Sumo.x, p2Sumo.y);
  
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.sqrt(dx*dx + dy*dy);
  if (len < 1) return;
  
  // Perpendicular vector for the bar width
  const nx = -dy / len;
  const ny = dx / len;
  
  const widthPx = (lane.width || 3.2) * T.scale;
  
  ctxToUse.beginPath();
  // Draw across the end of the lane
  ctxToUse.moveTo(p2.x - nx * widthPx/2, p2.y - ny * widthPx/2);
  ctxToUse.lineTo(p2.x + nx * widthPx/2, p2.y + ny * widthPx/2);
  
  ctxToUse.strokeStyle = color;
  // Make it a thick bar (approx 1m wide)
  ctxToUse.lineWidth = Math.max(2, 1.0 * T.scale);
  ctxToUse.lineCap = 'butt';
  ctxToUse.stroke();
}

function resolveSignalState(signalGroup, trafficLights, fallbackNsState, fallbackEwState) {
  const trafficLightState = trafficLights?.[signalGroup.signal_id];
  if (trafficLightState?.state && Array.isArray(signalGroup.link_indices) && signalGroup.link_indices.length > 0) {
    let bestState = 'r';
    for (const index of signalGroup.link_indices) {
      if (index >= trafficLightState.state.length) continue;
      const tlsChar = trafficLightState.state[index].toLowerCase();
      if (tlsChar === 'g') bestState = 'g';
      else if (tlsChar === 'y' && bestState !== 'g') bestState = 'y';
    }
    if (bestState === 'g') return 'green';
    if (bestState === 'y') return 'yellow';
    return 'red';
  }

  const approachId = String(signalGroup.from_edge_id || signalGroup.lane_id || '').toLowerCase();
  const directionalState = approachId.includes('north') || approachId.includes('south')
    ? fallbackNsState
    : fallbackEwState;
  return directionalState || 'red';
}

function drawConstraintMarker(ctxToUse, x, y) {
  const p = toPixel(x, y);
  const size = 6 * T.scale;
  ctxToUse.strokeStyle = C.constraint;
  ctxToUse.lineWidth = Math.max(2, T.scale * 0.5);
  ctxToUse.beginPath();
  ctxToUse.moveTo(p.x - size, p.y - size);
  ctxToUse.lineTo(p.x + size, p.y + size);
  ctxToUse.moveTo(p.x + size, p.y - size);
  ctxToUse.lineTo(p.x - size, p.y + size);
  ctxToUse.stroke();
}

// ── Draw dynamic entities on main canvas ─────────────────────────
function drawDynamicLayer(now = performance.now()) {
  if (!ctx || !network) return;

  const state = currentState;
  const cw = T.cw;
  const ch = T.ch;

  // Clear canvas
  ctx.clearRect(0, 0, cw, ch);

  // Draw static layer
  if (bgCanvas) {
    ctx.drawImage(bgCanvas, 0, 0);
  }

  // --- Traffic Signal Bars (per signal group) ---
  for (const group of network.signal_groups || []) {
    if (!group.stop_line || group.stop_line.length < 2) continue;
    if (group.kind === 'pedestrian') continue; // Optional: skip pedestrian signals for now or draw them differently

    const signalState = resolveSignalState(group, state.traffic_lights, state.ns_state, state.ew_state);
    let sigColor = C.signalRed;
    if (signalState === 'green') sigColor = C.signalGreen;
    else if (signalState === 'yellow') sigColor = C.signalYellow;

    const p1 = toPixel(group.stop_line[0].x, group.stop_line[0].y);
    const p2 = toPixel(group.stop_line[1].x, group.stop_line[1].y);

    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = sigColor;
    ctx.lineWidth = Math.max(3, 1.2 * T.scale);
    ctx.lineCap = 'butt';
    ctx.stroke();
  }

  // --- Pedestrians ---
  for (const ped of (state.pedestrians || [])) {
    const x = Number(ped.x);
    const y = Number(ped.y);
    if (!isInsideBounds(x, y)) continue;
    drawPedestrian(ctx, x, y);
  }

  // --- Vehicles ---
  const flashOn = Math.floor(now / 250) % 2 === 0;

  for (const vehicle of (state.vehicles || [])) {
    let x = Number(vehicle.x);
    let y = Number(vehicle.y);
    let angle = Number(vehicle.angle || 0);

    const lanePose = sampleLanePoint(vehicle.lane_id, vehicle.lane_position, x, y, angle);
    if (lanePose.projected) {
      x = lanePose.x;
      y = lanePose.y;
      angle = lanePose.angle;
    }
    
    if (!isInsideBounds(x, y)) continue;
    const isEm = Boolean(vehicle.emergency) || vehicle.visual_type === 'ambulance';
    drawVehicle(
      ctx,
      x, y, angle, 
      vehicle.visual_type || 'car', 
      isEm, 
      flashOn,
      vehicle.length,
      vehicle.width,
      vehicle.id,
    );
  }
  
  // --- Constraint Marker ---
  const visual = state.visual || {};
  const marker = visual.constraint_marker;
  if (marker && marker.active && isInsideBounds(Number(marker.x), Number(marker.y))) {
    drawConstraintMarker(ctx, Number(marker.x), Number(marker.y));
  }
}

// ── Main render loop ─────────────────────────────────────────────
function loop() {
  if (disposed) return;
  animFrameId = requestAnimationFrame(loop);

  const isVisible = isViewportVisible('canvas-container');
  if (!isVisible) {
    viewportWasVisible = false;
    return;
  }

  if (!viewportWasVisible) {
    viewportWasVisible = true;
    needsRedraw = true;
  }

  const now = performance.now();
  if (!needsRedraw && now - lastDrawTime < FRAME_INTERVAL_MS) {
    return;
  }

  const hasEms = currentState.vehicles && currentState.vehicles.some(v => v.emergency || v.visual_type === 'ambulance');
  
  if (needsRedraw || hasEms) {
    drawDynamicLayer(now);
    needsRedraw = false;
    lastDrawTime = now;
  }
}

// ── Resize handler ───────────────────────────────────────────────
function onResize() {
  const container = document.getElementById('canvas-container');
  if (!container || !canvas) return;
  const rect = container.getBoundingClientRect();
  const w = Math.floor(rect.width) || 640;
  const h = Math.floor(rect.height) || 480;
  if (w === T.cw && h === T.ch) return;

  // Resize canvas backing store to match CSS size
  const dpr = getCanvasDpr();
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  if (network) {
    configureTransform(network, w, h);
    buildStaticLayer();
  }
  T.cw = w;
  T.ch = h;
  needsRedraw = true;
}

// ── Initialisation ───────────────────────────────────────────────
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
    if (!document.getElementById('canvas-container')) return;
    init();
    if (initialized) stopInitObserver();
  });
  initObserver.observe(document.body, { childList: true, subtree: true });
}

function init(containerEl) {
  if (initialized) {
    const target = containerEl || document.getElementById('canvas-container');
    if (canvas && target && !target.contains(canvas)) {
      const loading = document.getElementById('canvas-loading-msg');
      if (loading) loading.style.display = 'none';
      target.appendChild(canvas);
      onResize();
    }
    startRenderStream();
    return true;
  }

  const container = containerEl || document.getElementById('canvas-container');
  if (!container) {
    scheduleInitWhenContainerAvailable();
    return false;
  }
  stopInitObserver();
  startRenderStream();

  canvas = document.createElement('canvas');
  canvas.className = 'traffic-canvas-element';
  canvas.id = 'traffic-canvas';
  // Use crisp image rendering for the tactical map look
  canvas.style.imageRendering = 'auto'; 
  container.appendChild(canvas);

  const dpr = getCanvasDpr();
  const rect = container.getBoundingClientRect();
  const w = Math.floor(rect.width) || 640;
  const h = Math.floor(rect.height) || 480;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';

  ctx = canvas.getContext('2d', { alpha: false }); // Optimize, no transparency needed
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  T.cw = w;
  T.ch = h;

  initialized = true;
  disposed = false;

  window.addEventListener('resize', onResize);
  onResize();

  // Load network geometry
  reloadNetwork(currentState.intersection_id).catch((error) => {
    console.warn('[SmartFlow2D] Failed to load visual network:', error);
  });

  loop();
  return true;
}

async function loadNetwork(intersectionId = '') {
  const rawNetwork = await fetchJsonWithLimit(
    buildVisualNetworkUrl(intersectionId),
    'Visual network',
  );
  return sanitizeNetworkPayload(rawNetwork);
}

function reloadNetwork(intersectionId = '') {
  const normalizedIntersectionId = String(intersectionId || '').trim().toLowerCase();
  if (networkLoadPromise && normalizedIntersectionId === pendingNetworkIntersectionId) {
    return networkLoadPromise;
  }

  pendingNetworkIntersectionId = normalizedIntersectionId;
  ready = false;
  setLoadingMessageVisible(true);

  networkLoadPromise = loadNetwork(normalizedIntersectionId)
    .then((loadedNetwork) => {
      if (pendingNetworkIntersectionId !== normalizedIntersectionId) {
        return;
      }
      network = loadedNetwork;
      currentNetworkIntersectionId = normalizedIntersectionId;
      configureTransform(network, T.cw, T.ch);
      buildStaticLayer();
      ready = true;
      needsRedraw = true;
      setLoadingMessageVisible(false);
    })
    .catch((error) => {
      if (pendingNetworkIntersectionId !== normalizedIntersectionId) {
        return;
      }
      console.warn('[SmartFlow2D] Failed to load visual network:', error);
      ready = true;
      setLoadingMessageVisible(false);
    })
    .finally(() => {
      if (pendingNetworkIntersectionId === normalizedIntersectionId) {
        networkLoadPromise = null;
        pendingNetworkIntersectionId = '';
      }
    });

  return networkLoadPromise;
}

// ── Public API ───────────────────────────────────────────────────
function update(state) {
  const nextState = sanitizeLiveState(state);
  if (!init()) {
    currentState = nextState;
    needsRedraw = true;
    return;
  }
  const nextIntersectionId = String(nextState?.intersection_id || '').trim().toLowerCase();
  if (
    nextIntersectionId &&
    nextIntersectionId !== currentNetworkIntersectionId &&
    nextIntersectionId !== pendingNetworkIntersectionId
  ) {
    reloadNetwork(nextIntersectionId).catch((error) => {
      console.warn('[SmartFlow2D] Failed to switch visual network:', error);
    });
  }
  const snapshotKey = snapshotKeyForState(nextState);
  if (snapshotKey && snapshotKey === lastSnapshotKey) {
    return;
  }

  const now = performance.now();
  previousState = currentState;
  previousVehiclesById = new Map((previousState?.vehicles || []).map((vehicle) => [vehicle.id, vehicle]));
  previousPedestriansById = new Map((previousState?.pedestrians || []).map((pedestrian) => [pedestrian.id, pedestrian]));
  currentState = nextState;
  expectedUpdateIntervalMs = resolveExpectedUpdateIntervalMs(nextState, now, previousState);
  const playbackJustStarted = isPlaybackState(nextState) && (!isPlaybackState(previousState) || previousState?.status !== 'running');
  if (playbackJustStarted) {
    playbackWarmStartUntil = now + Math.min(expectedUpdateIntervalMs * 0.8, 80);
  }
  stateTransitionTime = now;
  if (playbackJustStarted) {
    stateTransitionTime = now - Math.min(expectedUpdateIntervalMs * 0.2, 20);
  }
  lastSnapshotKey = snapshotKey;
  needsRedraw = true;
}

function dispose() {
  disposed = true;
  if (animFrameId) cancelAnimationFrame(animFrameId);
  window.removeEventListener('resize', onResize);
  if (canvas && canvas.parentNode) {
    canvas.parentNode.removeChild(canvas);
  }
  canvas = null;
  ctx = null;
  bgCanvas = null;
  laneGeometryById = new Map();
  previousState = null;
  previousVehiclesById = new Map();
  previousPedestriansById = new Map();
  currentState = sanitizeLiveState({ status: 'stopped', step_length: 0.1 });
  currentNetworkIntersectionId = '';
  pendingNetworkIntersectionId = '';
  networkLoadPromise = null;
  stopInitObserver();
  stopRenderStream();
  stateTransitionTime = 0;
  expectedUpdateIntervalMs = SNAPSHOT_INTERVAL_FALLBACK_MS;
  playbackWarmStartUntil = 0;
  lastSnapshotKey = '';
  lastDrawTime = 0;
  viewportWasVisible = false;
  initialized = false;
  ready = false;
}

function isReady() {
  return ready;
}

export const SmartFlowCanvas2D = { init, update, dispose, isReady };

// Auto-init if container exists
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (!init()) scheduleInitWhenContainerAvailable();
  });
} else {
  if (!init()) scheduleInitWhenContainerAvailable();
}

// Listen for Dash clientside callbacks
document.addEventListener(RENDERER_STATE_EVENT, (e) => {
  if (isRenderStreamFresh()) return;
  if (e.detail) {
    update(e.detail);
  }
});
