"""RAPTOR — 6~7장 검증 기준.

정답을 손으로 계산할 수 있는 작은 시간표를 만들어 대조합니다.
실제 GTFS 로는 값을 손으로 확인할 수 없으므로, 여기서 알고리즘의 정확성을 못 박고
실제 피드에서는 불변식만 확인합니다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from smartmob.data import load_gtfs
from smartmob.teaching.raptor import (
    INF,
    TransitData,
    haversine_m,
    journey,
    raptor,
    summarize,
)


# --------------------------------------------------------------------------- #
# 손으로 답을 아는 작은 피드
# --------------------------------------------------------------------------- #
#
#   A --(1호선)--> B --(1호선)--> C        1호선: 08:00 A, 08:10 B, 08:20 C
#                  |                                08:30 A, 08:40 B, 08:50 C
#              도보 100m
#                  |
#                  D --(2호선)--> E        2호선: 08:15 D, 08:25 E
#
# A 에서 08:00 출발 → C 는 08:20 (환승 0회)
# A 에서 08:00 출발 → E 는 B(08:10) → 도보 → D(08:15) → E(08:25), 환승 1회


def _toy_feed() -> dict:
    stops = pd.DataFrame(
        [
            ("A", "A역", 37.5000, 127.0000),
            ("B", "B역", 37.5100, 127.0000),
            ("C", "C역", 37.5200, 127.0000),
            ("D", "D역", 37.5100, 127.0011),   # B 에서 동쪽으로 약 100m
            ("E", "E역", 37.5300, 127.0011),
        ],
        columns=["stop_id", "stop_name", "stop_lat", "stop_lon"],
    )
    routes = pd.DataFrame(
        [("L1", "1호선", 1), ("L2", "2호선", 1)],
        columns=["route_id", "route_short_name", "route_type"],
    )
    trips = pd.DataFrame(
        [("L1", "S", "L1-1"), ("L1", "S", "L1-2"), ("L2", "S", "L2-1")],
        columns=["route_id", "service_id", "trip_id"],
    )
    rows = [
        ("L1-1", "08:00:00", "08:00:00", "A", 1),
        ("L1-1", "08:10:00", "08:10:00", "B", 2),
        ("L1-1", "08:20:00", "08:20:00", "C", 3),
        ("L1-2", "08:30:00", "08:30:00", "A", 1),
        ("L1-2", "08:40:00", "08:40:00", "B", 2),
        ("L1-2", "08:50:00", "08:50:00", "C", 3),
        ("L2-1", "08:15:00", "08:15:00", "D", 1),
        ("L2-1", "08:25:00", "08:25:00", "E", 2),
    ]
    stop_times = pd.DataFrame(
        rows, columns=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]
    )
    return {"stops": stops, "routes": routes, "trips": trips, "stop_times": stop_times}


@pytest.fixture(scope="module")
def toy() -> TransitData:
    return TransitData.from_gtfs(_toy_feed(), max_transfer_m=300)


def _at(data: TransitData, stop_id: str) -> int:
    return data.index_of[stop_id]


def test_toy_patterns_grouped(toy):
    """정류장 순서가 같은 두 운행은 패턴 하나로 묶여야 합니다."""
    assert len(toy.patterns) == 2
    l1 = next(p for p in toy.patterns if p.route_id == "L1")
    assert l1.n_trips == 2
    assert l1.departures[0][0] < l1.departures[1][0]   # 첫 출발 시각 순 정렬


def test_toy_transfer_built(toy):
    """B 와 D 는 약 100m 라 도보 환승이 생겨야 합니다."""
    b, d = _at(toy, "B"), _at(toy, "D")
    assert any(other == d for other, _ in toy.transfers[b])
    seconds = next(s for other, s in toy.transfers[b] if other == d)
    assert 60 <= seconds <= 180


def test_toy_direct_ride(toy):
    """A 08:00 출발 → C 는 08:20 도착, 환승 없음."""
    res = raptor(toy, [(_at(toy, "A"), 0)], 8 * 3600)
    assert res.best[_at(toy, "C")] == 8 * 3600 + 20 * 60
    legs = journey(toy, res, _at(toy, "C"))
    transit = [leg for leg in legs if leg["kind"] == "transit"]
    assert len(transit) == 1
    assert transit[0]["route"] == "1호선"


def test_toy_one_transfer(toy):
    """A → B 에서 걸어 D 로, 2호선으로 E. 08:25 도착, 환승 1회."""
    res = raptor(toy, [(_at(toy, "A"), 0)], 8 * 3600)
    assert res.best[_at(toy, "E")] == 8 * 3600 + 25 * 60
    legs = journey(toy, res, _at(toy, "E"))
    s = summarize(toy, legs, 8 * 3600)
    assert s["transfers"] == 1
    assert s["total_min"] == pytest.approx(25.0)


def test_toy_later_departure_takes_second_trip(toy):
    """08:05 에 출발하면 08:00 차를 놓쳐 08:30 차를 타야 합니다."""
    res = raptor(toy, [(_at(toy, "A"), 0)], 8 * 3600 + 5 * 60)
    assert res.best[_at(toy, "C")] == 8 * 3600 + 50 * 60


def test_toy_unreachable_before_service(toy):
    """막차 이후에 출발하면 아무 데도 못 갑니다."""
    res = raptor(toy, [(_at(toy, "A"), 0)], 23 * 3600)
    assert res.best[_at(toy, "C")] == INF
    assert journey(toy, res, _at(toy, "C")) == []


def test_toy_access_walk_delays_departure(toy):
    """접근 도보 10분이 붙으면 08:00 차를 못 탑니다."""
    res = raptor(toy, [(_at(toy, "A"), 600)], 8 * 3600 - 300)   # 07:55 출발 + 10분 도보
    assert res.best[_at(toy, "C")] == 8 * 3600 + 50 * 60


def test_max_rounds_limits_transfers(toy):
    """라운드를 1로 줄이면 환승이 필요한 E 에 못 갑니다."""
    res = raptor(toy, [(_at(toy, "A"), 0)], 8 * 3600, max_rounds=1)
    assert res.best[_at(toy, "C")] < INF     # 직통은 됩니다
    assert res.best[_at(toy, "E")] == INF    # 환승은 안 됩니다


# --------------------------------------------------------------------------- #
# 실제 피드 — 불변식
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def hanam() -> TransitData:
    return TransitData.from_gtfs(load_gtfs("hanam"))


def test_hanam_build(hanam):
    info = hanam.describe()
    assert info["정류장"] == 4203
    assert info["패턴"] > 100
    assert info["운행"] == 8923
    assert info["도보 환승"] > 1000


def test_hanam_patterns_fewer_than_trips(hanam):
    """패턴 묶기가 실제로 압축을 해야 합니다."""
    assert len(hanam.patterns) < sum(p.n_trips for p in hanam.patterns) / 10


def test_hanam_query_reaches_most_stops(hanam):
    origins = hanam.access_stops(37.5393, 127.2148)   # 하남시청
    assert origins, "접근 가능한 정류장이 없습니다"
    res = raptor(hanam, origins, 8 * 3600)
    reached = sum(1 for t in res.best if t < INF)
    assert reached > hanam.n_stops * 0.9


def test_hanam_arrival_never_before_departure(hanam):
    """도착시각이 출발시각보다 이르면 시각 파싱이 틀린 것입니다."""
    res = raptor(hanam, hanam.access_stops(37.5393, 127.2148), 8 * 3600)
    for t in res.best:
        assert t == INF or t >= 8 * 3600


def test_hanam_journey_is_consistent(hanam):
    """복원한 구간의 시각이 단조 증가해야 합니다."""
    res = raptor(hanam, hanam.access_stops(37.5393, 127.2148), 8 * 3600)
    target = hanam.nearest_stop(37.5606, 127.1930)     # 미사역 부근
    legs = journey(hanam, res, target)
    assert legs
    last = 8 * 3600
    for leg in legs:
        if leg["kind"] == "transit":
            assert leg["board_time"] >= last
            assert leg["alight_time"] >= leg["board_time"]
            last = leg["alight_time"]


def test_hanam_later_departure_never_arrives_earlier(hanam):
    """늦게 출발했는데 더 일찍 도착하면 알고리즘이 틀린 것입니다."""
    origins = hanam.access_stops(37.5393, 127.2148)
    early = raptor(hanam, origins, 8 * 3600)
    late = raptor(hanam, origins, 8 * 3600 + 1800)
    violations = sum(
        1 for a, b in zip(early.best, late.best) if b < INF and a < INF and b < a
    )
    assert violations == 0


def test_haversine_m():
    """서울시청 → 하남시청은 약 19km 입니다."""
    d = haversine_m(37.5665, 126.9780, 37.5393, 127.2148)
    assert 18_000 < d < 22_000
