"""통행 수요 생성기.

8장에서 다루는 코드입니다. 직접 짜지는 않고, 읽고 인자를 바꿔 가며 실험합니다.

시뮬레이터에 넣을 수요는 "누가 몇 시에 어디서 어디로 가려 하는가"의 목록입니다.
실제 데이터가 있으면 그대로 쓰고, 없으면 만들어야 합니다. 만드는 방법이 세 단계로
점점 그럴듯해집니다.

1. **경계 안에 균등하게** — 산과 강 위에서도 택시를 부릅니다
2. **도로 위에** — 길이 있는 곳에서만 부릅니다
3. **시간대 프로파일을 반영해** — 출퇴근 첨두가 생깁니다

    from smartmob.teaching.demand_gen import generate_demand
    demand = generate_demand(boundary, graph, n=1000, seed=42)
"""

from __future__ import annotations

import bisect
import random
from typing import Sequence

from smartmob.data.demand import REQUIRED_COLUMNS

# 수도권 생활이동 하남시 자료에서 뽑은 시간대별 통행 비중(0시~23시).
# 8장에서 이 값을 직접 계산합니다.
HANAM_HOURLY = (
    0.003, 0.008, 0.006, 0.006, 0.011, 0.024, 0.048, 0.076, 0.079, 0.052,
    0.045, 0.046, 0.052, 0.056, 0.053, 0.060, 0.066, 0.074, 0.074, 0.051,
    0.045, 0.038, 0.022, 0.004,
)


# --------------------------------------------------------------------------- #
# 1단계 — 경계 안 균등 샘플링
# --------------------------------------------------------------------------- #


def uniform_in_boundary(boundary, n: int, rng: random.Random) -> list[tuple[float, float]]:
    """경계 폴리곤 안에 점 n개를 고르게 찍습니다.

    외접 사각형에서 뽑아 폴리곤 안에 드는 것만 남기는 기각 표집(rejection sampling)입니다.
    폴리곤이 길쭉하면 버려지는 점이 많아 느려집니다.
    """
    min_lon, min_lat, max_lon, max_lat = boundary.bounds
    from shapely.geometry import Point

    points: list[tuple[float, float]] = []
    attempts = 0
    while len(points) < n:
        attempts += 1
        if attempts > n * 200:
            raise RuntimeError("경계가 너무 좁아 점을 뽑지 못했습니다")
        lon = rng.uniform(min_lon, max_lon)
        lat = rng.uniform(min_lat, max_lat)
        if boundary.contains(Point(lon, lat)):
            points.append((lat, lon))
    return points


# --------------------------------------------------------------------------- #
# 2단계 — 도로 위 샘플링
# --------------------------------------------------------------------------- #


def _edge_weights(graph) -> tuple[list[tuple[str, str]], list[float]]:
    """엣지 목록과 누적 길이. 긴 도로가 뽑힐 확률이 높아야 합니다."""
    pairs: list[tuple[str, str]] = []
    cumulative: list[float] = []
    total = 0.0
    for u, out in graph.adj.items():
        for v, seconds, _ in out:
            lat1, lon1 = graph.coord[u]
            lat2, lon2 = graph.coord[v]
            length = abs(lat2 - lat1) + abs(lon2 - lon1)   # 상대 가중치면 충분합니다
            if length <= 0:
                continue
            total += length
            pairs.append((u, v))
            cumulative.append(total)
    return pairs, cumulative


def sample_on_edges(graph, n: int, rng: random.Random) -> list[tuple[float, float]]:
    """도로 위에 점 n개를 찍습니다. 긴 도로일수록 많이 뽑힙니다."""
    pairs, cumulative = _edge_weights(graph)
    if not pairs:
        raise ValueError("그래프에 엣지가 없습니다")
    total = cumulative[-1]

    points: list[tuple[float, float]] = []
    for _ in range(n):
        idx = bisect.bisect_left(cumulative, rng.uniform(0, total))
        u, v = pairs[min(idx, len(pairs) - 1)]
        lat1, lon1 = graph.coord[u]
        lat2, lon2 = graph.coord[v]
        t = rng.random()                                    # 엣지 위 임의의 지점
        points.append((lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t))
    return points


