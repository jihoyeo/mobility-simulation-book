"""저장소 루트에서 python tools/build_ch10_optimization.py로 결과·그림·HTML 재생성."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from smartmob.teaching import optimization_examples as ex
import ortools


def build():
    costs = ex.taxi_costs()
    baseline = [[0, 1, 4, 5, 0], [0, 2, 3, 6, 0]]
    data = {"source": "교재 자체 가상 격자, 좌표 km, 격자 최단거리, 택시 20km/h",
            "ortools_version": ortools.__version__, "passengers": ex.PASSENGERS,
            "vehicles": ex.VEHICLES, "costs": costs, "stops": ex.STOPS,
            "demands": ex.DEMANDS, "greedy": ex.taxi_assignment(costs, False),
            "optimal": ex.taxi_assignment(costs),
            "baseline": {"routes": baseline, "cost": sum(ex.route_distance(r, ex.distance_matrix()) for r in baseline),
                         "loads": [sum(ex.DEMANDS[i] for i in r) for r in baseline]},
            "delivery": {str(c): ex.delivery(c) for c in (7, 10)},
            "exact": {str(c): ex.exact_delivery(c) for c in (7, 10)}}
    assert data["optimal"]["status"] == "OPTIMAL"
    for capacity in (7, 10):
        result = data["delivery"][str(capacity)]
        assert sorted(i for r in result["routes"] for i in r[1:-1]) == list(range(1, 7))
        assert max(result["loads"]) <= capacity
        assert result["cost"] >= data["exact"][str(capacity)]["cost"]
    (ROOT / "_static/ch10_optimization.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    panels = []
    for offset, title, pairs in [(0, "Greedy", data["greedy"]), (420, "Optimal", data["optimal"])]:
        panels.append(f'<text x="{offset+20}" y="30" font-size="20">{title}: {pairs["cost"]} min</text>')
        def point(p):
            return offset + 50 + p[0] * 65, 345 - p[1] * 55
        for i, j in pairs["pairs"]:
            x, y = point(ex.VEHICLES[j]); a, b = point(ex.PASSENGERS[i])
            panels.append(f'<path d="M{x},{y} H{a} V{b}" stroke="#777" fill="none" stroke-width="2"/>')
        for label, points, color in [("V", ex.VEHICLES, "#1864ab"), ("P", ex.PASSENGERS, "#c43e00")]:
            for i, p in enumerate(points):
                x, y = point(p)
                shape = f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="{color}"/>' if label == "V" else f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>'
                panels.append(shape + f'<text x="{x+9}" y="{y-9}" font-size="16">{label}{i}</text>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 390" role="img"><title>Taxi matching on synthetic km grid: squares vehicles, circles passengers</title><rect width="840" height="390" fill="white"/>' + ''.join(panels) + '</svg>'
    (ROOT / "figures/ch10_assignment.svg").write_text(svg, encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
