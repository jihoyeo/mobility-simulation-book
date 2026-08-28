"""6주차 실습 — RAPTOR (교재 6장)

빈칸을 채운 뒤 자가 채점을 돌립니다.

    python exercises/check.py w06

채점은 두 단계입니다. 먼저 답을 손으로 아는 작은 시간표로 정확성을 봅니다.
그다음 실제 하남 GTFS 로 불변식을 확인합니다.

--------------------------------------------------------------------------
GTFS 다루기
--------------------------------------------------------------------------
    from smartmob.data import load_gtfs, parse_gtfs_time
    feed = load_gtfs("hanam")

    feed["stops"]       stop_id, stop_name, stop_lat, stop_lon
    feed["routes"]      route_id, route_short_name, route_type
    feed["trips"]       trip_id, route_id, service_id
    feed["stop_times"]  trip_id, stop_id, stop_sequence, arrival_time, departure_time

    parse_gtfs_time("25:30:00")  ->  91800   (24시를 넘는 표기를 그대로 받습니다)
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

INF = float("inf")

WALK_SPEED_MPS = 1.2      # 시속 4.3km
MAX_TRANSFER_M = 500.0    # 이보다 먼 정류장 사이는 환승으로 보지 않습니다
MAX_ACCESS_M = 800.0      # 출발지에서 첫 정류장까지
DETOUR_FACTOR = 1.35      # 직선거리 → 실제 도보거리 보정
MAX_ROUNDS = 5


def haversine_m(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 거리(m). 이건 만들어 두었습니다."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class Pattern:
    """정류장 순서가 완전히 같은 운행들의 묶음."""

    name: str
    route_type: int
    stops: list           # 정류장 인덱스 순서
    arrivals: list        # [운행][위치] 도착 시각(초)
    departures: list      # [운행][위치] 출발 시각(초)
    _dep_by_pos: list = field(default_factory=list, repr=False)

    def build_index(self):
        """위치별 출발시각 열을 만들어 둡니다. `earliest_trip` 의 이분 탐색에 씁니다."""
        self._dep_by_pos = [
            [trip[i] for trip in self.departures] for i in range(len(self.stops))
        ]

    def earliest_trip(self, position, not_before):
        """position 에서 not_before 이후 가장 이르게 출발하는 운행 번호. 없으면 None.

        운행이 첫 정류장 출발 시각 순으로 정렬되어 있으면 `bisect_left` 로 찾습니다.
        """
        raise NotImplementedError("earliest_trip 을 구현하세요")


@dataclass
class TransitData:
    """RAPTOR 가 쓰는 자료구조 네 개."""

    stop_ids: list
    stop_names: list
    stop_lats: list
    stop_lons: list
    patterns: list
    routes_by_stop: list      # 정류장 → [(패턴 번호, 그 패턴에서의 위치), ...]
    transfers: list           # 정류장 → [(정류장, 도보 초), ...]
    index_of: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_gtfs(cls, feed, max_transfer_m=MAX_TRANSFER_M):
        """GTFS 를 RAPTOR 자료구조로 바꿉니다.

        순서
        ----
        1. `stops` 로 정류장 목록과 `stop_id -> 인덱스` 사전을 만듭니다
        2. `stop_times` 를 `trip_id`, `stop_sequence` 로 정렬하고 시각을 초로 바꿉니다
        3. 운행을 **정류장 순서가 같은 것끼리** 묶어 패턴을 만듭니다
           (묶는 열쇠: `(route_id, 정류장 인덱스 튜플)`)
        4. 각 패턴의 운행을 **첫 정류장 출발 시각 순으로 정렬**합니다
        5. 정류장 → 패턴 역색인을 만듭니다
        6. 가까운 정류장 사이를 도보 환승으로 잇습니다

        6번 힌트: `scipy.spatial.cKDTree` 의 `query_ball_point` 로 후보를 좁힌 뒤
        `haversine_m` 으로 정확한 거리를 재고 `DETOUR_FACTOR` 를 곱합니다.
        """
        raise NotImplementedError("TransitData.from_gtfs 를 구현하세요")

    # -- 아래 셋은 만들어 두었습니다 ----------------------------------------- #

    @property
    def n_stops(self):
        return len(self.stop_ids)

    def _kdtree(self):
        from scipy.spatial import cKDTree

        if not hasattr(self, "_tree_cache"):
            self._tree_cache = cKDTree(list(zip(self.stop_lats, self.stop_lons)))
        return self._tree_cache

    def access_stops(self, lat, lon, max_walk_m=MAX_ACCESS_M, limit=30):
        """좌표에서 걸어갈 수 있는 정류장과 도보 소요시간(초)."""
        deg = max_walk_m / 111_000 * DETOUR_FACTOR
        found = []
        for j in self._kdtree().query_ball_point([lat, lon], deg):
            metres = haversine_m(lat, lon, self.stop_lats[j], self.stop_lons[j]) * DETOUR_FACTOR
            if metres <= max_walk_m:
                found.append((int(j), int(math.ceil(metres / WALK_SPEED_MPS))))
        found.sort(key=lambda x: x[1])
        return found[:limit]


def raptor(data, origins, departure_secs, max_rounds=MAX_ROUNDS):
    """모든 정류장까지의 가장 이른 도착시각.

    Parameters
    ----------
    origins : [(정류장 인덱스, 접근 도보 초), ...]
    departure_secs : 자정부터의 초

    Returns
    -------
    list[float]
        ``best[i]`` 는 정류장 i 의 가장 이른 도착시각(초). 못 가면 ``INF``.

    알고리즘
    --------
    라운드 0
        출발 정류장마다 `departure_secs + 도보시간` 을 적고 표시합니다.

    라운드 k
        1. 표시된 정류장을 지나는 패턴을 모읍니다.
           같은 패턴이 여러 정류장에서 걸리면 **가장 앞 위치**에서 시작합니다.
        2. 각 패턴을 그 위치부터 끝까지 훑습니다.
           - 손에 든 차가 있으면 이 정류장의 도착시각으로 내려 봅니다
           - 직전 라운드에 이 정류장에 도달했다면, 여기서 더 이른 차를 탈 수 있는지 봅니다
        3. 이번 라운드에 도달한 정류장에서 걸어갈 수 있는 곳을 채웁니다
        4. 개선된 정류장이 없으면 끝냅니다

    주의
    ----
    - 2번에서 "타기"와 "내리기"의 순서가 중요합니다. 먼저 내려 보고, 그다음 갈아탑니다
    - 타는 판단에는 **직전 라운드**의 도착시각을 씁니다. 이번 라운드 값을 쓰면
      한 라운드에 여러 번 갈아타게 되어 환승 횟수가 무너집니다
    """
    raise NotImplementedError("raptor 를 구현하세요")


# --------------------------------------------------------------------------- #
# 직접 돌려 보기
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    from smartmob.data import load_gtfs

    data = TransitData.from_gtfs(load_gtfs("hanam"))
    print(f"정류장 {data.n_stops:,}개, 패턴 {len(data.patterns)}개")

    origins = data.access_stops(37.5393, 127.2148)      # 하남시청
    best = raptor(data, origins, 8 * 3600)

    reached = sum(1 for t in best if t < INF)
    print(f"오전 8시 출발, {reached:,}개 정류장 도달")

    target = min(range(data.n_stops),
                 key=lambda i: haversine_m(data.stop_lats[i], data.stop_lons[i],
                                           37.5606, 127.1930))
    arrival = best[target]
    if arrival < INF:
        print(f"{data.stop_names[target]} 도착 {int(arrival) // 3600:02d}:"
              f"{int(arrival) % 3600 // 60:02d} "
              f"(통행시간 {(arrival - 8 * 3600) / 60:.1f}분)")
