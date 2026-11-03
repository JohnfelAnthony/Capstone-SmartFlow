import test from 'node:test';
import assert from 'node:assert/strict';
import { closestRoadPoint, connectCrossing, deleteNode, editIslandCorner, junctionMovements, previewNodeDeletion, roadLaneInfo, setMovementAllowed, setRoadLanes, splitRoadAt, splitRoadAtLongestMidpoint } from './topology.js';

const fixture = () => ({
  nodes: [{id:'a',x:0,y:0},{id:'b',x:100,y:0},{id:'edit_node_1',x:100,y:50}],
  roads: [{id:'road',source:'a',target:'b',oneway:false,shape:[[0,0],[100,0]],osm_tags:{lanes:'2'},extra:{keep:true}},
          {id:'edit_road_1',source:'b',target:'edit_node_1',oneway:false,shape:[[100,0],[100,50]]}],
  prohibited_turns:[['roadf','edit_road_1f'],['edit_road_1r','roadr'],['roadr','otherf'],['otherf','roadf']],
});

test('node deletion previews and removes only incident roads and their restrictions', () => {
  const input=fixture(); input.roads.push({id:'other',source:'a',target:'edit_node_1'});
  input.prohibited_turns.push(['otherf','unrelatedf']);
  const before=structuredClone(input), preview=previewNodeDeletion(input,'b');
  assert.deepEqual(preview.roads,['road','edit_road_1']);
  assert.equal(preview.restrictions.length,4);
  const result=deleteNode(input,'b');
  assert.deepEqual(input,before);
  assert.deepEqual(result.network.roads.map(r=>r.id),['other']);
  assert.deepEqual(result.network.prohibited_turns,[['otherf','unrelatedf']]);
  assert.equal(result.network.nodes.some(n=>n.id==='b'),false);
  assert.throws(()=>deleteNode({...input,id:'tagum_site_b'},'tagum_site_b_j'),/existing node/);
  const site={...input,id:'tagum_site_b',nodes:[...input.nodes,{id:'tagum_site_b_j'}]};
  assert.throws(()=>deleteNode(site,'tagum_site_b_j'),/cannot be deleted/);
  assert.throws(()=>deleteNode({...input,prohibited_turns:[['roadf']]},'b'),/restrictions/);
});

test('lane edits preserve actual width and original map tags', () => {
  const network=fixture(), road=network.roads[0];
  road.osm_tags.lanes='4;3';
  assert.deepEqual(roadLaneInfo(road),{perDirection:2,ambiguous:true,raw:'4;3'});
  const updated=setRoadLanes(network,'road',3,false), changed=updated.roads[0];
  assert.equal(changed.osm_tags.lanes,'6');
  assert.equal(changed.width_per_direction_m,6.6);
  assert.equal(changed.editor_provenance.original_osm_lanes,'4;3');
  assert.equal(network.roads[0].osm_tags.lanes,'4;3');
  const oneway=setRoadLanes(updated,'road',3,true).roads[0];
  assert.equal(oneway.osm_tags.lanes,'3');
  assert.equal(oneway.width_per_direction_m,6.6);
  assert.equal(oneway.editor_provenance.original_osm_lanes,'4;3');
  assert.equal(roadLaneInfo({oneway:true,osm_tags:{lanes:'4oops'}}).perDirection,1);
  assert.equal(roadLaneInfo({oneway:false,osm_tags:{lanes:'3'}}).ambiguous,true);
  assert.throws(()=>setRoadLanes(network,'road',0,true),/integer/);
});

test('island corner edits retain explicitly closed rings and enforce three corners', () => {
  const input={islands:[{id:'median',planted:true,shape:[[0,0],[10,0],[10,5],[0,5],[0,0]]}]};
  const added=editIslandCorner(input,'median','insert-longest');
  assert.deepEqual(added.islands[0].shape,[[0,0],[5,0],[10,0],[10,5],[0,5],[0,0]]);
  const removed=editIslandCorner(added,'median','remove',0);
  assert.deepEqual(removed.islands[0].shape.at(-1),removed.islands[0].shape[0]);
  assert.equal(input.islands[0].shape.length,5);
  const triangle={islands:[{id:'a',shape:[[0,0],[5,0],[0,5]]}]};
  assert.throws(()=>editIslandCorner(triangle,'a','remove',0),/three corners/);
});

test('split retains endpoint road IDs, restrictions, metadata and new no-signal junction', () => {
  const original=fixture(), result=splitRoadAtLongestMidpoint(original,'road');
  assert.equal(result.nodeId,'edit_node_2'); assert.equal(result.newRoadId,'edit_road_2');
  assert.deepEqual(result.network.roads[0].shape,[[0,0],[50,0]]);
  assert.deepEqual(result.network.roads.at(-1).shape,[[50,0],[100,0]]);
  assert.equal(result.network.roads[0].target,result.nodeId);
  assert.equal(result.network.roads.at(-1).source,result.nodeId);
  assert.deepEqual(result.network.roads.at(-1).extra,{keep:true});
  assert.equal(result.network.nodes.at(-1).default_control_mode,'first_come');
  assert.deepEqual(result.network.prohibited_turns,[['edit_road_2f','edit_road_1f'],['edit_road_1r','edit_road_2r'],['roadr','otherf'],['otherf','roadf']]);
  assert.equal(result.changedRestrictions,2);
  assert.equal(original.roads.length,2);
});

