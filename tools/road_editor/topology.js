/** Pure draft operations. Native validation remains authoritative. */
function nextId(prefix, items) {
  let number = 1;
  while (items.some(item => item.id === `${prefix}${number}`)) number++;
  return `${prefix}${number}`;
}

/** Match the native parser's first-semicolon lane rule, while exposing ambiguous tags. */
export function roadLaneInfo(road) {
  const raw = road.osm_tags?.lanes;
  const first = String(raw ?? '').split(';')[0].trim();
  const valid = /^[0-9]+$/.test(first) && Number.isSafeInteger(Number(first)) && Number(first) > 0;
  const total = valid ? Number(first) : 1;
  const perDirection = valid ? (road.oneway ? total : Math.max(1, Math.floor(total / 2))) : 1;
  const ambiguous = !valid || String(raw).includes(';') || (!road.oneway && total > 1 && total % 2 !== 0);
  return {perDirection, ambiguous, raw};
}

/** Change lane count or direction without implicitly changing paved width. */
export function setRoadLanes(input, roadId, perDirection, oneway) {
  if (!Number.isInteger(perDirection) || perDirection < 1 || perDirection > 8 || typeof oneway !== 'boolean') throw Error('Lanes must be an integer from 1 to 8.');
  const network = structuredClone(input), road = network.roads.find(item => item.id === roadId);
  if (!road) throw Error('Road no longer exists.');
  const previous = roadLaneInfo(road);
  const width = road.width_per_direction_m ?? previous.perDirection * 3.3;
  if (!Number.isFinite(width) || width < 2.5 || width > 15) throw Error('Set a width between 2.5 and 15 metres before changing lanes.');
  if (road.editor_provenance !== undefined && (!road.editor_provenance || typeof road.editor_provenance !== 'object' || Array.isArray(road.editor_provenance))) throw Error('Existing editor provenance needs review.');
  road.editor_provenance ??= {};
  if (!Object.hasOwn(road.editor_provenance, 'original_osm_lanes')) road.editor_provenance.original_osm_lanes = previous.raw ?? null;
  road.osm_tags ??= {};
  road.osm_tags.lanes = String(oneway ? perDirection : perDirection * 2);
  road.oneway = oneway;
  road.width_per_direction_m = width;
  return network;
}

/** Edit polygon corners while retaining an explicitly closed ring if present. */
export function editIslandCorner(input, islandId, operation, index = null) {
  const network = structuredClone(input), island = (network.islands || []).find(item => item.id === islandId);
  if (!island || !Array.isArray(island.shape) || island.shape.length < 3) throw Error('Choose an island with at least three corners.');
  const shape = island.shape, first = shape[0], last = shape.at(-1);
  const closed = shape.length > 3 && first[0] === last[0] && first[1] === last[1];
  const corners = closed ? shape.slice(0, -1) : [...shape];
  if (operation === 'remove') {
    if (corners.length <= 3 || !Number.isInteger(index) || index < 0 || index >= corners.length) throw Error('An island needs at least three corners.');
    corners.splice(index, 1);
  } else if (operation === 'insert-longest') {
    let longest = -1, position = -1;
    for (let i = 0; i < corners.length; i++) {
      const a = corners[i], b = corners[(i + 1) % corners.length], distance = Math.hypot(a[0]-b[0], a[1]-b[1]);
      if (distance > longest) {longest = distance; position = i;}
    }
    if (longest < 1e-6) throw Error('Island needs a nonzero edge.');
    const a = corners[position], b = corners[(position + 1) % corners.length];
    corners.splice(position + 1, 0, [(a[0]+b[0])/2, (a[1]+b[1])/2]);
  } else throw Error('Unknown island edit.');
  island.shape = closed ? [...corners, [...corners[0]]] : corners;
  return network;
}

/** Preview exactly which roads and restrictions deleting a node removes. */
export function previewNodeDeletion(network, nodeId) {
  if (!network.nodes.some(node => node.id === nodeId)) throw Error('Choose an existing node.');
  if (network.id === 'tagum_site_b' && nodeId === 'tagum_site_b_j') throw Error('The Site B study junction cannot be deleted.');
  const roads = network.roads.filter(road => road.source === nodeId || road.target === nodeId).map(road => road.id);
  const laneIds = new Set(roads.flatMap(id => [`${id}f`, `${id}r`]));
  const restrictions = network.prohibited_turns ?? [];
  if (!Array.isArray(restrictions) || restrictions.some(pair => !Array.isArray(pair) || pair.length !== 2 || pair.some(id => typeof id !== 'string'))) {
    throw Error('Turn restrictions need repair before deleting this node.');
  }
  return {nodeId, roads, restrictions: restrictions.filter(pair => pair.some(id => laneIds.has(id))).map(pair => [...pair])};
}

