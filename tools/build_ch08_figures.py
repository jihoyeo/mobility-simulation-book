"""8장 데이터 형태·수요 생성 본문의 정적 그림을 재현합니다.

저장소 루트에서 .venv/bin/python tools/build_ch08_figures.py로 실행합니다.
입력은 기존 하남 O-D, 시군구 경계, 자동차 도로망입니다. NAS 연결은 없습니다.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from smartmob.data import data_path, load_road_graph, load_sigungu
from smartmob.teaching.demand_gen import generate_demand, hourly_profile_from_od
from smartmob.viz import use_korean_font


def save(fig, name):
    fig.tight_layout()
    path = ROOT / "figures" / name
    fig.savefig(path, metadata={"Date": None})
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


def main():
    use_korean_font()
    plt.rcParams.update({
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.hashsalt": "ch08-demand-forms",
    })
    od = pd.read_parquet(data_path("hanam/od_2024.parquet"))
    profile = hourly_profile_from_od(od)
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.bar(range(24), np.asarray(profile) * 100, color="#4263eb")
    ax.set(xlabel="출발 시간대 (시)",
           ylabel="파일 전체에서의 비중 (%)", xticks=range(0, 24, 2))
    ax.grid(axis="y", alpha=0.2)
    save(fig, "ch08_hourly_profile.svg")

    boundary = load_sigungu("하남시")
    graph = load_road_graph("hanam", modes=("drive",))
    flat = generate_demand(boundary=boundary, n=1000, seed=42, hourly=None)
    road = generate_demand(graph=graph, n=1000, seed=42, hourly=None)
    profiled = generate_demand(graph=graph, n=1000, seed=42, hourly=profile)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), sharex=True, sharey=True)
    for ax, frame, title, color in zip(
        axes, [flat, road], ["경계 안 균등", "도로 엣지"], ["#d97706", "#4263eb"]
    ):
        bx, by = boundary.exterior.xy
        ax.fill(bx, by, color="#f1f3f5", edgecolor="#868e96", linewidth=0.7)
        ax.scatter(frame.origin_lon, frame.origin_lat, s=5, alpha=0.5, color=color)
        ax.set(title=title, xlabel="경도", aspect=1 / np.cos(np.deg2rad(37.54)))
    axes[0].set_ylabel("위도")
    save(fig, "ch08_spatial_sampling.svg")

    fig, ax = plt.subplots(figsize=(9, 3.5))
    for frame, label, color in [(road, "균등 시간대", "#d97706"),
                                 (profiled, "O-D 시간대 비중", "#4263eb")]:
        counts = frame.request_time.floordiv(60).value_counts().reindex(range(18, 24), fill_value=0)
        ax.plot(counts.index, counts.values, marker="o", label=label, color=color)
    ax.set(xlabel="요청 시간대 (시)", ylabel="요청 수 (건)", xticks=range(18, 24), ylim=(0, None))
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False)
    save(fig, "ch08_generated_hours.svg")
    print(f"그림 3개 생성: O-D {len(od):,}행, 요청 각 1,000건, 시드 42")


if __name__ == "__main__":
    main()
