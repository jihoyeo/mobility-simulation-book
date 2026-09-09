---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 3장 최단경로 — 다익스트라와 A\*

하남시청에서 미사역까지 차로 몇 분 걸릴까요.

직선거리는 3km입니다. 그런데 차는 직선으로 못 갑니다. 도로를 따라 가야 하고, 어느 길로 가느냐에 따라 시간이 달라집니다. 2장에서 만든 인접 리스트 위에서 가장 빠른 길을 찾는 것이 이 장의 일입니다.

최단경로는 이 책에서 직접 구현하는 세 가지 기능 중 첫 번째입니다.

## 학습 목표

- 다익스트라 알고리즘을 힙으로 구현하고 경로를 복원합니다
- 우선순위 큐에서 꺼낸 노드가 왜 그 시점에 확정되는지 설명합니다
- A\* 로 확장하고, 휴리스틱이 최적해를 깨뜨리지 않는 조건을 확인합니다
- 구현 결과를 `NetworkX` 와 대조해 정확도를 검증합니다

## 3.1 문제를 정확히 적어 봅니다

2장에서 만든 그래프를 다시 불러옵니다.

```{code-cell} python
from smartmob.data import load_road_graph
from smartmob.teaching.graph import haversine_km

G = load_road_graph("hanam", modes=("drive",))

hanam_city_hall = (37.5393, 127.2148)
misa_station = (37.5606, 127.1930)

start = G.nearest_node(*hanam_city_hall)
goal = G.nearest_node(*misa_station)
print(f"출발 {start}  도착 {goal}")
print(f"직선거리 {haversine_km(*hanam_city_hall, *misa_station):.2f} km")
```

풀어야 할 문제는 이것입니다. `start` 에서 `goal` 까지 가는 여러 경로 중, 엣지 소요시간의 합이 가장 작은 것을 찾습니다.

먼저 가장 단순한 방법을 생각해 봅시다. 모든 경로를 다 만들어 보고 가장 짧은 것을 고르는 방법입니다. 노드가 12,566개인 그래프에서 경로의 개수는 셀 수 없이 많으므로 불가능합니다.

## 3.2 다익스트라의 아이디어

아직 확정하지 않은 노드 중 출발점에서 가장 가까운 것은, 지금 알고 있는 그 거리가 이미 **최종 답**입니다.

왜 그럴까요. 그 노드에 더 짧게 가는 길이 있다면, 그 길은 아직 확정되지 않은 다른 노드를 거쳐야 합니다. 그런데 그 노드는 지금 노드보다 멀리 있습니다. 엣지 비용이 음수가 아니므로, 더 먼 곳을 거쳐 가면 더 짧아질 수 없습니다.

그래서 알고리즘은 이렇게 됩니다.

1. 출발점의 거리를 0으로 두고, 나머지는 무한대로 둡니다
2. 아직 확정하지 않은 노드 중 가장 가까운 것을 꺼내 확정합니다
3. 그 노드의 이웃들에 대해 "여기를 거쳐 가면 더 짧은가"를 확인하고, 짧으면 갱신합니다
4. 도착점을 꺼내면 끝입니다

2번의 "가장 가까운 것을 꺼내기"를 매번 전부 훑으면 느립니다. 최소 힙(`heapq`)을 쓰면 로그 시간에 됩니다.

```{note}
엣지 비용이 음수가 아니라는 조건이 중요합니다. 소요시간은 음수가 될 수 없으니 우리 문제에는 항상 맞습니다. 음수 비용이 있는 문제(예: 통행료 환급)라면 다익스트라를 쓸 수 없고 벨만-포드를 써야 합니다.
```

하남시로 가기 전에 손으로 한 번 돌려 봅니다. 노드 여섯 개짜리 그래프이고, 실습 노트북에 있는 것과 같습니다.

```
       (600m)        (900m)
  A ────────────► B ────────────► C
  │               │               ▲
  │(2000m)        │(300m)         │(300m)
  │               ▼               │
  └──────────────►D───────────────┘

  E ────────────► F        (A 쪽과 이어져 있지 않습니다)
         (300m)
```

모든 도로가 시속 36km, 즉 초속 10m입니다. 거리를 10으로 나누면 초가 됩니다.

