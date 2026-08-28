"""프로젝트 B 2단계 — 고정노선 셔틀을 GTFS 로 쓰기 (2주차)

    python 02_fixed_route.py

5장에서 읽기만 하던 GTFS 를 이번에는 직접 씁니다.
정류장 순서와 배차간격을 정하면 `shuttle_gtfs/` 에 표 다섯 개가 만들어집니다.

만든 GTFS 를 자기 RAPTOR 에 넣으면 학생들의 통행시간이 나옵니다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from smartmob.data import hhmm_to_minutes, save_gtfs, seconds_to_gtfs_time
from smartmob.teaching.graph import haversine_km

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = Path("shuttle_gtfs")

# ---------------------------------------------------------------------------
# 노선 설계 — 여기를 여러분이 정합니다
# ---------------------------------------------------------------------------

# 셔틀이 서는 순서. candidate_stops.csv 의 name 을 씁니다.
# 캠퍼스 안 정류장을 추가하려면 candidate_stops.csv 에 행을 더하세요.
ROUTE_STOPS = [
    "가천대역.가천대학교",
    "가천대 [경기]",
    "캠퍼스",
]

HEADWAY_MIN = 5              # 배차간격
SERVICE_START = "07:30"
SERVICE_END = "20:00"
DWELL_SEC = 25               # 정류장당 정차 시간
SHUTTLE_SPEED_KMH = 18.0     # 캠퍼스가 언덕입니다. 시내 평균보다 낮게 잡았습니다

CAMPUS = {"name": "캠퍼스", "lat": 37.4505, "lon": 127.1285}


def load_stops() -> pd.DataFrame:
    stops = pd.read_csv(DATA / "candidate_stops.csv")
    if CAMPUS["name"] not in set(stops["name"]):
        stops = pd.concat([stops, pd.DataFrame([{
            "stop_id": "SHUTTLE_CAMPUS", "name": CAMPUS["name"], "kind": "셔틀",
            "lat": CAMPUS["lat"], "lon": CAMPUS["lon"],
            "campus_dist_m": 0, "daily_trips": 0,
        }])], ignore_index=True)
    return stops.set_index("name")


def leg_seconds(stops: pd.DataFrame, a: str, b: str) -> int:
    """두 정류장 사이 소요시간(초).

    지금은 직선거리를 평균 속도로 나눈 값입니다. **3장의 최단경로로 바꾸세요.**
    캠퍼스가 언덕이라 오르막 구간은 더 걸립니다. 계수를 곱하고 그 사실을 적으세요.
    """
    p, q = stops.loc[a], stops.loc[b]
    km = haversine_km(p["lat"], p["lon"], q["lat"], q["lon"])
    return int(round(km / SHUTTLE_SPEED_KMH * 3600))


def build_gtfs(stops: pd.DataFrame) -> dict:
    """정류장 순서와 배차간격에서 GTFS 표 다섯 개를 만듭니다."""
    missing = [s for s in ROUTE_STOPS if s not in stops.index]
    if missing:
        raise KeyError(f"candidate_stops.csv 에 없는 정류장: {missing}")

    used = stops.loc[ROUTE_STOPS].reset_index()
    stops_txt = pd.DataFrame({
        "stop_id": used["stop_id"],
        "stop_name": used["name"],
        "stop_lat": used["lat"],
        "stop_lon": used["lon"],
    })

    routes_txt = pd.DataFrame([{
        "route_id": "SHUTTLE", "route_short_name": "셔틀",
        "route_long_name": " → ".join(ROUTE_STOPS), "route_type": 0,
    }])

    # 정류장 사이 누적 소요시간
    offsets, running = [0], 0
    for a, b in zip(ROUTE_STOPS, ROUTE_STOPS[1:]):
        running += leg_seconds(stops, a, b) + DWELL_SEC
        offsets.append(running)
    print(f"편도 소요시간 {running / 60:.1f}분 (정차 포함)")

    start = hhmm_to_minutes(SERVICE_START) * 60
    end = hhmm_to_minutes(SERVICE_END) * 60

    trips, stop_times = [], []
    for i, depart in enumerate(range(start, end, HEADWAY_MIN * 60)):
        trip_id = f"SHUTTLE_{i:03d}"
        trips.append({"route_id": "SHUTTLE", "service_id": "ALL", "trip_id": trip_id})
        for seq, (stop_name, offset) in enumerate(zip(ROUTE_STOPS, offsets), start=1):
            clock = seconds_to_gtfs_time(depart + offset)
            stop_times.append({
                "trip_id": trip_id,
                "arrival_time": clock, "departure_time": clock,
                "stop_id": stops.loc[stop_name, "stop_id"],
                "stop_sequence": seq,
            })

    calendar_txt = pd.DataFrame([{
        "service_id": "ALL", "monday": 1, "tuesday": 1, "wednesday": 1,
        "thursday": 1, "friday": 1, "saturday": 0, "sunday": 0,
        "start_date": "20260901", "end_date": "20261231",
    }])

    return {
        "stops": stops_txt,
        "routes": routes_txt,
        "trips": pd.DataFrame(trips),
        "stop_times": pd.DataFrame(stop_times),
        "calendar": calendar_txt,
    }


def vehicles_needed(cycle_min: float, headway_min: float) -> int:
    """왕복 한 바퀴 시간과 배차간격에서 필요한 차량 대수.

    올림입니다. 5분 간격에 왕복 12분이면 3대가 필요합니다.
    """
    import math

    return max(1, math.ceil(cycle_min / headway_min))


def main() -> int:
    stops = load_stops()
    feed = build_gtfs(stops)

    save_gtfs(feed, OUT)
    print(f"\n{OUT}/ 에 저장했습니다")
    for name, table in feed.items():
        print(f"  {name:12s} {len(table):>6,}행")

    one_way = (
        pd.to_datetime(feed["stop_times"].iloc[len(ROUTE_STOPS) - 1]["arrival_time"])
        - pd.to_datetime(feed["stop_times"].iloc[0]["departure_time"])
    ).total_seconds() / 60
    cycle = one_way * 2 + 2          # 왕복 + 종점 대기
    n = vehicles_needed(cycle, HEADWAY_MIN)
    print(f"\n왕복 약 {cycle:.1f}분, 배차간격 {HEADWAY_MIN}분 → 차량 {n}대 필요")

    print("\n다음에 할 일")
    print("  - 이 GTFS 를 TransitData.from_gtfs 에 넣어 학생 통행시간을 계산합니다")
    print("  - 같은 수요를 11장 루프로 수요응답 방식으로 돌립니다")
    print("  - 두 방식을 12장 지표로 비교합니다. 시간대를 나눠 보세요")
    print("\n확인할 것")
    print("  - leg_seconds 가 아직 직선거리입니다. 3장의 최단경로로 바꾸세요")
    print("  - 정류장 순서가 실제로 버스가 다닐 수 있는 길인지 지도에서 확인하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
