"""시뮬레이션 지표 그래프.

`record.csv` 와 `result.json` 을 그대로 받아 그립니다. 한글 폰트는 자동으로 잡습니다.

    from smartmob.viz import plot_record
    plot_record(sim.record)
"""

from __future__ import annotations

from smartmob.viz.fonts import use_korean_font


def _hhmm(minutes: float) -> str:
    m = int(minutes) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def plot_record(record, figsize=(11, 6)):
    """대기 승객·실패·차량 상태의 시간 변화 4분할.

    ``record`` 는 컬럼 time, waiting_passenger_cnt, fail_passenger_cnt,
    empty_vehicle_cnt, driving_vehicle_cnt 를 가진 DataFrame 입니다.
    """
    import matplotlib.pyplot as plt

    use_korean_font()
    if record is None or len(record) == 0:
        raise ValueError("record 가 비어 있습니다.")

    panels = [
        ("waiting_passenger_cnt", "대기 승객 수", "tab:red"),
        ("fail_passenger_cnt", "누적 배차 실패", "tab:gray"),
        ("driving_vehicle_cnt", "운행 중 차량", "tab:blue"),
        ("empty_vehicle_cnt", "대기 중 차량", "tab:green"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=figsize, sharex=True)
    for ax, (col, title, color) in zip(axes.ravel(), panels):
        if col not in record.columns:
            ax.set_visible(False)
            continue
        ax.plot(record["time"], record[col], color=color, linewidth=1.4)
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.25, linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)

    ticks = range(int(record["time"].min()), int(record["time"].max()) + 1, 60)
    for ax in axes[-1]:
        ax.set_xticks(list(ticks))
        ax.set_xticklabels([_hhmm(t) for t in ticks], rotation=0)
    fig.tight_layout()
    return fig


def plot_waiting_time(result, figsize=(9, 4)):
    """분 단위 평균 대기시간."""
    import matplotlib.pyplot as plt

    use_korean_font()
    if result is None or len(result) == 0 or "average_waiting_time" not in result:
        raise ValueError("result 에 average_waiting_time 이 없습니다.")

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(result["time"], result["average_waiting_time"], color="tab:red", linewidth=1.4)
    ax.set_xlabel("시각")
    ax.set_ylabel("평균 대기시간 (분)")
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ticks = range(int(result["time"].min()), int(result["time"].max()) + 1, 60)
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([_hhmm(t) for t in ticks])
    fig.tight_layout()
    return fig


def plot_comparison(summaries, metric="avg_waiting_time_min", labels=None, figsize=(7, 4)):
    """여러 시나리오의 지표 하나를 막대로 비교합니다.

    ``summaries`` 는 :meth:`SimulationResult.summary` 결과의 목록입니다.
    """
    import matplotlib.pyplot as plt

    use_korean_font()
    values = [s.get(metric) for s in summaries]
    names = labels or [s.get("simulation_id", f"#{i}") for i, s in enumerate(summaries)]

    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(names, values, color="tab:blue", width=0.55)
    ax.set_ylabel(metric)
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    return fig
