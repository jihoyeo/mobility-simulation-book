"""프로젝트 B 1단계 — 셔틀 수요 만들기 (1주차)

    python 01_class_demand.py

교시 시간표에서 셔틀 수요를 만듭니다. 8장의 `generate_demand` 를 그대로 쓸 수 없습니다.
그건 도로망 위에 흩뿌리는 방식이고, 셔틀 수요는 정해진 몇 지점 사이를 오갑니다.

여기서 정할 것이 셋입니다. 셋 다 **가정**이고, 보고서에 전부 적어야 합니다.

1. 몇 명이 타는가
2. 언제 도착하려 하는가
3. 어느 지점에서 오는가
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from smartmob.data import hhmm_to_minutes, normalize_demand

DATA = Path(__file__).resolve().parent.parent / "data"
CAMPUS = (37.4505, 127.1285)      # 캠퍼스 중심. 실제 하차 지점으로 고치세요

# ---------------------------------------------------------------------------
# 가정 — 전부 여러분이 정하고 보고서에 적습니다
# ---------------------------------------------------------------------------

# 1교시 직전에 셔틀을 타는 학생 수. 학과 정원과 시간표에서 추정하세요.
RIDERS_PER_PERIOD = {1: 480, 2: 260, 3: 180, 4: 150, 5: 120, 6: 80, 7: 40}

# 어느 지점에서 오는가. 합이 1이 되게 합니다.
# candidate_stops.csv 의 daily_trips 가 힌트입니다. 공급이 많은 곳에 사람도 많습니다.
ORIGIN_SHARE = {
    "가천대역.가천대학교": 0.55,
    "가천대역(마을)": 0.15,
    "복정": 0.10,
    "태평": 0.10,
    "복우물.웃말입구": 0.10,
}

# 수업 시작 몇 분 전에 도착하려 하는가. (평균, 표준편차) 분.
ARRIVE_BEFORE = (10.0, 4.0)

SEED = 42


def load_stops() -> pd.DataFrame:
    stops = pd.read_csv(DATA / "candidate_stops.csv")
    return stops.set_index("name")


def load_schedule() -> pd.DataFrame:
    schedule = pd.read_csv(DATA / "class_schedule.csv")
    if schedule["note"].notna().any():
        print("class_schedule.csv 가 예시 값입니다. 학사일정에서 확인해 고치세요.\n")
    return schedule


def build_demand(stops: pd.DataFrame, schedule: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """교시별로 승객을 만들어 수요 표를 냅니다.

    출발 지점은 `ORIGIN_SHARE` 비율로 뽑고, 호출 시각은 수업 시작에서
    `ARRIVE_BEFORE` 만큼 앞선 정규분포로 흩뿌립니다.

    돌려주는 표는 8장의 계약을 지킵니다.
    request_time, origin_lat, origin_lon, dest_lat, dest_lon
    """
    rng = random.Random(seed)
    missing = [n for n in ORIGIN_SHARE if n not in stops.index]
    if missing:
        raise KeyError(f"candidate_stops.csv 에 없는 지점: {missing}")

    names = list(ORIGIN_SHARE)
    weights = [ORIGIN_SHARE[n] for n in names]

    rows = []
    for period, start in zip(schedule["period"], schedule["start"]):
        n_riders = RIDERS_PER_PERIOD.get(int(period), 0)
        if n_riders <= 0:
            continue
        start_min = hhmm_to_minutes(str(start))
        for _ in range(n_riders):
            name = rng.choices(names, weights=weights, k=1)[0]
            stop = stops.loc[name]
            lead = max(1.0, rng.gauss(*ARRIVE_BEFORE))
            rows.append({
                "request_time": int(round(start_min - lead)),
                "origin_lat": float(stop["lat"]),
                "origin_lon": float(stop["lon"]),
                "dest_lat": CAMPUS[0],
                "dest_lon": CAMPUS[1],
                "period": int(period),
                "origin_name": name,
            })

    return normalize_demand(pd.DataFrame(rows))


def main() -> int:
    stops, schedule = load_stops(), load_schedule()
    demand = build_demand(stops, schedule)

    demand.to_csv("demand.csv", index=False, encoding="utf-8")
    print(f"수요 {len(demand):,}건 → demand.csv")

    print("\n시간대별 호출 수")
    by_hour = demand["request_time"] // 60
    for hour, count in by_hour.value_counts().sort_index().items():
        bar = "█" * (count // 20)
        print(f"  {hour:02d}시  {count:>5,}  {bar}")

    print("\n출발 지점 분포")
    print(demand["origin_name"].value_counts().to_string())

    peak = by_hour.value_counts().idxmax()
    peak_n = (by_hour == peak).sum()
    print(f"\n첨두 {peak}시대 {peak_n:,}건")
    print("  이 시간대에 차량이 몇 대 필요한지가 이 프로젝트의 질문입니다.")

    print("\n보고서에 적을 가정")
    print(f"  - 교시별 이용자 수: {RIDERS_PER_PERIOD}")
    print(f"  - 출발 지점 비율: {ORIGIN_SHARE}")
    print(f"  - 수업 시작 {ARRIVE_BEFORE[0]:.0f}분 전 도착 목표 (표준편차 {ARRIVE_BEFORE[1]:.0f}분)")
    print("  - 각 가정을 절반/두 배로 바꿨을 때 결론이 바뀌는지 확인하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
