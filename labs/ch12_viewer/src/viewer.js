// =============================================================================
// 배선. 고칠 것이 없습니다.
//
// main.js 의 다섯 함수를 deck.gl 레이어로 엮고, 재생 버튼과 슬라이더를 붙입니다.
// DTUMOS 프론트엔드에서 이 부분에 해당하는 코드가 1,700줄쯤 됩니다.
// 패널과 필터와 테마와 차트를 걷어내면 아래만 남습니다.
// =============================================================================

import { Deck } from "@deck.gl/core";
import { BitmapLayer, ScatterplotLayer } from "@deck.gl/layers";
import { TileLayer, TripsLayer } from "@deck.gl/geo-layers";

import { COLOR } from "./palette.js";
import {
  nextTime,
  tripColor,
  tripPath,
  tripTimestamps,
  waitingPassengers,
} from "./main.js";

// 브이월드 배경지도. 공개 시험용 키라 가끔 느립니다.
// 자기 키는 https://www.vworld.kr 에서 무료로 받습니다. 없어도 통행은 그려집니다.
const VWORLD_KEY = import.meta.env.VITE_VWORLD_KEY || "EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE";

const state = {
  trips: [],
  passengers: [],
  meta: null,
  time: 0,
  playing: false,
  speed: 2,
  trail: 20,
  frame: null,
};

let deck = null;

// --------------------------------------------------------------------------- //
// 레이어
// --------------------------------------------------------------------------- //

function basemapLayer() {
  return new TileLayer({
    id: "basemap",
    data: `https://api.vworld.kr/req/wmts/1.0.0/${VWORLD_KEY}/Base/{z}/{y}/{x}.png`,
    minZoom: 6,
    maxZoom: 18,
    tileSize: 256,
    renderSubLayers: (props) => {
      const [[west, south], [east, north]] = props.tile.boundingBox;
      return new BitmapLayer(props, {
        data: null,
        image: props.data,
        bounds: [west, south, east, north],
      });
    },
  });
}

function tripsLayer() {
  // 빈칸 1이 아직 비어 있으면 레이어를 만들지 않습니다.
  if (!state.trips.length || !tripPath(state.trips[0])) return null;

  return new TripsLayer({
    id: "trips",
    data: state.trips,
    getPath: tripPath,
    getTimestamps: tripTimestamps,
    getColor: tripColor,
    currentTime: state.time,
    trailLength: state.trail,
    widthMinPixels: 2,
    capRounded: true,
    jointRounded: true,
    opacity: 0.85,
  });
}

function passengerLayer() {
  const waiting = waitingPassengers(state.passengers, state.time);
  if (!waiting.length) return null;

  return new ScatterplotLayer({
    id: "passengers",
    data: waiting,
    getPosition: (d) => d.location,
    getFillColor: COLOR.passenger,
    getRadius: 70,
    radiusMinPixels: 2.5,
    radiusMaxPixels: 7,
    opacity: 0.8,
  });
}

function render() {
  if (!deck) return;
  deck.setProps({
    layers: [basemapLayer(), tripsLayer(), passengerLayer()].filter(Boolean),
  });
  el("clock").textContent = hhmm(state.time);
  el("time").value = state.time;
}

// --------------------------------------------------------------------------- //
// 재생
// --------------------------------------------------------------------------- //

function step() {
  if (!state.playing) return;
  state.time = nextTime(state.time, state.speed, state.meta);
  render();
  state.frame = requestAnimationFrame(step);
}

// --------------------------------------------------------------------------- //
// 화면 조작
// --------------------------------------------------------------------------- //

const el = (id) => document.getElementById(id);

function hhmm(minutes) {
  const m = Math.floor(minutes) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

function wireControls() {
  el("play").onclick = () => {
    state.playing = !state.playing;
    el("play").textContent = state.playing ? "멈춤" : "재생";
    if (state.playing) step();
    else if (state.frame) cancelAnimationFrame(state.frame);
  };

  el("time").oninput = (e) => {
    state.time = Number(e.target.value);
    render();
  };

  el("speed").oninput = (e) => {
    state.speed = Number(e.target.value);
    el("speedText").textContent = `${state.speed.toFixed(1)}x`;
  };

  el("trail").oninput = (e) => {
    state.trail = Number(e.target.value);
    el("trailText").textContent = `${state.trail}분`;
    render();
  };
}

// --------------------------------------------------------------------------- //
// 남은 빈칸 알려 주기
// --------------------------------------------------------------------------- //

function showRemainingTodos() {
  const left = [];
  const sample = state.trips[0];

  if (!sample || !tripPath(sample)) left.push("1 — 좌표열 (tripPath)");
  else if (!tripTimestamps(sample)) left.push("2 — 시각열 (tripTimestamps)");
  else if (String(tripColor(sample)) === "200,200,200") left.push("3 — 색 (tripColor)");

  if (state.passengers.length && !waitingPassengers(state.passengers, state.time).length) {
    left.push("4 — 기다리는 승객 (waitingPassengers)");
  }
  if (state.meta && nextTime(state.meta.time_start, 2, state.meta) === state.meta.time_start) {
    left.push("5 — 시간 흘리기 (nextTime)");
  }

  const box = el("todo");
  box.hidden = left.length === 0;
  if (left.length) {
    box.innerHTML =
      "아직 채우지 않은 곳<br>" +
      left.map((s) => `· 빈칸 ${s}`).join("<br>") +
      "<br><br><code>src/main.js</code> 를 고치고 저장하면 바로 반영됩니다.";
  }
}

// --------------------------------------------------------------------------- //
// 시작
// --------------------------------------------------------------------------- //

async function loadJson(name) {
  const res = await fetch(`data/${name}`);
  if (!res.ok) throw new Error(`data/${name} 을 읽지 못했습니다 (HTTP ${res.status})`);
  return res.json();
}

async function main() {
  try {
    const [trips, passengers, meta] = await Promise.all([
      loadJson("trip.json"),
      loadJson("passenger_marker.json"),
      loadJson("meta.json"),
    ]);
    Object.assign(state, { trips, passengers, meta, time: meta.time_start });
  } catch (err) {
    el("meta").innerHTML =
      "데이터를 읽지 못했습니다. <code>public/data/</code> 가 비어 있습니다.<br>" +
      "노트북에서 <code>export_viewer</code> 를 먼저 실행하세요.<br>" +
      `<span style="color:#a33">${err.message}</span>`;
    return;
  }

  const { meta } = state;
  const slider = el("time");
  slider.min = meta.time_start;
  slider.max = meta.time_end;
  slider.value = state.time;

  el("meta").innerHTML =
    `${meta.source} · 구간 ${meta.n_trips.toLocaleString()}개<br>` +
    `${hhmm(meta.time_start)} ~ ${hhmm(meta.time_end)}`;

  deck = new Deck({
    parent: el("map"),
    initialViewState: {
      longitude: meta.center[0],
      latitude: meta.center[1],
      zoom: meta.zoom,
      pitch: 0,
      bearing: 0,
    },
    controller: true,
    layers: [],
  });

  wireControls();
  render();
  showRemainingTodos();
}

main();
