import test from 'node:test';
import assert from 'node:assert/strict';
const network = {
  nodes: {
    A: { x: 120, y: 225 }, U1: { x: 280, y: 125 }, U2: { x: 500, y: 125 },
    B: { x: 680, y: 225 }, L1: { x: 280, y: 325 }, L2: { x: 500, y: 325 },
  },
  // 양방향 도로도 두 개의 유향 링크로 표현합니다.
  edges: [ ['A', 'U1', 180], ['U1', 'U2', 220], ['U2', 'B', 180],
    ['A', 'L1', 210], ['L1', 'L2', 250], ['L2', 'B', 210] ]
    .flatMap(([from, to, meters]) => [{ from, to, meters }, { from: to, to: from, meters }]),
};

import { shortestPath, positionOnPath } from '../src/routing.js';

test('가상 도로의 최단거리 경로는 580m입니다', () => {
  const path = shortestPath(network, 'A', 'B');
  assert.equal(path.meters, 580);
  assert.deepEqual(path.nodes, ['A', 'U1', 'U2', 'B']);
  assert.deepEqual(positionOnPath(path, network, 0), [120, 225]);
  assert.deepEqual(positionOnPath(path, network, 1), [680, 225]);
  assert.deepEqual(positionOnPath(path, network, 180 / 580), [280, 125]);
});

test('거리 변경이 선택 경로를 바꿉니다', () => {
  const changed = { ...network, edges: network.edges.map(e =>
    e.from === 'U1' && e.to === 'U2' ? { ...e, meters: 1000 } : e) };
  const path = shortestPath(changed, 'A', 'B');
  assert.equal(path.meters, 670);
  assert.deepEqual(path.nodes, ['A', 'L1', 'L2', 'B']);
});

test('역방향·단절·미등록 노드·잘못된 거리를 구분합니다', () => {
  assert.deepEqual(shortestPath(network, 'B', 'A').nodes, ['B', 'U2', 'U1', 'A']);
  assert.throws(() => shortestPath({ ...network, edges: [] }, 'A', 'B'), /경로/);
  assert.throws(() => shortestPath(network, 'X', 'B'), /노드/);
  assert.throws(() => shortestPath({ ...network, edges: [{ from: 'A', to: 'B', meters: -1 }] }, 'A', 'B'), /거리/);
});

// 실제 도로 경로의 모든 굴곡 노드를 유지하는지 확인합니다.
test('교내 도로의 왕복 경로와 위치 보간', async () => {
  const { network: roads, stopNodes } = await import('../src/network.js');
  for (const [a,b] of [['S0','S1'],['S1','S0']]) {
    const p = shortestPath(roads, stopNodes[a], stopNodes[b]);
    assert.ok(p.nodes.length > 30);
    assert.ok(p.meters > 900 && p.meters < 1100);
    let distance = 0;
    for (const e of p.links) {
      const position = positionOnPath(p, roads, (distance + e.meters / 2) / p.meters);
      const from = roads.nodes[e.from], to = roads.nodes[e.to];
      assert.ok(Math.abs(position[0] - (from.x + to.x)/2) < 1e-9);
      assert.ok(Math.abs(position[1] - (from.y + to.y)/2) < 1e-9);
      distance += e.meters;
    }
  }
});
