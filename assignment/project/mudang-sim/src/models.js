// 학생은 이 두 함수를 관측 자료로 만든 모형으로 교체합니다.
export function exampleDemand(route, duration, count = 180, seed = 42) {
  if (!Number.isInteger(count) || count < 0 || count > 10000) throw new Error('수요는 0~10000명입니다.');
  let state = seed >>> 0;
  const random = () => ((state = (1664525 * state + 1013904223) >>> 0) / 4294967296);
  const origins = route.visits.flatMap((v, i) => v.pickup && i < route.visits.length - 1 ? [i] : []);
  if (!origins.length && count) throw new Error('승차 가능한 정류장이 없습니다.');
  return Array.from({ length: count }, (_, id) => {
    const origin = random() < 0.6 ? origins[0] : origins[Math.floor(random() * origins.length)];
    const destinations = route.visits.flatMap((v, i) => i > origin && v.dropoff && v.stopId !== route.visits[origin].stopId ? [i] : []);
    if (!destinations.length) throw new Error('하차 가능한 목적지가 없습니다.');
    return { id, arrival: Math.floor(random() * duration), origin,
      destination: destinations[Math.floor(random() * destinations.length)] };
  }).sort((a, b) => a.arrival - b.arrival || a.id - b.id);
}

export function timetableETA(route, legIndex, departureSecond, scale = 1) {
  // departureSecond를 받으므로 시간대별 ETA로 교체할 수 있습니다.
  return Math.round(route.travelSeconds[legIndex] * scale);
}

export function headwayDepartures(duration, headwaySeconds) {
  if (!Number.isFinite(headwaySeconds) || headwaySeconds <= 0) throw new Error('배차간격은 양수입니다.');
  return Array.from({ length: Math.ceil(duration / headwaySeconds) }, (_, i) => i * headwaySeconds);
}
