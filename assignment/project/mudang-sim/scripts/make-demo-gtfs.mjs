// 두 정류장의 가상 GTFS를 생성합니다. 실제 교내 자료는 아닙니다.
import { mkdirSync, writeFileSync } from 'node:fs';
const directory = new URL('../demo-gtfs/', import.meta.url);
mkdirSync(directory, { recursive: true });
function write(name, header, rows) {
  const quote = value => '"' + String(value).replaceAll('"', '""') + '"';
  const text = [header, ...rows].map(row => row.map(quote).join(',')).join('\n') + '\n';
  writeFileSync(new URL(`${name}.txt`, directory), text);
}
function clock(seconds) {
  return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60]
    .map(value => String(value).padStart(2, '0')).join(':');
}
write('agency', ['agency_id', 'agency_name', 'agency_url', 'agency_timezone'],
  [['DEMO', '실습용 가상 셔틀', 'https://www.gachon.ac.kr', 'Asia/Seoul']]);
write('stops', ['stop_id', 'stop_name', 'stop_lat', 'stop_lon'], [
  ['S0', '반도체대학', 37.4500, 127.1280],
  ['S1', 'AI공학관', 37.4530, 127.1310],
]);
write('routes', ['route_id', 'agency_id', 'route_short_name', 'route_long_name', 'route_type'],
  [['DEMO', 'DEMO', '가상 직통', '반도체대학–AI공학관 가상 왕복', 3]]);
write('calendar', ['service_id', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
  'saturday', 'sunday', 'start_date', 'end_date'], [['CLASS', 1, 1, 1, 1, 1, 0, 0, '20260101', '20261231']]);
write('calendar_dates', ['service_id', 'date', 'exception_type'], []);
const trips = [], times = [];
for (let i = 0; i < 6; i++) {
  const id = `DEMO_${String(i).padStart(2, '0')}`, start = 11 * 3600 + i * 600;
  trips.push(['DEMO', 'CLASS', id]);
  // 편도 5분, AI공학관 정차 30초, 회차 후 반도체대학 도착으로 가정합니다.
  times.push([id, clock(start), clock(start), 'S0', 1, 0, 1]);
  times.push([id, clock(start + 300), clock(start + 330), 'S1', 2, 0, 0]);
  times.push([id, clock(start + 630), clock(start + 630), 'S0', 3, 1, 0]);
}
write('trips', ['route_id', 'service_id', 'trip_id'], trips);
write('stop_times', ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence',
  'pickup_type', 'drop_off_type'], times);
console.log('demo-gtfs/에 가상 두 정류장 시간표를 생성했습니다.');