```{code-cell} python
import pandas as pd
from smartmob.teaching.graph import RoadGraph

toy_nodes = pd.DataFrame([
    {"node_id": "n1", "lat": 37.5000, "lon": 127.2000},   # A
    {"node_id": "n2", "lat": 37.5030, "lon": 127.2000},   # B
    {"node_id": "n3", "lat": 37.5080, "lon": 127.2000},   # C
    {"node_id": "n4", "lat": 37.5050, "lon": 127.2010},   # D
    {"node_id": "n5", "lat": 37.5500, "lon": 127.2500},   # E
    {"node_id": "n6", "lat": 37.5520, "lon": 127.2500},   # F
])
toy_edges = pd.DataFrame([
    {"edge_id": "e1_f_1_2", "length": 600.0},
    {"edge_id": "e2_f_1_3", "length": 2000.0},
    {"edge_id": "e3_f_2_3", "length": 900.0},
    {"edge_id": "e4_f_2_4", "length": 300.0},
    {"edge_id": "e5_f_4_3", "length": 300.0},
    {"edge_id": "e6_f_5_6", "length": 300.0},
]).assign(highway="residential", free_flow_speed_kmh=36.0)

toy = RoadGraph.from_frames(toy_nodes, toy_edges, modes=("drive",))
toy
```

A에서 C까지 위의 네 단계를 따라가면 힙에서 꺼내는 순서가 이렇게 됩니다. 괄호 안은 (출발점에서의 초, 노드)입니다.

| 꺼낸 것 | 확정 | 이웃을 보고 갱신한 뒤 힙에 남은 것 |
|---|---|---|
| (0, A) | A | (60, B), (200, C) |
| (60, B) | B | (90, D), (150, C), (200, C) |
| (90, D) | D | (120, C), (150, C), (200, C) |
| (120, C) | C | 끝 |

C 가 힙에 세 번 들어갔습니다. 120초짜리가 먼저 나오고, 남은 둘은 나중에 나와도 이미 확정된 노드이므로 버립니다. 답은 120초, 경로는 A→B→D→C, 확정한 노드는 4개입니다. 이 표를 코드로 옮긴 것이 다음 절입니다.

## 3.3 구현

`graph.neighbors(u)` 는 (이웃 노드, 소요시간 초, 엣지 번호) 세 값을 돌려줍니다. 2장에서 손으로 만든 인접 리스트에 엣지 번호가 하나 더 붙은 것입니다. 지금은 쓰지 않으므로 `_` 로 받습니다.

```{code-cell} python
import heapq


class NoPath(Exception):
    """두 노드가 이어져 있지 않습니다."""


def dijkstra(graph, source, target):
    dist = {source: 0.0}          # 출발점에서의 최단 소요시간
    prev = {}                     # 경로 복원용. prev[v] = v 직전 노드
    done = set()                  # 확정된 노드
    heap = [(0.0, source)]        # (거리, 노드)

    while heap:
        d, u = heapq.heappop(heap)
        if u in done:
            continue              # 같은 노드가 여러 번 들어갈 수 있습니다
        done.add(u)

        if u == target:
            return d, _trace(prev, source, target), len(done)

        for v, seconds, _ in graph.neighbors(u):
            if v in done:
                continue
            nd = d + seconds
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    raise NoPath(f"{source} 에서 {target} 로 가는 길이 없습니다")


def _trace(prev, source, target):
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()
    return path
```

작은 그래프로 먼저 확인합니다.

```{code-cell} python
seconds, path, settled = dijkstra(toy, "n1", "n3")
print(f"{seconds:.0f}초  경로 {path}  확정 {settled}개")
```

3.2절의 표와 같습니다. 이제 하남시 도로망에서 돌립니다.

```{code-cell} python
seconds, path, settled = dijkstra(G, start, goal)
km = sum(haversine_km(*G.coord[u], *G.coord[v]) for u, v in zip(path, path[1:]))
print(f"소요시간 {seconds / 60:.1f}분   경로 길이 {km:.1f}km")
print(f"거친 노드 {len(path)}개")
print(f"확정한 노드 {settled:,}개")
```

5분 32초입니다. 직선 3km 자리를 도로로 4.2km 달렸으니 평균 시속 45km 정도입니다. 자유류 속도로 계산한 값이라 신호 대기가 빠져 있습니다. 실제로는 더 걸립니다.

