"""배차와 물류 — 10장 검증 기준."""

from __future__ import annotations

import random

import numpy as np
import pytest

from smartmob.teaching.dispatch import (
    cost_matrix,
    greedy_match,
    nearest_neighbour,
    optimal_match,
    route_length_km,
    two_opt,
)


def _points(n: int, rng: random.Random):
    return [(37.50 + rng.random() * 0.10, 127.13 + rng.random() * 0.14) for _ in range(n)]


# --------------------------------------------------------------------------- #
# 비용행렬
# --------------------------------------------------------------------------- #


def test_cost_matrix_shape_and_symmetry():
    rng = random.Random(0)
    P, V = _points(4, rng), _points(6, rng)
    c = cost_matrix(P, V)
    assert c.shape == (4, 6)
    assert (c >= 0).all()


def test_cost_matrix_zero_for_same_point():
    p = [(37.54, 127.20)]
    assert cost_matrix(p, p)[0, 0] == pytest.approx(0.0)


def test_cost_matrix_scales_with_speed():
    rng = random.Random(1)
    P, V = _points(3, rng), _points(3, rng)
    slow = cost_matrix(P, V, speed_kmh=10)
    fast = cost_matrix(P, V, speed_kmh=40)
    assert np.allclose(slow, fast * 4)


# --------------------------------------------------------------------------- #
# 배차 — 가장 중요한 불변식
# --------------------------------------------------------------------------- #


def test_optimal_is_never_worse_than_greedy():
    """최적해가 탐욕보다 나쁘면 구현이 틀린 것입니다."""
    rng = random.Random(0)
    for _ in range(200):
        c = cost_matrix(_points(8, rng), _points(10, rng))
        assert optimal_match(c).total_cost <= greedy_match(c).total_cost + 1e-9


def test_optimal_beats_greedy_on_average():
    rng = random.Random(0)
    gaps = []
    for _ in range(100):
        c = cost_matrix(_points(8, rng), _points(10, rng))
        g, o = greedy_match(c).total_cost, optimal_match(c).total_cost
        gaps.append((g - o) / o)
    assert np.mean(gaps) > 0.05      # 평균 5% 이상은 개선되어야 합니다


def test_optimal_matches_brute_force_on_small_case():
    """3×3 은 손으로 다 세어 볼 수 있습니다."""
    from itertools import permutations

    rng = random.Random(5)
    c = cost_matrix(_points(3, rng), _points(3, rng))
    brute = min(sum(c[i, p[i]] for i in range(3)) for p in permutations(range(3)))
    assert optimal_match(c).total_cost == pytest.approx(brute)


def test_no_vehicle_assigned_twice():
    rng = random.Random(2)
    c = cost_matrix(_points(10, rng), _points(10, rng))
    for result in (greedy_match(c), optimal_match(c)):
        used = [m.vehicle for m in result.matches]
        assert len(used) == len(set(used))
        served = [m.passenger for m in result.matches]
        assert len(served) == len(set(served))


def test_more_passengers_than_vehicles_leaves_some_unmatched():
    rng = random.Random(3)
    c = cost_matrix(_points(10, rng), _points(4, rng))
    result = optimal_match(c)
    assert len(result.matches) == 4
    assert len(result.unmatched_passengers) == 6


def test_more_vehicles_than_passengers_leaves_some_idle():
    rng = random.Random(4)
    c = cost_matrix(_points(3, rng), _points(9, rng))
    result = optimal_match(c)
    assert len(result.matches) == 3
    assert len(result.unmatched_vehicles) == 6


def test_greedy_respects_order():
    """첫 번째로 처리하는 승객은 항상 최선의 차를 받습니다."""
    rng = random.Random(6)
    c = cost_matrix(_points(5, rng), _points(5, rng))
    result = greedy_match(c, order=[3, 0, 1, 2, 4])
    first = next(m for m in result.matches if m.passenger == 3)
    assert first.cost == pytest.approx(c[3].min())


def test_summary_fields():
    rng = random.Random(7)
    c = cost_matrix(_points(5, rng), _points(6, rng))
    s = optimal_match(c).summary()
    assert s["배차"] == 5
    assert s["미배차 승객"] == 0
    assert s["남은 차량"] == 1
    assert s["평균 대기(분)"] == pytest.approx(s["총 대기(분)"] / 5, abs=0.01)


# --------------------------------------------------------------------------- #
# 물류 — 순회 경로
# --------------------------------------------------------------------------- #


def test_two_opt_never_lengthens():
    rng = random.Random(0)
    for _ in range(20):
        stops = _points(10, rng)
        nn = nearest_neighbour(stops)
        assert route_length_km(stops, two_opt(stops, nn)) <= route_length_km(stops, nn) + 1e-9


def test_nearest_neighbour_visits_everything_once():
    rng = random.Random(1)
    stops = _points(12, rng)
    order = nearest_neighbour(stops)
    assert sorted(order) == list(range(12))


def test_two_opt_preserves_all_stops():
    rng = random.Random(2)
    stops = _points(12, rng)
    order = two_opt(stops, nearest_neighbour(stops))
    assert sorted(order) == list(range(12))
    assert order[0] == 0          # 출발지는 그대로여야 합니다


def test_route_length_closed_vs_open():
    stops = [(37.50, 127.15), (37.52, 127.15), (37.52, 127.18)]
    closed = route_length_km(stops, [0, 1, 2], closed=True)
    open_ = route_length_km(stops, [0, 1, 2], closed=False)
    assert closed > open_


def test_two_opt_beats_naive_order():
    """무작정 순서보다는 나아야 합니다."""
    rng = random.Random(11)
    wins = 0
    for _ in range(20):
        stops = _points(10, rng)
        naive = route_length_km(stops, list(range(10)))
        best = route_length_km(stops, two_opt(stops, nearest_neighbour(stops)))
        wins += best < naive
    assert wins >= 18
