"""하남 OSM 도로망에서 비용행렬·실제 엣지 형상·배송 비교 결과를 저장합니다.

교재 실습 환경에 optimization 선택 의존성을 설치한 뒤 저장소 루트에서 실행합니다.
python tools/build_ch10_city.py
작은 손계산 예제와 그림은 python tools/build_ch10_optimization.py로 재생성합니다.
"""
import hashlib
import math
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from smartmob.data import load_road_graph
from smartmob.teaching.search import record_search
from smartmob.teaching.graph import parse_edge_id
from smartmob.teaching.optimization_examples import delivery, exact_delivery, DEMANDS
from smartmob.teaching.fleet import ExactFleet, heuristic_fleet
from shapely import from_wkb
import ortools


def city_data():
    # 일정 속도에서는 최소 시간 경로와 최소 거리 경로가 같습니다.
    graph = load_road_graph("hanam", modes=("drive",), speed_kmh=30)
    candidates = sorted(n for n in graph.adj if 37.535 < graph.coord[n][0] < 37.568
                        and 127.185 < graph.coord[n][1] < 127.225)
    rng = random.Random(42)
    nodes = rng.sample(candidates, 35)
    traces = {n: record_search(graph, n) for n in nodes}
    # 서로 왕복 가능한 위치만 사용하며 단절된 도로는 후보에서 제외합니다.
    nodes = [n for n in nodes if all(n in t.times for t in traces.values())]
    if len(nodes) < 35:
        raise ValueError("서로 연결된 표본 노드 35개를 확보하지 못했습니다.")
    shapes = []
    for row in graph.edges.itertuples():
        geom = from_wkb(bytes(row.geometry))
        points = [[round(lat, 7), round(lon, 7)] for lon, lat, *_ in geom.coords]
        u, _ = parse_edge_id(row.edge_id)
        origin = graph.coord[u]
        if sum((a-b)**2 for a,b in zip(points[-1], origin)) < sum((a-b)**2 for a,b in zip(points[0], origin)):
            points.reverse()
        shapes.append(points)

    def route(a, b):
        trace = record_search(graph, a, b)
        assert trace.path
        return {"seconds": round(trace.times[b]), "edges": trace.path_edges,
                "meters": round(sum(float(graph.edges.iloc[e]['length']) for e in trace.path_edges))}

    vehicles, passengers, stops = nodes[:16], nodes[16:28], nodes[28:35]
    taxi = [[route(v, p) for v in vehicles] for p in passengers]
    legs = [[route(a, b) for b in stops] for a in stops]
    distances = [[r["meters"] for r in row] for row in legs]
    results = {str(c): delivery(c, distances) for c in (7, 10)}
    exact = {str(c): exact_delivery(c, distances) for c in (7, 10)}
    for c in results:
        assert results[c]["cost"] >= exact[c]["cost"]
        assert max(results[c]["loads"]) <= int(c)
        assert sorted(i for r in results[c]["routes"] for i in r[1:-1]) == list(range(1, 7))
    # 지도 배경만 화면 주변으로 고르고 경로 계산은 전체 도로망을 사용합니다.
    background = [i for i, s in enumerate(shapes) if any(37.528 < lat < 37.575 and 127.177 < lon < 127.234 for lat, lon in s)]
    data = {"vehicles": [graph.coord[n] for n in vehicles], "passengers": [graph.coord[n] for n in passengers],
            "vehicle_nodes": vehicles, "passenger_nodes": passengers, "stops": [graph.coord[n] for n in stops],
            "stop_nodes": stops, "demands": DEMANDS, "taxi": taxi, "legs": legs,
            "distances": distances, "shapes": shapes, "background": background,
            "delivery": results, "exact": exact, "ortools_version": ortools.__version__,
            "speed_kmh": 30, "seed": 42, "license": "ODbL-1.0", "source": "© OpenStreetMap contributors",
            "inputs": {name: hashlib.sha256((ROOT / 'data/hanam' / name).read_bytes()).hexdigest()
                       for name in ('road_graph_nodes.parquet', 'road_graph_edges.parquet')}}
    return data


