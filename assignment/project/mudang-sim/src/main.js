import './style.css';
import stops from '../demo-gtfs/stops.txt?raw';
import routes from '../demo-gtfs/routes.txt?raw';
import trips from '../demo-gtfs/trips.txt?raw';
import stop_times from '../demo-gtfs/stop_times.txt?raw';
import calendar from '../demo-gtfs/calendar.txt?raw';
import calendar_dates from '../demo-gtfs/calendar_dates.txt?raw';
import { readFeed } from './gtfs.js';
import { exampleDemand, timetableETA, headwayDepartures } from './models.js';
import { simulate } from './simulation.js';
import { network, stopNodes } from './network.js';
import { createRouteMap } from './map.js';
import { connectRoute } from './routing.js';

const route = readFeed({ stops, routes, trips, stop_times, calendar, calendar_dates });
const paths = connectRoute(route, network, stopNodes);
const duration = 3600, seed = 42;
const colors = ['#c94b40', '#186a80', '#bc8728', '#75539c'];
const $ = selector => document.querySelector(selector);
const escape = value => String(value).replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
const clock = seconds => {
  const t = route.start + seconds;
  return `${String(Math.floor(t / 3600)).padStart(2, '0')}:${String(Math.floor(t / 60) % 60).padStart(2, '0')}`;
};
const minutes = seconds => seconds === null ? '—' : (seconds / 60).toFixed(1);
let baseline, result, demand, config, timer, frame = 0;
$('#app').innerHTML = `
<header class="topbar"><div class="brand"><span class="bug" aria-hidden="true">●</span> 무당이 실험실 <span class="badge">조교 실습용 MVP</span></div><span class="top-note">가상 직통 노선 · 실제 운행과 무관</span></header>
<main>
  <section class="intro"><div><p class="eyebrow">GACHON · SHUTTLE SIMULATION</p><h1>같은 수요, 다른 운행.</h1><p>차량 수와 배차간격을 바꾸고, 정류장의 기다림을 비교해 봅니다.</p></div><span class="period">예제 운행일 2026.11.02<br><strong>${clock(0)} — ${clock(duration)}</strong></span></section>
  <div class="notice"><span class="notice-dot"></span><p><strong>실제 운행 결과가 아닌 학습용 예제입니다.</strong> 반도체대학 ↔ AI공학관 직통 노선, 실제 도로 위에 가상 시간표·수요를 적용합니다. 정차점은 건물 인근의 예시 위치입니다.</p></div>
  <div class="workspace">
    <aside class="panel controls"><p class="eyebrow">01 / 실험 조건</p><h2>운행을 바꿔 봅시다</h2>
      <form id="controls">
        <label for="fleet">차량 수 <span>대</span></label><input id="fleet" type="number" value="2" min="1" max="4" required>
        <label for="headway">목표 배차간격 <span>분</span></label><input id="headway" type="number" value="10" min="2" max="30" required>
        <label for="capacity">차량 정원 <span>명</span></label><input id="capacity" type="number" value="20" min="1" max="50" required>
        <label for="eta">구간 이동시간 배율</label><select id="eta"><option value="0.75">0.75배 · 더 빠르게</option><option value="1" selected>1.00배 · GTFS 기준</option><option value="1.5">1.50배 · 더 느리게</option><option value="2">2.00배 · 더 느리게</option></select>
        <div class="divider"></div><label for="demand">공통 예제 수요 <span>명 / 1시간</span></label><input id="demand" type="number" min="0" max="600" value="180" step="10" required>
        <p class="help">두 시나리오에 같은 승객 목록을 사용합니다. 난수 시드는 42입니다.</p>
        <button class="primary" type="submit">시나리오 실행 <span>→</span></button><button id="reset" type="button" class="quiet">기본값으로 되돌리기</button>
      </form><p id="status" role="status" class="status"></p>
      <p class="help bottom-note">기준 운행: GTFS 출발 시각 · 2대 · 정원 20명 · 이동시간 1배</p>
    </aside>
    <div class="results">
      <section class="panel route-panel"><div class="section-head"><div><p class="eyebrow">02 / 운행 재생</p><h2>정류장에서 일어나는 일</h2></div><span class="live-time" id="clock">11:00</span></div>
        <div class="map-label"><span>실제 교내 도로 · 최단거리 경로</span><span>● 정류장 옆 숫자 = 대기인원</span></div>
        <div id="route-map" aria-label="교내 도로와 차량 위치 지도"></div><p class="help" id="map-note">드래그·확대 가능 · 초록색은 도로 최단경로 · 차량 숫자는 탑승인원</p>
        <div class="playback"><button id="play" type="button" aria-label="운행 재생">▶ 재생</button><label class="sr-only" for="timeline">운행 시각</label><input type="range" id="timeline" min="0" max="240" value="0"><span id="frame-label">0 / 60분</span></div>
        <div class="snapshot-info" id="snapshot-info"></div>
      </section>
      <section class="metric-grid" aria-label="실험 종료 시점의 결과"><article><span>탑승자의 평균 대기</span><strong id="mean">—</strong><small>실제 탑승 시각 − 도착 시각</small></article><article><span>도착 완료</span><strong id="completed">—</strong><small>실험 종료 전 하차한 승객</small></article><article><span>종료 시 미탑승</span><strong id="waiting">—</strong><small>아직 정류장에서 기다리는 승객</small></article><article><span>종료 시 차내</span><strong id="onboard">—</strong><small>탑승했지만 아직 하차 전인 승객</small></article></section>
      <section class="panel comparison"><div class="section-head"><div><p class="eyebrow">03 / 같은 조건에서 비교</p><h2>종료 시점의 결과</h2></div><button id="download" class="small-button" type="button">결과 JSON ↓</button></div><p class="help">수요가 남아 있으면 탑승자의 평균 대기만으로 개선 여부를 판단하지 않습니다.</p>
        <div class="table-scroll"><table><thead><tr><th>지표</th><th>기준 운행</th><th>실험 운행</th></tr></thead><tbody id="comparison"></tbody></table></div>
        <div class="chart-title">시간에 따른 전체 대기인원 <span><i class="legend base"></i>기준 <i class="legend scenario"></i>실험</span></div><svg id="queue-chart" viewBox="0 0 760 150" role="img" aria-label="기준 운행과 실험 운행의 대기인원 추이"></svg>
      </section>
      <details class="panel detail-panel"><summary>승하차 기록 보기</summary><div class="table-scroll"><table><thead><tr><th>시각</th><th>차량</th><th>정류장</th><th>승차</th><th>하차</th><th>차내</th><th>대기</th></tr></thead><tbody id="events"></tbody></table></div><p class="help">최근 12개 정차 기록입니다. 전체 기록은 결과 JSON에 포함됩니다.</p></details>
    </div>
  </div>
  <details class="panel learning"><summary>이 예제로 확인할 것 · 학생이 개발할 것</summary><div class="learning-grid"><div><h3>제공하는 계산</h3><p>GTFS 읽기, 선착순 대기열, 하차 후 승차, 차량 정원, 차량 회차, 결과 비교입니다. 저장된 OSM 도로망의 최단거리 경로는 다익스트라로 구합니다. RAPTOR는 사용하지 않습니다.</p></div><div><h3>학생이 채우는 모형</h3><p>실제 GTFS·도로망, 관측 기반 ETA, 시간대별 수요·OD와 검증 자료를 구축합니다. 완성 대시보드와 운영 개선안도 학생의 과제입니다.</p></div><div><h3>예제의 범위</h3><p>두 정류장만 오가는 가상의 직통 노선입니다. 모든 차량은 반도체대학에서 출발합니다. 도로 좌표는 OSM 자료이며, 노선·정차점·시간표·수요는 실습용입니다.</p></div></div><p class="sources">GTFS → 도로 경로 → ETA·수요 → 승하차 → 화면 순서로 연결합니다. <a href="https://gtfs.org/documentation/schedule/reference/">GTFS 명세 ↗</a><br>예제는 실행 구조를 익히기 위한 출발점입니다. 실제 무당이 자료는 직접 구축합니다.</p></details>
</main><footer>무당이 시뮬레이션 실습 <span>가상 GTFS → 도로 경로 → 승객 대기열 → 운행 결과</span></footer>`;

