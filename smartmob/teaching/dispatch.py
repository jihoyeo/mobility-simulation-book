"""배차 — 누구에게 어느 차를 보낼 것인가.

10장에서 다루는 코드입니다.

승객 여러 명과 빈 차 여러 대가 동시에 있을 때, 짝을 어떻게 지을지 정해야 합니다.
방법이 두 가지입니다.

- **탐욕(greedy)** — 먼저 부른 사람부터 가장 가까운 차를 줍니다. 빠르고 단순합니다
- **할당 문제(assignment)** — 전체 대기시간의 합이 가장 작아지도록 한꺼번에 정합니다

같은 수학이 물류 배송에도 쓰입니다. 배송지 여러 곳을 도는 순서를 정하는 문제는
외판원 문제(TSP)이고, 차량이 여러 대면 차량경로 문제(VRP)가 됩니다.

    from smartmob.teaching.dispatch import cost_matrix, greedy_match, optimal_match
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from smartmob.teaching.graph import haversine_km

Point = tuple[float, float]


@dataclass(frozen=True)
class Match:
    """배차 결과 한 건."""

    passenger: int          # 승객 번호(입력 목록의 인덱스)
    vehicle: int            # 차량 번호
    cost: float             # 이 짝의 비용(분)


@dataclass
class MatchResult:
    matches: list[Match]
    unmatched_passengers: list[int]
    unmatched_vehicles: list[int]

    @property
    def total_cost(self) -> float:
        return sum(m.cost for m in self.matches)

    @property
    def max_cost(self) -> float:
        return max((m.cost for m in self.matches), default=0.0)

    def summary(self) -> dict:
        n = len(self.matches)
        return {
            "배차": n,
            "총 대기(분)": round(self.total_cost, 1),
            "평균 대기(분)": round(self.total_cost / n, 2) if n else None,
            "최대 대기(분)": round(self.max_cost, 2),
            "미배차 승객": len(self.unmatched_passengers),
            "남은 차량": len(self.unmatched_vehicles),
        }


# --------------------------------------------------------------------------- #
# 비용행렬
# --------------------------------------------------------------------------- #


def cost_matrix(
    passengers: Sequence[Point],
    vehicles: Sequence[Point],
    speed_kmh: float = 25.0,
):
    """직선거리를 평균 속도로 나눈 도착 예상시간(분) 행렬.

    행이 승객, 열이 차량입니다. 가장 싼 방법이고, 강 건너 차를 가깝다고 잘못 고릅니다.
    """
    import numpy as np

    out = np.empty((len(passengers), len(vehicles)), dtype=float)
    for i, (plat, plon) in enumerate(passengers):
        for j, (vlat, vlon) in enumerate(vehicles):
            out[i, j] = haversine_km(vlat, vlon, plat, plon) / speed_kmh * 60
    return out


def cost_matrix_from_model(
    passengers: Sequence[Point],
    vehicles: Sequence[Point],
    predict: Callable,
    hour: int = 18,
):
    """9장의 ETA 모델로 만든 비용행렬.

    ``predict`` 는 특징 DataFrame 을 받아 분 단위 예측을 돌려주는 함수입니다.
    한 쌍씩 부르지 않고 전부 모아 한 번에 부릅니다. 그래야 빠릅니다.
    """
    import numpy as np
    import pandas as pd

    from smartmob.teaching.eta import FEATURES, make_features

    rows = [
        make_features((vlat, vlon), (plat, plon), hour)
        for plat, plon in passengers
        for vlat, vlon in vehicles
    ]
    predicted = predict(pd.DataFrame(rows)[FEATURES])
    return np.asarray(predicted).reshape(len(passengers), len(vehicles))


def cost_matrix_from_router(
    passengers: Sequence[Point],
    vehicles: Sequence[Point],
    graph,
):
    """3장의 최단경로로 만든 비용행렬. 정확하지만 느립니다."""
    import numpy as np

    from smartmob.teaching.dijkstra import NoPath, shortest_path

    out = np.full((len(passengers), len(vehicles)), np.inf)
    for i, p in enumerate(passengers):
        for j, v in enumerate(vehicles):
            try:
                out[i, j] = shortest_path(graph, v, p, algorithm="dijkstra").duration_min
            except (NoPath, ValueError):
                pass
    return out


# --------------------------------------------------------------------------- #
# 배차 방법
# --------------------------------------------------------------------------- #


def greedy_match(costs, order: Sequence[int] | None = None) -> MatchResult:
    """먼저 부른 사람부터 남은 차 중 가장 가까운 것을 줍니다.

    ``order`` 로 처리 순서를 바꿀 수 있습니다. 기본은 입력 순서(호출 순)입니다.
    """
    import numpy as np

    n_pax, n_veh = costs.shape
    order = list(order) if order is not None else list(range(n_pax))

    taken: set[int] = set()
    matches: list[Match] = []
    unmatched: list[int] = []

    for i in order:
        best, best_cost = None, np.inf
        for j in range(n_veh):
            if j in taken:
                continue
            if costs[i, j] < best_cost:
                best, best_cost = j, costs[i, j]
        if best is None or not np.isfinite(best_cost):
            unmatched.append(i)
        else:
            taken.add(best)
            matches.append(Match(i, best, float(best_cost)))

    return MatchResult(matches, unmatched, [j for j in range(n_veh) if j not in taken])


def optimal_match(costs) -> MatchResult:
    """전체 비용의 합이 가장 작아지도록 한꺼번에 정합니다.

    이것을 할당 문제(assignment problem)라고 하고, 헝가리안 알고리즘으로 풉니다.
    `scipy` 가 구현을 제공하므로 직접 짜지 않습니다.
    """
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    n_pax, n_veh = costs.shape
    # 무한대가 있으면 solver 가 실패하므로 아주 큰 유한값으로 바꿉니다.
    finite = np.where(np.isfinite(costs), costs, np.nanmax(costs[np.isfinite(costs)], initial=1e3) * 100)
    rows, cols = linear_sum_assignment(finite)

    matches, unmatched = [], []
    used_veh = set()
    for i, j in zip(rows, cols):
        if np.isfinite(costs[i, j]):
            matches.append(Match(int(i), int(j), float(costs[i, j])))
            used_veh.add(int(j))
        else:
            unmatched.append(int(i))
    matched_pax = {m.passenger for m in matches}
    unmatched += [i for i in range(n_pax) if i not in matched_pax and i not in unmatched]

    return MatchResult(matches, sorted(unmatched), [j for j in range(n_veh) if j not in used_veh])


# --------------------------------------------------------------------------- #
# 물류 — 한 대가 여러 곳을 도는 문제
# --------------------------------------------------------------------------- #


def route_length_km(points: Sequence[Point], order: Sequence[int], closed: bool = True) -> float:
    """방문 순서대로 이동한 거리(km). ``closed`` 면 출발지로 돌아옵니다."""
    seq = list(order) + ([order[0]] if closed and order else [])
    return sum(
        haversine_km(points[a][0], points[a][1], points[b][0], points[b][1])
        for a, b in zip(seq, seq[1:])
    )


def nearest_neighbour(points: Sequence[Point], start: int = 0) -> list[int]:
    """가장 가까운 곳부터 차례로 방문합니다. 빠르지만 마지막이 멀어집니다."""
    remaining = set(range(len(points))) - {start}
    order = [start]
    while remaining:
        last = order[-1]
        nxt = min(
            remaining,
            key=lambda k: haversine_km(points[last][0], points[last][1], points[k][0], points[k][1]),
        )
        order.append(nxt)
        remaining.discard(nxt)
    return order


def two_opt(points: Sequence[Point], order: Sequence[int], max_passes: int = 20) -> list[int]:
    """경로에서 교차하는 두 구간을 뒤집어 짧게 만듭니다.

    더 이상 줄지 않을 때까지 반복합니다. 최적해를 보장하지는 않지만
    가장 가까운 곳부터 도는 방법보다 눈에 띄게 낫습니다.
    """
    best = list(order)
    best_len = route_length_km(points, best)

    for _ in range(max_passes):
        improved = False
        for i in range(1, len(best) - 1):
            for k in range(i + 1, len(best)):
                candidate = best[:i] + best[i:k + 1][::-1] + best[k + 1:]
                length = route_length_km(points, candidate)
                if length < best_len - 1e-9:
                    best, best_len, improved = candidate, length, True
        if not improved:
            break
    return best
