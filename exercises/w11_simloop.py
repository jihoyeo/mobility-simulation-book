"""11주차 실습 — 시뮬레이션 루프 (교재 11장)

빈칸을 채운 뒤 자가 채점을 돌립니다.

    python exercises/check.py w11

채점 기준은 실제 엔진과의 거리입니다. 평균 대기시간이 1.5분 이내로 붙어야 합니다.
완전히 같을 수는 없습니다. 어디서 왜 갈라지는지를 설명할 수 있으면 됩니다.

--------------------------------------------------------------------------
쓸 수 있는 것
--------------------------------------------------------------------------
    from smartmob.data import load_demand, load_vehicles
    demand = load_demand("hanam")      # id, request_time, origin_lat/lon, dest_lat/lon
    vehicles = load_vehicles("hanam")  # id, work_start, work_end, lat, lon

    from smartmob.teaching.dispatch import optimal_match
    result = optimal_match(비용행렬)   # result.matches -> [Match(passenger, vehicle, cost), ...]
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smartmob.teaching.graph import haversine_km

BOARD_MIN = 1.0            # 승차에 걸리는 시간
ALIGHT_MIN = 1.0           # 하차에 걸리는 시간
DEFAULT_FAIL_MIN = 10      # 배차를 이만큼 못 받으면 포기합니다
DEFAULT_SPEED_KMH = 25.0


def straight_line_time(origin, dest, minute, speed_kmh=DEFAULT_SPEED_KMH):
    """직선거리를 평균 속도로 나눈 소요시간(분). 이건 만들어 두었습니다."""
    return haversine_km(origin[0], origin[1], dest[0], dest[1]) / speed_kmh * 60


@dataclass
class Vehicle:
    """차량 한 대.

    상태를 열거형으로 두지 않습니다. `free_at` 이 현재 시각보다 크면 운행 중,
    아니면 대기 중입니다. 상태와 시각이 어긋날 수가 없습니다.
    """

    id: int
    location: tuple
    work_start: int
    work_end: int
    free_at: float = 0.0
    empty_km: float = 0.0     # 승객을 태우러 가는 거리
    loaded_km: float = 0.0    # 승객을 태우고 가는 거리
    busy_min: float = 0.0

    def on_duty(self, minute):
        return self.work_start <= minute < self.work_end

    def idle(self, minute):
        """지금 배차받을 수 있는가."""
        raise NotImplementedError("Vehicle.idle 을 구현하세요")


@dataclass
class Request:
    """호출 한 건."""

    id: int
    origin: tuple
    dest: tuple
    request_time: int
    assigned_time: int | None = None    # 배차가 확정된 시각
    pickup_time: float | None = None    # 차가 실제로 도착한 시각
    dropoff_time: float | None = None
    vehicle_id: int | None = None
    failed: bool = False

    @property
    def wait_min(self):
        """호출부터 탑승까지. 배차 대기 + 차가 오는 시간입니다."""
        if self.pickup_time is None:
            return None
        return self.pickup_time - self.request_time


@dataclass
class SimResult:
    record: object            # pandas.DataFrame
    requests: list
    vehicles: list
    config: dict = field(default_factory=dict)

    def summary(self):
        """채점과 비교에 쓰는 지표.

        내야 하는 열쇠
        --------------
        total_passengers, served_passengers, failed_passengers,
        service_rate, avg_waiting_time_min, max_waiting_time_min,
        utilization, empty_km, loaded_km

        `utilization` 은 (전체 차량이 실제로 일한 분) / (근무한 분) 입니다.
        """
        raise NotImplementedError("SimResult.summary 를 구현하세요")


def build_costs(waiting, idle, minute, travel_time):
    """대기 승객 × 빈 차 비용행렬.

    행이 승객, 열이 차량, 칸이 그 차가 그 승객에게 가는 데 걸리는 시간(분)입니다.
    `numpy.empty((len(waiting), len(idle)))` 로 만들어 채웁니다.
    """
    raise NotImplementedError("build_costs 를 구현하세요")


def assign(req, veh, minute, pickup_min, travel_time):
    """배차를 확정하고 차량 상태를 갱신합니다.

    해야 할 것
    ----------
    - `req.assigned_time` = 지금 시각
    - `req.pickup_time` = 지금 + 차가 오는 시간 + 승차 시간
    - `req.dropoff_time` = 탑승 시각 + 이동 시간 + 하차 시간
    - 차량의 `empty_km`(태우러 간 거리)와 `loaded_km`(태우고 간 거리) 누적
    - `veh.free_at` = 하차 시각, `veh.location` = 목적지

    순서 주의
    ---------
    `veh.location` 을 바꾸기 **전에** 공차 거리를 재야 합니다.
    바꾼 뒤에 재면 0이 나옵니다.
    """
    raise NotImplementedError("assign 을 구현하세요")


def simulate(demand, vehicles, time_start=1080, time_end=1440,
             travel_time=None, fail_after_min=DEFAULT_FAIL_MIN):
    """1분 단위 시뮬레이션.

    매 분에 하는 일
    ---------------
    1. 이번 분에 들어온 호출을 대기 목록에 넣습니다
    2. `fail_after_min` 이상 기다린 호출을 포기 처리합니다
    3. 대기 승객과 빈 차가 둘 다 있으면 비용행렬을 만들고 `optimal_match` 로 배차합니다
    4. 배차된 승객을 대기 목록에서 뺍니다
    5. 이번 분의 상태를 기록합니다

    기록 컬럼 (엔진의 record.csv 와 같아야 합니다)
    ----------------------------------------------
    time, waiting_passenger_cnt, fail_passenger_cnt,
    empty_vehicle_cnt, driving_vehicle_cnt

    주의
    ----
    - 포기 기준은 **배차까지**의 시간에 걸립니다. 차가 오는 시간은 별개입니다
    - `driving_vehicle_cnt` 는 근무 중이면서 `free_at > minute` 인 차량 수입니다
    """
    raise NotImplementedError("simulate 를 구현하세요")


# --------------------------------------------------------------------------- #
# 직접 돌려 보기
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    from smartmob.data import load_demand, load_vehicles

    demand, vehicles = load_demand("hanam"), load_vehicles("hanam")

    run = simulate(demand, vehicles, 1080, 1440)
    for key, value in run.summary().items():
        print(f"{key:24s} {value}")

    print()
    for n in (20, 40, 80):
        s = simulate(demand, vehicles.head(n), 1080, 1440).summary()
        print(f"차량 {n:2d}대  서비스율 {s['service_rate']:.3f}  "
              f"평균대기 {s['avg_waiting_time_min']:.2f}분")
