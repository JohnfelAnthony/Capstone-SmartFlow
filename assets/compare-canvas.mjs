/**
 * SMARTFLOW Compare Static Canvas Renderer
 * =======================================
 * Draws two non-animated timeline snapshots for the Compare page using the
 * same 2D visual style as the dashboard canvas.
 */

import {
  fetchJsonWithLimit,
  sanitizeLiveState,
  sanitizeNetworkPayload,
} from '/assets/render-safety.mjs';

const COMPARE_FRAME_EVENT = 'smartflow:compare-frame';
const VISUAL_NETWORK_URL = '/api/visual-network';
const MAX_DPR = 1.25;

const C = {
  bg: '#2e8b00',
  road: '#333333',
  sidewalk: '#999999',
  crosswalk: '#ffffff',
  laneLine: '#ffffff',
  edgeLine: '#cccccc',
  internalLane: '#3e3e3e',
  signalRed: '#ff0000',
  signalGreen: '#00ff00',
  signalYellow: '#ffd84d',
  signalOff: '#333333',
  vehicle: '#ffd700',
  emsWhite: '#ffffff',
  emsCross: '#00ff00',
  emsRed: '#ff0000',
  emsBlue: '#0000ff',
  pedestrian: '#ff8c00',
  constraint: '#ff0000',
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



const SIDES = {
  left: { containerId: 'compare-left-canvas' },
  right: { containerId: 'compare-right-canvas' },
};

const networkCache = new Map();
let latestPayload = null;
let resizeObserver = null;

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

function toIntersectionId(frame) {
  return String(frame?.intersection_id || 'tagum_1').trim().toLowerCase() || 'tagum_1';
}

function buildVisualNetworkUrl(intersectionId) {
  const normalizedId = toIntersectionId({ intersection_id: intersectionId });
  return `${VISUAL_NETWORK_URL}?intersection_id=${encodeURIComponent(normalizedId)}`;
}

async function loadNetwork(intersectionId) {
  const normalizedId = toIntersectionId({ intersection_id: intersectionId });
  if (networkCache.has(normalizedId)) return networkCache.get(normalizedId);

  const loadPromise = fetchJsonWithLimit(
    buildVisualNetworkUrl(normalizedId),
    `compare visual network ${normalizedId}`,
  ).then((rawNetwork) => sanitizeNetworkPayload(rawNetwork));
  networkCache.set(normalizedId, loadPromise);
  return loadPromise;
}

function ensureCanvas(sideKey) {
  const side = SIDES[sideKey];
  const container = document.getElementById(side.containerId);
  if (!container) return null;

  if (!side.canvas || !container.contains(side.canvas)) {
    container.textContent = '';
    side.canvas = document.createElement('canvas');
    side.canvas.className = 'traffic-canvas-element compare-canvas-element';
    container.appendChild(side.canvas);
    side.ctx = side.canvas.getContext('2d', { alpha: false });
  }

  const rect = container.getBoundingClientRect();
  const width = Math.max(320, Math.floor(rect.width || 640));
  const height = Math.max(260, Math.floor(rect.height || 360));
  const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
  const pixelWidth = Math.floor(width * dpr);
  const pixelHeight = Math.floor(height * dpr);

  if (side.canvas.width !== pixelWidth || side.canvas.height !== pixelHeight) {
    side.canvas.width = pixelWidth;
    side.canvas.height = pixelHeight;
    side.canvas.style.width = `${width}px`;
    side.canvas.style.height = `${height}px`;
    side.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  side.width = width;
  side.height = height;
  return side;
}

function configureTransform(networkData, cw, ch) {
  let minX = 0;
  let maxX = 0;
  let minY = 0;
  let maxY = 0;
  let hasJunction = false;

  if (networkData?.signals?.length > 0 && networkData.signals[0].shape) {
    const shape = networkData.signals[0].shape;
    minX = Math.min(...shape.map((point) => point.x));
    maxX = Math.max(...shape.map((point) => point.x));
    minY = Math.min(...shape.map((point) => point.y));
    maxY = Math.max(...shape.map((point) => point.y));
    hasJunction = true;
  }

  if (hasJunction) {
    const margin = 15;
    minX -= margin;
    maxX += margin;
    minY -= margin;
    maxY += margin;
  } else {
    const b = networkData?.bounds || { min_x: -50, min_y: -50, max_x: 50, max_y: 50 };
    minX = b.min_x;
    maxX = b.max_x;
    minY = b.min_y;
    maxY = b.max_y;
  }

  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const pad = 0.90;
  const scale = Math.min((cw * pad) / spanX, (ch * pad) / spanY);
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  return {
    scale,
    ox: cw / 2 - centerX * scale,
    oy: ch / 2 - (-centerY * scale),
    cw,
    ch,
    viewBounds: { min_x: minX, max_x: maxX, min_y: minY, max_y: maxY },
  };
}

function toPixel(transform, sx, sy) {
  return {
    x: Number(sx) * transform.scale + transform.ox,
    y: -Number(sy) * transform.scale + transform.oy,
  };
}

function isInsideBounds(transform, sx, sy) {
  if (!transform.viewBounds) return true;
  const b = transform.viewBounds;
  const buffer = 10;
  return (
    sx >= b.min_x - buffer && sx <= b.max_x + buffer &&
    sy >= b.min_y - buffer && sy <= b.max_y + buffer
  );
}

function expandLaneToPolygon(shape, width) {
  if (!shape || shape.length < 2) return [];
  const halfWidth = width / 2;
  const leftEdge = [];
  const rightEdge = [];

  for (let i = 0; i < shape.length; i += 1) {
    let dx;
    let dy;
    if (i === 0) {
      dx = shape[1].x - shape[0].x;
      dy = shape[1].y - shape[0].y;
    } else if (i === shape.length - 1) {
      dx = shape[i].x - shape[i - 1].x;
      dy = shape[i].y - shape[i - 1].y;
    } else {
      const dx1 = shape[i].x - shape[i - 1].x;
      const dy1 = shape[i].y - shape[i - 1].y;
      const dx2 = shape[i + 1].x - shape[i].x;
      const dy2 = shape[i + 1].y - shape[i].y;
      const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1);
      const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);
      dx = (dx1 / len1) + (dx2 / len2);
      dy = (dy1 / len1) + (dy2 / len2);
    }

    const len = Math.sqrt(dx * dx + dy * dy);
    if (len === 0) continue;
    const nx = -dy / len;
    const ny = dx / len;

    leftEdge.push({
      x: shape[i].x + nx * halfWidth,
      y: shape[i].y + ny * halfWidth,
    });
    rightEdge.unshift({
      x: shape[i].x - nx * halfWidth,
      y: shape[i].y - ny * halfWidth,
    });
  }

  return leftEdge.concat(rightEdge);
}

