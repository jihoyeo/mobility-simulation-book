import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { simulate } from '../src/simulation.js';
import { readFeed, seconds, csv } from '../src/gtfs.js';
import { exampleDemand, timetableETA } from '../src/models.js';

const files = Object.fromEntries(['stops', 'routes', 'trips', 'stop_times', 'calendar', 'calendar_dates']
  .map(name => [name, readFileSync(new URL(`../demo-gtfs/${name}.txt`, import.meta.url), 'utf8')]));
const demo = readFeed(files);
const route = { visits: [
  { stopId: 'A', name: 'A', dwell: 0, pickup: true, dropoff: false },
  { stopId: 'B', name: 'B', dwell: 0, pickup: true, dropoff: true },
  { stopId: 'A', name: 'A', dwell: 0, pickup: false, dropoff: true },
] };
const run = options => simulate({ route, duration: 40, snapshotEvery: 1,
  departures: [0, 20], fleetSize: 1, capacity: 1, travelTime: () => 10, demand: [], ...options });

test('정원 초과 승객은 다음 회차까지 기다립니다', () => {
  const demand = [0, 1].map(id => ({ id, arrival: 0, origin: 0, destination: 1 }));
  const result = run({ demand });
  assert.deepEqual(result.passengers.map(p => p.boardedAt), [0, 20]);
  assert.deepEqual(result.passengers.map(p => p.alightedAt), [10, 30]);
  assert.equal(result.summary.meanWait, 10);
  assert.equal(result.summary.completed, 2);
  assert.equal(demand[0].boardedAt, undefined);
});

test('하차로 생긴 자리에 같은 시각 도착 승객이 탑승합니다', () => {
  const result = run({ demand: [
    { id: 0, arrival: 0, origin: 0, destination: 1 },
    { id: 1, arrival: 10, origin: 1, destination: 2 },
  ] });
  assert.equal(result.passengers[1].boardedAt, 10);
  assert.equal(result.passengers[1].alightedAt, 20);
  assert.deepEqual(result.events.find(e => e.time === 10),
    { time: 10, vehicleId: 0, stop: 1, board: 1, alight: 1, onboard: 1, waiting: 0 });
});

test('차량이 돌아오기 전에는 새 운행편에 중복 투입되지 않습니다', () => {
  const result = run({ departures: [0, 5, 10], duration: 31 });
  assert.deepEqual(result.dispatches.map(d => d.actual), [0, 20]);
  assert.equal(result.summary.unstartedTrips, 1);
  assert.equal(result.summary.meanDepartureDelay, 7.5);
});

test('종료 시 대기·차내·도착 완료를 구분합니다', () => {
  const result = run({ duration: 5, departures: [0], demand: [
    { id: 0, arrival: 0, origin: 0, destination: 1 },
    { id: 1, arrival: 1, origin: 0, destination: 1 },
  ] });
  assert.deepEqual([result.summary.waiting, result.summary.onboard, result.summary.completed], [1, 1, 0]);
  assert.equal(result.summary.meanWait, 0);
  assert.equal(result.summary.waitingElapsed, 4);
  assert.equal(result.passengers[0].alightedAt, null);
});

test('종료 시각에 내리는 승객은 완료하고 새 승객은 태우지 않습니다', () => {
  const result = run({ duration: 10, departures: [0], demand: [
    { id: 0, arrival: 0, origin: 0, destination: 1 },
    { id: 1, arrival: 9, origin: 1, destination: 2 },
  ] });
  assert.equal(result.summary.completed, 1);
  assert.equal(result.summary.waiting, 1);
});

test('빈 수요의 평균 대기는 0이 아닌 null입니다', () => {
  const result = run({});
  assert.equal(result.summary.total, 0);
  assert.equal(result.summary.meanWait, null);
});

test('운행편이 없으면 전원이 대기합니다', () => {
  const result = run({ departures: [], demand: [{ id: 'a', arrival: 3, origin: 0, destination: 1 }] });
  assert.equal(result.summary.waiting, 1);
  assert.equal(result.summary.waitingElapsed, 37);
});

test('ETA 교체가 실제 도착 시각을 바꿉니다', () => {
  const demand = [{ id: 0, arrival: 0, origin: 0, destination: 1 }];
  assert.equal(run({ demand, travelTime: (leg, departure) => departure === 0 ? 15 : 10 }).passengers[0].alightedAt, 15);
  assert.throws(() => run({ travelTime: () => 0 }), /ETA/);
});

test('가상 GTFS의 시간표·달력·반복 정류장을 읽습니다', () => {
  assert.equal(demo.start, 39600);
  assert.deepEqual(demo.departures, [0, 600, 1200, 1800, 2400, 3000]);
  assert.equal(demo.visits.length, 3);
  assert.equal(demo.visits[0].stopId, demo.visits[2].stopId);
  assert.equal(demo.visits[2].pickup, false);
  assert.equal(seconds('25:01:02'), 90062);
  assert.throws(() => seconds('11:99:00'));
  assert.throws(() => readFeed(files, '20261101'), /운행/);
  const exceptions = { ...files, calendar_dates: 'service_id,date,exception_type\nCLASS,20261102,2\n' };
  assert.throws(() => readFeed(exceptions), /운행/);
  exceptions.calendar_dates = 'service_id,date,exception_type\nCLASS,20261101,1\n';
  assert.equal(readFeed(exceptions, '20261101').departures.length, 6);
});

test('CSV 따옴표·쉼표·줄바꿈을 보존합니다', () => {
  assert.deepEqual(csv('id,name\r\nA,"a,b"\r\nB,"say ""yes"""\r\nC,"a\nb"\r\n'),
    [{ id: 'A', name: 'a,b' }, { id: 'B', name: 'say "yes"' }, { id: 'C', name: 'a\nb' }]);
});

test('시드가 같으면 같은 수요이고 가상 OD는 서로 다른 정류장입니다', () => {
  const a = exampleDemand(demo, 3600, 180, 42);
  assert.deepEqual(a, exampleDemand(demo, 3600, 180, 42));
  assert.notDeepEqual(a, exampleDemand(demo, 3600, 180, 43));
  assert.ok(a.every(p => demo.visits[p.origin].stopId !== demo.visits[p.destination].stopId));
});

test('모든 스냅샷에서 인원 보존과 차량 정원을 만족합니다', () => {
  for (const fleetSize of [1, 2, 4]) {
    const demand = exampleDemand(demo, 3600, 300, 42);
    const result = simulate({ route: demo, demand, duration: 3600, departures: demo.departures,
      fleetSize, capacity: 12, travelTime: (i, t) => timetableETA(demo, i, t) });
    for (const s of result.snapshots) {
      assert.equal(s.arrived, s.completed + s.queues.reduce((a, b) => a + b, 0)
        + s.vehicles.reduce((a, b) => a + b.load, 0));
      assert.ok(s.vehicles.every(v => v.load <= 12));
    }
    const s = result.summary;
    assert.equal(s.total, s.completed + s.waiting + s.onboard);
    assert.ok(result.passengers.every(p => p.boardedAt === null || p.boardedAt >= p.arrival));
  }
});
