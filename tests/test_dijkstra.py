"""최단경로 — 3장 검증 기준.

학생 구현이 맞는지 판정하는 기준은 하나입니다.
**NetworkX 의 최단거리와 같은 값이 나오는가.**
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

from smartmob.data import load_road_graph
from smartmob.teaching.dijkstra import NoPath, astar, dijkstra, shortest_path


@pytest.fixture(scope="module")
def graph():
    return load_road_graph("hanam", modes=("drive",))


@pytest.fixture(scope="module")
def nx_graph(graph):
    G = nx.DiGraph()
    for u, out in graph.adj.items():
        for v, w, _ in out:
            if not G.has_edge(u, v) or G[u][v]["weight"] > w:
                G.add_edge(u, v, weight=w)
    return G


def _sample_pairs(graph, nx_graph, n=40, seed=42):
    """서로 이어져 있는 O-D 쌍을 n 개 뽑습니다."""
    rng = random.Random(seed)
    nodes = [x for x in graph.adj if graph.adj[x]]
    pairs, tries = [], 0
    while len(pairs) < n and tries < n * 60:
        tries += 1
        s, t = rng.choice(nodes), rng.choice(nodes)
        if s == t:
            continue
        if nx.has_path(nx_graph, s, t):
            pairs.append((s, t))
    return pairs


def test_dijkstra_matches_networkx(graph, nx_graph):
    pairs = _sample_pairs(graph, nx_graph, n=40)
    assert len(pairs) >= 20, "이어진 O-D 쌍을 충분히 뽑지 못했습니다."
    for s, t in pairs:
        expected = nx.shortest_path_length(nx_graph, s, t, weight="weight")
        assert dijkstra(graph, s, t).duration_s == pytest.approx(expected, rel=1e-9)


def test_astar_matches_dijkstra(graph, nx_graph):
    """A* 는 허용 가능 휴리스틱을 쓰므로 최적해가 다익스트라와 같아야 합니다."""
    for s, t in _sample_pairs(graph, nx_graph, n=20, seed=7):
        assert astar(graph, s, t).duration_s == pytest.approx(
            dijkstra(graph, s, t).duration_s, rel=1e-9
        )


def test_astar_settles_fewer_nodes(graph, nx_graph):
    """A* 가 확정하는 노드가 평균적으로 더 적어야 합니다(그게 A* 를 쓰는 이유입니다)."""
    pairs = _sample_pairs(graph, nx_graph, n=15, seed=11)
    d_total = sum(dijkstra(graph, s, t).settled for s, t in pairs)
    a_total = sum(astar(graph, s, t).settled for s, t in pairs)
    assert a_total < d_total


def test_path_is_connected(graph, nx_graph):
    """경로의 이웃한 노드 쌍이 실제 엣지여야 합니다."""
    s, t = _sample_pairs(graph, nx_graph, n=1, seed=3)[0]
    path = dijkstra(graph, s, t)
    assert path.nodes[0] == s and path.nodes[-1] == t
    for u, v in zip(path.nodes, path.nodes[1:]):
        assert any(nb == v for nb, _, _ in graph.neighbors(u))


def test_shortest_path_from_coordinates(graph):
    """좌표로 부르면 가장 가까운 노드에 붙여 경로를 냅니다."""
    hanam_city_hall = (37.5393, 127.2148)
    misa_station = (37.5606, 127.1930)
    path = shortest_path(graph, hanam_city_hall, misa_station)
    assert path.duration_min > 0
    assert path.distance_km(graph) > 1.0


def test_missing_node_raises(graph):
    with pytest.raises(NoPath):
        dijkstra(graph, "n_does_not_exist", next(iter(graph.adj)))
