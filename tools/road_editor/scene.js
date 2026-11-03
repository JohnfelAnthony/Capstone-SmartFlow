// Display-only street styling that mirrors the SmartFlow 2D map (src/simulation/scene-geometry.ts and the light city palette).
// Lane positions, widths and junction outlines come from the native parser's visual(); nothing here feeds validation.
export const PALETTE = { ground: '#C8CCCE', plaza: '#D3D6D5', parking: '#7B8087', sidewalk: '#DEE0DF', kerb: '#F4F4F0', asphalt: '#6C7178', marking: '#F7F7F2', centre: '#F3C54F', lawn: '#8FC27D', shed: '#63C7C2', landmarkLight: '#E4E7EA', landmarkGreen: '#BFDC8B', arm: '#4A5159' };
export const SIDEWALK_M = 3;
const ZEBRA = { start: .6, end: 3.6, stripe: .5, period: 1, kerbMargin: .15 };

/** Read direction and permitted connector geometry directly from native visual(). */
export function movementPreview(visual) {
  const lanes=(visual?.roads || []).flatMap(road=>road.lanes || []).filter(lane=>lane.shape?.length>1);
  const arrows=lanes.flatMap(lane=>{
    const segments=lane.shape.slice(1).map((b,i)=>({a:lane.shape[i],b,length:Math.hypot(b.x-lane.shape[i].x,b.y-lane.shape[i].y)}));
    const total=segments.reduce((sum,part)=>sum+part.length,0);if(total<1e-8)return [];
    let remaining=total/2,part=segments.at(-1);
    for(const candidate of segments){if(candidate.length>0&&remaining<=candidate.length){part=candidate;break;}remaining-=candidate.length;}
    if(part.length<1e-8)return [];
    const ux=(part.b.x-part.a.x)/part.length,uy=(part.b.y-part.a.y)/part.length,t=Math.max(0,Math.min(1,remaining/part.length));
    const x=part.a.x+(part.b.x-part.a.x)*t,y=part.a.y+(part.b.y-part.a.y)*t,size=Math.min(2,Math.max(.5,lane.width*.32));
    return [{id:lane.id,shape:[{x:x+ux*size,y:y+uy*size},{x:x-ux*size-uy*size*.55,y:y-uy*size+ux*size*.55},{x:x-ux*size+uy*size*.55,y:y-uy*size-ux*size*.55}]}];
  });
  const connectors=(visual?.internal_lanes || []).filter(lane=>lane.shape?.length>1).map(lane=>({id:lane.lanes?.[0]?.id || '',shape:lane.shape}));
  return {arrows,connectors};
}

function miterNormals(points) {
  const directions = points.slice(1).map((point, index) => {
    const dx = point.x - points[index].x, dy = point.y - points[index].y, length = Math.hypot(dx, dy) || 1;
    return { x: dx / length, y: dy / length };
  });
  return points.map((_, index) => {
    const previous = directions[Math.max(0, index - 1)], next = directions[Math.min(index, directions.length - 1)];
    const normalX = -(previous.y + next.y), normalY = previous.x + next.x, normalLength = Math.hypot(normalX, normalY);
    const nx = normalLength > 1e-8 ? normalX / normalLength : -previous.y, ny = normalLength > 1e-8 ? normalY / normalLength : previous.x;
    return { nx, ny, stretch: 1 / Math.max(Math.abs(nx * -previous.y + ny * previous.x), 1e-8) };
  });
}

/** The polyline moved `distance` metres to its left (negative: right), with bounded miter joins. */
export function offsetLine(points, distance) {
  return miterNormals(points).map(({ nx, ny, stretch }, index) => {
    const offset = Math.sign(distance) * Math.min(Math.abs(distance) * 3, Math.abs(distance) * stretch);
    return { x: points[index].x + nx * offset, y: points[index].y + ny * offset };
  });
}

function lanePolygon(points, width) {
  return [...offsetLine(points, width / 2), ...offsetLine(points, -width / 2).reverse()];
}