눈여겨볼 것은 마지막 줄입니다. 83개 노드짜리 경로를 얻으려고 **4,500개가 넘는 노드를 확정**했습니다. 전체 12,566개의 3분의 1입니다. 출발점에서 도착점 방향으로만 퍼지는 게 아니라 사방으로 고르게 퍼지기 때문입니다.

경로가 실제로 이어져 있는지 확인합니다. 이런 확인을 안 하면 `prev` 를 잘못 채워도 모르고 넘어갑니다.

```{code-cell} python
total = 0.0
for u, v in zip(path, path[1:]):
    edge = next((w for nb, w, _ in G.neighbors(u) if nb == v), None)
    assert edge is not None, f"{u} → {v} 엣지가 없습니다"
    total += edge
print(f"엣지를 다시 더한 값 {total / 60:.1f}분 (알고리즘 결과와 같아야 합니다)")
```

## 3.4 맞는 답인지 어떻게 아는가

코드가 실행된다는 것과 결과가 맞다는 것은 별개입니다. `NetworkX` 의 최단거리와 맞춰 봅니다.

```{code-cell} python
import random
import networkx as nx

nxG = nx.DiGraph()
for u, out in G.adj.items():
    for v, w, _ in out:
        if not nxG.has_edge(u, v) or nxG[u][v]["weight"] > w:
            nxG.add_edge(u, v, weight=w)

rng = random.Random(42)
nodes = [n for n in G.adj if G.adj[n]]

checked, mismatch = 0, 0
while checked < 50:
    s, t = rng.choice(nodes), rng.choice(nodes)
    if s == t or not nx.has_path(nxG, s, t):
        continue
    mine, _, _ = dijkstra(G, s, t)
    theirs = nx.shortest_path_length(nxG, s, t, weight="weight")
    if abs(mine - theirs) > 1e-9:
        mismatch += 1
    checked += 1

print(f"50쌍 대조: 어긋난 것 {mismatch}개")
```

무작위 50쌍에서 직접 구현한 결과와 `NetworkX` 의 결과가 모두 일치합니다.

무작위로 뽑은 노드 쌍 중에는 방향을 따라 도달할 수 없는 경우도 있습니다.

```{code-cell} python
no_path = 0
for _ in range(200):
    s, t = rng.choice(nodes), rng.choice(nodes)
    if not nx.has_path(nxG, s, t):
        no_path += 1
print(f"200쌍 중 경로 없음: {no_path}개")
```

6% 남짓입니다. 일방통행만 있는 막다른 골목이나, 시 경계에서 잘려 나머지와 끊어진 조각이 있기 때문입니다. 그래서 `dijkstra` 는 이 경우에 `NoPath` 예외를 던지고, 부르는 쪽이 `except NoPath:` 로 받아 그 쌍을 건너뜁니다. 4장에서 그렇게 씁니다. 조용히 무한대를 돌려주면 시뮬레이터가 그 승객을 영원히 기다리게 만듭니다.

## 3.5 A\* — 휴리스틱으로 탐색 범위 줄이기

다익스트라는 목적지의 방향을 고려하지 않고 소요시간이 작은 노드부터 확정합니다. 남은 소요시간의 하한을 우선순위에 더하면 목적지와 무관한 노드를 덜 탐색할 수 있습니다.

그러려면 "이 노드에서 목적지까지 앞으로 얼마나 남았는가"를 어림해야 합니다. 정확한 값은 모르지만 **하한**은 압니다. 직선거리를 이 도로망의 최고 속도로 달리는 시간입니다. 실제로는 그보다 빠를 수 없습니다.

이 어림값을 `h(n)` 이라 하고, 힙에 넣는 우선순위를 `이미 온 시간 + h(n)` 으로 바꿉니다. 이것이 A\* 입니다.

```{code-cell} python
def astar(graph, source, target):
    vmax = graph.max_speed_kmh()
    tlat, tlon = graph.coord[target]

    def h(node):
        lat, lon = graph.coord[node]
        return haversine_km(lat, lon, tlat, tlon) / vmax * 3600

    dist = {source: 0.0}
    prev, done = {}, set()
    heap = [(h(source), 0.0, source)]

    while heap:
        _, d, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)

        if u == target:
            return d, _trace(prev, source, target), len(done)

        for v, seconds, _ in graph.neighbors(u):
            if v in done:
                continue
            nd = d + seconds
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd + h(v), nd, v))

    raise NoPath(f"{source} 에서 {target} 로 가는 길이 없습니다")
```

