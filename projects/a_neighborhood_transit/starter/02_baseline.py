"""프로젝트 A 2단계 — 현재 상태 재기 (9~11주차)

    python 02_baseline.py

`gtfs/` 를 읽어 O-D 100쌍의 통행시간·환승·요금을 계산하고 `baseline.csv` 로 저장합니다.

O-D 를 고르는 부분은 여러분이 채웁니다. 무작위로 뽑아도 되지만,
의미 있는 기준(주거지 → 고용지, 각 동 → 가장 가까운 역)으로 고르면 결론이 강해집니다.
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from smartmob.data.gtfs import load_gtfs_feed
from smartmob.teaching.fare import calc_fare
from smartmob.teaching.raptor import TransitData, journey, raptor, summarize

GTFS_DIR = Path("gtfs")
DEPARTURE = 8 * 3600        # 오전 8시. 분석하려는 시간대로 바꾸세요
N_PAIRS = 100
SEED = 42


def pick_od_pairs(data: TransitData, n: int, seed: int) -> list[tuple[int, int]]:
    """분석할 O-D 쌍을 고릅니다.

    지금은 무작위입니다. **여기를 여러분의 기준으로 바꾸세요.**

    바꾸는 예
    ---------
    - 목적지를 시청·대학·산업단지 한 곳으로 고정하고 출발지만 흩뿌리기
    - 8장의 O-D 데이터에서 통행량 상위 쌍을 골라 좌표로 바꾸기
    - 각 행정동 중심에서 가장 가까운 지하철역으로

    03_demand.md 에 **어떤 기준으로 골랐는지** 적어야 합니다.
    """
    rng = random.Random(seed)
    stops = list(range(data.n_stops))
    pairs = []
    while len(pairs) < n:
        o, d = rng.choice(stops), rng.choice(stops)
        if o != d:
            pairs.append((o, d))
    return pairs


def main() -> int:
    if not GTFS_DIR.exists():
        print(f"{GTFS_DIR}/ 가 없습니다. 01_clip_gtfs.py 를 먼저 돌리세요.")
        return 1

    print("GTFS 를 읽는 중…")
    data = TransitData.from_gtfs(load_gtfs_feed(GTFS_DIR))
    print(f"  {data.describe()}")

    pairs = pick_od_pairs(data, N_PAIRS, SEED)
    print(f"\nO-D {len(pairs)}쌍을 계산합니다 (출발 {DEPARTURE // 3600:02d}:00)")

    rows = []
    unreachable = 0
    for origin, dest in pairs:
        result = raptor(data, [(origin, 0)], DEPARTURE)
        legs = journey(data, result, dest)
        s = summarize(data, legs, DEPARTURE)
        if not s.get("reachable"):
            unreachable += 1
            continue
        s["fare"] = calc_fare(legs)
        s["origin"] = data.stop_names[origin]
        s["dest"] = data.stop_names[dest]
        s.pop("modes", None)
        s["routes"] = " → ".join(s.pop("routes", []))
        rows.append(s)

    df = pd.DataFrame(rows)
    df.to_csv("baseline.csv", index=False, encoding="utf-8")
    print(f"  도달 {len(df)}쌍, 도달 불가 {unreachable}쌍")
    print("  저장: baseline.csv")

    cols = ["total_min", "in_vehicle_min", "walk_min", "wait_min", "transfers", "fare"]
    print("\n지표 요약")
    print(df[cols].describe().round(1).to_string())

    print("\n분위 (12장에서 배운 대로 평균만 보지 않습니다)")
    for q in (0.5, 0.9):
        print(f"  통행시간 {q:.0%} 분위  {df['total_min'].quantile(q):6.1f}분")

    print("\n다음에 할 일 — 04_baseline.md 에 적을 것")
    print("  - 위 표와 분위")
    print("  - 엔진 또는 지도 앱과 10쌍 이상 대조한 표")
    print("  - 차이가 큰 쌍 3개와 그 이유")
    print("  - 도달 불가 쌍이 왜 생겼는지")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