export function deleteNode(input, nodeId) {
  const preview = previewNodeDeletion(input, nodeId);
  const network = structuredClone(input), roads = new Set(preview.roads);
  const laneIds = new Set(preview.roads.flatMap(id => [`${id}f`, `${id}r`]));
  network.nodes = network.nodes.filter(node => node.id !== nodeId);
  network.roads = network.roads.filter(road => !roads.has(road.id));
  if (network.prohibited_turns) network.prohibited_turns = network.prohibited_turns.filter(pair => !pair.some(id => laneIds.has(id)));
  return {network, ...preview};
}

/** Enumerate native-compatible movements at a junction; U-turns are omitted. */
export function junctionMovements(network, nodeId) {
  const node=network.nodes.find(item=>item.id===nodeId);
  if (!node || node.boundary) return [];
  const incoming=[], outgoing=[];
  for(const road of network.roads) {
    const name=road.name || road.id;
    if(road.target===nodeId) incoming.push({id:`${road.id}f`,other:road.source,name});
    if(road.source===nodeId) outgoing.push({id:`${road.id}f`,other:road.target,name});
    if(!road.oneway && road.source===nodeId) incoming.push({id:`${road.id}r`,other:road.target,name});
    if(!road.oneway && road.target===nodeId) outgoing.push({id:`${road.id}r`,other:road.source,name});
  }
  const restrictions=network.prohibited_turns ?? [];
  if(!Array.isArray(restrictions) || restrictions.some(pair=>!Array.isArray(pair)||pair.length!==2)) throw Error('Turn restrictions need repair before editing.');
  return incoming.flatMap(from=>outgoing.filter(to=>from.other!==to.other).map(to=>({
    incoming:from.id,outgoing:to.id,fromName:from.name,toName:to.name,
    allowed:!restrictions.some(pair=>pair[0]===from.id&&pair[1]===to.id),
  })));
}

export function setMovementAllowed(input, nodeId, incoming, outgoing, allowed) {
  if(typeof allowed!=='boolean' || !junctionMovements(input,nodeId).some(item=>item.incoming===incoming&&item.outgoing===outgoing)) {
    throw Error('Choose a connected non-U-turn movement.');
  }
  const network=structuredClone(input);
  const restrictions=(network.prohibited_turns ?? []).filter(pair=>pair[0]!==incoming||pair[1]!==outgoing);
  if(!allowed) restrictions.push([incoming,outgoing]);
  network.prohibited_turns=restrictions;
  return network;
}

/** Split a segment at an explicit fraction, preserving endpoint restrictions. */
export function splitRoadAt(input, roadId, index, fraction, reuseNodeId = null) {
  const network = structuredClone(input);
  const road = network.roads.find(item => item.id === roadId);
  if (!road || !Array.isArray(road.shape) || road.shape.length < 2) throw Error('Choose a road with a valid shape.');
  if (!Number.isInteger(index) || index < 0 || index >= road.shape.length - 1 || !Number.isFinite(fraction) || fraction < 0 || fraction > 1) throw Error('Choose a point on the road.');
  const a = road.shape[index], b = road.shape[index + 1];
  if (![...a, ...b].every(Number.isFinite) || Math.hypot(b[0]-a[0], b[1]-a[1]) < 1e-6) throw Error('Road needs a nonzero finite segment.');
  const atStart = fraction < 1e-6, atEnd = fraction > 1-1e-6;
  if ((atStart && index === 0) || (atEnd && index === road.shape.length-2)) throw Error('Split inside the road, away from its endpoints.');
  const point = atStart ? [...a] : atEnd ? [...b] : [a[0] + fraction*(b[0]-a[0]), a[1] + fraction*(b[1]-a[1])];
  const reused = reuseNodeId === null ? null : network.nodes.find(node => node.id === reuseNodeId);
  if (reuseNodeId !== null && (!reused || reused.boundary || Math.hypot(reused.x-point[0],reused.y-point[1]) > .001)) {
    throw Error('The shared junction does not match the crossing point.');
  }
  if (network.nodes.some(node => node.id !== reuseNodeId && Math.hypot(node.x - point[0], node.y - point[1]) < .01)) {
    throw Error('The split point coincides with an existing node; use an explicit connect operation.');
  }
  const restrictions = network.prohibited_turns ?? [];
  if (!Array.isArray(restrictions) || restrictions.some(turn => !Array.isArray(turn) || turn.length !== 2 || turn.some(lane => typeof lane !== 'string'))) {
    throw Error('Turn restrictions need review before splitting this road.');
  }
  const nodeId = reuseNodeId ?? nextId('edit_node_', network.nodes);
  const newRoadId = nextId('edit_road_', network.roads);
  const target = road.target;
  const headPoints = atStart ? [...road.shape.slice(0, index), point] : [...road.shape.slice(0, index + 1), point];
  const tailPoints = atEnd ? [point, ...road.shape.slice(index + 2)] : [point, ...road.shape.slice(index + 1)];
  const tail = {...structuredClone(road), id: newRoadId, source: nodeId, target, shape: tailPoints};
  road.target = nodeId;
  road.shape = headPoints;
  if (reused) { point[0]=reused.x; point[1]=reused.y; }
  else network.nodes.push({id: nodeId, x: point[0], y: point[1], boundary: false, default_control_mode: 'first_come'});
  network.roads.push(tail);
  // Incoming forward and outgoing reverse lanes meet the original target;
  // the other two directions still meet the original source.
  network.prohibited_turns = restrictions.map(([incoming, outgoing]) => [
    incoming === `${roadId}f` ? `${newRoadId}f` : incoming,
    outgoing === `${roadId}r` ? `${newRoadId}r` : outgoing,
  ]);
  return {network, nodeId, newRoadId, changedRestrictions: restrictions.filter(([i, o]) => i === `${roadId}f` || o === `${roadId}r`).length};
}