def fleet_data(graph):
    """중앙 차고지 주변 12개 가상 주문을 실제 도로 노드에 배치합니다."""
    center = (37.550, 127.203)
    cosine = math.cos(math.radians(center[0]))

    def proximity(node, target):
        lat, lon = graph.coord[node]
        return (lat-target[0])**2 + ((lon-target[1])*cosine)**2

    depot = min(graph.adj, key=lambda n: (proximity(n, center), n))
    reverse = {n: [] for n in graph.adj}
    for u, edges in graph.adj.items():
        for v, _, _ in edges:
            reverse.setdefault(v, []).append(u)

    def reachable(adjacency):
        seen, stack = {depot}, [depot]
        while stack:
            for n in adjacency.get(stack.pop(), []):
                if n not in seen:
                    seen.add(n)
                    stack.append(n)
        return seen

    connected = reachable({n: [v for v, _, _ in edges] for n, edges in graph.adj.items()}) & reachable(reverse)
    targets, stops = [], [depot]
    for i in range(12):
        angle, radius = math.radians(i*30 + 10), (1.1, 1.5, 1.3)[i % 3]
        target = (center[0] + radius*math.sin(angle)/111.32,
                  center[1] + radius*math.cos(angle)/(111.32*cosine))
        targets.append(target)
        stops.append(min(connected - set(stops), key=lambda n: (proximity(n, target), n)))
    assert len(set(stops)) == 13
    lengths = graph.edges['length'].to_numpy()
    legs = []
    for a in stops:
        row = []
        for b in stops:
            trace = record_search(graph, a, b)
            assert trace.path, (a, b)
            row.append({"seconds": round(trace.times[b]), "edges": trace.path_edges,
                        "meters": round(sum(float(lengths[e]) for e in trace.path_edges))})
        legs.append(row)
    distances = [[leg['meters'] for leg in row] for row in legs]
    demands = [0, *([2, 2, 3, 2, 3, 2]*2)]
    exact = ExactFleet(distances, demands)
    solutions = {}
    for trucks in range(2, 7):
        for capacity in (7, 10, 15):
            for objective in ('sum', 'max'):
                optimal = exact.solve(trucks, capacity, objective)
                heuristic = heuristic_fleet(distances, demands, trucks, capacity, objective)
                for result in (optimal, heuristic):
                    if result['cost'] is None:
                        continue
                    assert len(result['routes']) == trucks
                    assert all(len(r) >= 3 and r[0] == r[-1] == 0 for r in result['routes'])
                    assert sorted(i for r in result['routes'] for i in r[1:-1]) == list(range(1, 13))
                    assert max(result['loads']) <= capacity
                if heuristic['cost'] is not None:
                    assert optimal['cost'] is not None
                    score = lambda r: (r['max_distance'], r['cost']) if objective == 'max' else (r['cost'],)
                    assert score(heuristic) >= score(optimal)
                solutions[f'{trucks}:{capacity}:{objective}'] = {'exact': optimal, 'delivery': heuristic}
        print(f'Fleet: {trucks} trucks complete', flush=True)
    return {"stops": [graph.coord[n] for n in stops], "stop_nodes": stops,
            "demands": demands, "legs": legs, "distances": distances, "solutions": solutions,
            "truck_counts": list(range(2, 7)), "capacities": [7, 10, 15],
            "layout": {"center": center, "targets": targets, "kind": "synthetic_radial_snapped_to_osm"},
            "require_all_trucks": True, "distance_unit": "m", "demand_unit": "boxes",
            "exact_method": "Held-Karp subset tours + exact fleet partition DP",
            "heuristic_search_ms": 500}


if __name__ == "__main__":
    # 화면용 배송 예제만 바꿀 때 택시·기존 6곳 예제의 계산 결과를 보존합니다.
    data = json.loads((ROOT / '_static/ch10_city.json').read_text(encoding='utf-8')) if '--fleet-only' in sys.argv else city_data()
    for name, expected in data['inputs'].items():
        assert hashlib.sha256((ROOT / 'data/hanam' / name).read_bytes()).hexdigest() == expected
    graph = load_road_graph('hanam', modes=('drive',), speed_kmh=30)
    assert len(graph.edges) == len(data['shapes'])
    data['fleet'] = fleet_data(graph)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    (ROOT / "_static/ch10_city.json").write_text(text, encoding="utf-8")
    template = (ROOT / "tools/templates/ch10_city.html").read_text(encoding="utf-8")
    (ROOT / "_static/ch10_optimization.html").write_text(template.replace("__DATA__", text), encoding="utf-8")
    print({c: r['cost'] for c, r in data['delivery'].items()})
