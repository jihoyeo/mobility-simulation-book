// 단일 순환 노선·동일 정차 패턴만 읽는 실습용 GTFS 어댑터입니다.
export function csv(text) {
  const rows = []; let row = [], field = '', quoted = false;
  const source = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n');
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (c === '"') {
      if (quoted && source[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (c === ',' || c === '\n')) {
      row.push(field); field = '';
      if (c === '\n') { if (row.some(Boolean)) rows.push(row); row = []; }
    } else field += c;
  }
  if (quoted) throw new Error('CSV 따옴표가 닫히지 않았습니다.');
  if (field || row.length) { row.push(field); rows.push(row); }
  const header = rows.shift() ?? [];
  return rows.map(values => {
    if (values.length !== header.length) throw new Error('CSV 열 수가 맞지 않습니다.');
    return Object.fromEntries(header.map((key, i) => [key, values[i]]));
  });
}

export function seconds(value) {
  if (!/^\d{2,}:\d{2}:\d{2}$/.test(value)) throw new Error(`GTFS 시각 오류: ${value}`);
  const [h, m, s] = value.split(':').map(Number);
  if (m > 59 || s > 59) throw new Error(`GTFS 시각 오류: ${value}`);
  return h * 3600 + m * 60 + s;
}

export function readFeed(files, serviceDate = '20261102') {
  const tables = Object.fromEntries(Object.entries(files).map(([key, text]) => [key, csv(text)]));
  for (const key of ['stops', 'routes', 'trips', 'stop_times', 'calendar']) {
    if (!tables[key]) throw new Error(`${key}.txt가 필요합니다.`);
  }
  if (tables.routes.length !== 1) throw new Error('이 예제는 노선 하나만 지원합니다.');
  const date = new Date(`${serviceDate.slice(0, 4)}-${serviceDate.slice(4, 6)}-${serviceDate.slice(6)}T00:00:00Z`);
  const day = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'][date.getUTCDay()];
  const services = new Set(tables.calendar.filter(r => r.start_date <= serviceDate
    && serviceDate <= r.end_date && r[day] === '1').map(r => r.service_id));
  for (const r of tables.calendar_dates ?? []) {
    if (r.date === serviceDate) {
      if (r.exception_type === '1') services.add(r.service_id);
      if (r.exception_type === '2') services.delete(r.service_id);
    }
  }
  const stops = new Map(tables.stops.map(r => [r.stop_id, r]));
  const trips = tables.trips.filter(r => services.has(r.service_id)).map(trip => {
    if (trip.route_id !== tables.routes[0].route_id) throw new Error('route_id가 일치하지 않습니다.');
    const times = tables.stop_times.filter(r => r.trip_id === trip.trip_id)
      .sort((a, b) => Number(a.stop_sequence) - Number(b.stop_sequence));
    const visits = times.map((r, i) => {
      if (!stops.has(r.stop_id)) throw new Error(`없는 정류장: ${r.stop_id}`);
      if (i && Number(r.stop_sequence) <= Number(times[i - 1].stop_sequence)) throw new Error('stop_sequence 오류');
      for (const key of ['pickup_type', 'drop_off_type']) {
        if (!['', '0', '1'].includes(r[key] ?? '')) throw new Error('예약 승하차는 지원하지 않습니다.');
      }
      const arrival = seconds(r.arrival_time), departure = seconds(r.departure_time);
      if (departure < arrival) throw new Error('출발 시각이 도착 시각보다 빠릅니다.');
      return { stopId: r.stop_id, name: stops.get(r.stop_id).stop_name, arrival, departure,
        pickup: r.pickup_type !== '1', dropoff: r.drop_off_type !== '1' };
    });
    if (visits.length < 3 || visits[0].stopId !== visits.at(-1).stopId) {
      throw new Error('이 예제는 같은 정류장으로 돌아오는 순환 노선을 사용합니다.');
    }
    const travel = visits.slice(1).map((v, i) => v.arrival - visits[i].departure);
    if (travel.some(t => t <= 0)) throw new Error('구간 이동시간은 양수여야 합니다.');
    return { id: trip.trip_id, start: visits[0].departure, visits, travel };
  }).sort((a, b) => a.start - b.start);
  if (!trips.length) throw new Error('선택한 날짜에 운행하는 예제 편이 없습니다.');
  const pattern = t => JSON.stringify([t.travel, t.visits.map(v =>
    [v.stopId, v.departure - v.arrival, v.pickup, v.dropoff])]);
  if (trips.some(t => pattern(t) !== pattern(trips[0]))) {
    throw new Error('운행편별 정차 순서·구간시간이 다른 GTFS는 어댑터 확장이 필요합니다.');
  }
  const first = trips[0];
  return { serviceDate, start: first.start, departures: trips.map(t => t.start - first.start),
    tripIds: trips.map(t => t.id), travelSeconds: first.travel,
    visits: first.visits.map(v => ({ stopId: v.stopId, name: v.name,
      dwell: v.departure - v.arrival, pickup: v.pickup, dropoff: v.dropoff })) };
}
