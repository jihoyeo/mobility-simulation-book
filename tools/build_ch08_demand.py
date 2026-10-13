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

from smartmob.teaching.demand_gen import (
    hourly_profile_from_od, sample_poisson_times,
)
from smartmob.viz import use_korean_font


def build():
    data = ROOT / "data/hanam"
    od = pd.read_parquet(data / "od_2024.parquet")
    profile = np.asarray(hourly_profile_from_od(od))
    hourly = od.groupby("ST_TIME_CD").CNT.sum().reindex(range(24), fill_value=0)
    payload = {
        "odRows": len(od), "odHourly": hourly.tolist(),
        "sources": {"od_2024.parquet": hashlib.sha256(
            (data / "od_2024.parquet").read_bytes()).hexdigest()},
    }
    template_dir = ROOT / "tools/templates"
    html = (template_dir / "ch08_demand.html").read_text(encoding="utf-8-sig")
    html = html.replace("__DEMAND_DATA__", json.dumps(payload, separators=(",", ":")))
    html = html.replace("__DEMAND_SCRIPT__", (template_dir / "ch08_demand.js").read_text(encoding="utf-8-sig"))
    target = ROOT / "_static/ch08_demand.html"
    target.write_text(html, encoding="utf-8")

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
    figure_path.write_text("\n".join(line.rstrip() for line in figure_path.read_text(encoding="utf-8-sig").splitlines()) + "\n")
    plt.close(fig)
    print(json.dumps({"html_bytes": target.stat().st_size, "od_rows": len(od),
                      "od_total": float(hourly.sum()), "evening_profile": (profile[18:] / profile[18:].sum()).tolist(),
                      "poisson_500_mean": float(np.mean(totals)),
                      "poisson_500_sd": float(np.std(totals, ddof=1))}, ensure_ascii=False))


if __name__ == "__main__":
    build()
