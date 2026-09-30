"""6장 실습에서 사용하는 RAPTOR의 기본 자료구조와 탐색 함수.

이 파일은 완성된 참고 구현입니다. 수정하거나 채점기에 제출할 필요가 없습니다.
`labs/ch06_raptor.ipynb`에서 작은 시간표를 이용해 운행 선택과 라운드 갱신을
직접 작성한 뒤, 이 파일의 결과와 비교합니다.

흐름은 다음과 같습니다.

1. `TransitData.from_gtfs`가 GTFS를 정류장·운행 패턴·도보 연결로 바꿉니다.
2. `Pattern.earliest_trip`이 한 정류장에서 탈 수 있는 첫 운행을 찾습니다.
3. `raptor`가 탑승 횟수를 하나씩 늘리며 정류장별 최선 도착시각을 구합니다.

이 파일의 `raptor`는 정류장별 도착시각 배열을 반환합니다. 경로의 승하차 구간을
복원하려면 `smartmob.teaching.raptor`의 `journey`와 결과 객체를 사용합니다.

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
    """같은 정류장 순서로 움직이는 여러 차량의 시간표입니다.

    `stops`는 패턴 안의 정류장 순서입니다. `arrivals`와 `departures`는
    `[운행 번호][정류장 위치]`로 시각을 읽는 이차원 배열이며 단위는
    자정부터의 초입니다. 한 운행의 행을 따라가면 같은 차량의 뒤 정류장
    도착시각을 확인할 수 있습니다.
    """

    name: str
    route_type: int
    stops: list           # 정류장 인덱스 순서
    arrivals: list        # [운행][위치] 도착 시각(초)
    departures: list      # [운행][위치] 출발 시각(초)
    _dep_by_pos: list = field(default_factory=list, repr=False)
    _sorted: bool = True

    def build_index(self):
        """정류장 위치마다 운행들의 출발시각을 모아 둡니다.

        운행을 첫 정류장 출발시각으로 정렬했더라도 뒤 정류장의 순서까지
        같다는 보장은 없으므로, 모든 위치의 정렬 상태를 함께 확인합니다.
        """
        # 각 위치 i에서 운행별 출발시각을 한 열로 모읍니다.
        self._dep_by_pos = [
            [trip[i] for trip in self.departures] for i in range(len(self.stops))
        ]
        # 모든 열이 정렬되어 있을 때만 이분 탐색을 사용할 수 있습니다.
        self._sorted = all(
            all(a <= b for a, b in zip(col, col[1:]))
            for col in self._dep_by_pos
        )

    def earliest_trip(self, position, not_before):
        """해당 위치에서 준비 시각 이후 첫 출발 운행의 번호를 반환합니다.

        `position`은 패턴 안의 정류장 위치, `not_before`는 승객이
        탑승할 준비가 된 시각입니다. 출발시각이 준비 시각과 같아도 탈 수
        있습니다. 탈 운행이 없으면 `None`을 반환합니다.
        """
        # 이 정류장에서 운행들이 출발하는 시각을 읽습니다.
        departures = self._dep_by_pos[position]
        if self._sorted:
            # 정렬된 열에서는 준비 시각 이상인 첫 칸을 이분 탐색합니다.
            trip = bisect_left(departures, not_before)
            # 배열 끝까지 갔다면 이후에 출발하는 차량이 없습니다.
            return trip if trip < len(departures) else None

        # 운행의 순서가 뒤집힌 열은 직접 훑어 가장 이른 출발을 고릅니다.
        chosen, earliest = None, INF
        for trip, departure in enumerate(departures):
            # 이미 떠난 차와 현재 후보보다 늦은 차는 제외합니다.
            if not_before <= departure < earliest:
                chosen, earliest = trip, departure
        return chosen


@dataclass
class TransitData:
    """GTFS를 RAPTOR가 읽기 쉬운 배열로 바꾼 결과입니다.

    `stop_ids[i]`는 정류장 i의 원래 ID입니다. `patterns`는 차량별 시간표를
    정류장 순서로 묶은 목록입니다. `routes_by_stop[i]`는 정류장 i를 지나는
    패턴과 그 안의 위치를 알려 주고, `transfers[i]`는 걸어서 갈 수 있는
    정류장과 소요시간을 알려 줍니다. `index_of`는 ID를 배열 번호로 바꿉니다.
    """

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
        """제공 코드: GTFS를 학생 탐색 함수가 읽을 자료구조로 바꿉니다.

        기본 실습에서는 반환된 패턴·역색인·도보 연결을 읽습니다.
        `Pattern`은 이 파일의 클래스로 만들므로 `earliest_trip`은 학생 구현을 씁니다.
        아래 변환 과정을 직접 작성하는 일은 기본 탐색을 마친 뒤의 심화 과제입니다.

        순서
        ----
        1. `stops` 로 정류장 목록과 `stop_id -> 인덱스` 사전을 만듭니다
        2. `stop_times` 를 `trip_id`, `stop_sequence` 로 정렬하고 시각을 초로 바꿉니다
        3. 운행을 **정류장 순서가 같은 것끼리** 묶어 패턴을 만듭니다
           (묶는 열쇠: `(route_id, 정류장 인덱스 튜플)`)
        4. 각 패턴의 운행을 **첫 정류장 출발 시각 순으로 정렬**합니다
        5. 정류장 → 패턴 역색인을 만듭니다
        6. 가까운 정류장 사이를 도보 환승으로 잇습니다

        만들 것: `Pattern` 목록, `routes_by_stop`, `transfers`, `index_of`.
        `Pattern` 하나를 만든 뒤에는 반드시 `build_index()` 를 불러 둡니다.
        그래야 `earliest_trip` 이 쓸 열이 생깁니다.

        3번 힌트: `collections.defaultdict(list)` 에 열쇠별로 trip_id 를 모읍니다.
        패턴의 `name` 은 `routes` 의 `route_short_name`, `route_type` 은 정수로 둡니다.

        4번 힌트: 운행별 첫 출발 시각은 정렬된 `stop_times` 를
        `groupby("trip_id")["dep"].first()` 로 얻습니다.

        6번 힌트: `scipy.spatial.cKDTree` 의 `query_ball_point` 로 후보를 좁힌 뒤
        `haversine_m` 으로 정확한 거리를 재고 `DETOUR_FACTOR` 를 곱합니다.
        도보 초는 거리를 `WALK_SPEED_MPS` 로 나눈 값이고, 자기 자신은 넣지 않습니다.
        """
        from smartmob.teaching.raptor import TransitData as PreparedData

        prepared = PreparedData.from_gtfs(feed, max_transfer_m=max_transfer_m)
        patterns = [
            Pattern(p.name, p.route_type, p.stops, p.arrivals, p.departures)
            for p in prepared.patterns
        ]
        for pattern in patterns:
            pattern.build_index()
        return cls(
            stop_ids=prepared.stop_ids, stop_names=prepared.stop_names,
            stop_lats=prepared.stop_lats, stop_lons=prepared.stop_lons,
            patterns=patterns, routes_by_stop=prepared.routes_by_stop,
            transfers=prepared.transfers, index_of=prepared.index_of,
        )

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
    """출발 가능한 정류장들에서 모든 정류장까지의 최선 도착시각을 구합니다.

    `origins`의 각 항목은 `(정류장 번호, 출발지에서 걷는 초)`입니다.
    `departure_secs`는 출발 시각을 자정부터의 초로 나타냅니다.
    반환 배열의 `best[i]`는 정류장 i에 도착할 수 있는 가장 이른 시각이며,
    도달할 수 없으면 `INF`입니다.

    라운드 k는 차량에 최대 k번 탑승한 경로를 다룹니다. 새 라운드는 이전
    결과를 복사해 시작하므로 탑승 횟수가 적은 좋은 경로도 계속 남습니다.
    새 차량에 탈 수 있는지는 이전 라운드의 시각으로만 판단합니다.

    Parameters
    ----------
    origins : [(정류장 인덱스, 접근 도보 초), ...]
    departure_secs : 자정부터의 초

    Returns
    -------
    list[float]
        ``best[i]`` 는 정류장 i 의 가장 이른 도착시각(초). 못 가면 ``INF``.

    """
    # 정류장마다 현재까지 찾은 가장 이른 시각을 보관합니다.
    best = [INF] * data.n_stops
    # 라운드 0은 차량에 타기 전입니다. 출발지에서 걸어갈 시간을 더합니다.
    prev = [INF] * data.n_stops
    marked = set()
    for stop, walk_seconds in origins:
        arrival = departure_secs + walk_seconds
        if arrival < prev[stop]:
            prev[stop] = best[stop] = arrival
            marked.add(stop)

    for _round in range(1, max_rounds + 1):
        # 이전 라운드의 좋은 경로도 이번 답에 포함합니다.
        cur = list(prev)
        new_marked = set()

        # 도착시각이 개선된 정류장을 지나는 패턴만 고릅니다.
        # 한 패턴에서 여러 정류장이 표시되면 가장 앞 위치부터 훑습니다.
        queue = {}
        for stop in marked:
            for pattern_idx, position in data.routes_by_stop[stop]:
                queue[pattern_idx] = min(position, queue.get(pattern_idx, position))

        for pattern_idx, start_position in queue.items():
            pattern = data.patterns[pattern_idx]
            trip = None  # 현재 비교 중인 운행 번호. 아직 선택 전이면 None입니다.
            for position in range(start_position, len(pattern.stops)):
                stop = pattern.stops[position]

                # 앞 정류장에서 선택한 차를 타고 여기서 내리는 후보를 봅니다.
                if trip is not None:
                    arrival = pattern.arrivals[trip][position]
                    if arrival < best[stop]:
                        best[stop] = cur[stop] = arrival
                        new_marked.add(stop)

                # 새 승차는 이전 라운드에 이 정류장에 도착한 경로에서만 허용합니다.
                ready = prev[stop]
                if ready < INF:
                    candidate = pattern.earliest_trip(position, int(ready))
                    # 더 이른 운행을 탈 수 있으면 비교할 경로 후보를 바꿉니다.
                    if candidate is not None and (
                        trip is None
                        or pattern.departures[candidate][position]
                        < pattern.departures[trip][position]
                    ):
                        trip = candidate

        # 새로 개선된 정류장에서 한 번 걸어갈 수 있는 곳도 같은 라운드에 둡니다.
        # 목록을 복사해 순회하므로 이번 도보의 도착지에서 다시 걷지는 않습니다.
        for stop in list(new_marked):
            for other, walk_seconds in data.transfers[stop]:
                arrival = cur[stop] + walk_seconds
                if arrival < best[other]:
                    best[other] = cur[other] = arrival
                    new_marked.add(other)

        # 도착시각이 하나도 개선되지 않았다면 다음 라운드의 후보가 없습니다.
        if not new_marked:
            break
        # 이번 결과가 다음 라운드의 승차 판단 기준이 됩니다.
        prev, marked = cur, new_marked

    return best


# --------------------------------------------------------------------------- #
# 하남 자료로 실행해 보기
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
