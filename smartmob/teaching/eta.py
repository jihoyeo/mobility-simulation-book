"""ETA — 통행시간 예측.

9장에서 다루는 코드입니다.

배차 비용행렬의 각 칸에는 차량 위치에서 요청 위치까지의 소요시간이 들어갑니다.
대기 요청과 빈 차량이 많아지면 계산해야 할 최단경로 수도 늘어납니다.

이 모듈은 좌표와 시각으로 최단경로 소요시간을 근사할 학습 자료와 특징을 만듭니다.
학습한 모델은 경로를 반환하지 않습니다.

    from smartmob.teaching.eta import make_features, build_dataset
"""

from __future__ import annotations

import math
import random

from smartmob.teaching.graph import haversine_km

# 학습에 쓰는 특징. 전부 라우팅 없이 좌표와 시각만으로 구합니다.
FEATURES = [
    "straight_km",     # 직선거리
    "hour",            # 출발 시각(시)
    "sin_bearing",     # 방위각. 남북 방향과 동서 방향의 속도가 다릅니다
    "cos_bearing",
    "origin_lat", "origin_lon",
    "dest_lat", "dest_lon",
]
TARGET = "duration_min"


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """출발지에서 목적지를 바라보는 방위각(라디안)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.atan2(y, x)


def make_features(origin: tuple[float, float], dest: tuple[float, float], hour: int) -> dict:
    """좌표 한 쌍과 시각에서 특징을 만듭니다. 라우팅을 부르지 않습니다."""
    theta = bearing(origin[0], origin[1], dest[0], dest[1])
    return {
        "straight_km": haversine_km(origin[0], origin[1], dest[0], dest[1]),
        "hour": hour,
        "sin_bearing": math.sin(theta),
        "cos_bearing": math.cos(theta),
        "origin_lat": origin[0], "origin_lon": origin[1],
        "dest_lat": dest[0], "dest_lon": dest[1],
    }


# 4장의 시간대 슬롯을 시(hour) 단위로 편 것입니다.
HOUR_TO_COLUMN = {
    **{h: "weekday_night_p50" for h in list(range(0, 6)) + [22, 23]},
    6: "weekday_offpeak_p50",
    7: "weekday_am_peak_p50", 8: "weekday_am_peak_p50",
    9: "weekday_am_shoulder_p50",
    10: "weekday_midday_p50", 11: "weekday_midday_p50",
    **{h: "weekday_afternoon_p50" for h in range(12, 17)},
    17: "weekday_pm_peak_p50", 18: "weekday_pm_peak_p50",
    **{h: "weekday_pm_shoulder_p50" for h in range(19, 22)},
}


def build_dataset(city: str = "hanam", n: int = 20_000, seed: int = 0, hours=None):
    """라우팅을 정답으로 삼는 학습 데이터를 만듭니다.

    시간대마다 그래프를 하나씩 만들고, 무작위 O-D 쌍의 최단경로 소요시간을 구합니다.
    실행 시간은 도로망 크기와 컴퓨터에 따라 달라집니다. 반복해 쓸 자료는 parquet
    파일로 저장할 수 있습니다.
    """
    import pandas as pd

    from smartmob.data import load_road_graph
    from smartmob.teaching.dijkstra import NoPath, dijkstra

    hours = hours or [0, 6, 8, 11, 14, 17, 19, 22]
    graphs = {h: load_road_graph(city, modes=("drive",), speed_column=HOUR_TO_COLUMN[h])
              for h in hours}
    base = graphs[hours[0]]
    nodes = [n_ for n_ in base.adj if base.adj[n_]]

    rng = random.Random(seed)
    rows = []
    while len(rows) < n:
        u, v = rng.choice(nodes), rng.choice(nodes)
        if u == v:
            continue
        hour = rng.choice(hours)
        try:
            path = dijkstra(graphs[hour], u, v)
        except NoPath:
            continue
        o = base.coord[u]
        d = base.coord[v]
        row = make_features(o, d, hour)
        row[TARGET] = path.duration_s / 60
        row["network_km"] = path.distance_km(graphs[hour])
        rows.append(row)

    return pd.DataFrame(rows)