```{code-cell} python
a_seconds, a_path, a_settled = astar(G, start, goal)
print(f"다익스트라  {seconds / 60:6.2f}분   확정 {settled:,}개")
print(f"A*          {a_seconds / 60:6.2f}분   확정 {a_settled:,}개")
```

소요시간은 같고 확정한 노드는 4,565개에서 3,571개로 줄었습니다.

`h(n)` 이 실제 남은 시간보다 **작거나 같아야** 한다는 조건이 결정적입니다. 이것을 허용 가능(admissible)하다고 합니다. 만약 `h` 가 실제보다 크면, 아직 확정하지 않은 노드가 실은 더 짧은데도 뒤로 밀려서 최적해를 놓칩니다.

직선거리를 최고 속도로 나눈 값은 실제 남은 소요시간을 넘지 않습니다. 도로 경로는 직선거리보다 짧을 수 없고 각 엣지의 속도는 `vmax` 이하이기 때문입니다.

## 3.6 확정 노드 수와 실행시간 비교

여러 쌍으로 재 봅니다.

```{code-cell} python
import statistics as st
import time

pairs = []
while len(pairs) < 30:
    s, t = rng.choice(nodes), rng.choice(nodes)
    if s != t and nx.has_path(nxG, s, t):
        pairs.append((s, t))

d_ms, a_ms, d_set, a_set = [], [], [], []
for s, t in pairs:
    t0 = time.perf_counter()
    _, _, n1 = dijkstra(G, s, t)
    d_ms.append((time.perf_counter() - t0) * 1000)
    d_set.append(n1)

    t0 = time.perf_counter()
    _, _, n2 = astar(G, s, t)
    a_ms.append((time.perf_counter() - t0) * 1000)
    a_set.append(n2)

print(f"확정 노드   다익스트라 {st.median(d_set):7,.0f}   A* {st.median(a_set):7,.0f}   ({st.median(d_set) / st.median(a_set):.2f}배 적음)")
print(f"실행 시간   다익스트라 {st.median(d_ms):7.1f}ms   A* {st.median(a_ms):7.1f}ms")
```

확정 노드는 A\*가 1.7배쯤 적은데, 실행 시간은 오히려 더 깁니다. 다익스트라는 한 번에 7ms 안팎입니다. 이 책을 만든 컴퓨터에서 중앙값이 7.4ms 였고, 4장에서 이 값을 씁니다.

두 구현의 차이는 `h(n)` 계산입니다. A\*는 후보 노드를 힙에 넣을 때마다 하버사인 거리를 계산합니다. 이 코드에서는 탐색 노드 감소로 절약한 시간보다 파이썬에서 휴리스틱을 계산한 시간이 더 큽니다.

C나 Rust로 짜면 하버사인 계산이 훨씬 싸지므로 A\*가 이깁니다. 그래프가 커질수록 확정 노드 차이가 벌어지므로, 그때도 A\*가 유리해집니다.

```{tip}
확정 노드 수가 줄었다고 실행시간도 줄었다고 가정해서는 안 됩니다. 알고리즘을 바꾸면 같은 입력으로 실행시간을 다시 측정합니다.
```

## 3.7 전용 라우팅 엔진 호출

DTUMOS 의 라우팅 엔진은 A\*를 쓰지 않습니다. 질의를 받기 전에 그래프를 전처리해 지름길 엣지를 넣어 두는 **축약 계층(Contraction Hierarchies)** 을 씁니다. 전처리에 시간이 들지만 그 뒤의 질의는 훨씬 빨라집니다. 어떻게 하는지는 4.5절에서 봅니다.

우리가 축약 계층을 직접 짜지는 않습니다. 대신 필요할 때 HTTP로 부릅니다.

```{code-cell} python
:tags: [skip-execution]

from smartmob import Dtumos

dt = Dtumos()
result = dt.route("hanam", origin=hanam_city_hall, destination=misa_station)
print(result["duration"] / 60, "분")
```

```{note}
위 셀은 DTUMOS 서버가 있어야 실행됩니다. 서버가 없다면 건너뛰고 `shortest_path` 로 다음 절을 진행합니다.
```

## 3.8 정리된 코드

지금까지 만든 것이 `smartmob.teaching.dijkstra` 에 들어 있습니다. 4장부터는 이걸 씁니다.

