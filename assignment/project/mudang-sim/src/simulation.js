// 1초 단위: 승객 도착 → 차량 도착·하차·승차 → 가능한 차량 출발 → 기록.
export function simulate({ route, demand, departures, fleetSize = 2, capacity = 20,
  duration = 3600, travelTime, snapshotEvery = 15 }) {
  const integer = (v, low, high) => Number.isInteger(v) && v >= low && v <= high;
  if (!integer(fleetSize, 1, 20) || !integer(capacity, 1, 200)
    || !integer(duration, 1, 86400) || !integer(snapshotEvery, 1, duration)) {
    throw new Error('차량 수·정원·실험 시간·기록 간격을 확인합니다.');
  }
  const end = route.visits.length - 1;
  if (end < 2 || route.visits[0].stopId !== route.visits[end].stopId) throw new Error('순환 노선이 필요합니다.');
  if (route.visits.some(v => !integer(v.dwell, 0, 3600))) throw new Error('정차시간은 0 이상의 정수 초입니다.');
  if (departures.some((t, i) => !integer(t, 0, duration - 1) || (i && t < departures[i - 1]))) {
    throw new Error('출발 시각은 실험 구간 안에서 오름차순이어야 합니다.');
  }
  const ids = new Set();
  const passengers = demand.map(p => {
    if (ids.has(p.id) || !integer(p.arrival, 0, duration - 1)
      || !integer(p.origin, 0, end - 1) || !integer(p.destination, p.origin + 1, end)
      || !route.visits[p.origin].pickup || !route.visits[p.destination].dropoff) {
      throw new Error('수요의 ID·시각·승하차 순서를 확인합니다.');
    }
    ids.add(p.id);
    return { ...p, boardedAt: null, alightedAt: null, vehicleId: null };
  }).sort((a, b) => a.arrival - b.arrival || String(a.id).localeCompare(String(b.id)));
  const queues = route.visits.map(() => []), snapshots = [], events = [], dispatches = [];
  const vehicles = Array.from({ length: fleetSize }, (_, id) => ({ id, onboard: [],
    active: false, from: 0, to: 0, departAt: 0, arriveAt: Infinity }));
  let incoming = 0, nextTrip = 0, completed = 0, boarded = 0;

  function visit(vehicle, stop, time) {
    const gettingOff = vehicle.onboard.filter(p => p.destination === stop);
    for (const p of gettingOff) { p.alightedAt = time; completed++; }
    vehicle.onboard = vehicle.onboard.filter(p => p.destination !== stop);
    let gettingOn = 0;
    // 종료 시점에는 새 승차 없이 하차만 반영합니다.
    if (time < duration && stop < end && route.visits[stop].pickup) {
      while (queues[stop].length && vehicle.onboard.length < capacity) {
        const p = queues[stop].shift();
        p.boardedAt = time; p.vehicleId = vehicle.id;
        vehicle.onboard.push(p); gettingOn++; boarded++;
      }
    }
    events.push({ time, vehicleId: vehicle.id, stop, board: gettingOn,
      alight: gettingOff.length, onboard: vehicle.onboard.length, waiting: queues[stop].length });
    vehicle.from = stop;
    if (stop === end) {
      vehicle.active = false; vehicle.from = 0; vehicle.to = 0; vehicle.arriveAt = Infinity;
      return;
    }
    vehicle.to = stop + 1;
    vehicle.departAt = time + (stop === 0 ? 0 : route.visits[stop].dwell);
    const travel = travelTime(stop, vehicle.departAt);
    if (!integer(travel, 1, 86400)) throw new Error('ETA는 양의 정수 초를 반환해야 합니다.');
    vehicle.arriveAt = vehicle.departAt + travel;
  }

  for (let time = 0; time <= duration; time++) {
    while (incoming < passengers.length && passengers[incoming].arrival <= time) {
      const passenger = passengers[incoming++]; queues[passenger.origin].push(passenger);
    }
    for (const vehicle of vehicles) {
      if (vehicle.active && vehicle.arriveAt === time) visit(vehicle, vehicle.to, time);
    }
    // 아직 돌아오지 않은 차량은 새 운행편에 중복 투입하지 않습니다.
    while (time < duration && nextTrip < departures.length && departures[nextTrip] <= time) {
      const vehicle = vehicles.find(v => !v.active);
      if (!vehicle) break;
      dispatches.push({ planned: departures[nextTrip], actual: time, vehicleId: vehicle.id });
      nextTrip++; vehicle.active = true; visit(vehicle, 0, time);
    }
    if (time % snapshotEvery === 0 || time === duration) {
      snapshots.push({ time, arrived: incoming, boarded, completed,
        queues: queues.map(q => q.length),
        vehicles: vehicles.map(v => ({ id: v.id, active: v.active, from: v.from,
          to: v.to, load: v.onboard.length, progress: !v.active || time <= v.departAt ? 0
            : Math.min(1, (time - v.departAt) / (v.arriveAt - v.departAt)) })) });
    }
  }
  const waits = passengers.filter(p => p.boardedAt !== null)
    .map(p => p.boardedAt - p.arrival).sort((a, b) => a - b);
  const mean = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
  const waiting = queues.reduce((n, q) => n + q.length, 0);
  return { passengers, snapshots, events, dispatches, summary: {
    total: passengers.length, boarded, completed, waiting, onboard: boarded - completed,
    meanWait: mean(waits), p90Wait: waits.length ? waits[Math.ceil(waits.length * 0.9) - 1] : null,
    waitingElapsed: mean(passengers.filter(p => p.boardedAt === null).map(p => duration - p.arrival)),
    meanDepartureDelay: mean(dispatches.map(d => d.actual - d.planned)),
    plannedTrips: departures.length, dispatchedTrips: dispatches.length,
    unstartedTrips: departures.length - dispatches.length,
  } };
}
