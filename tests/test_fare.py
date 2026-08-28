"""수도권 통합환승요금 — 7장 검증 기준.

손으로 계산할 수 있는 사례로 규칙 세 개를 하나씩 못 박습니다.
"""

from __future__ import annotations

import pytest

from smartmob.teaching.fare import (
    BASE_FARE,
    calc_fare,
    count_transfers,
    fare_detail,
)


def leg(mode: str, km: float = 0.0, **extra) -> dict:
    return {"mode": mode, "km": km, **extra}


# --- 규칙 1: 기본요금은 가장 비싼 수단 하나만 -------------------------------- #


def test_bus_only_short_trip():
    assert calc_fare([leg("BUS", 3.0)]) == BASE_FARE["BUS"]


def test_subway_only_short_trip():
    assert calc_fare([leg("SUBWAY", 5.0)]) == BASE_FARE["SUBWAY"]


def test_bus_plus_subway_pays_the_higher_base_once():
    """버스 1,500 + 지하철 1,550 을 따로 내지 않고 1,550 한 번만 냅니다."""
    fare = calc_fare([leg("BUS", 3.0), leg("SUBWAY", 4.0)])
    assert fare == BASE_FARE["SUBWAY"]
    assert fare < BASE_FARE["BUS"] + BASE_FARE["SUBWAY"]


def test_two_buses_still_one_base_fare():
    """버스에서 버스로 갈아타도 기본요금은 한 번입니다."""
    assert calc_fare([leg("BUS", 3.0), leg("BUS", 4.0)]) == BASE_FARE["BUS"]


# --- 규칙 2: 10km 까지는 기본요금만 ------------------------------------------ #


def test_exactly_ten_km_is_base_fare():
    assert calc_fare([leg("BUS", 10.0)]) == BASE_FARE["BUS"]


def test_just_under_ten_km_is_base_fare():
    assert calc_fare([leg("BUS", 9.99)]) == BASE_FARE["BUS"]


# --- 규칙 3: 초과분은 5km 마다 100원 ----------------------------------------- #


@pytest.mark.parametrize(
    "km, expected_blocks",
    [(10.1, 1), (15.0, 1), (15.1, 2), (20.0, 2), (23.0, 3)],
)
def test_distance_surcharge_blocks(km, expected_blocks):
    """10km 를 넘으면 5km 단위로 올림해 가산합니다."""
    detail = fare_detail([leg("BUS", km)])
    assert detail["blocks"] == expected_blocks
    assert detail["fare"] == BASE_FARE["BUS"] + expected_blocks * 100


def test_gtx_surcharge_is_larger():
    """GTX 가 섞이면 가산액이 100원이 아니라 250원입니다."""
    without = calc_fare([leg("SUBWAY", 20.0)])
    with_gtx = calc_fare([leg("GTX", 20.0)])
    assert without == BASE_FARE["SUBWAY"] + 2 * 100
    assert with_gtx == BASE_FARE["GTX"] + 2 * 250


def test_distance_is_summed_across_legs():
    """구간별로 따로 재지 않고 합쳐서 한 번 계산합니다."""
    together = calc_fare([leg("BUS", 6.0), leg("SUBWAY", 6.0)])
    detail = fare_detail([leg("BUS", 6.0), leg("SUBWAY", 6.0)])
    assert detail["total_km"] == pytest.approx(12.0)
    assert together == BASE_FARE["SUBWAY"] + 100


# --- 도보·미탑승 --------------------------------------------------------------- #


def test_walking_legs_do_not_add_distance_or_fare():
    with_walk = calc_fare([leg("WALK", 1.2), leg("BUS", 9.0), leg("WALK", 0.5)])
    assert with_walk == BASE_FARE["BUS"]


def test_walk_only_journey_is_free():
    assert calc_fare([leg("WALK", 2.0)]) == 0
    assert fare_detail([leg("WALK", 2.0)])["fare"] == 0


# --- 환승 횟수 ----------------------------------------------------------------- #


def test_transfer_count_ignores_walking():
    legs = [leg("WALK"), leg("BUS"), leg("WALK"), leg("SUBWAY"), leg("WALK")]
    assert count_transfers(legs) == 1


def test_transfer_count_zero_for_single_ride():
    assert count_transfers([leg("WALK"), leg("BUS")]) == 0


def test_transfer_count_two_rides_two_transfers():
    assert count_transfers([leg("BUS"), leg("SUBWAY"), leg("BUS")]) == 2


def test_transfer_count_walk_only():
    assert count_transfers([leg("WALK")]) == 0


# --- 상세 내역 ----------------------------------------------------------------- #


def test_fare_detail_explains_itself():
    d = fare_detail([leg("BUS", 4.0), leg("SUBWAY", 12.0)])
    assert d["base_mode"] == "SUBWAY"
    assert d["total_km"] == pytest.approx(16.0)
    assert d["over_km"] == pytest.approx(6.0)
    assert d["blocks"] == 2
    assert d["surcharge"] == 200
    assert d["fare"] == BASE_FARE["SUBWAY"] + 200
