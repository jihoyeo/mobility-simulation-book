"""RAPTOR — 시간표 기반 대중교통 경로 탐색.

6~7장에서 유도한 코드의 정돈본입니다.

    from smartmob.data import load_gtfs
    from smartmob.teaching.raptor import TransitData, raptor, journey

    data = TransitData.from_gtfs(load_gtfs("hanam"))
    result = raptor(data, data.access_stops(37.5393, 127.2148), 8 * 3600)
    journey(data, result, data.nearest_stop(37.5606, 127.1930))

도로망 최단경로와 무엇이 다른가
-------------------------------
도로에서는 "다음 노드로 몇 초"가 정해져 있습니다. 대중교통에서는 정해져 있지 않습니다.
같은 정류장에서 같은 노선을 타도 몇 시에 도착했느냐에 따라 다음 차까지 기다리는 시간이
달라집니다. 그래서 그래프가 아니라 **시간표를 훑는** 방식이 자연스럽습니다.

RAPTOR 는 "환승 k번 이하로 갈 수 있는 가장 이른 도착시각"을 k=0,1,2,… 로 한 라운드씩
넓혀 갑니다. 라운드마다 두 가지를 합니다.

1. 직전 라운드에서 개선된 정류장을 지나는 노선을 훑어 타고 내립니다
2. 그렇게 도착한 정류장에서 걸어서 갈 수 있는 곳을 채웁니다
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Iterable

WALK_SPEED_MPS = 1.2          # 시속 4.3km. 신호와 우회를 감안한 통상값
MAX_TRANSFER_M = 500.0        # 이보다 먼 정류장 사이는 환승으로 보지 않습니다
MAX_ACCESS_M = 800.0          # 출발지에서 첫 정류장까지 걸어갈 수 있는 거리
DETOUR_FACTOR = 1.35          # 직선거리 → 실제 도보거리 보정
MAX_ROUNDS = 5                # 환승 4회까지
INF = float("inf")


@dataclass
class Pattern:
    """정류장 순서가 완전히 같은 운행들의 묶음.

    GTFS 의 노선(route)은 상행·하행·지선이 섞여 있어 그대로 쓸 수 없습니다.
    정류장 순서가 같은 것끼리 묶어야 "이 정류장 다음은 저 정류장"이 하나로 정해집니다.
    RAPTOR 논문이 말하는 route 는 이 묶음입니다.
    """

    route_id: str
    name: str
    route_type: int
    stops: list[int]                      # 정류장 인덱스 순서
    arrivals: list[list[int]]             # [운행][위치] 도착 시각(초)
    departures: list[list[int]]           # [운행][위치] 출발 시각(초)
    _dep_by_pos: list[list[int]] = field(default_factory=list, repr=False)
    _sorted: bool = True

    def build_index(self) -> None:
        """위치별 출발시각 열을 만들어 둡니다. 이분 탐색에 씁니다."""
        self._dep_by_pos = [
            [trip[i] for trip in self.departures] for i in range(len(self.stops))
        ]
        self._sorted = all(
            all(col[j] <= col[j + 1] for j in range(len(col) - 1))
            for col in self._dep_by_pos
        )

    def earliest_trip(self, position: int, not_before: int) -> int | None:
        """position 에서 not_before 이후에 출발하는 가장 이른 운행의 번호."""
        col = self._dep_by_pos[position]
        if self._sorted:
            i = bisect_left(col, not_before)
            return i if i < len(col) else None
        best, best_t = None, INF
        for i, t in enumerate(col):
            if not_before <= t < best_t:
                best, best_t = i, t
        return best

    @property
    def n_trips(self) -> int:
        return len(self.departures)


@dataclass
class TransitData:
    """RAPTOR 가 쓰는 자료구조 네 개."""

    stop_ids: list[str]
    stop_names: list[str]
    stop_lats: list[float]
    stop_lons: list[float]
    patterns: list[Pattern]
    routes_by_stop: list[list[tuple[int, int]]]     # 정류장 → [(패턴, 위치)]
    transfers: list[list[tuple[int, int]]]          # 정류장 → [(정류장, 도보 초)]
    index_of: dict[str, int] = field(default_factory=dict, repr=False)
    _tree: object = field(default=None, repr=False)

    # -- 만들기 -------------------------------------------------------------- #

    @classmethod
    def from_gtfs(
        cls,
        feed: dict,
        max_transfer_m: float = MAX_TRANSFER_M,
        walk_speed_mps: float = WALK_SPEED_MPS,
    ) -> "TransitData":
        from smartmob.data.gtfs import parse_gtfs_time

        stops = feed["stops"]
        stop_ids = stops["stop_id"].astype(str).tolist()
        index_of = {sid: i for i, sid in enumerate(stop_ids)}

        st = feed["stop_times"].copy()
        st["stop_sequence"] = st["stop_sequence"].astype(int)
        st = st.sort_values(["trip_id", "stop_sequence"])
        st["arr"] = st["arrival_time"].map(parse_gtfs_time)
        st["dep"] = st["departure_time"].map(parse_gtfs_time)
        st["idx"] = st["stop_id"].astype(str).map(index_of)
        st = st.dropna(subset=["idx"])
        st["idx"] = st["idx"].astype(int)

        route_of = dict(zip(feed["trips"]["trip_id"], feed["trips"]["route_id"]))
        routes = feed["routes"].set_index("route_id")

        # 1) 정류장 순서가 같은 운행끼리 묶습니다.
        grouped: dict[tuple, dict] = {}
        for trip_id, rows in st.groupby("trip_id", sort=False):
            seq = tuple(rows["idx"].tolist())
            if len(seq) < 2:
                continue
            key = (route_of.get(trip_id, "?"), seq)
            bucket = grouped.setdefault(
                key, {"arr": [], "dep": [], "stops": list(seq), "route_id": key[0]}
            )
            bucket["arr"].append(rows["arr"].tolist())
            bucket["dep"].append(rows["dep"].tolist())

        # 2) 각 묶음의 운행을 첫 정류장 출발 시각 순으로 정렬합니다.
        patterns: list[Pattern] = []
        for (route_id, _seq), bucket in grouped.items():
            order = sorted(range(len(bucket["dep"])), key=lambda i: bucket["dep"][i][0])
            row = routes.loc[route_id] if route_id in routes.index else None
            patterns.append(
                Pattern(
                    route_id=route_id,
                    name=str(row["route_short_name"]) if row is not None else str(route_id),
                    route_type=int(row["route_type"]) if row is not None else -1,
                    stops=bucket["stops"],
                    arrivals=[bucket["arr"][i] for i in order],
                    departures=[bucket["dep"][i] for i in order],
                )
            )
        for p in patterns:
            p.build_index()

        # 3) 정류장에서 그 정류장을 지나는 패턴을 바로 찾을 수 있게 뒤집어 둡니다.
        routes_by_stop: list[list[tuple[int, int]]] = [[] for _ in stop_ids]
        for pi, p in enumerate(patterns):
            for pos, s in enumerate(p.stops):
                routes_by_stop[s].append((pi, pos))

        data = cls(
            stop_ids=stop_ids,
            stop_names=stops["stop_name"].astype(str).tolist(),
            stop_lats=stops["stop_lat"].astype(float).tolist(),
            stop_lons=stops["stop_lon"].astype(float).tolist(),
            patterns=patterns,
            routes_by_stop=routes_by_stop,
            transfers=[],
            index_of=index_of,
        )
        data.transfers = data._build_transfers(max_transfer_m, walk_speed_mps)
        return data

    def _build_transfers(self, max_m: float, speed: float) -> list[list[tuple[int, int]]]:
        """가까운 정류장 사이를 도보 환승으로 잇습니다.

        GTFS 에 `transfers.txt` 가 없으면(한국 피드는 대부분 없습니다) 이렇게 만듭니다.
        직선거리에 보정계수를 곱한 값이라 실제 도보 경로보다 낙관적입니다.
        """
        tree = self._kdtree()
        deg = max_m / 111_000 * DETOUR_FACTOR   # 위경도 1도 ≈ 111km
        out: list[list[tuple[int, int]]] = [[] for _ in self.stop_ids]
        for i, neighbours in enumerate(tree.query_ball_point(self._points(), deg)):
            lat1, lon1 = self.stop_lats[i], self.stop_lons[i]
            found = []
            for j in neighbours:
                if j == i:
                    continue
                metres = haversine_m(lat1, lon1, self.stop_lats[j], self.stop_lons[j]) * DETOUR_FACTOR
                if metres <= max_m:
                    found.append((j, int(math.ceil(metres / speed))))
            found.sort(key=lambda x: x[1])
            out[i] = found
        return out

    # -- 조회 ---------------------------------------------------------------- #

    @property
    def n_stops(self) -> int:
        return len(self.stop_ids)

    def _points(self):
        return list(zip(self.stop_lats, self.stop_lons))

    def _kdtree(self):
        if self._tree is None:
            from scipy.spatial import cKDTree

            object.__setattr__(self, "_tree", cKDTree(self._points()))
        return self._tree

    def nearest_stop(self, lat: float, lon: float) -> int:
        _, idx = self._kdtree().query([lat, lon])
        return int(idx)

    def access_stops(
        self, lat: float, lon: float, max_walk_m: float = MAX_ACCESS_M,
        walk_speed_mps: float = WALK_SPEED_MPS, limit: int = 30,
    ) -> list[tuple[int, int]]:
        """좌표에서 걸어갈 수 있는 정류장과 도보 소요시간(초)."""
        deg = max_walk_m / 111_000 * DETOUR_FACTOR
        found = []
        for j in self._kdtree().query_ball_point([lat, lon], deg):
            metres = haversine_m(lat, lon, self.stop_lats[j], self.stop_lons[j]) * DETOUR_FACTOR
            if metres <= max_walk_m:
                found.append((int(j), int(math.ceil(metres / walk_speed_mps))))
        found.sort(key=lambda x: x[1])
        return found[:limit]

    def describe(self) -> dict:
        return {
            "정류장": self.n_stops,
            "패턴": len(self.patterns),
            "운행": sum(p.n_trips for p in self.patterns),
            "도보 환승": sum(len(t) for t in self.transfers),
        }


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(min(1.0, math.sqrt(a)))


def path_km(data: "TransitData", stops: list[int]) -> float:
    """정류장 순서를 따라간 거리(km).

    정류장 사이를 직선으로 잇습니다. 실제 노선은 도로를 따라 돌아가므로
    이 값은 실제보다 짧습니다. 요금 계산에 쓸 때 이 점을 감안해야 합니다.
    """
    total = 0.0
    for a, b in zip(stops, stops[1:]):
        total += haversine_m(
            data.stop_lats[a], data.stop_lons[a], data.stop_lats[b], data.stop_lons[b]
        )
    return total / 1000


# --------------------------------------------------------------------------- #
# 알고리즘
# --------------------------------------------------------------------------- #


@dataclass
class RaptorResult:
    """라운드별 최선 도착시각과 경로 복원용 기록."""

    best: list[float]                       # 정류장별 최선 도착시각(초)
    rounds: list[list[float]]               # rounds[k][stop]
    parent: dict[tuple[int, int], tuple]    # (라운드, 정류장) → 어떻게 왔는가
    departure: int
    n_rounds: int

    def arrival(self, stop: int) -> float:
        return self.best[stop]

    def transfers_to(self, stop: int) -> int | None:
        """그 정류장에 최선으로 도착한 라운드 = 탄 횟수."""
        for k, row in enumerate(self.rounds):
            if row[stop] == self.best[stop] < INF:
                return max(k - 1, 0)
        return None


def raptor(
    data: TransitData,
    origins: Iterable[tuple[int, int]],
    departure_secs: int,
    max_rounds: int = MAX_ROUNDS,
) -> RaptorResult:
    """출발 정류장 목록에서 시작해 모든 정류장까지의 가장 이른 도착시각을 구합니다.

    ``origins`` 는 ``(정류장 인덱스, 접근 도보 초)`` 목록입니다.
    """
    n = data.n_stops
    best = [INF] * n
    rounds = [[INF] * n]
    parent: dict[tuple[int, int], tuple] = {}

    marked = set()
    for stop, walk in origins:
        t = departure_secs + walk
        if t < rounds[0][stop]:
            rounds[0][stop] = t
            best[stop] = min(best[stop], t)
            parent[(0, stop)] = ("access", walk)
            marked.add(stop)

    for k in range(1, max_rounds + 1):
        prev, cur = rounds[k - 1], list(rounds[k - 1])
        rounds.append(cur)
        new_marked: set[int] = set()

        # 1단계 — 훑을 패턴을 모읍니다. 같은 패턴은 가장 앞 위치에서 시작합니다.
        queue: dict[int, int] = {}
        for stop in marked:
            for pattern_idx, pos in data.routes_by_stop[stop]:
                if pattern_idx not in queue or pos < queue[pattern_idx]:
                    queue[pattern_idx] = pos

        # 2단계 — 패턴을 훑으며 타고 내립니다.
        for pattern_idx, start_pos in queue.items():
            p = data.patterns[pattern_idx]
            trip: int | None = None
            board_pos = 0
            for pos in range(start_pos, len(p.stops)):
                stop = p.stops[pos]

                if trip is not None:
                    arrive = p.arrivals[trip][pos]
                    if arrive < best[stop]:
                        best[stop] = arrive
                        cur[stop] = arrive
                        parent[(k, stop)] = ("ride", pattern_idx, trip, board_pos, pos)
                        new_marked.add(stop)

                # 여기서 더 이른 차를 탈 수 있으면 갈아탑니다.
                ready = prev[stop]
                if ready < INF:
                    candidate = p.earliest_trip(pos, int(ready))
                    if candidate is not None and (
                        trip is None or p.departures[candidate][pos] < p.departures[trip][pos]
                    ):
                        trip, board_pos = candidate, pos

        # 3단계 — 내린 곳에서 걸어갑니다. 한 라운드에 도보는 한 번만 합니다.
        for stop in list(new_marked):
            base = cur[stop]
            for other, seconds in data.transfers[stop]:
                arrive = base + seconds
                if arrive < best[other]:
                    best[other] = arrive
                    cur[other] = arrive
                    parent[(k, other)] = ("walk", stop, seconds)
                    new_marked.add(other)

        if not new_marked:
            return RaptorResult(best, rounds, parent, departure_secs, k)
        marked = new_marked

    return RaptorResult(best, rounds, parent, departure_secs, max_rounds)


def journey(data: TransitData, result: RaptorResult, target: int) -> list[dict]:
    """도착 정류장에서 거꾸로 따라가 구간 목록을 복원합니다."""
    if result.best[target] == INF:
        return []

    k = next(k for k, row in enumerate(result.rounds) if row[target] == result.best[target])
    legs: list[dict] = []
    stop, round_idx = target, k

    while True:
        entry = result.parent.get((round_idx, stop))
        if entry is None:
            if round_idx == 0:
                break
            round_idx -= 1
            continue

        kind = entry[0]
        if kind == "access":
            legs.append({"mode": "WALK", "kind": "access", "seconds": entry[1],
                         "to": stop, "km": round(entry[1] * WALK_SPEED_MPS / 1000, 3)})
            break
        if kind == "walk":
            _, prev_stop, seconds = entry
            legs.append({"mode": "WALK", "kind": "transfer", "seconds": seconds,
                         "from": prev_stop, "to": stop,
                         "km": round(seconds * WALK_SPEED_MPS / 1000, 3)})
            stop = prev_stop
            continue
        # ride
        _, pattern_idx, trip, board_pos, alight_pos = entry
        p = data.patterns[pattern_idx]
        ridden = p.stops[board_pos:alight_pos + 1]
        legs.append({
            "mode": _mode_label(p.route_type),
            "kind": "transit",
            "route": p.name,
            "route_type": p.route_type,
            "from": p.stops[board_pos],
            "to": p.stops[alight_pos],
            "board_time": p.departures[trip][board_pos],
            "alight_time": p.arrivals[trip][alight_pos],
            "n_stops": alight_pos - board_pos,
            "stop_path": ridden,
            "km": round(path_km(data, ridden), 3),
        })
        stop = p.stops[board_pos]
        round_idx -= 1

    legs.reverse()
    return legs


_MODE_LABEL = {
    0: "BUS", 1: "SUBWAY", 2: "FERRY", 3: "BUS",
    4: "RAIL", 5: "BUS", 6: "RAIL", 7: "AIR", 8: "GTX",
}


def _mode_label(route_type: int) -> str:
    return _MODE_LABEL.get(route_type, "TRANSIT")


def summarize(data: TransitData, legs: list[dict], departure_secs: int) -> dict:
    """구간 목록을 지표로 요약합니다.

    총 통행시간은 출발 시각부터 마지막 구간이 끝나는 시각까지입니다.
    차내시간과 도보시간을 빼고 남는 것이 대기시간입니다.
    """
    if not legs:
        return {"reachable": False}

    transit = [leg for leg in legs if leg["kind"] == "transit"]
    walk_s = sum(leg["seconds"] for leg in legs if leg["mode"] == "WALK")
    ivt = sum(leg["alight_time"] - leg["board_time"] for leg in transit)

    if transit:
        # 마지막 하차 시각 + 그 뒤에 남은 도보
        tail = sum(leg["seconds"] for leg in legs[legs.index(transit[-1]) + 1:]
                   if leg["mode"] == "WALK")
        total = transit[-1]["alight_time"] + tail - departure_secs
    else:
        total = walk_s

    return {
        "reachable": True,
        "total_min": round(total / 60, 1),
        "in_vehicle_min": round(ivt / 60, 1),
        "walk_min": round(walk_s / 60, 1),
        "wait_min": round(max(total - ivt - walk_s, 0) / 60, 1),
        "transfers": max(len(transit) - 1, 0),
        "modes": [leg["mode"] for leg in transit],
        "routes": [leg["route"] for leg in transit],
    }