const routeMap = createRouteMap(network, paths, route.visits, stopNodes, colors);

function pause() { clearInterval(timer); timer = null; $('#play').textContent = '▶ 재생'; }
function showFrame(index) {
  frame = Math.max(0, Math.min(index, result.snapshots.length - 1));
  const snap = result.snapshots[frame];
  $('#timeline').value = frame; $('#clock').textContent = clock(snap.time);
  $('#frame-label').textContent = `${Math.floor(snap.time / 60)} / 60분`;
  routeMap.update(snap);
  $('#snapshot-info').textContent = `현재까지 도착 ${snap.arrived}명 · 대기 ${snap.queues.reduce((a, b) => a + b, 0)}명 · 차내 ${snap.boarded - snap.completed}명 · 도착 완료 ${snap.completed}명`;
}

function drawResults() {
  const s = result.summary;
  $('#mean').textContent = `${minutes(s.meanWait)} 분`;
  for (const key of ['completed', 'waiting', 'onboard']) $(`#${key}`).textContent = `${s[key]} 명`;
  const rows = [ ['총 수요', 'total', '명'], ['탑승 누계', 'boarded', '명'], ['도착 완료', 'completed', '명'],
    ['종료 시 미탑승', 'waiting', '명'], ['종료 시 차내', 'onboard', '명'],
    ['탑승자 평균 대기', 'meanWait', '분'], ['탑승자 대기시간 90백분위', 'p90Wait', '분'],
    ['미탑승자의 현재까지 평균 대기', 'waitingElapsed', '분'], ['실제 출발편', 'dispatchedTrips', '편'],
    ['아직 출발 못 한 예정편', 'unstartedTrips', '편'], ['출발편 평균 지연', 'meanDepartureDelay', '분'] ];
  $('#comparison').innerHTML = rows.map(([name, key, unit]) => `<tr><th scope="row">${name}</th>${[baseline, result].map(r => `<td>${unit === '분' ? minutes(r.summary[key]) : r.summary[key]} ${unit}</td>`).join('')}</tr>`).join('');
  const max = Math.max(1, ...[baseline, result].flatMap(r => r.snapshots.map(s => s.queues.reduce((a, b) => a + b, 0))));
  const line = r => r.snapshots.map(s => `${35 + s.time / duration * 705},${115 - s.queues.reduce((a, b) => a + b, 0) / max * 95}`).join(' ');
  $('#queue-chart').innerHTML = `<path d="M35 20V115H740" fill="none" stroke="#dce5df"/><text x="5" y="24" class="chart-label">${max}명</text><text x="15" y="119" class="chart-label">0</text><text x="35" y="141" class="chart-label">${clock(0)}</text><text x="700" y="141" class="chart-label">${clock(duration)}</text><polyline points="${line(baseline)}" fill="none" stroke="#aeb9b5" stroke-width="3"/><polyline points="${line(result)}" fill="none" stroke="#186a80" stroke-width="2.5"/>`;
  $('#events').innerHTML = result.events.slice(-12).map(e => `<tr><td>${clock(e.time)}</td><td>${e.vehicleId + 1}호</td><td>${escape(route.visits[e.stop].name)}</td><td>${e.board}</td><td>${e.alight}</td><td>${e.onboard}</td><td>${e.waiting}</td></tr>`).join('');
}

