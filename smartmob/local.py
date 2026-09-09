"""내장 파이썬 엔진 — 서버 없이 그 자리에서 돌리는 시뮬레이션.

DTUMOS 서버가 없을 때 :class:`~smartmob.client.Dtumos` 가 이 모듈로 옵니다.
11장에서 함께 만드는 루프(:mod:`smartmob.teaching.simloop`)를 그대로 돌려서,
DTUMOS 가 내는 것과 같은 이름의 결과 파일을 씁니다. 그래서 ``sim.record``,
``sim.passengers``, ``sim.summary()``, 뷰어까지 모두 같은 코드로 읽힙니다.

실제 엔진과 다른 점은 셋입니다.

- 도로망을 달리지 않습니다. 두 점 사이 직선거리를 시속 25km 로 나눈 시간을 씁니다.
  11장에서 확인하듯 평균 대기시간이 실제 엔진과 0.2분 안쪽으로 맞습니다.
- 구간(``trip.json``)이 직선 두 점입니다. 지도에 그리면 도로가 아니라 직선이 보입니다.
- 승객 1,000명·차량 80대 기준으로 1초 안에 끝납니다. 실제 엔진은 수십 초 걸립니다.

수요와 차량은 이렇게 정합니다.

- 저장소의 ``data/<city>/demand.csv`` 가 기준 수요입니다. 책의 기준 실험
  (``num_passengers`` 가 파일 행 수와 같고 ``random_seed=42``)이면 그대로 씁니다.
  값이 다르면 8장의 :func:`~smartmob.teaching.demand_gen.generate_demand` 로
  도로망 위에서 새로 뽑습니다. 같은 seed 면 같은 수요가 나옵니다.
- 차량은 처음 ``fleet_size`` 건 호출의 출발지에 세워 둡니다. DTUMOS 의 규칙과 같습니다.

    from smartmob.local import run_simulation
    path = run_simulation({"city": "hanam", "fleet_size": 40, ...})
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smartmob.config import data_dir, repo_root
from smartmob.teaching.graph import haversine_km

ENGINE_NAME = "smartmob.local"
REFERENCE_SEED = 42

_graph_cache: dict[str, Any] = {}


def road_graph(city: str):
    """도로망을 한 번만 읽어 둡니다. 경로 질의와 수요 생성이 같이 씁니다."""
    if city not in _graph_cache:
        from smartmob.data import load_road_graph

        _graph_cache[city] = load_road_graph(city)
    return _graph_cache[city]


# --------------------------------------------------------------------------- #
# 입력 준비
# --------------------------------------------------------------------------- #


def demand_for(city: str, n: int, time_start: int, time_end: int, seed: int):
    """기준 수요 파일을 쓸 수 있으면 그대로, 아니면 도로망 위에서 새로 뽑습니다."""
    import pandas as pd

    base = data_dir() / city / "demand.csv"
    if base.exists():
        df = pd.read_csv(base, encoding="utf-8-sig")
        in_range = df["request_time"].between(time_start, time_end - 1)
        if seed == REFERENCE_SEED and n == len(df) and in_range.all():
            return df, "file"

    from smartmob.teaching.demand_gen import generate_demand

    df = generate_demand(graph=road_graph(city), n=n, time_range=(time_start, time_end), seed=seed)
    return df, "generated"


def vehicles_for(demand, fleet_size: int, time_start: int, time_end: int):
    """차량 i 는 i 번째 호출의 출발지에서 근무를 시작합니다."""
    import pandas as pd

    n = len(demand)
    rows = []
    for i in range(fleet_size):
        src = demand.iloc[i % n]
        rows.append({
            "id": i,
            "work_start": time_start,
            "work_end": time_end,
            "lat": float(src["origin_lat"]),
            "lon": float(src["origin_lon"]),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 실행
# --------------------------------------------------------------------------- #


def run_simulation(payload: dict[str, Any], dest: Path | None = None) -> Path:
    """``payload`` 로 한 번 돌리고 결과 디렉터리를 돌려줍니다.

    ``payload`` 의 키는 :meth:`Dtumos.run_simulation` 의 인자와 같습니다.
    """
    from smartmob import fixtures
    from smartmob.teaching.simloop import simulate

    city = payload["city"]
    fleet_size = int(payload["fleet_size"])
    n = int(payload["num_passengers"])
    time_start = int(payload["time_start"])
    time_end = int(payload["time_end"])
    seed = int(payload.get("random_seed", REFERENCE_SEED))
    match = "greedy" if payload.get("dispatch_mode") == "greedy" else "optimal"

    demand, demand_source = demand_for(city, n, time_start, time_end, seed)
    vehicles = vehicles_for(demand, fleet_size, time_start, time_end)
    result = simulate(demand, vehicles, time_start, time_end, match=match)

    if dest is None:
        key = fixtures.key_for(payload)
        dest = repo_root() / "simul_result" / f"local_{city}_V{fleet_size}_{n}p_seed{seed}_{key}"
    dest.mkdir(parents=True, exist_ok=True)
    write_result_files(result, dest, payload, demand_source)
    return dest


def write_result_files(result, dest: Path, payload: dict[str, Any], demand_source: str) -> None:
    """:class:`~smartmob.teaching.simloop.SimResult` 를 DTUMOS 형식의 파일로 씁니다."""
    config = {
        "engine": ENGINE_NAME,
        "target_region": payload["city"],
        "time_range": [int(payload["time_start"]), int(payload["time_end"])],
        "fleet_size": int(payload["fleet_size"]),
        "num_passengers": int(payload["num_passengers"]),
        "vehicle_capacity": int(payload.get("vehicle_capacity", 1)),
        "simulation_mode": payload.get("mode", "taxi"),
        "dispatch_mode": payload.get("dispatch_mode", "optimization"),
        "matrix_mode": "haversine_25kmh",
        "random_seed": int(payload.get("random_seed", REFERENCE_SEED)),
        "fail_time": result.config.get("fail_after_min"),
        "add_board_time": 1.0,
        "add_alight_time": 1.0,
        "demand_source": demand_source,
        "_note": (
            "smartmob 내장 파이썬 엔진 실행본입니다. 도로망 대신 직선거리·시속 25km 근사를 "
            "쓰고, trip.json 의 구간은 직선 두 점입니다."
        ),
    }
    _dump(dest / "config.json", config)
    result.record.to_csv(dest / "record.csv", index=False)
    _dump(dest / "result.json", _minute_states(result))
    _dump(dest / "trip.json", _trips(result))
    _dump(dest / "passenger_marker.json", _passengers(result))
    _dump(dest / "vehicle_marker.json", _vehicles(result))


# --------------------------------------------------------------------------- #
# 파일별 변환
# --------------------------------------------------------------------------- #


def _minute_states(result) -> list[dict[str, Any]]:
    """result.json — 분마다 승객·차량 상태.

    차량 상태는 둘로만 나눕니다. ``occupied_vehicle_num`` 은 배차를 받아 움직이는 차
    (승객을 데리러 가는 중 + 태우고 가는 중), ``empty_vehicle_num`` 은 빈 차입니다.
    둘을 더하면 근무 중 차량 수입니다. 그래야 :meth:`SimulationResult.summary` 의
    가동률이 11장 ``SimResult.summary`` 의 정의(움직인 시간 / 근무 시간)와 같아집니다.
    ``dispatched_vehicle_num`` 은 그중 데리러 가는 차만 따로 센 것입니다.

    ``average_waiting_time`` 은 일부러 넣지 않습니다. 그러면 ``summary()`` 가
    승객별 대기시간의 평균을 쓰는데, 그것도 11장과 같은 정의입니다.
    """
    ts, te = result.config["time_start"], result.config["time_end"]
    fail_after = result.config["fail_after_min"]
    reqs = result.requests
    rows = []
    for minute in range(ts, te):
        dispatched = waiting = failed = 0
        for r in reqs:
            if r.request_time > minute:
                continue
            if r.assigned_time is None:
                if r.failed and minute - r.request_time >= fail_after:
                    failed += 1
                else:
                    waiting += 1
            elif r.assigned_time > minute:
                waiting += 1
            elif minute < r.pickup_time:
                dispatched += 1
        empty = sum(1 for v in result.vehicles if v.idle(minute))
        busy = sum(1 for v in result.vehicles if v.on_duty(minute) and v.free_at > minute)
        rows.append({
            "time": minute,
            "driving_vehicle_num": busy,
            "dispatched_vehicle_num": dispatched,
            "occupied_vehicle_num": busy,
            "empty_vehicle_num": empty,
            "fail_passenger_cumNum": failed,
            "waiting_passenger_num": waiting,
        })
    return rows


def _served_by_vehicle(result) -> dict[int, list]:
    by_vehicle: dict[int, list] = {}
    for r in result.requests:
        if r.vehicle_id is not None:
            by_vehicle.setdefault(r.vehicle_id, []).append(r)
    for legs in by_vehicle.values():
        legs.sort(key=lambda r: r.assigned_time)
    return by_vehicle


def _trips(result) -> list[dict[str, Any]]:
    """trip.json — 배차마다 공차 구간(board=0)과 실차 구간(board=1)."""
    out = []
    by_vehicle = _served_by_vehicle(result)
    for v in result.vehicles:
        here = v.start_location
        for r in by_vehicle.get(v.id, []):
            board_at = r.pickup_time - 1.0          # BOARD_MIN 전에 도착
            out.append({
                "vehicle_id": v.id, "cartype": 0, "passenger_id": r.id, "board": 0,
                "trip": [[here[1], here[0]], [r.origin[1], r.origin[0]]],
                "timestamp": [float(r.assigned_time), float(board_at)],
                "network_distance": round(haversine_km(here[0], here[1], *r.origin), 3),
            })
            out.append({
                "vehicle_id": v.id, "cartype": 0, "passenger_id": r.id, "board": 1,
                "trip": [[r.origin[1], r.origin[0]], [r.dest[1], r.dest[0]]],
                "timestamp": [float(r.pickup_time), float(r.dropoff_time - 1.0)],
                "network_distance": round(haversine_km(*r.origin, *r.dest), 3),
            })
            here = r.dest
    return out


def _passengers(result) -> list[dict[str, Any]]:
    """passenger_marker.json — 승객마다 한 줄.

    ``timestamp`` 는 [호출 시각, 탑승 시각]입니다. 포기한 승객은 탑승 시각이 없으므로
    호출 시각 하나만 둡니다. 그래야 ``sim.passengers`` 의 ``wait_min`` 이 비고,
    평균 대기시간이 태운 승객만으로 계산됩니다.
    """
    out = []
    for r in result.requests:
        served = r.pickup_time is not None
        stamps = [int(r.request_time), float(r.pickup_time)] if served else [int(r.request_time)]
        out.append({
            "passenger_id": r.id,
            "status": 1 if served else 0,
            "location": [r.origin[1], r.origin[0]],
            "destination": [r.dest[1], r.dest[0]],
            "timestamp": stamps,
            "chosen_mode": "taxi",
        })
    return out


def _vehicles(result) -> list[dict[str, Any]]:
    """vehicle_marker.json — 차량이 한자리에 서 있던 구간."""
    out = []
    by_vehicle = _served_by_vehicle(result)
    for v in result.vehicles:
        here, since = v.start_location, float(v.work_start)
        for r in by_vehicle.get(v.id, []):
            out.append({"vehicle_id": v.id, "cartype": 0,
                        "location": [here[1], here[0]], "timestamp": [since, float(r.assigned_time)]})
            here, since = r.dest, float(r.dropoff_time)
        out.append({"vehicle_id": v.id, "cartype": 0,
                    "location": [here[1], here[0]], "timestamp": [since, float(v.work_end)]})
    return out


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 경로 한 건
# --------------------------------------------------------------------------- #


def route(city: str, origin: tuple[float, float], destination: tuple[float, float]) -> dict[str, Any]:
    """3장의 다익스트라로 최단경로 한 건. 서버 응답과 같은 키를 돌려줍니다."""
    from smartmob.teaching.dijkstra import shortest_path

    graph = road_graph(city)
    path = shortest_path(graph, origin, destination, algorithm="dijkstra")
    coords = path.coords(graph)
    return {
        "engine": ENGINE_NAME,
        "duration": path.duration_s,                     # 초
        "distance": path.distance_km(graph) * 1000,      # m
        "route": [[lon, lat] for lat, lon in coords],
    }