```{code-cell} python
from smartmob.teaching.dijkstra import NoPath, dijkstra, shortest_path

p = dijkstra(G, start, goal)
print(f"{p.duration_min:.1f}분, 확정 {p.settled:,}개")
```

이름은 우리가 짠 것과 같지만 반환값이 다릅니다. 튜플 셋 대신 `Path` 객체 하나를 돌려주고, `duration_s`, `nodes`, `settled` 를 속성으로 꺼냅니다. 길이 없으면 같은 이름의 `NoPath` 를 던집니다.

```{code-cell} python
p = shortest_path(G, hanam_city_hall, misa_station, algorithm="dijkstra")
print(f"{p.duration_min:.1f}분, {p.distance_km(G):.2f}km, 확정 {p.settled:,}개")
```

`shortest_path` 는 좌표를 받아 스냅부터 해 줍니다. `coords(G)` 로 지도에 그릴 좌표열을 얻을 수 있습니다.

```{code-cell} python
p.coords(G)[:3]
```

## 이 장의 실습

노트북 `labs/ch03_dijkstra.ipynb` 를 열어 함께 돌립니다.

노드 여섯 개짜리 그래프에서 시작해 하남시 도로망으로 옮기고, `NetworkX` 와 대조합니다.

```bash
jupyter lab labs/ch03_dijkstra.ipynb
```

이 장은 채점받는 실습입니다. 노트북이 아니라 옆의 `labs/ch03_dijkstra.py` 의 빈칸을 채웁니다.
채운 뒤 자가 채점을 돌립니다. 이 기준이 곧 과제 채점 기준입니다.

```bash
python labs/check.py ch03
```

## 정리

- 다익스트라의 핵심은 "미확정 노드 중 가장 가까운 것은 이미 최종 답이다"입니다. 엣지 비용이 음수가 아니어야 성립합니다
- 최소 힙으로 구현하면 90줄입니다. `prev` 를 따라가 경로를 복원하고, 길이 없으면 `NoPath` 를 던집니다
- 하남시청→미사역 질의 하나에 4,500개가 넘는 노드를 확정합니다. 정작 경로에 쓰인 노드는 83개입니다
- A\*는 직선거리를 최고 속도로 나눈 값을 힌트로 씁니다. 이 값이 실제보다 작아야(허용 가능) 최적해가 유지됩니다
- 이 표본에서 A\*는 확정 노드 중앙값을 7,320개에서 3,978.5개로 줄였지만 실행시간은 더 길었습니다
- 무작위 노드 200쌍 중 18쌍은 방향을 따라 도달할 수 없었습니다
- 4장에서 같은 그래프에 시간대별 실측 속도를 넣어 경로가 어떻게 바뀌는지 봅니다

## 연습문제

```{admonition} 연습 3.1  ★
:class: tip

`dijkstra` 를 고쳐, 도착점을 꺼냈을 때 멈추지 말고 끝까지 돌려 봅시다.
확정 노드가 몇 개가 되는지, 시간이 얼마나 더 걸리는지 재 봅니다.
출발점 하나에서 모든 노드까지의 거리를 한꺼번에 얻는 것을 일대다(one-to-all) 탐색이라고 합니다.

산출물: 조기 종료 유무별 확정 노드 수와 실행 시간 표 1개.
```

```{admonition} 연습 3.2  ★★
:class: tip

`astar` 의 휴리스틱에 1.5를 곱해 봅시다(`h(node) * 1.5`).
경로 결과가 다익스트라와 달라지는 쌍이 몇 개나 나오는지, 확정 노드는 얼마나 줄어드는지 재 봅니다.
빨라지는 대신 무엇을 잃는지 설명합니다.

산출물: 50쌍 대조 결과(불일치 건수, 최대 오차 %, 확정 노드 감소율), 설명 3줄.
```

```{admonition} 연습 3.3  ★★★
:class: tip

출발점과 도착점 양쪽에서 동시에 탐색을 진행하는 양방향 다익스트라를 구현해 봅시다.
두 탐색이 만났을 때 언제 멈춰도 되는지가 핵심입니다. 만나자마자 멈추면 틀립니다.

산출물: 구현 코드, 단방향 대비 확정 노드 수와 실행 시간 비교표, 종료 조건 설명.
```

[dtumos-repo]: https://github.com/HNU209/DTUMOS
[osrm-repo]: https://github.com/Project-OSRM/osrm-backend
