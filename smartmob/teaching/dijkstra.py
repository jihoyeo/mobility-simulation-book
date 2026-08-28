"""최단경로 — 다익스트라와 A*.

3장에서 유도한 코드의 정돈본입니다. 비용은 **소요시간(초)** 입니다.
엣지의 길이를 속도로 나눈 값이므로, 속도 컬럼을 바꾸면 최단경로도 바뀝니다.

    from smartmob.teaching.graph import RoadGraph
    from smartmob.teaching.dijkstra import shortest_path

    G = RoadGraph.from_parquet("hanam")
    path = shortest_path(G, origin, destination)
    path.duration_min, path.distance_km
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from smartmob.teaching.graph import RoadGraph, haversine_km


@dataclass
class Path:
    """탐색 결과."""

    nodes: list[str]
    duration_s: float
    settled: int  # 확정한 노드 수 — A* 와 비교할 때 씁니다

    @property
    def duration_min(self) -> float:
        return self.duration_s / 60

    def coords(self, graph: RoadGraph) -> list[tuple[float, float]]:
        return [graph.coord[n] for n in self.nodes]

    def distance_km(self, graph: RoadGraph) -> float:
        pts = self.coords(graph)
        return sum(
            haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])
        )

    def __bool__(self) -> bool:
        return bool(self.nodes)


class NoPath(RuntimeError):
    """두 노드가 이어져 있지 않습니다."""


def dijkstra(graph: RoadGraph, source: str, target: str) -> Path:
    """출발 노드에서 도착 노드까지의 최소 소요시간 경로.

    우선순위 큐에서 꺼낸 노드는 그 시점에 이미 최단이 확정됩니다.
    그래서 도착 노드를 꺼내는 순간 멈출 수 있습니다.
    """
    if source not in graph.adj or target not in graph.adj:
        raise NoPath(f"그래프에 없는 노드입니다: {source} 또는 {target}")

    dist: dict[str, float] = {source: 0.0}
    prev: dict[str, str] = {}
    done: set[str] = set()
    heap: list[tuple[float, str]] = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == target:
            return Path(_trace(prev, source, target), d, len(done))
        for v, w, _ in graph.neighbors(u):
            if v in done:
                continue
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    raise NoPath(f"{source} 에서 {target} 로 가는 길이 없습니다.")


def astar(graph: RoadGraph, source: str, target: str, max_speed_kmh: float | None = None) -> Path:
    """다익스트라에 목적지 방향 힌트를 더한 것.

    남은 거리를 이 도로망의 **최고 속도**로 달렸을 때의 시간을 휴리스틱으로 씁니다.
    실제 소요시간보다 절대 크지 않으므로(허용 가능, admissible) 최적해가 보장됩니다.
    """
    if source not in graph.adj or target not in graph.adj:
        raise NoPath(f"그래프에 없는 노드입니다: {source} 또는 {target}")

    vmax = max_speed_kmh or graph.max_speed_kmh()
    tlat, tlon = graph.coord[target]

    def h(node: str) -> float:
        lat, lon = graph.coord[node]
        return haversine_km(lat, lon, tlat, tlon) / max(vmax, 1.0) * 3600

    dist: dict[str, float] = {source: 0.0}
    prev: dict[str, str] = {}
    done: set[str] = set()
    heap: list[tuple[float, float, str]] = [(h(source), 0.0, source)]

    while heap:
        _, d, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == target:
            return Path(_trace(prev, source, target), d, len(done))
        for v, w, _ in graph.neighbors(u):
            if v in done:
                continue
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd + h(v), nd, v))

    raise NoPath(f"{source} 에서 {target} 로 가는 길이 없습니다.")


def shortest_path(
    graph: RoadGraph,
    origin: tuple[float, float],
    destination: tuple[float, float],
    algorithm: str = "astar",
) -> Path:
    """좌표 두 개로 최단경로를 구합니다. 가장 가까운 노드에 붙여서 시작합니다."""
    s = graph.nearest_node(*origin)
    t = graph.nearest_node(*destination)
    return (astar if algorithm == "astar" else dijkstra)(graph, s, t)


def _trace(prev: dict[str, str], source: str, target: str) -> list[str]:
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()
    return path
