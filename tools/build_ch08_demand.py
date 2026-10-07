"""저장소 자료로 8장 그림과 독립 실행 HTML을 만듭니다.

저장소 루트에서: .venv/bin/python tools/build_ch08_demand.py
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import shape

from smartmob.data import load_road_graph
from smartmob.teaching.demand_gen import (
    hourly_profile_from_od, sample_poisson_times,
)
from smartmob.viz import use_korean_font


def build():
    data = ROOT / "data/hanam"
    od = pd.read_parquet(data / "od_2024.parquet")
    requests = pd.read_csv(data / "demand.csv")
    boundary_json = json.loads((data / "boundary.geojson").read_text())
    boundary = shape(boundary_json["features"][0]["geometry"])
    graph = load_road_graph("hanam", modes=("drive",))
    profile = np.asarray(hourly_profile_from_od(od))
    hourly = od.groupby("ST_TIME_CD").CNT.sum().reindex(range(24), fill_value=0)
    source_hours = np.bincount(requests.request_time.to_numpy() // 60, minlength=24)
    nodes = [[round(lon, 6), round(lat, 6)] for lat, lon in graph.coord.values()]
    node_ids = {key: i for i, key in enumerate(graph.coord)}
    edges = sorted({tuple(sorted((node_ids[u], node_ids[v])))
                    for u, outgoing in graph.adj.items() for v, *_ in outgoing})
    payload = {
        "odRows": len(od), "odHourly": hourly.tolist(),
        "referenceHourly": source_hours.tolist(),
        "requests": requests[["id", "request_time", "origin_lat", "origin_lon",
                               "dest_lat", "dest_lon"]].to_numpy().tolist(),
        "boundary": boundary.simplify(0.00004).exterior.coords[:],
        "nodes": nodes, "edges": edges,
        "sources": {name: hashlib.sha256((data / name).read_bytes()).hexdigest()
                    for name in ["od_2024.parquet", "demand.csv", "boundary.geojson",
                                 "road_graph_nodes.parquet", "road_graph_edges.parquet"]},
    }
    template_dir = ROOT / "tools/templates"
    html = (template_dir / "ch08_demand.html").read_text()
    html = html.replace("__DEMAND_DATA__", json.dumps(payload, separators=(",", ":")))
    html = html.replace("__DEMAND_SCRIPT__", (template_dir / "ch08_demand.js").read_text())
    target = ROOT / "_static/ch08_demand.html"
    target.write_text(html)

    use_korean_font()
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.hashsalt": "ch08-demand"})
    figures = ROOT / "figures"
    totals = [len(sample_poisson_times(1000, np.random.default_rng(s), profile))
              for s in range(42, 542)]
    fig, ax = plt.subplots(figsize=(10, 3.7))
    ax.hist(totals, bins=20, color="#137f79", alpha=.85, label="포아송 생성 · 500회")
    ax.axvline(1000, color="#b97732", linewidth=2, linestyle="--",
               label="총건수 고정·행 재표집: 매회 1,000건")
    ax.set(xlabel="18~24시 총 호출 건수", ylabel="반복 횟수")
    ax.legend(frameon=False)
    fig.tight_layout()
    figure_path = figures / "ch08_count_variation.svg"
    fig.savefig(figure_path, metadata={"Date": None})
    figure_path.write_text("\n".join(line.rstrip() for line in figure_path.read_text().splitlines()) + "\n")
    plt.close(fig)
    print(json.dumps({"html_bytes": target.stat().st_size, "od_rows": len(od),
                      "od_total": float(hourly.sum()), "evening_profile": (profile[18:] / profile[18:].sum()).tolist(),
                      "poisson_500_mean": float(np.mean(totals)),
                      "poisson_500_sd": float(np.std(totals, ddof=1))}, ensure_ascii=False))


if __name__ == "__main__":
    build()
