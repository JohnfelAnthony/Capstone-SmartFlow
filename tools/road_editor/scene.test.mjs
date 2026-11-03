import assert from 'node:assert/strict';
import { test } from 'node:test';
import { movementPreview, offsetLine, streetScene } from './scene.js';

const lane = (id, shape, width, lane_count) => ({ id, shape, width, lane_count });

test('native movement overlay follows lane direction and uses only supplied connectors', () => {
  const visual={roads:[{lanes:[lane('east', [{x:0,y:0},{x:10,y:0}],3.3,1),lane('west',[{x:10,y:4},{x:0,y:4}],3.3,1)]}],
    internal_lanes:[{lanes:[{id:'east->north'}],shape:[{x:10,y:0},{x:12,y:2}]}]};
  const preview=movementPreview(visual);
  assert.equal(preview.arrows.length,2);
  assert.ok(preview.arrows[0].shape[0].x>preview.arrows[0].shape[1].x);
  assert.ok(preview.arrows[1].shape[0].x<preview.arrows[1].shape[1].x);
  assert.deepEqual(preview.connectors,[{id:'east->north',shape:visual.internal_lanes[0].shape}]);
  assert.deepEqual(movementPreview(null),{arrows:[],connectors:[]});
});

test('offsetLine moves a straight line left by the distance', () => {
  assert.deepEqual(offsetLine([{ x: 0, y: 0 }, { x: 10, y: 0 }], 2), [{ x: 0, y: 2 }, { x: 10, y: 2 }]);
});

test('two-way roads get one centre line per carriageway, dividers per lane and zebra stripes at the junction', () => {
  // A two-lane carriageway heading east into a junction at x = 20, and its opposing carriageway heading west.
  const visual = {
    roads: [{ lanes: [lane('r0f', [{ x: 0, y: -3.3 }, { x: 15, y: -3.3 }], 6.6, 2)] }, { lanes: [lane('r0r', [{ x: 15, y: 3.3 }, { x: 0, y: 3.3 }], 6.6, 2)] },
      { lanes: [lane('oneway', [{ x: 0, y: 40 }, { x: 15, y: 40 }], 3.3, 1)] }],
    signals: [{ id: 'j', x: 20, y: 0, shape: [{ x: 15, y: -7 }, { x: 25, y: -7 }, { x: 25, y: 7 }, { x: 15, y: 7 }] }],
    signal_groups: [{ stop_line: [{ x: 15, y: 0 }, { x: 15, y: -6.6 }] }],
  };
  const scene = streetScene(visual);
  const byId = Object.fromEntries(scene.roads.map(road => [road.id, road]));
  assert.ok(byId.r0f.centreLine && byId.r0r.centreLine, 'opposing carriageways share a centre line');
  assert.equal(byId.oneway.centreLine, null, 'a lone one-way road has no centre line');
  assert.equal(byId.r0f.dividers.length, 1);
  assert.equal(byId.oneway.dividers.length, 0);
  assert.equal(scene.stopLines.length, 1);
  assert.ok(scene.junctions[0].crosswalks.length >= 10, 'stripes span both carriageways');
  assert.equal(streetScene(null).roads.length, 0);
});

test('site features sort into layers and an explicit pavement replaces the junction polygon', () => {
  const shape = [{ x: 0, y: 0 }, { x: 40, y: 0 }, { x: 40, y: 40 }];
  const signals = [{ id: 'j', x: 20, y: 0, shape: [{ x: 15, y: -7 }, { x: 25, y: -7 }, { x: 25, y: 7 }] }];
  const scene = streetScene({ roads: [{ lanes: [lane('kept', [{ x: 0, y: 2 }, { x: 15, y: 2 }], 3.3, 1), lane('side', [{ x: 20, y: -30 }, { x: 20, y: -7 }], 3.3, 1)] }], signals,
    site_features: [{ id: 'pave', kind: 'junction_pavement', junction: 'j', zebra_lanes: ['kept'], shape }, { id: 'strip', kind: 'concrete', shape }, { id: 'paint', kind: 'marking', shape }, { id: 'citi', kind: 'building', shape }] });
  assert.equal(scene.junctions[0].polygon, shape);
  assert.ok(scene.junctions[0].crosswalks.length > 0);
  assert.deepEqual([scene.ground.map(f => f.id), scene.paint.map(f => f.id), scene.landmarks.map(f => f.id)], [['strip'], ['paint'], ['citi']]);
  const unlisted = streetScene({ roads: [{ lanes: [lane('side', [{ x: 20, y: -30 }, { x: 20, y: -7 }], 3.3, 1)] }], signals, site_features: [{ id: 'pave', kind: 'junction_pavement', junction: 'j', zebra_lanes: [], shape }] });
  assert.equal(unlisted.junctions[0].crosswalks.length, 0);
});