# --------------------------------------------------------------------------- #
# 3단계 — 시간대 프로파일
# --------------------------------------------------------------------------- #


def sample_times(
    n: int,
    rng: random.Random,
    hourly: Sequence[float] = HANAM_HOURLY,
    time_range: tuple[int, int] = (0, 1440),
) -> list[int]:
    """시간대 비중에 따라 호출 시각(자정부터의 분)을 뽑습니다.

    시간 안에서는 균등하게 흩뜨립니다. 그래서 8시 첨두가 8:00 에 몰리지 않고
    8:00~8:59 에 퍼집니다.
    """
    start, end = time_range
    weights = []
    for hour, w in enumerate(hourly):
        hour_start, hour_end = hour * 60, hour * 60 + 60
        overlap = max(0, min(end, hour_end) - max(start, hour_start))
        weights.append(w * overlap / 60)

    total = sum(weights)
    if total <= 0:
        raise ValueError(f"시간 범위 {time_range} 에 해당하는 수요 비중이 0입니다")

    cumulative, running = [], 0.0
    for w in weights:
        running += w
        cumulative.append(running)

    times = []
    for _ in range(n):
        hour = bisect.bisect_left(cumulative, rng.uniform(0, total))
        lo = max(start, hour * 60)
        hi = min(end, hour * 60 + 60)
        times.append(rng.randrange(lo, max(hi, lo + 1)))
    return sorted(times)


# --------------------------------------------------------------------------- #
# 합치기
# --------------------------------------------------------------------------- #


def generate_demand(
    boundary=None,
    graph=None,
    n: int = 1000,
    time_range: tuple[int, int] = (1080, 1440),
    seed: int | None = 42,
    hourly: Sequence[float] | None = HANAM_HOURLY,
    min_km: float = 0.5,
):
    """시뮬레이터가 받는 형식의 수요 DataFrame 을 만듭니다.

    ``graph`` 를 주면 도로 위에서, 아니면 ``boundary`` 안에서 균등하게 뽑습니다.
    ``hourly`` 를 ``None`` 으로 두면 시간 범위에 고르게 흩뜨립니다.
    출발지와 목적지가 ``min_km`` 보다 가까우면 다시 뽑습니다.
    """
    import pandas as pd

    from smartmob.teaching.graph import haversine_km

    if graph is None and boundary is None:
        raise ValueError("graph 또는 boundary 중 하나는 있어야 합니다")

    rng = random.Random(seed)
    pick = (lambda k: sample_on_edges(graph, k, rng)) if graph is not None \
        else (lambda k: uniform_in_boundary(boundary, k, rng))

    origins, destinations = [], []
    while len(origins) < n:
        need = n - len(origins)
        candidates_o = pick(need * 2)
        candidates_d = pick(need * 2)
        for o, d in zip(candidates_o, candidates_d):
            if len(origins) >= n:
                break
            if haversine_km(o[0], o[1], d[0], d[1]) >= min_km:
                origins.append(o)
                destinations.append(d)

    times = (
        sample_times(n, rng, hourly, time_range) if hourly
        else sorted(rng.randrange(*time_range) for _ in range(n))
    )

    df = pd.DataFrame({
        "id": range(n),
        "request_time": times,
        "origin_lat": [o[0] for o in origins],
        "origin_lon": [o[1] for o in origins],
        "dest_lat": [d[0] for d in destinations],
        "dest_lon": [d[1] for d in destinations],
        "mode": "taxi",
    })
    return df[["id", *REQUIRED_COLUMNS, "mode"]]


def hourly_profile_from_od(od, count_col: str = "CNT", hour_col: str = "ST_TIME_CD"):
    """O-D 표에서 시간대 비중을 뽑습니다. 합이 1이 되도록 정규화합니다."""
    totals = od.groupby(hour_col)[count_col].sum()
    full = [float(totals.get(h, 0.0)) for h in range(24)]
    s = sum(full)
    return tuple(x / s for x in full) if s else tuple(full)