/** Connect two distinct roads at one unambiguous interior crossing. */
export function connectCrossing(input, firstId, secondId) {
  if (firstId === secondId) throw Error('Choose two different roads.');
  const first=input.roads.find(road=>road.id===firstId), second=input.roads.find(road=>road.id===secondId);
  if (!first || !second) throw Error('Both roads must still exist.');
  const cross=(a,b)=>a[0]*b[1]-a[1]*b[0];
  const found=[];
  for(let i=0;i<first.shape.length-1;i++) for(let j=0;j<second.shape.length-1;j++) {
    const a=first.shape[i], b=first.shape[i+1], c=second.shape[j], d=second.shape[j+1];
    const r=[b[0]-a[0],b[1]-a[1]], s=[d[0]-c[0],d[1]-c[1]], den=cross(r,s), q=[c[0]-a[0],c[1]-a[1]];
    if (Math.abs(den)<1e-9) {
      const axis=Math.abs(r[0])>=Math.abs(r[1])?0:1;
      const overlap=Math.min(Math.max(a[axis],b[axis]),Math.max(c[axis],d[axis]))-Math.max(Math.min(a[axis],b[axis]),Math.min(c[axis],d[axis]));
      if (Math.abs(cross(q,r))<1e-9 && overlap>=-1e-9) throw Error('Overlapping segments need manual review.');
      continue;
    }
    const t=cross(q,s)/den, u=cross(q,r)/den;
    if(t < -1e-9 || t > 1+1e-9 || u < -1e-9 || u > 1+1e-9) continue;
    const point=[a[0]+t*r[0],a[1]+t*r[1]];
    if (!found.some(item=>Math.hypot(item.point[0]-point[0],item.point[1]-point[1])<.001)) found.push({i,j,t:Math.max(0,Math.min(1,t)),u:Math.max(0,Math.min(1,u)),point});
  }
  if(found.length!==1) throw Error(found.length?'Roads cross more than once; split them individually first.':'The selected roads do not cross.');
  const hit=found[0], one=splitRoadAt(input, firstId, hit.i, hit.t);
  const two=splitRoadAt(one.network, secondId, hit.j, hit.u, one.nodeId);
  const incoming=two.network.roads.filter(road=>road.target===one.nodeId || (!road.oneway && road.source===one.nodeId)).length;
  if(incoming>4) throw Error('This junction would exceed four incoming approaches.');
  return {network:two.network,nodeId:one.nodeId,newRoadIds:[one.newRoadId,two.newRoadId],changedRestrictions:one.changedRestrictions+two.changedRestrictions};
}

export function closestRoadPoint(shape, point) {
  let best = null;
  for (let i=0; i<shape.length-1; i++) {
    const a=shape[i], b=shape[i+1], dx=b[0]-a[0], dy=b[1]-a[1], length2=dx*dx+dy*dy;
    if (length2 < 1e-12) continue;
    const fraction=Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2));
    const distance=Math.hypot(point[0]-a[0]-fraction*dx,point[1]-a[1]-fraction*dy);
    if (!best || distance<best.distance) best={index:i,fraction,distance};
  }
  if (!best) throw Error('Road needs a nonzero segment.');
  return best;
}

/** Convenience split used by the inspector. */
export function splitRoadAtLongestMidpoint(input, roadId) {
  const road = input.roads.find(item => item.id === roadId);
  if (!road || !Array.isArray(road.shape) || road.shape.length < 2) throw Error('Choose a road with a valid shape.');
  let index=-1, longest=0;
  for (let i=0;i<road.shape.length-1;i++) {
    const a=road.shape[i], b=road.shape[i+1], distance=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if (distance>longest) { longest=distance; index=i; }
  }
  if (index<0 || longest<1e-6) throw Error('Road needs a nonzero segment.');
  return splitRoadAt(input, roadId, index, .5);
}