function run() {
  pause();
  try {
    config = { fleetSize: +$('#fleet').value, capacity: +$('#capacity').value,
      headwayMinutes: +$('#headway').value, etaScale: +$('#eta').value, count: +$('#demand').value };
    demand = exampleDemand(route, duration, config.count, seed);
    const common = { route, demand, duration, snapshotEvery: 1 };
    baseline = simulate({ ...common, departures: route.departures.filter(t => t < duration),
      travelTime: (leg, time) => timetableETA(route, leg, time) });
    result = simulate({ ...common, fleetSize: config.fleetSize, capacity: config.capacity,
      departures: headwayDepartures(duration, config.headwayMinutes * 60),
      travelTime: (leg, time) => timetableETA(route, leg, time, config.etaScale) });
    $('#timeline').max = result.snapshots.length - 1;
    drawResults(); showFrame(0);
    $('#status').textContent = `계산 완료 · 두 시나리오에 동일한 ${demand.length}명 적용`;
  } catch (error) { $('#status').textContent = `실행 오류: ${error.message}`; }
}
$('#controls').addEventListener('submit', event => { event.preventDefault(); run(); });
$('#controls').addEventListener('input', () => { $('#status').textContent = '조건 변경됨 · 시나리오 실행을 누르면 반영됩니다.'; });
$('#reset').addEventListener('click', () => { HTMLFormElement.prototype.reset.call($('#controls')); run(); });
$('#play').addEventListener('click', () => {
  if (!result) return;
  if (timer) { pause(); return; }
  if (frame === result.snapshots.length - 1) showFrame(0);
  $('#play').textContent = 'Ⅱ 일시정지';
  timer = setInterval(() => { showFrame(frame + 1); if (frame === result.snapshots.length - 1) pause(); }, 50);
});
$('#timeline').addEventListener('input', event => { pause(); showFrame(+event.target.value); });
$('#download').addEventListener('click', () => {
  if (!result) return;
  const payload = { exampleOnly: true, serviceDate: route.serviceDate, duration, seed, config,
    network, stopNodes, paths, baselineConfig: { fleetSize: 2, capacity: 20, etaScale: 1, departures: route.departures }, route,
    demand, baseline, scenario: result };
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = 'mudang-scenario.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
run();
