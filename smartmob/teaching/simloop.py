"""이산시간 시뮬레이션 루프.

11장에서 유도한 코드의 정돈본입니다.

1분씩 시간을 밀면서 호출을 받고, 차량 상태를 갱신하고, 배차하고, 기록합니다.
지금까지 만든 것이 전부 여기로 들어옵니다.

    수요(8장) → 배차(10장) → 소요시간(3장 또는 9장) → 기록 → 지표(12장)

    from smartmob.teaching.simloop import simulate
    result = simulate(demand, vehicles, travel_time=...)
    result.record.head()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from smartmob.teaching.graph import haversine_km

Point = tuple[float, float]

# 승하차에 걸리는 시간(분). 실제 엔진의 기본값과 맞췄습니다.
BOARD_MIN = 1.0
ALIGHT_MIN = 1.0
DEFAULT_FAIL_MIN = 10        # 이만큼 기다려도 배차가 안 되면 포기합니다
DEFAULT_SPEED_KMH = 25.0


def straight_line_time(origin: Point, dest: Point, minute: int,
                       speed_kmh: float = DEFAULT_SPEED_KMH) -> float:
    """직선거리를 평균 속도로 나눈 소요시간(분). 가장 싼 근사입니다."""
    return haversine_km(origin[0], origin[1], dest[0], dest[1]) / speed_kmh * 60


@dataclass
class Vehicle:
    """차량 한 대의 상태.

    상태를 별도 열거형으로 두지 않고 `free_at` 과 `location` 두 값으로 표현합니다.
    `free_at` 이 현재 시각보다 크면 운행 중, 아니면 대기 중입니다.
    """

    id: int
    location: Point
    work_start: int
    work_end: int
    free_at: float = 0.0
    served: int = 0
    busy_min: float = 0.0
    empty_km: float = 0.0        # 승객을 태우러 가는 거리(공차)
    loaded_km: float = 0.0       # 승객을 태우고 가는 거리

    def on_duty(self, minute: int) -> bool:
        return self.work_start <= minute < self.work_end

    def idle(self, minute: int) -> bool:
        return self.on_duty(minute) and self.free_at <= minute


@dataclass
class Request:
    """호출 한 건."""

    id: int
    origin: Point
    dest: Point
    request_time: int
    assigned_time: int | None = None      # 배차가 확정된 시각
    pickup_time: float | None = None      # 차가 실제로 도착한 시각
    dropoff_time: float | None = None
    vehicle_id: int | None = None
    failed: bool = False

    @property
    def wait_min(self) -> float | None:
        """호출부터 탑승까지. 배차 대기 + 차가 오는 시간입니다."""
        if self.pickup_time is None:
            return None
        return self.pickup_time - self.request_time

    @property
    def assign_wait_min(self) -> float | None:
        """호출부터 배차 확정까지. 이 값이 `fail_after_min` 을 넘으면 포기합니다."""
        if self.assigned_time is None:
            return None
        return self.assigned_time - self.request_time

    @property
    def pickup_travel_min(self) -> float | None:
        """배차 확정부터 차가 도착하기까지. 공차 주행 시간입니다."""
        if self.pickup_time is None or self.assigned_time is None:
            return None
        return self.pickup_time - self.assigned_time


@dataclass
class SimResult:
    """시뮬레이션 산출물. DTUMOS 의 record.csv 와 같은 컬럼을 냅니다."""

    record: object                  # pandas.DataFrame
    requests: list[Request]
    vehicles: list[Vehicle]
    config: dict = field(default_factory=dict)

    def summary(self) -> dict:
        served = [r for r in self.requests if r.pickup_time is not None]
        failed = [r for r in self.requests if r.failed]
        waits = [r.wait_min for r in served]
        on_duty_min = sum(v.work_end - v.work_start for v in self.vehicles)
        busy_min = sum(v.busy_min for v in self.vehicles)
        return {
            "total_passengers": len(self.requests),
            "served_passengers": len(served),
            "failed_passengers": len(failed),
            "service_rate": len(served) / len(self.requests) if self.requests else None,
            "avg_waiting_time_min": sum(waits) / len(waits) if waits else None,
            "max_waiting_time_min": max(waits) if waits else None,
            "avg_assign_wait_min": _mean([r.assign_wait_min for r in served]),
            "avg_pickup_travel_min": _mean([r.pickup_travel_min for r in served]),
            "utilization": busy_min / on_duty_min if on_duty_min else None,
            "empty_km": round(sum(v.empty_km for v in self.vehicles), 1),
            "loaded_km": round(sum(v.loaded_km for v in self.vehicles), 1),
        }


def _mean(values) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def simulate(
    demand,
    vehicles,
    time_start: int = 1080,
    time_end: int = 1440,
    travel_time: Callable[[Point, Point, int], float] | None = None,
    fail_after_min: int = DEFAULT_FAIL_MIN,
    match: str = "optimal",
    progress: bool = False,
) -> SimResult:
    """1분 단위 시뮬레이션.

    ``demand`` 는 8장의 수요 DataFrame, ``vehicles`` 는 `id, work_start, work_end,
    lat, lon` 컬럼을 가진 DataFrame 입니다.
    ``travel_time(origin, dest, minute) -> 분`` 을 바꿔 끼우면 소요시간 모형이 바뀝니다.
    """
    import pandas as pd

    from smartmob.teaching.dispatch import greedy_match, optimal_match

    travel_time = travel_time or straight_line_time
    matcher = optimal_match if match == "optimal" else greedy_match

    fleet = [
        Vehicle(id=int(r.id), location=(float(r.lat), float(r.lon)),
                work_start=int(r.work_start), work_end=int(r.work_end))
        for r in vehicles.itertuples(index=False)
    ]
    pending = [
        Request(id=int(r.id), origin=(float(r.origin_lat), float(r.origin_lon)),
                dest=(float(r.dest_lat), float(r.dest_lon)), request_time=int(r.request_time))
        for r in demand.sort_values("request_time").itertuples(index=False)
        if time_start <= int(r.request_time) < time_end
    ]

    arrivals: dict[int, list[Request]] = {}
    for req in pending:
        arrivals.setdefault(req.request_time, []).append(req)

    waiting: list[Request] = []
    rows = []

    for minute in range(time_start, time_end):
        # 1) 이번 분에 들어온 호출을 대기 목록에 넣습니다
        waiting.extend(arrivals.get(minute, []))

        # 2) 너무 오래 기다린 호출은 포기 처리합니다
        still_waiting = []
        failed_now = 0
        for req in waiting:
            if minute - req.request_time >= fail_after_min:
                req.failed = True
                failed_now += 1
            else:
                still_waiting.append(req)
        waiting = still_waiting

        # 3) 대기 승객과 빈 차가 둘 다 있으면 배차합니다
        idle = [v for v in fleet if v.idle(minute)]
        if waiting and idle:
            costs = _build_costs(waiting, idle, minute, travel_time)
            result = matcher(costs)
            for m in result.matches:
                _assign(waiting[m.passenger], idle[m.vehicle], minute, m.cost, travel_time)
            assigned = {m.passenger for m in result.matches}
            waiting = [r for i, r in enumerate(waiting) if i not in assigned]

        # 4) 기록
        rows.append({
            "time": minute,
            "waiting_passenger_cnt": len(waiting),
            "fail_passenger_cnt": sum(1 for r in pending if r.failed),
            "empty_vehicle_cnt": sum(1 for v in fleet if v.idle(minute)),
            "driving_vehicle_cnt": sum(1 for v in fleet if v.on_duty(minute) and v.free_at > minute),
        })
        if progress and minute % 60 == 0:
            print(f"  {minute // 60:02d}:00  대기 {len(waiting):3d}  운행 {rows[-1]['driving_vehicle_cnt']:3d}")

    return SimResult(
        record=pd.DataFrame(rows),
        requests=pending,
        vehicles=fleet,
        config={
            "time_start": time_start, "time_end": time_end,
            "fleet_size": len(fleet), "num_passengers": len(pending),
            "fail_after_min": fail_after_min, "match": match,
        },
    )


def _build_costs(waiting: list[Request], idle: list[Vehicle], minute: int, travel_time):
    """대기 승객 × 빈 차 비용행렬. 칸마다 그 차가 그 승객에게 가는 시간(분)입니다."""
    import numpy as np

    costs = np.empty((len(waiting), len(idle)), dtype=float)
    for i, req in enumerate(waiting):
        for j, veh in enumerate(idle):
            costs[i, j] = travel_time(veh.location, req.origin, minute)
    return costs


def _assign(req: Request, veh: Vehicle, minute: int, pickup_min: float, travel_time) -> None:
    """배차를 확정하고 차량의 다음 가용 시각을 계산합니다.

    차량은 승객을 태우러 갔다가(공차) 목적지까지 태우고 간 뒤(실차) 그 자리에 섭니다.
    다음 호출은 그 자리에서 출발합니다. 빈 차를 수요가 많은 곳으로 미리 옮기는
    재배치(relocation)는 이 책에서 다루지 않습니다.
    """
    ride_min = travel_time(req.origin, req.dest, minute)

    req.vehicle_id = veh.id
    req.assigned_time = minute
    req.pickup_time = minute + pickup_min + BOARD_MIN
    req.dropoff_time = req.pickup_time + ride_min + ALIGHT_MIN

    # 위치를 바꾸기 전에 공차 거리를 재야 합니다.
    veh.empty_km += haversine_km(veh.location[0], veh.location[1], req.origin[0], req.origin[1])
    veh.loaded_km += haversine_km(req.origin[0], req.origin[1], req.dest[0], req.dest[1])
    veh.free_at = req.dropoff_time
    veh.location = req.dest
    veh.served += 1
    veh.busy_min += pickup_min + BOARD_MIN + ride_min + ALIGHT_MIN