test('split refuses ambiguous nodes and malformed restrictions without changing original', () => {
  const network=fixture(); network.nodes.push({id:'existing',x:50,y:0});
  assert.throws(()=>splitRoadAtLongestMidpoint(network,'road'),/existing node/);
  assert.equal(network.roads.length,2);
  const bad=fixture(); bad.prohibited_turns=[['roadf']];
  assert.throws(()=>splitRoadAtLongestMidpoint(bad,'road'),/restrictions/);
});

test('explicit split uses the clicked segment and supports existing interior vertices', () => {
  const input=fixture(); input.roads[0].shape=[[0,0],[30,0],[100,0]];
  const nearest=closestRoadPoint(input.roads[0].shape,[65,4]);
  assert.equal(nearest.index,1); assert.equal(nearest.fraction,.5);
  const split=splitRoadAt(input,'road',nearest.index,nearest.fraction);
  assert.deepEqual(split.network.roads[0].shape,[[0,0],[30,0],[65,0]]);
  assert.deepEqual(split.network.roads.at(-1).shape,[[65,0],[100,0]]);
  const vertex=splitRoadAt(input,'road',0,1);
  assert.deepEqual(vertex.network.roads[0].shape,[[0,0],[30,0]]);
  assert.deepEqual(vertex.network.roads.at(-1).shape,[[30,0],[100,0]]);
  assert.throws(()=>splitRoadAt(input,'road',0,0),/away from its endpoints/);
});

test('crossing roads connect at a single new no-signal node without mutating the input', () => {
  const input={nodes:[{id:'w',x:-100,y:0,boundary:true},{id:'e',x:100,y:0,boundary:true},{id:'s',x:0,y:-100,boundary:true},{id:'n',x:0,y:100,boundary:true}],
    roads:[{id:'ew',source:'w',target:'e',shape:[[-100,0],[100,0]],oneway:false},{id:'ns',source:'s',target:'n',shape:[[0,-100],[0,100]],oneway:false}],prohibited_turns:[]};
  const result=connectCrossing(input,'ew','ns'), node=result.network.nodes.find(n=>n.id===result.nodeId);
  assert.deepEqual([node.x,node.y,node.default_control_mode],[0,0,'first_come']);
  assert.equal(result.network.roads.filter(r=>r.source===node.id||r.target===node.id).length,4);
  assert.equal(result.network.roads.length,4); assert.equal(input.roads.length,2);
  assert.throws(()=>connectCrossing(input,'ew','ew'),/different roads/);
  const parallel=structuredClone(input); parallel.roads[1].shape=[[-100,0],[100,0]];
  assert.throws(()=>connectCrossing(parallel,'ew','ns'),/Overlapping/);
  const multiple=structuredClone(input); multiple.roads[1].shape=[[-50,-80],[-50,80],[50,80],[50,-80]];
  assert.throws(()=>connectCrossing(multiple,'ew','ns'),/more than once/);
});

test('movement review respects one-way direction, prohibits U-turns and preserves other restrictions', () => {
  const network={nodes:[{id:'j',x:0,y:0},{id:'w',x:-100,y:0,boundary:true},{id:'e',x:100,y:0,boundary:true},{id:'n',x:0,y:100,boundary:true}],roads:[
    {id:'w',name:'West',source:'w',target:'j',oneway:false},
    {id:'e',name:'East',source:'j',target:'e',oneway:true},
    {id:'n',name:'North',source:'n',target:'j',oneway:false}], prohibited_turns:[['wf','ef']]};
  const movements=junctionMovements(network,'j');
  assert.deepEqual(movements.map(m=>[m.incoming,m.outgoing,m.allowed]),[['wf','ef',false],['wf','nr',true],['nf','wr',true],['nf','ef',true]]);
  const blocked=setMovementAllowed(network,'j','wf','nr',false);
  assert.deepEqual(blocked.prohibited_turns,[['wf','ef'],['wf','nr']]);
  assert.deepEqual(setMovementAllowed(blocked,'j','wf','ef',true).prohibited_turns,[['wf','nr']]);
  assert.deepEqual(network.prohibited_turns,[['wf','ef']]);
  assert.throws(()=>setMovementAllowed(network,'j','wf','wr',true),/non-U-turn/);
  assert.throws(()=>setMovementAllowed(network,'j','ef','nr',true),/non-U-turn/);
});
