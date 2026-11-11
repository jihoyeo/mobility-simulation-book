"""작은 비대칭 거리 행렬의 모든 방문 순서·분할로 배송 목적함수를 검산합니다."""
from itertools import combinations, permutations
import random

import pytest

pytest.importorskip("ortools")
from smartmob.teaching.fleet import ExactFleet, heuristic_fleet


def brute(distances, demands, trucks, capacity, objective):
    n, best = len(demands)-1, None
    for order in permutations(range(1, n+1)):
        for cuts in combinations(range(1, n), trucks-1):
            bounds = (0, *cuts, n)
            groups = [order[a:b] for a, b in zip(bounds, bounds[1:])]
            if any(sum(demands[i] for i in group) > capacity for group in groups):
                continue
            routes = [(0, *group, 0) for group in groups]
            lengths = [sum(distances[a][b] for a, b in zip(r, r[1:])) for r in routes]
            score = (max(lengths), sum(lengths)) if objective == 'max' else (sum(lengths),)
            best = score if best is None or score < best else best
    return best


@pytest.mark.parametrize('seed', range(3))
def test_exact_fleet_matches_all_orders_and_partitions(seed):
    rng = random.Random(seed)
    matrix = [[0 if i == j else rng.randint(1, 40) for j in range(6)] for i in range(6)]
    demands = [0, 1, 2, 1, 2, 1]
    solver = ExactFleet(matrix, demands)
    for trucks in (2, 3):
        for capacity in (3, 5):
            for objective in ('sum', 'max'):
                expected = brute(matrix, demands, trucks, capacity, objective)
                result = solver.solve(trucks, capacity, objective)
                if expected is None:
                    assert result['status'] == 'INFEASIBLE'
                    continue
                score = (result['max_distance'], result['cost']) if objective == 'max' else (result['cost'],)
                assert score == expected
                assert len(result['routes']) == trucks
                assert all(r[0] == r[-1] == 0 and len(r) > 2 for r in result['routes'])
                assert sorted(i for r in result['routes'] for i in r[1:-1]) == list(range(1, 6))
                assert max(result['loads']) <= capacity


def test_packing_can_be_infeasible_even_with_enough_total_capacity():
    matrix = [[0 if i == j else 1 for j in range(4)] for i in range(4)]
    solver = ExactFleet(matrix, [0, 4, 4, 4])
    for objective in ('sum', 'max'):
        assert solver.solve(2, 6, objective)['status'] == 'INFEASIBLE'
        assert solver.solve(3, 4, objective)['cost'] == 6


@pytest.mark.parametrize('objective', ['sum', 'max'])
def test_heuristic_uses_each_requested_truck(objective):
    matrix = [[0 if i == j else abs(i-j)+1 for j in range(6)] for i in range(6)]
    demands = [0, 1, 2, 1, 2, 1]
    result = heuristic_fleet(matrix, demands, 3, 3, objective)
    assert result['cost'] is not None
    assert len(result['routes']) == 3
    assert all(len(r) > 2 and r[0] == r[-1] == 0 for r in result['routes'])
    assert sorted(i for r in result['routes'] for i in r[1:-1]) == list(range(1, 6))
    assert max(result['loads']) <= 3
