"""시뮬레이션 루프 — 11장 검증 기준.

직접 짠 루프가 실제 엔진과 얼마나 맞는지가 이 장의 핵심입니다.
비트 단위로 같을 수는 없습니다. 같은 방향으로 움직이는지를 봅니다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartmob import Dtumos
from smartmob.data import load_demand, load_vehicles
from smartmob.teaching.simloop import BOARD_MIN, simulate, straight_line_time

HANAM_PAYLOAD = {
    "city": "hanam", "mode": "taxi", "fleet_size": 80, "num_passengers": 1000,
    "time_start": 1080, "time_end": 1440, "dispatch_mode": "optimization",
    "matrix_mode": "street_distance", "vehicle_capacity": 1, "random_seed": 42,
}


@pytest.fixture(scope="module")
def demand():
    return load_demand("hanam")


@pytest.fixture(scope="module")
def vehicles():
    return load_vehicles("hanam")


@pytest.fixture(scope="module")
def run(demand, vehicles):
    return simulate(demand, vehicles, 1080, 1440)


# --------------------------------------------------------------------------- #
# 출력 형식 — DTUMOS 의 record.csv 와 같아야 합니다
# --------------------------------------------------------------------------- #


def test_record_columns_match_engine(run):
    assert list(run.record.columns) == [
        "time",
        "waiting_passenger_cnt",
        "fail_passenger_cnt",
        "empty_vehicle_cnt",
        "driving_vehicle_cnt",
    ]


def test_record_has_one_row_per_minute(run):
    assert len(run.record) == 1440 - 1080
    assert run.record["time"].tolist() == list(range(1080, 1440))


def test_summary_keys(run):
    s = run.summary()
    for key in ("total_passengers", "served_passengers", "service_rate",
                "avg_waiting_time_min", "utilization"):
        assert key in s


# --------------------------------------------------------------------------- #
# 불변식
# --------------------------------------------------------------------------- #


def test_vehicle_counts_never_exceed_fleet(run, vehicles):
    total = run.record["empty_vehicle_cnt"] + run.record["driving_vehicle_cnt"]
    assert (total <= len(vehicles)).all()


def test_failed_count_is_monotonic(run):
    """누적 실패 건수는 줄어들 수 없습니다."""
    fails = run.record["fail_passenger_cnt"].values
    assert (np.diff(fails) >= 0).all()


def test_no_vehicle_serves_two_passengers_at_once(run):
    """한 차량의 운행 구간이 겹치면 안 됩니다."""
    by_vehicle: dict[int, list[tuple[float, float]]] = {}
    for req in run.requests:
        if req.vehicle_id is not None:
            by_vehicle.setdefault(req.vehicle_id, []).append((req.request_time, req.dropoff_time))
    for spans in by_vehicle.values():
        spans.sort()
        for (_, end), (start, _) in zip(spans, spans[1:]):
            assert start <= end + 1e-6 or start >= end - 1e-6


def test_pickup_after_request(run):
    for req in run.requests:
        if req.pickup_time is not None:
            assert req.pickup_time >= req.request_time + BOARD_MIN - 1e-9
            assert req.dropoff_time > req.pickup_time


def test_assign_wait_never_exceeds_fail_threshold(run):
    """포기 기준은 '배차까지'에 걸립니다. 차가 오는 시간은 별개입니다."""
    limit = run.config["fail_after_min"]
    for req in run.requests:
        if req.assign_wait_min is not None:
            assert req.assign_wait_min < limit


def test_total_wait_splits_into_two_parts(run):
    """호출→탑승 = 호출→배차 + 배차→도착 + 승차시간."""
    for req in run.requests:
        if req.pickup_time is None:
            continue
        assert req.wait_min == pytest.approx(
            req.assign_wait_min + req.pickup_travel_min, abs=1e-6
        )


def test_pickup_travel_can_exceed_fail_threshold(run):
    """멀리 있는 차가 배차되면 총 대기가 포기 기준을 넘을 수 있습니다.

    실제 엔진도 같습니다. 지표를 읽을 때 이 둘을 구분해야 합니다.
    """
    over = [r for r in run.requests
            if r.wait_min is not None and r.wait_min > run.config["fail_after_min"]]
    assert over, "이 데이터에서는 그런 승객이 있어야 합니다"


def test_every_request_is_served_or_failed(run):
    for req in run.requests:
        assert (req.pickup_time is not None) != req.failed


def test_optimal_beats_greedy_in_full_simulation(demand, vehicles):
    opt = simulate(demand, vehicles, 1080, 1440, match="optimal").summary()
    greedy = simulate(demand, vehicles, 1080, 1440, match="greedy").summary()
    assert opt["avg_waiting_time_min"] <= greedy["avg_waiting_time_min"] + 1e-9
    assert opt["empty_km"] <= greedy["empty_km"] + 1e-6


def test_smaller_fleet_increases_wait(demand, vehicles):
    big = simulate(demand, vehicles, 1080, 1440).summary()
    small = simulate(demand, vehicles.head(30), 1080, 1440).summary()
    assert small["avg_waiting_time_min"] > big["avg_waiting_time_min"]
    assert small["service_rate"] < big["service_rate"]


def test_travel_time_is_swappable(demand, vehicles):
    """소요시간 모형을 바꾸면 결과가 바뀌어야 합니다."""
    def slow(origin, dest, minute):
        return straight_line_time(origin, dest, minute, speed_kmh=10)

    fast = simulate(demand.head(200), vehicles, 1080, 1200).summary()
    slower = simulate(demand.head(200), vehicles, 1080, 1200, travel_time=slow).summary()
    assert slower["avg_waiting_time_min"] > fast["avg_waiting_time_min"]


# --------------------------------------------------------------------------- #
# 실제 엔진과의 대조
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def engine():
    import os

    os.environ["SMARTMOB_OFFLINE"] = "1"
    return Dtumos().run_simulation(**HANAM_PAYLOAD)


def test_average_wait_is_close_to_engine(run, engine):
    """평균 대기시간이 엔진과 1분 이내여야 합니다."""
    mine = run.summary()["avg_waiting_time_min"]
    theirs = engine.summary()["avg_waiting_time_min"]
    assert abs(mine - theirs) < 1.0, f"내 루프 {mine:.2f} vs 엔진 {theirs:.2f}"


def test_service_rate_matches_engine(run, engine):
    assert run.summary()["service_rate"] == pytest.approx(
        engine.summary()["service_rate"], abs=0.05
    )


def test_driving_vehicle_series_correlates_with_engine(run, engine):
    """운행 중 차량 시계열이 같은 모양으로 움직여야 합니다."""
    mine = run.record["driving_vehicle_cnt"].values
    theirs = engine.record["driving_vehicle_cnt"].values
    assert len(mine) == len(theirs)
    assert float(np.corrcoef(mine, theirs)[0, 1]) > 0.8


def test_waiting_series_is_mostly_zero_in_both(run, engine):
    """대기 승객 시계열은 양쪽 다 대부분 0이라 상관계수로 비교할 수 없습니다.

    이런 경우 상관계수를 보고하면 오해를 부릅니다. 대신 분포를 비교합니다.
    """
    mine = run.record["waiting_passenger_cnt"]
    theirs = engine.record["waiting_passenger_cnt"]
    assert (mine == 0).mean() > 0.5
    assert (theirs == 0).mean() > 0.5
    assert abs(mine.mean() - theirs.mean()) < 3.0
