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
const clock = seconds => {
  const t = route.start + seconds;
  return `${String(Math.floor(t / 3600)).padStart(2, '0')}:${String(Math.floor(t / 60) % 60).padStart(2, '0')}`;
};
let result, timer, frame = 0;
$('#app').innerHTML = `
<header class="topbar"><div class="brand"><span class="bug" aria-hidden="true">●</span> 무당이 시뮬레이션 <span class="badge">실습 예제</span></div><span class="top-note">가상 직통 노선 · 실제 운행과 무관</span></header>
<main>
  <section class="intro"><div><p class="eyebrow">GACHON · SHUTTLE SIMULATION</p><h1>셔틀 운행 시뮬레이션</h1><p>차량의 이동과 정류장별 승하차를 확인합니다.</p></div><span class="period">예제 운행일 2026.11.02<br><strong>${clock(0)} — ${clock(duration)}</strong></span></section>
  <div class="notice"><span class="notice-dot"></span><p><strong>실제 운행 결과가 아닌 학습용 예제입니다.</strong> 반도체대학 ↔ AI공학관 직통 노선, 실제 도로 위에 가상 시간표·수요를 적용합니다. 정차점은 건물 인근의 예시 위치입니다.</p></div>
  <div class="workspace">
    <aside class="panel controls"><p class="eyebrow">01 / 실험 조건</p><h2>운행 설정</h2>
      <form id="controls">
        <label for="fleet">차량 수 <span>대</span></label><input id="fleet" type="number" value="2" min="1" max="4" required>
        <label for="headway">배차간격 <span>분</span></label><input id="headway" type="number" value="10" min="2" max="30" required>
        <label for="capacity">차량 정원 <span>명</span></label><input id="capacity" type="number" value="20" min="1" max="50" required>
        <button class="primary" type="submit">설정 적용 <span>→</span></button><button id="reset" type="button" class="quiet">초기화</button>
      </form><p id="status" role="status" class="status"></p>
      <p class="help bottom-note">예제 조건: 편도 5분 · 승객 180명/시간</p>
    </aside>
    <div class="results">
      <section class="panel route-panel"><div class="section-head"><div><p class="eyebrow">02 / 운행 재생</p><h2>차량 위치</h2></div><span class="live-time" id="clock">11:00</span></div>
        <div class="map-label"><span>실제 교내 도로 · 최단거리 경로</span><span>정류장: 대기인원 · 차량: 탑승인원</span></div>
        <div id="route-map" aria-label="교내 도로와 차량 위치 지도"></div><p class="help" id="map-note">초록색 선: 운행 경로 · 지도를 움직이거나 확대할 수 있습니다.</p>
        <div class="playback"><button id="play" type="button" aria-label="운행 재생">▶ 재생</button><label class="sr-only" for="timeline">운행 시각</label><input type="range" id="timeline" min="0" max="240" value="0"><span id="frame-label">0 / 60분</span></div>
        <div class="snapshot-info" id="snapshot-info"></div>
      </section>
      <section class="metric-grid" aria-label="재생 시각의 승객 현황">
        <article><span>정류장 도착 누계</span><strong id="arrived">0명</strong></article>
        <article><span>대기 중</span><strong id="waiting">0명</strong></article>
        <article><span>탑승 중</span><strong id="onboard">0명</strong></article>
        <article><span>하차 완료</span><strong id="completed">0명</strong></article>
      </section>
    </div>
  </div>
</main>`;

const routeMap = createRouteMap(network, paths, route.visits, stopNodes, colors);

function pause() { clearInterval(timer); timer = null; $('#play').textContent = '▶ 재생'; }
function showFrame(index) {
  frame = Math.max(0, Math.min(index, result.snapshots.length - 1));
  const snap = result.snapshots[frame];
  $('#timeline').value = frame; $('#clock').textContent = clock(snap.time);
  $('#frame-label').textContent = `${Math.floor(snap.time / 60)} / 60분`;
  routeMap.update(snap);
  const counts = { arrived: snap.arrived, waiting: snap.queues.reduce((a, b) => a + b, 0),
    onboard: snap.boarded - snap.completed, completed: snap.completed };
  for (const [key, value] of Object.entries(counts)) $(`#${key}`).textContent = `${value}명`;
  $('#snapshot-info').textContent = '아래 인원은 현재 재생 시각 기준입니다.';
}

function run() {
  pause();
  try {
    const demand = exampleDemand(route, duration, 180, seed);
    result = simulate({ route, demand, duration, snapshotEvery: 1,
      fleetSize: +$('#fleet').value, capacity: +$('#capacity').value,
      departures: headwayDepartures(duration, +$('#headway').value * 60),
      travelTime: (leg, time) => timetableETA(route, leg, time) });
    $('#timeline').max = result.snapshots.length - 1;
    showFrame(0);
    $('#status').textContent = '재생을 누르면 차량이 출발합니다.';
  } catch (error) { $('#status').textContent = `실행 오류: ${error.message}`; }
}
$('#controls').addEventListener('submit', event => { event.preventDefault(); run(); });
$('#controls').addEventListener('input', () => { $('#status').textContent = '설정 적용을 누르면 처음부터 다시 계산합니다.'; });
$('#reset').addEventListener('click', () => { HTMLFormElement.prototype.reset.call($('#controls')); run(); });
$('#play').addEventListener('click', () => {
  if (!result) return;
  if (timer) { pause(); return; }
  if (frame === result.snapshots.length - 1) showFrame(0);
  $('#play').textContent = 'Ⅱ 일시정지';
  timer = setInterval(() => { showFrame(frame + 1); if (frame === result.snapshots.length - 1) pause(); }, 50);
});
$('#timeline').addEventListener('input', event => { pause(); showFrame(+event.target.value); });
run();
