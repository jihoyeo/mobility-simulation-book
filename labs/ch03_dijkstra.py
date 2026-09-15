"""3장 실습 — 최단경로 함수를 작성하는 파일.

`ch03_dijkstra.ipynb`는 데이터를 준비하고 이 파일의 함수를 실행합니다.
이 파일에서 `trace`, `dijkstra`를 작성하고 저장한 뒤 노트북의 확인 셀을
다시 실행합니다. `astar`는 추가 실습이며 기본 채점에는 포함되지 않습니다.

저장소 루트에서 자가 채점:
    python labs/check.py ch03

2장에서 만든 그래프의 인터페이스:
    graph.neighbors(node) -> [(이웃 노드, 통행시간_초, 엣지 인덱스), ...]
    graph.adj             -> 노드별 이웃 목록. 키로 노드의 존재를 확인합니다.
    graph.coord[node]     -> (위도, 경도)
    graph.max_speed_kmh() -> 자유류 속도의 최댓값. 추가 실습에서 사용합니다.

함수 이름과 인자, 반환 형식은 유지합니다. 빈칸의 NotImplementedError를
작성한 코드로 바꿉니다. 경로가 없음을 알리는 NoPath는 아래에서 불러옵니다.
"""

from __future__ import annotations

import heapq

from smartmob.teaching.dijkstra import NoPath
from smartmob.teaching.graph import haversine_km


def trace(prev, source, target):
    """직전 노드 기록을 따라 경로 목록을 복원합니다(교재 3.3).

    입력 예:
        prev = {"n2": "n1", "n4": "n2", "n3": "n4"}
        source = "n1", target = "n3"
    반환 예:
        ["n1", "n2", "n4", "n3"]

    target부터 prev를 따라 source에 닿을 때까지 모은 뒤 순서를 뒤집습니다.
    source == target이면 노드 하나만 담은 목록을 반환합니다.
    이 함수는 dijkstra에서 도착 노드를 확정한 뒤 호출합니다.
    """
    raise NotImplementedError("trace를 구현합니다")


def dijkstra(graph, source, target):
    """출발 노드에서 도착 노드까지 최소 통행시간 경로를 구합니다.

    입력 조건
    ---------
    엣지 비용은 유한한 0 이상의 통행시간(초)입니다. 탐색 중 변하지 않습니다.

    반환값
    ------
    (통행시간_초, 경로_노드_목록, 확정_노드_수)
        경로는 [source, ..., target]입니다. source == target이면
        (0.0, [source], 1)을 반환합니다. 확정 노드 수에는 양 끝도 셉니다.

    예외
    ----
    NoPath
        출발·도착 노드가 그래프에 없거나, 방향을 따라 도달할 수 없을 때.
        함수 안에서 raise NoPath("경로가 없습니다")처럼 사용합니다.

    구현 순서(교재 3.2~3.3)
    ----------------------
    1. 출발·도착 노드가 graph.adj에 있는지 확인합니다.
    2. dist에 잠정 시간, prev에 직전 노드, done에 확정 노드를 기록합니다.
       출발점의 잠정 시간은 0이며 나머지는 아직 발견하지 않은 상태입니다.
    3. 힙에는 (잠정 시간, 노드)를 넣습니다. heapq.heappush와 heappop을 씁니다.
    4. 가장 작은 후보를 꺼냅니다. 이미 done에 있는 노드면 건너뜁니다.
    5. 노드를 확정합니다. 도착점이면 trace로 경로를 복원해 반환합니다.
    6. 이웃까지의 새 시간이 dist의 기존 값보다 작으면 dist와 prev를 갱신하고
       힙에 새 후보를 넣습니다. 아직 기록이 없으면 기존 값은 무한대로 봅니다.
    7. 힙이 비었는데 도착점을 확정하지 못했다면 NoPath를 발생시킵니다.

    도착점을 처음 발견해 힙에 넣은 시점에는 끝내지 않습니다.
    """
    raise NotImplementedError("dijkstra를 구현합니다")


def astar(graph, source, target):
    """추가 실습: 남은 시간의 추정치를 더해 탐색합니다(교재 3.5~3.6).

    반환 형식과 NoPath 처리는 dijkstra와 같습니다. 기본 채점에는 포함되지
    않으며 노트북에서 다익스트라와 결과를 비교합니다.

    이번 실습은 기본 자유류 속도로 읽은 그래프를 사용합니다.
    h(node) = haversine_km(*graph.coord[node], *graph.coord[target]) / vmax * 3600
    vmax는 graph.max_speed_kmh()입니다. km와 km/h를 나눈 뒤 초로 환산합니다.

    - 힙에는 (누적 시간 + h(node), 누적 시간, 노드)를 넣습니다.
    - 이웃까지의 시간을 갱신할 때는 h가 포함되지 않은 누적 시간을 씁니다.
    - h(target)는 0입니다. 모든 엣지에서 h(u) <= 통행시간(u,v) + h(v)를
      만족해야 확정 노드를 다시 처리하지 않는 방식을 쓸 수 있습니다.
    - 노트북에서 이번 목적지에 대한 이 조건을 확인한 뒤 실행합니다.
    """
    raise NotImplementedError("추가 실습: astar를 구현합니다")


if __name__ == "__main__":
    from smartmob.data import load_road_graph

    drive = load_road_graph("hanam", modes=("drive",))
    start = drive.nearest_node(37.5393, 127.2148)
    goal = drive.nearest_node(37.5606, 127.1930)

    for name, search in [("다익스트라", dijkstra), ("A* (추가 실습)", astar)]:
        try:
            seconds, path, settled = search(drive, start, goal)
            print(f"{name}: {seconds / 60:.2f}분, 경로 노드 {len(path)}개, 확정 {settled:,}개")
        except NotImplementedError as exc:
            print(f"[ ] {exc}")