function drawPolygon(ctx, transform, shape, fillColor, strokeColor = null, lineWidth = 1) {
  if (!shape || shape.length < 3) return;
  ctx.beginPath();
  const p0 = toPixel(transform, shape[0].x, shape[0].y);
  ctx.moveTo(p0.x, p0.y);
  for (let i = 1; i < shape.length; i += 1) {
    const p = toPixel(transform, shape[i].x, shape[i].y);
    ctx.lineTo(p.x, p.y);
  }
  ctx.closePath();
  if (fillColor) {
    ctx.fillStyle = fillColor;
    ctx.fill();
  }
  if (strokeColor) {
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }
}

function drawPolyline(ctx, transform, shape, color, width, isDashed = false) {
  if (!shape || shape.length < 2) return;
  ctx.beginPath();
  const p0 = toPixel(transform, shape[0].x, shape[0].y);
  ctx.moveTo(p0.x, p0.y);
  for (let i = 1; i < shape.length; i += 1) {
    const p = toPixel(transform, shape[i].x, shape[i].y);
    ctx.lineTo(p.x, p.y);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = 'butt';
  ctx.lineJoin = 'miter';
  ctx.setLineDash(isDashed ? [transform.scale * 2, transform.scale * 2] : []);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawCrosswalk(ctx, transform, lane) {
  const shape = lane.shape || [];
  if (shape.length < 2) return;

  const width = lane.width || 4;
  const p1 = toPixel(transform, shape[0].x, shape[0].y);
  const p2 = toPixel(transform, shape[shape.length - 1].x, shape[shape.length - 1].y);
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const pixelLen = Math.sqrt(dx * dx + dy * dy);
  if (pixelLen < 1) return;

  const sumoDx = shape[shape.length - 1].x - shape[0].x;
  const sumoDy = shape[shape.length - 1].y - shape[0].y;
  const sumoLen = Math.sqrt(sumoDx * sumoDx + sumoDy * sumoDy);
  const barWidthSumo = 0.5;
  const gapSumo = 0.5;
  const count = Math.floor(sumoLen / (barWidthSumo + gapSumo));
  const pixelWidth = width * transform.scale;
  const pixelBarWidth = barWidthSumo * transform.scale;

  ctx.fillStyle = C.crosswalk;
  for (let i = 0; i < count; i += 1) {
    const t = ((i * (barWidthSumo + gapSumo)) + (barWidthSumo / 2)) / sumoLen;
    if (t > 1) break;
    const cx = p1.x + dx * t;
    const cy = p1.y + dy * t;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(Math.atan2(dy, dx));
    ctx.fillRect(-pixelBarWidth / 2, -pixelWidth / 2, pixelBarWidth, pixelWidth);
    ctx.restore();
  }
}

function extrapolateLaneShape(shape, road, distance = 1000) {
  if (!shape || shape.length < 2) return shape;
  const newShape = [...shape];

  if (road.toward_intersection) {
    const p0 = shape[0];
    const p1 = shape[1];
    const dx = p0.x - p1.x;
    const dy = p0.y - p1.y;
    const len = Math.hypot(dx, dy);
    if (len > 0) {
      newShape[0] = { x: p0.x + (dx / len) * distance, y: p0.y + (dy / len) * distance };
    }
  }
  if (road.away_from_intersection) {
    const pN = shape[shape.length - 1];
    const pN1 = shape[shape.length - 2];
    const dx = pN.x - pN1.x;
    const dy = pN.y - pN1.y;
    const len = Math.hypot(dx, dy);
    if (len > 0) {
      newShape[shape.length - 1] = {
        x: pN.x + (dx / len) * distance,
        y: pN.y + (dy / len) * distance,
      };
    }
  }
  return newShape;
}

function isTagum1Network(network) {
  const sourceNet = String(network?.source_net || '').toLowerCase();
  const scopeMode = String(network?.scope?.mode || '').toLowerCase();
  return sourceNet.includes('tagum1') || scopeMode.includes('tagum_j1');
}

function drawPolygons(ctx, transform, network) {
  for (const poly of network.polygons || []) {
    if (!poly.shape || poly.shape.length < 3) continue;
    
    // Base shadow
    ctx.save();
    ctx.translate(transform.scale * 0.45, transform.scale * 0.55);
    drawPolygon(ctx, transform, poly.shape, 'rgba(9, 18, 24, 0.24)', null);
    ctx.restore();

    // Building body
    let color = poly.color;
    if (!color || color === '#808080' || color === 'red') {
      const palette = ['#526b7a', '#7a8f55', '#9b7352', '#a26455', '#1f5f7a', '#8b6f9f', '#4b6b5a', '#8c7d55'];
      color = palette[hashStringToIndex(poly.id, palette.length)];
    }
    drawPolygon(ctx, transform, poly.shape, color, 'rgba(8, 18, 24, 0.55)', Math.max(1, transform.scale * 0.08));

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
    drawPolygon(ctx, transform, roofShape, 'rgba(0, 0, 0, 0.35)', 'rgba(255, 255, 255, 0.16)', Math.max(1, transform.scale * 0.06));

    // Draw procedural windows/skylights
    ctx.save();
    // Draw a subtle "elevator shaft" or HVAC unit near the centroid to break up the flat roof
    const centerPixel = toPixel(transform, cx, cy);
    ctx.translate(centerPixel.x, centerPixel.y);
    let dx = poly.shape[1].x - poly.shape[0].x;
    let dy = poly.shape[1].y - poly.shape[0].y;
    ctx.rotate(-Math.atan2(dy, dx));
    
    ctx.fillStyle = 'rgba(18, 30, 38, 0.4)';
    const shaftW = 3.0 * transform.scale;
    const shaftH = 2.0 * transform.scale;
    if (Math.abs(maxX - minX) > 5 && Math.abs(maxY - minY) > 5) {
       ctx.fillRect(-shaftW/2, -shaftH/2, shaftW, shaftH);
       ctx.fillStyle = 'rgba(255, 255, 255, 0.06)';
       ctx.fillRect(-shaftW/2 + 0.5*transform.scale, -shaftH/2 - 1.5*transform.scale, 1.5*transform.scale, 1.2*transform.scale);
    }
    ctx.restore();
  }
}

function drawStaticLayer(ctx, transform, network) {
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, transform.cw, transform.ch);
  drawPolygons(ctx, transform, network);

  for (const road of network.roads || []) {
    for (const lane of road.lanes || []) {
      const isPedestrianLane = String(lane.allow || '').includes('pedestrian');
      if (isPedestrianLane) {
        const extShape = extrapolateLaneShape(lane.shape, road);
        const poly = expandLaneToPolygon(extShape, lane.width || 2.0);
        drawPolygon(ctx, transform, poly, C.sidewalk, C.edgeLine, 1.5);
      }
    }

    let previousVehicleLaneShape = null;
    for (const lane of road.lanes || []) {
      const isPedestrianLane = String(lane.allow || '').includes('pedestrian');
      if (isPedestrianLane) continue;

      const extShape = extrapolateLaneShape(lane.shape, road);
      const poly = expandLaneToPolygon(extShape, lane.width || 3.2);
      drawPolygon(ctx, transform, poly, C.road, null);

      if (previousVehicleLaneShape) {
        const separatorShape = [];
        const minLen = Math.min(extShape.length, previousVehicleLaneShape.length);
        for (let i = 0; i < minLen; i += 1) {
          separatorShape.push({
            x: (extShape[i].x + previousVehicleLaneShape[i].x) / 2,
            y: (extShape[i].y + previousVehicleLaneShape[i].y) / 2,
          });
        }
        drawPolyline(ctx, transform, separatorShape, C.laneLine, Math.max(1, transform.scale * 0.15), true);
      }
      previousVehicleLaneShape = extShape;
    }
  }

  for (const road of network.internal_lanes || []) {
    for (const lane of road.lanes || []) {
      const isPedestrianLane = String(lane.allow || '').includes('pedestrian');
      const width = lane.width || (isPedestrianLane ? 2.0 : 3.0);
      const poly = expandLaneToPolygon(lane.shape, width);
      drawPolygon(ctx, transform, poly, isPedestrianLane ? C.sidewalk : C.internalLane, null);
    }
  }

  const signals = network.signals || [];
  if (signals.length > 0 && signals[0].shape) {
    drawPolygon(ctx, transform, signals[0].shape, C.road, null);
  }

  for (const area of network.walking_areas || []) {
    for (const lane of area.lanes || []) {
      drawPolygon(ctx, transform, lane.shape, C.sidewalk, C.edgeLine, 1.5);
    }
  }

  for (const crossing of network.crossings || []) {
    for (const lane of crossing.lanes || []) {
      drawCrosswalk(ctx, transform, lane);
    }
  }
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

function drawSignals(ctx, transform, network, frame) {
  for (const group of network.signal_groups || []) {
    if (!group.stop_line || group.stop_line.length < 2) continue;
    if (group.kind === 'pedestrian') continue;

    const signalState = resolveSignalState(group, frame.traffic_lights, frame.ns_state, frame.ew_state);
    let sigColor = C.signalRed;
    if (signalState === 'green') sigColor = C.signalGreen;
    else if (signalState === 'yellow') sigColor = C.signalYellow;

    const p1 = toPixel(transform, group.stop_line[0].x, group.stop_line[0].y);
    const p2 = toPixel(transform, group.stop_line[1].x, group.stop_line[1].y);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = sigColor;
    ctx.lineWidth = Math.max(3, 1.2 * transform.scale);
    ctx.lineCap = 'butt';
    ctx.stroke();
  }
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, Math.abs(width) / 2, Math.abs(height) / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawVehicle(ctx, transform, vehicle) {
  const p = toPixel(transform, vehicle.x, vehicle.y);
  const angleRad = (Number(vehicle.angle || 0) - 90) * Math.PI / 180;
  const effectiveLengthMeters = Math.max(3.6, Number(vehicle.length || 4.5));
  const effectiveWidthMeters = Math.max(1.4, Number(vehicle.width || 1.8));
  const vLen = effectiveLengthMeters * transform.scale;
  const vWid = effectiveWidthMeters * transform.scale;
  const isEmergency = Boolean(vehicle.emergency) || vehicle.visual_type === 'ambulance';

  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.rotate(angleRad);

  if (isEmergency) {
    ctx.fillStyle = C.emsWhite;
    ctx.fillRect(-vLen, -vWid / 2, vLen, vWid);

    ctx.fillStyle = C.emsCross;
    const cW = vWid * 0.4;
    const cH = cW * 0.3;
    const cx = -vLen / 2;
    ctx.fillRect(cx - cH / 2, -cW / 2, cH, cW);
    ctx.fillRect(cx - cW / 2, -cH / 2, cW, cH);

    const lbW = vWid * 0.8;
    const lbH = vLen * 0.15;
    const lbX = -vLen * 0.25;
    ctx.fillStyle = C.emsRed;
    ctx.fillRect(lbX - lbH / 2, -lbW / 2, lbH, lbW);
  } else {
    const bodyTop = -vWid * 0.5;
    const bodyBottom = vWid * 0.5;
    const rearX = -vLen;
    const noseX = 0;
    const shoulderX = -vLen * 0.18;
    const tailInset = Math.max(1.2, vWid * 0.12);
    const noseInset = Math.max(1.4, vWid * 0.18);

    ctx.beginPath();
    ctx.moveTo(rearX + tailInset, bodyTop);
    ctx.lineTo(shoulderX, bodyTop);
    ctx.quadraticCurveTo(noseX - noseInset, bodyTop, noseX, -vWid * 0.2);
    ctx.lineTo(noseX, vWid * 0.2);
    ctx.quadraticCurveTo(noseX - noseInset, bodyBottom, shoulderX, bodyBottom);
    ctx.lineTo(rearX + tailInset, bodyBottom);
    ctx.quadraticCurveTo(rearX, bodyBottom, rearX, bodyBottom - tailInset);
    ctx.lineTo(rearX, bodyTop + tailInset);
    ctx.quadraticCurveTo(rearX, bodyTop, rearX + tailInset, bodyTop);
    ctx.closePath();
    ctx.fillStyle = getVehicleColor(vehicle.id);
    ctx.fill();
    ctx.lineWidth = Math.max(1, transform.scale * 0.12);
    ctx.strokeStyle = 'rgba(82, 61, 0, 0.75)';
    ctx.stroke();

    const wheelRadius = Math.max(1.1, vWid * 0.13);
    ctx.fillStyle = 'rgba(20,20,20,0.86)';
    for (const wheelX of [-vLen * 0.78, -vLen * 0.26]) {
      ctx.beginPath();
      ctx.arc(wheelX, bodyTop + wheelRadius * 0.35, wheelRadius, 0, Math.PI * 2);
      ctx.arc(wheelX, bodyBottom - wheelRadius * 0.35, wheelRadius, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.fillStyle = 'rgba(26, 50, 70, 0.72)';
    drawRoundedRect(ctx, -vLen * 0.36, -vWid * 0.36, vLen * 0.16, vWid * 0.72, Math.max(1, vWid * 0.1));
    ctx.fill();
    drawRoundedRect(ctx, -vLen * 0.64, -vWid * 0.32, vLen * 0.16, vWid * 0.64, Math.max(1, vWid * 0.1));
    ctx.fill();

    ctx.fillStyle = 'rgba(255,255,190,0.85)';
    ctx.fillRect(-vLen * 0.05, -vWid * 0.28, Math.max(1, vLen * 0.035), vWid * 0.18);
    ctx.fillRect(-vLen * 0.05, vWid * 0.1, Math.max(1, vLen * 0.035), vWid * 0.18);
  }

  ctx.restore();
}

function drawPedestrian(ctx, transform, pedestrian) {
  const p = toPixel(transform, pedestrian.x, pedestrian.y);
  const radius = 0.5 * transform.scale;
  ctx.fillStyle = C.pedestrian;
  ctx.beginPath();
  ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
  ctx.fill();
}

function drawConstraintMarker(ctx, transform, x, y) {
  const p = toPixel(transform, x, y);
  const size = 6 * transform.scale;
  ctx.strokeStyle = C.constraint;
  ctx.lineWidth = Math.max(2, transform.scale * 0.5);
  ctx.beginPath();
  ctx.moveTo(p.x - size, p.y - size);
  ctx.lineTo(p.x + size, p.y + size);
  ctx.moveTo(p.x + size, p.y - size);
  ctx.lineTo(p.x - size, p.y + size);
  ctx.stroke();
}

function drawFrame(side, network, rawFrame) {
  const frame = sanitizeLiveState(rawFrame || {});
  const ctx = side.ctx;
  if (!ctx) return;

  const transform = configureTransform(network, side.width, side.height);
  ctx.clearRect(0, 0, transform.cw, transform.ch);
  drawStaticLayer(ctx, transform, network);
  drawSignals(ctx, transform, network, frame);

  for (const pedestrian of frame.pedestrians || []) {
    const x = Number(pedestrian.x);
    const y = Number(pedestrian.y);
    if (!isInsideBounds(transform, x, y)) continue;
    drawPedestrian(ctx, transform, pedestrian);
  }

  for (const vehicle of frame.vehicles || []) {
    const x = Number(vehicle.x);
    const y = Number(vehicle.y);
    if (!isInsideBounds(transform, x, y)) continue;
    drawVehicle(ctx, transform, vehicle);
  }

  const marker = frame.visual?.constraint_marker;
  if (marker && marker.active && isInsideBounds(transform, Number(marker.x), Number(marker.y))) {
    drawConstraintMarker(ctx, transform, Number(marker.x), Number(marker.y));
  }
}

function showEmpty(side, message) {
  const ctx = side?.ctx;
  if (!ctx) return;
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, side.width, side.height);
  ctx.fillStyle = 'rgba(15,23,42,0.82)';
  ctx.fillRect(24, 24, Math.min(360, side.width - 48), 54);
  ctx.fillStyle = '#cbd5e1';
  ctx.font = '600 13px Inter, sans-serif';
  ctx.fillText(message, 42, 56);
}

async function renderSide(sideKey, frame) {
  const side = ensureCanvas(sideKey);
  if (!side) return;
  if (!frame) {
    showEmpty(side, 'Select a run and frame.');
    return;
  }

  try {
    const network = await loadNetwork(toIntersectionId(frame));
    drawFrame(side, network, frame);
  } catch (error) {
    console.warn(`[SmartFlowCompare] ${sideKey} render failed:`, error);
    showEmpty(side, 'Frame unavailable.');
  }
}

function renderPayload(payload) {
  latestPayload = payload || {};
  renderSide('left', latestPayload.left);
  renderSide('right', latestPayload.right);
}

function renderLatest() {
  if (latestPayload) renderPayload(latestPayload);
}

function observeContainers() {
  if (resizeObserver || !window.ResizeObserver) return;
  resizeObserver = new ResizeObserver(renderLatest);
  for (const side of Object.values(SIDES)) {
    const container = document.getElementById(side.containerId);
    if (container) resizeObserver.observe(container);
  }
}

document.addEventListener(COMPARE_FRAME_EVENT, (event) => {
  observeContainers();
  renderPayload(event.detail || {});
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', observeContainers, { once: true });
} else {
  observeContainers();
}
