"""프로젝트 B 3단계 — 파라미터 스윕과 파레토 (3주차)

    python 03_sweep.py

차량 대수를 바꿔 가며 훑고, 12.4절의 파레토 프론트를 그립니다.

난수는 어디에 있는가
--------------------
11장의 시뮬레이션 루프는 **결정론적**입니다. 같은 수요와 같은 차량을 주면
언제나 같은 답이 나옵니다. 난수가 들어가는 곳은 **수요를 만들 때**입니다.

그래서 seed 를 바꾼다는 것은 "같은 가정 아래 다른 하루"를 만드는 것입니다.
seed 마다 수요를 새로 만들어야 반복 실험이 됩니다. 차량 배치만 바꾸고
같은 수요를 쓰면 표준편차가 0으로 나옵니다.
"""

from __future__ import annotations

import importlib.util
import itertools
import sys
from pathlib import Path

import pandas as pd

from smartmob.teaching.metrics import kpi_table
from smartmob.teaching.simloop import simulate

HERE = Path(__file__).resolve().parent

FLEET_SIZES = [2, 4, 6, 10, 16]
SEEDS = [0, 1, 2]
TIME_START, TIME_END = 7 * 60, 20 * 60      # 07:00 ~ 20:00
DEPOT = (37.4505, 127.1285)                 # 차량 대기 위치


def _demand_module():
    """01_class_demand.py 를 불러옵니다. 파일명이 숫자로 시작해 그냥 import 가 안 됩니다."""
    spec = importlib.util.spec_from_file_location("class_demand", HERE / "01_class_demand.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["class_demand"] = module
    spec.loader.exec_module(module)
    return module


def make_demand(seed: int) -> pd.DataFrame:
    """seed 마다 다른 하루를 만듭니다. 가정은 같고 실현값만 다릅니다."""
    cd = _demand_module()
    return cd.build_demand(cd.load_stops(), cd.load_schedule(), seed=seed)


def make_vehicles(n: int) -> pd.DataFrame:
    """차량 표. 지금은 전부 캠퍼스에서 출발합니다. 차고지를 나누는 것도 실험해 보세요."""
    return pd.DataFrame([{
        "id": i, "work_start": TIME_START, "work_end": TIME_END,
        "lat": DEPOT[0], "lon": DEPOT[1],
    } for i in range(n)])


def run_sweep() -> pd.DataFrame:
    rows = []
    for seed in SEEDS:
        demand = make_demand(seed)
        for fleet in FLEET_SIZES:
            result = simulate(demand, make_vehicles(fleet), TIME_START, TIME_END)
            kpi = kpi_table(result)
            rows.append({
                "fleet_size": fleet,
                "seed": seed,
                "service_rate": kpi.get("service_rate"),
                "wait_p50": kpi.get("wait_p50"),
                "wait_p90": kpi.get("wait_p90"),
                "utilization": kpi.get("utilization"),
                "empty_share": kpi.get("empty_share"),
                "vehicle_hours": fleet * (TIME_END - TIME_START) / 60,
            })
            print(f"  seed {seed}  차량 {fleet:2d}대: "
                  f"서비스율 {kpi.get('service_rate', 0):.3f}  "
                  f"대기 중앙값 {kpi.get('wait_p50', 0):.1f}분")
    return pd.DataFrame(rows)


def summarize(sweep: pd.DataFrame) -> pd.DataFrame:
    """seed 를 묶어 평균과 표준편차를 냅니다.

    표준편차가 시나리오 간 차이보다 크면 그 차이는 난수일 뿐입니다.
    """
    return sweep.groupby("fleet_size").agg(
        service_rate=("service_rate", "mean"),
        service_sd=("service_rate", "std"),
        wait_p50=("wait_p50", "mean"),
        wait_p50_sd=("wait_p50", "std"),
        wait_p90=("wait_p90", "mean"),
        utilization=("utilization", "mean"),
        vehicle_hours=("vehicle_hours", "first"),
    ).round(3)


def plot_pareto(summary: pd.DataFrame, path: str = "pareto.png") -> None:
    import matplotlib.pyplot as plt

    from smartmob.viz import use_korean_font

    use_korean_font()
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.plot(summary["service_rate"], summary["vehicle_hours"], "-o", color="tab:blue")
    for fleet, row in summary.iterrows():
        ax.annotate(f"{fleet}대", (row["service_rate"], row["vehicle_hours"]),
                    textcoords="offset points", xytext=(8, 4), fontsize=9)
    ax.set_xlabel("서비스율 (학생이 좋아하는 것)")
    ax.set_ylabel("차량-시간 (운영비 대리 지표)")
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"\n파레토 그림 저장: {path}")


def main() -> int:
    print(f"{len(FLEET_SIZES) * len(SEEDS)}회 실행\n")
    sweep = run_sweep()
    sweep.to_csv("sweep_results.csv", index=False, encoding="utf-8")
    print("\n전체 결과 저장: sweep_results.csv")

    summary = summarize(sweep)
    print("\nseed 평균")
    print(summary.to_string())

    print("\n난수 변동")
    for fleet, row in summary.iterrows():
        print(f"  차량 {fleet:2d}대  대기 중앙값 {row['wait_p50']:.2f} ± {row['wait_p50_sd']:.2f}분  "
              f"서비스율 {row['service_rate']:.3f} ± {row['service_sd']:.3f}")
    print("  시나리오 간 차이가 이 표준편차보다 커야 의미가 있습니다")

    plot_pareto(summary)

    best = summary["service_rate"].max()
    print(f"\n지금 최고 서비스율이 {best:.0%} 입니다.")
    if best < 0.9:
        print("""
낮은 이유
  11장의 루프는 차량 한 대가 승객 한 명만 태웁니다. 1교시 직전 30분에
  수백 명이 몰리는 셔틀 수요에서는 이 방식으로 감당이 안 됩니다.

  이 프로젝트의 핵심이 여기 있습니다. 셔틀은 **여러 명을 함께 태웁니다.**
  다음 중 하나를 하세요.

  1. simulate 를 고쳐 정원을 넣습니다. 같은 방향 승객을 묶어 한 번에 배차합니다
  2. 고정노선(02_fixed_route.py)과 비교합니다. 고정노선은 정원이 자연스럽게 들어갑니다
  3. 정원 1로 두고 그 한계를 보고서에 명시합니다 (감점되지 않습니다)

  1번을 하면 서비스율이 어디까지 오르는지, 대신 대기시간이 얼마나 늘어나는지가
  좋은 결과가 됩니다.""")

    print("\n다음에 할 일")
    print("  - 첨두(1교시 직전)와 비첨두를 나눠 같은 스윕을 돌리세요")
    print("  - 고정노선과 같은 그림 위에 올려 비교하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
