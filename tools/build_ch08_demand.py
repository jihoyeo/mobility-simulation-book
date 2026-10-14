"""저장소 자료로 8장 그림과 독립 실행 HTML을 만듭니다.

저장소 루트에서: .venv/bin/python tools/build_ch08_demand.py
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def build(html_only=False):
    import pyarrow.parquet as pq

    data = ROOT / "data/hanam"
    records = pq.read_table(data / "od_2024.parquet").to_pylist()
    hourly = [0.0] * 24
    pairs = [{} for _ in range(6)]
    for row in records:
        hour, weight = int(row["ST_TIME_CD"]), float(row["CNT"])
        hourly[hour] += weight
        if 18 <= hour < 24 and weight > 0:
            key = (str(row["O_ADMDONG_CD"]), str(row["D_ADMDONG_CD"]))
            pairs[hour - 18][key] = pairs[hour - 18].get(key, 0) + weight
    payload = {
        "odRows": len(records), "odHourly": hourly,
        "odPairs": [[[o, d, w] for (o, d), w in sorted(group.items())] for group in pairs],
        "sources": {"od_2024.parquet": hashlib.sha256(
            (data / "od_2024.parquet").read_bytes()).hexdigest()},
    }
    template_dir = ROOT / "tools/templates"
    html = (template_dir / "ch08_demand.html").read_text(encoding="utf-8-sig")
    html = html.replace("__DEMAND_DATA__", json.dumps(payload, separators=(",", ":")))
    html = html.replace("__DEMAND_SCRIPT__", (template_dir / "ch08_demand.js").read_text(encoding="utf-8-sig"))
    target = ROOT / "_static/ch08_demand.html"
    target.write_text(html, encoding="utf-8")

    if html_only:
        print(json.dumps({"html_bytes": target.stat().st_size,
                          "evening_od_pairs": sum(map(len, pairs))}))
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from smartmob.teaching.demand_gen import sample_poisson_times
    from smartmob.viz import use_korean_font
    profile = np.asarray(hourly) / sum(hourly)

    use_korean_font()
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.hashsalt": "ch08-demand"})
    figures = ROOT / "figures"
    # 한 번의 과정: 발생 시각과 누적 건수를 같은 난수 결과로 그립니다.
    rng = np.random.default_rng(42)
    n = rng.poisson(10)
    arrivals = np.sort(rng.uniform(0, 60, n))
    fig, axes = plt.subplots(2, 1, figsize=(10, 4.5), sharex=True,
                             gridspec_kw={"height_ratios": [1, 2]})
    axes[0].scatter(arrivals, np.zeros(n), color="#137f79", s=35)
    axes[0].set(yticks=[], ylim=(-1, 1), title=f"한 번의 실행: 발생 시각 {n}개 · 시간당 평균 10건 · 시드 42")
    axes[1].step(np.r_[0, arrivals, 60], np.r_[0, np.arange(1, n + 1), n], where="post", color="#137f79")
    axes[1].set(xlim=(0, 60), ylim=(0, n + 1), xlabel="18:00부터 지난 시간 (분)", ylabel="누적 요청 수 (건)")
    axes[1].set_xticks(range(0, 61, 10))
    axes[1].grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(figures / "ch08_poisson_process.svg", metadata={"Date": None})
    plt.close(fig)
    totals = [len(sample_poisson_times(1000, np.random.default_rng(s), profile))
              for s in range(42, 542)]
    fig, ax = plt.subplots(figsize=(10, 3.7))
    ax.hist(totals, bins=20, color="#137f79", alpha=.85, label="포아송 생성 · 500회")
    ax.axvline(1000, color="#b97732", linewidth=2, linestyle="--",
               label="총건수 고정·행 리샘플링: 매회 1,000건")
    ax.set(xlabel="18~24시 총 호출 건수", ylabel="반복 횟수")
    ax.legend(frameon=False)
    fig.tight_layout()
    figure_path = figures / "ch08_count_variation.svg"
    fig.savefig(figure_path, metadata={"Date": None})
    figure_path.write_text("\n".join(line.rstrip() for line in figure_path.read_text(encoding="utf-8-sig").splitlines()) + "\n")
    plt.close(fig)
    print(json.dumps({"html_bytes": target.stat().st_size, "od_rows": len(records),
                      "od_total": sum(hourly), "evening_profile": (profile[18:] / profile[18:].sum()).tolist(),
                      "poisson_500_mean": float(np.mean(totals)),
                      "poisson_500_sd": float(np.std(totals, ddof=1))}, ensure_ascii=False))


if __name__ == "__main__":
    build(html_only="--html-only" in sys.argv)
