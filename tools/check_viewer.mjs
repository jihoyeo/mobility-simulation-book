// 12장 웹 뷰어의 빈칸을 채점합니다.
//
//     node tools/check_viewer.mjs
//
// 브라우저가 필요 없습니다. `labs/ch12_viewer/src/main.js` 의 다섯 함수는
// 화면과 무관한 순수 함수라서 그대로 불러다 확인할 수 있습니다.
//
// `labs/check.py` 가 파이썬 실습을 채점하는 것과 같은 자리입니다.
// 두 방향을 다 봅니다.
//
//   빈칸판은 전부 실패해야 합니다. 실수로 정답이 남아 있으면 안 됩니다
//   아래 REFERENCE 는 전부 통과해야 합니다. 기준이 달성 가능해야 합니다

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PROJECT = path.join(ROOT, "labs", "ch12_viewer");
const DATA = path.join(PROJECT, "public", "data");

let failed = 0;
let filledCount = 0;

function report(name, ok, detail = "") {
  const mark = ok ? "PASS" : "FAIL";
  console.log(`  [${mark}] ${name}` + (ok || !detail ? "" : `\n         ${detail}`));
  if (!ok) failed += 1;
  return ok;
}

function readJson(name) {
  return JSON.parse(fs.readFileSync(path.join(DATA, name), "utf8"));
}

// --------------------------------------------------------------------------- //
// 정답. 학생이 채워야 할 다섯 자리입니다.
//
// 교재가 다익스트라 정돈본을 smartmob/teaching/ 에 두는 것과 같은 이유로
// 여기에 둡니다. 채점 기준이 실제로 달성 가능한지 확인하려면 정답이 필요합니다.
// --------------------------------------------------------------------------- //

function makeReference(COLOR, TRANSIT_COLOR) {
  return {
    tripPath: (d) => d.trip,
    tripTimestamps: (d) => d.timestamp,
    tripColor: (d) => {
      if (d.cartype >= 10) return TRANSIT_COLOR[d.cartype] || COLOR.walk;
      return d.board === 1 ? COLOR.occupied : COLOR.deadhead;
    },
    waitingPassengers: (passengers, now) =>
      passengers.filter((p) => p.timestamp[0] <= now && now <= p.timestamp[1]),
    nextTime: (now, speed, meta) => {
      const next = now + 0.04 * speed;
      return next > meta.time_end ? meta.time_start : next;
    },
  };
}

// --------------------------------------------------------------------------- //
// 다섯 자리를 같은 기준으로 봅니다.
// --------------------------------------------------------------------------- //

function grade(fns, data, { label }) {
  const { trips, passengers, meta } = data;
  const sample = trips[0];
  const results = [];

  const push = (name, fn) => {
    try {
      results.push([name, fn()]);
    } catch (err) {
      results.push([name, [false, `${err.constructor.name}: ${err.message}`]]);
    }
  };

  push("1. 좌표열을 꺼낸다", () => {
    const got = fns.tripPath(sample);
    if (!Array.isArray(got)) return [false, "아직 구현하지 않았습니다"];
    if (got !== sample.trip) return [false, "trip 키를 그대로 돌려줘야 합니다"];
    return [true, `좌표 ${got.length}개`];
  });

  push("2. 시각열을 꺼낸다", () => {
    const got = fns.tripTimestamps(sample);
    if (!Array.isArray(got)) return [false, "아직 구현하지 않았습니다"];
    if (got.length !== fns.tripPath(sample)?.length) {
      return [false, "좌표 수와 시각 수가 같아야 합니다"];
    }
    return [true, `시각 ${got.length}개`];
  });

  push("3. 탑승과 공차의 색이 다르다", () => {
    const occupied = String(fns.tripColor({ cartype: 0, board: 1 }));
    const deadhead = String(fns.tripColor({ cartype: 0, board: 0 }));
    if (occupied === deadhead) return [false, "아직 구현하지 않았습니다"];
    return [true, `${occupied} vs ${deadhead}`];
  });

  push("4. 대중교통은 다른 색이다", () => {
    const bus = String(fns.tripColor({ cartype: 11, board: 1 }));
    const taxi = String(fns.tripColor({ cartype: 0, board: 1 }));
    if (bus === taxi) return [false, "cartype 이 10 이상이면 대중교통입니다"];
    return [true, ""];
  });

  const now = meta.time_start + 30;
  push("5. 지금 기다리는 승객만 고른다", () => {
    const got = fns.waitingPassengers(passengers, now);
    if (!got.length) return [false, "아직 구현하지 않았습니다"];
    const wrong = got.filter((p) => !(p.timestamp[0] <= now && now <= p.timestamp[1]));
    if (wrong.length) return [false, `${wrong.length}명이 그 시각에 대기 중이 아닙니다`];
    return [true, `${got.length}명`];
  });

  push("6. 시간이 흐른다", () => {
    const next = fns.nextTime(meta.time_start, 2, meta);
    if (next === meta.time_start) return [false, "아직 구현하지 않았습니다"];
    if (next <= meta.time_start) return [false, "시각이 줄어들었습니다"];
    return [true, `${meta.time_start} → ${next.toFixed(2)}`];
  });

  push("7. 끝에 닿으면 처음으로 돌아간다", () => {
    const wrapped = fns.nextTime(meta.time_end, 2, meta);
    if (wrapped !== meta.time_start) {
      return [false, `${meta.time_end} 다음이 ${wrapped} 입니다. time_start 여야 합니다`];
    }
    return [true, ""];
  });

  console.log(`${label}`);
  console.log("-".repeat(40));
  let passed = 0;
  for (const [name, [ok, detail]] of results) {
    if (report(name, ok, detail)) passed += 1;
  }
  console.log(`\n${passed}/${results.length} 통과\n`);
  return passed;
}

// --------------------------------------------------------------------------- //

async function main() {
  if (!fs.existsSync(path.join(DATA, "meta.json"))) {
    console.error(
      `${DATA} 가 비어 있습니다.\n` +
      `labs/ch12_metrics.ipynb 에서 export_viewer 를 먼저 실행하세요.`
    );
    return 1;
  }

  const data = {
    trips: readJson("trip.json"),
    passengers: readJson("passenger_marker.json"),
    meta: readJson("meta.json"),
  };

  const student = await import(pathToFileURL(path.join(PROJECT, "src", "main.js")).href);
  const palette = await import(pathToFileURL(path.join(PROJECT, "src", "palette.js")).href);

  filledCount = grade(student, data, { label: "12장 웹 뷰어 자가 채점" });

  // 채점 기준이 달성 가능한지 확인합니다.
  const before = failed;
  const reference = makeReference(palette.COLOR, palette.TRANSIT_COLOR);
  const refPassed = grade(reference, data, { label: "참고 — 정답 구현" });
  if (refPassed !== 7) {
    console.error("채점 기준이 잘못되었습니다. 정답 구현이 통과하지 못합니다.");
    return 1;
  }
  failed = before;   // 정답 구현의 결과는 학생 점수에 넣지 않습니다

  if (filledCount === 0) {
    console.log("아직 빈칸을 채우지 않았습니다. labs/ch12_viewer/src/main.js 를 여세요.");
    return 0;          // 시작 상태는 실패가 아닙니다
  }
  return failed === 0 ? 0 : 1;
}

main().then((code) => process.exit(code));
