import test from 'node:test';
import assert from 'node:assert/strict';
import { network } from '../src/network.js';
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
