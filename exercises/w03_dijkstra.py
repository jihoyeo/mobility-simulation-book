"""3주차 실습 — 최단경로 (교재 3장)

빈칸을 채운 뒤 자가 채점을 돌립니다.

    python exercises/check.py w03

채점 기준은 하나입니다. NetworkX 의 최단거리와 완전히 같은 값이 나오는가.
"돌아간다"와 "맞다"는 다릅니다.

--------------------------------------------------------------------------
그래프 다루기
--------------------------------------------------------------------------
    from smartmob.data import load_road_graph
    G = load_road_graph("hanam", modes=("drive",))

    G.adj[node]          -> [(이웃 노드, 소요시간_초, 엣지 번호), ...]
    G.neighbors(node)    -> 같은 목록
    G.coord[node]        -> (위도, 경도)
    G.nearest_node(위도, 경도) -> 가장 가까운 노드
    G.max_speed_kmh()    -> 이 도로망의 최고 속도 (A* 휴리스틱에 씁니다)
"""

from __future__ import annotations

import heapq

from smartmob.teaching.graph import haversine_km


def dijkstra(graph, source, target):
    """출발 노드에서 도착 노드까지 소요시간이 가장 짧은 경로.

    Returns
    -------
    (초, 경로 노드 목록, 확정한 노드 수)
        경로 목록은 ``[source, ..., target]`` 입니다.

    Raises
    ------
    ValueError
        길이 없거나 그래프에 없는 노드일 때.

    힌트
    ----
    - `dist[노드]` 로 지금까지 알아낸 최단 소요시간을 들고 있습니다
    - `prev[노드]` 로 직전 노드를 기록해 두면 나중에 경로를 되짚을 수 있습니다
    - `done` 집합에 확정한 노드를 넣습니다. 같은 노드가 힙에 여러 번 들어갈 수 있습니다
    - 도착 노드를 힙에서 **꺼냈을 때** 끝냅니다. 넣을 때가 아닙니다
    """
    raise NotImplementedError("dijkstra 를 구현하세요")


def trace(prev, source, target):
    """`prev` 를 거꾸로 따라가 경로 목록을 만듭니다.

    `prev[target]` 에서 시작해 `source` 에 닿을 때까지 올라간 뒤 뒤집습니다.
    """
    raise NotImplementedError("trace 를 구현하세요")


def astar(graph, source, target):
    """다익스트라에 목적지 방향 힌트를 더한 것.

    힌트로 쓰는 값은 **남은 직선거리를 이 도로망의 최고 속도로 달리는 시간**입니다.
    이 값은 실제 남은 시간보다 항상 작으므로(허용 가능) 최적해가 유지됩니다.

    Returns
    -------
    dijkstra 와 같은 형식.

    힌트
    ----
    - 힙에 넣는 우선순위는 `이미 온 시간 + h(노드)` 입니다
    - 힙에서 꺼낼 때 쓰는 것은 `이미 온 시간` 입니다. 둘을 같이 넣어 둡니다
    - `haversine_km(위도1, 경도1, 위도2, 경도2)` 로 직선거리를 구합니다
    """
    raise NotImplementedError("astar 를 구현하세요")


# --------------------------------------------------------------------------- #
# 직접 돌려 보기
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    from smartmob.data import load_road_graph

    G = load_road_graph("hanam", modes=("drive",))
    start = G.nearest_node(37.5393, 127.2148)   # 하남시청
    goal = G.nearest_node(37.5606, 127.1930)    # 미사역

    seconds, path, settled = dijkstra(G, start, goal)
    print(f"다익스트라  {seconds / 60:.2f}분, 노드 {len(path)}개, 확정 {settled:,}개")

    seconds, path, settled = astar(G, start, goal)
    print(f"A*          {seconds / 60:.2f}분, 노드 {len(path)}개, 확정 {settled:,}개")