const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const unit = (dx, dy) => { const length = Math.hypot(dx, dy) || 1; return { x: dx / length, y: dy / length }; };
function distanceToPolyline(point, line) {
  let best = Infinity;
  for (let index = 1; index < line.length; index++) {
    const a = line[index - 1], b = line[index], dx = b.x - a.x, dy = b.y - a.y, span = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / span));
    best = Math.min(best, Math.hypot(point.x - a.x - t * dx, point.y - a.y - t * dy));
  }
  return best;
}
function middleOf(points) {
  const index = Math.max(0, Math.floor((points.length - 2) / 2));
  return { x: (points[index].x + points[index + 1].x) / 2, y: (points[index].y + points[index + 1].y) / 2 };
}

/** Zebra stripes 0.6–3.6 m inside the junction across one carriageway end, on a junction-wide 1 m grid. */
function crosswalk(lane, junction) {
  const points = lane.points, last = points.length - 1;
  const entering = distance(points[last], junction.center) <= distance(points[0], junction.center);
  const travel = entering ? unit(points[last].x - points[last - 1].x, points[last].y - points[last - 1].y) : unit(points[1].x - points[0].x, points[1].y - points[0].y);
  const point = entering ? points[last] : points[0], inward = entering ? travel : { x: -travel.x, y: -travel.y }, across = { x: -inward.y, y: inward.x };
  const offset = (point.x - junction.center.x) * across.x + (point.y - junction.center.y) * across.y;
  const at = (lateral, depth) => ({ x: point.x + across.x * (lateral - offset) + inward.x * depth, y: point.y + across.y * (lateral - offset) + inward.y * depth });
  const low = offset - lane.width / 2 + ZEBRA.kerbMargin, high = offset + lane.width / 2 - ZEBRA.kerbMargin, phase = (ZEBRA.period - ZEBRA.stripe) / 2;
  const stripes = [];
  for (let start = Math.ceil((low - phase) / ZEBRA.period) * ZEBRA.period + phase; start + ZEBRA.stripe <= high + 1e-9; start += ZEBRA.period) {
    stripes.push([at(start, ZEBRA.start), at(start + ZEBRA.stripe, ZEBRA.start), at(start + ZEBRA.stripe, ZEBRA.end), at(start, ZEBRA.end)]);
  }
  return stripes;
}

/** Pavement, markings and crosswalks for a native visual() payload, in native metres. */
export function streetScene(visual) {
  const roads = (visual?.roads || []).flatMap(road => road.lanes || []).filter(lane => lane.shape?.length > 1).map(lane => {
    const width = lane.width > 0 ? lane.width : 3.3, count = Number.isInteger(lane.lane_count) && lane.lane_count > 0 ? lane.lane_count : 1;
    return { id: lane.id, points: lane.shape, width, polygon: lanePolygon(lane.shape, width), leftEdge: offsetLine(lane.shape, width / 2),
      dividers: Array.from({ length: count - 1 }, (_, index) => offsetLine(lane.shape, -width / 2 + (index + 1) * width / count)), centreLine: null };
  });
  // A yellow centre line only where an opposing carriageway shares this left edge.
  for (const lane of roads) {
    const middle = middleOf(lane.leftEdge);
    if (roads.some(other => other !== lane && distanceToPolyline(middle, other.leftEdge) < .3)) lane.centreLine = lane.leftEdge;
  }
  const features = visual?.site_features || [];
  const junctions = (visual?.signals || []).filter(signal => signal.shape?.length > 2).map(signal => {
    const center = { x: signal.x, y: signal.y }, reach = Math.max(...signal.shape.map(point => distance(point, center))) + 1;
    const ends = roads.filter(lane => Math.min(distance(lane.points[0], center), distance(lane.points[lane.points.length - 1], center)) <= reach);
    const pavement = features.find(feature => feature.kind === 'junction_pavement' && feature.junction === signal.id);
    const zebraEnds = pavement?.zebra_lanes ? ends.filter(lane => pavement.zebra_lanes.includes(lane.id)) : ends;
    return { id: signal.id, polygon: pavement?.shape ?? signal.shape, crosswalks: zebraEnds.flatMap(lane => crosswalk(lane, { center })) };
  });
  const stopLines = (visual?.signal_groups || []).map(group => group.stop_line).filter(line => line?.length > 1);
  const ofKind = (...kinds) => features.filter(feature => kinds.includes(feature.kind));
  return { roads, junctions, stopLines, ground: ofKind('plaza', 'parking', 'concrete', 'service_lane'), paint: ofKind('marking', 'dashes'), landmarks: ofKind('building', 'shed', 'street_light') };
}
