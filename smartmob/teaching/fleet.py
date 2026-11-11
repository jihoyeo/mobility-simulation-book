"""작은 단일 차고지 배송 예제: 모든 운행 트럭에 주문을 배정합니다."""

from functools import lru_cache
from math import inf

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def route_result(routes, distances, demands, status):
    routes = sorted(routes, key=lambda r: min(r[1:-1]))
    lengths = [sum(distances[a][b] for a, b in zip(r, r[1:])) for r in routes]
    return {"routes": routes, "lengths": lengths, "cost": sum(lengths),
            "max_distance": max(lengths),
            "loads": [sum(demands[i] for i in r) for r in routes], "status": status}


def infeasible():
    return {"routes": [], "lengths": [], "loads": [], "cost": None,
            "max_distance": None, "status": "INFEASIBLE"}


class ExactFleet:
    """부분집합별 최단 순회와 분할을 동적계획법으로 검산합니다(최대 12곳)."""

    def __init__(self, distances, demands):
        self.distances, self.demands = distances, demands
        self.n = len(demands) - 1
        if not 1 <= self.n <= 12 or len(distances) != len(demands):
            raise ValueError("배송지는 1~12곳이며 거리 행렬과 수량의 크기가 같아야 합니다.")
        if any(len(row) != len(demands) or any(v < 0 for v in row) for row in distances):
            raise ValueError("거리 행렬은 음수가 없는 정사각 행렬이어야 합니다.")
        self.full = (1 << self.n) - 1
        self.loads = [0] * (self.full + 1)
        self.costs = [0] * (self.full + 1)
        self.ends = [None] * (self.full + 1)

        @lru_cache(None)
        def path(mask, end):
            previous = mask ^ (1 << end)
            if not previous:
                return distances[0][end + 1], None
            return min((path(previous, j)[0] + distances[j + 1][end + 1], j)
                       for j in range(self.n) if previous & (1 << j))

        self.path = path
        for mask in range(1, self.full + 1):
            bit = mask & -mask
            self.loads[mask] = self.loads[mask ^ bit] + demands[bit.bit_length()]
            cost, end = min((path(mask, j)[0] + distances[j + 1][0], j)
                            for j in range(self.n) if mask & (1 << j))
            self.costs[mask], self.ends[mask] = cost, end

    def solve(self, trucks, capacity, objective):
        if objective not in {"sum", "max"}:
            raise ValueError(objective)
        if not 1 <= trucks <= self.n or max(self.demands) > capacity or sum(self.demands) > trucks * capacity:
            return infeasible()

        def partition(kind, ceiling=inf):
            choices = {}

            @lru_cache(None)
            def visit(mask, count):
                if mask == 0:
                    return 0 if count == 0 else inf
                if count < 1 or mask.bit_count() < count or self.loads[mask] > count * capacity:
                    return inf
                if count == 1:
                    if self.loads[mask] <= capacity and self.costs[mask] <= ceiling:
                        choices[mask, count] = mask
                        return self.costs[mask]
                    return inf
                first, submask, best = mask & -mask, mask, inf
                while submask:
                    # 최소 번호가 포함된 경로부터 골라 같은 분할의 중복을 없앱니다.
                    if submask & first and self.loads[submask] <= capacity and self.costs[submask] <= ceiling:
                        rest = visit(mask ^ submask, count - 1)
                        value = max(self.costs[submask], rest) if kind == "max" else self.costs[submask] + rest
                        if value < best:
                            best, choices[mask, count] = value, submask
                    submask = (submask - 1) & mask
                return best

            value = visit(self.full, trucks)
            return value, choices

        # 최장 거리를 고정한 뒤 총거리로 동점을 해소합니다.
        bound = partition("max")[0] if objective == "max" else inf
        value, choices = partition("sum", bound)
        if value == inf:
            return infeasible()
        mask, routes = self.full, []
        for count in range(trucks, 0, -1):
            group = choices[mask, count]
            end, remaining, order = self.ends[group], group, []
            while end is not None:
                order.append(end + 1)
                parent = self.path(remaining, end)[1]
                remaining ^= 1 << end
                end = parent
            routes.append([0, *reversed(order), 0])
            mask ^= group
        return route_result(routes, self.distances, self.demands, "OPTIMAL_DP")


def heuristic_fleet(distances, demands, trucks, capacity, objective):
    if sum(demands) > trucks * capacity or max(demands) > capacity or trucks > len(demands) - 1:
        return infeasible()
    manager = pywrapcp.RoutingIndexManager(len(demands), trucks, 0)
    routing = pywrapcp.RoutingModel(manager)
    transit = routing.RegisterTransitCallback(
        lambda a, b: distances[manager.IndexToNode(a)][manager.IndexToNode(b)])
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    demand = routing.RegisterUnaryTransitCallback(lambda a: demands[manager.IndexToNode(a)])
    routing.AddDimensionWithVehicleCapacity(demand, 0, [capacity] * trucks, True, "Capacity")
    for k in range(trucks):
        routing.solver().Add(routing.NextVar(routing.Start(k)) != routing.End(k))
    if objective == "max":
        # 각 해의 구간 수는 배송지 수+차량 수이므로 총거리 상계로 가중치를 정합니다.
        upper = (len(demands) - 1 + trucks) * max(max(row) for row in distances)
        routing.AddDimension(transit, 0, upper, True, "Distance")
        routing.GetDimensionOrDie("Distance").SetGlobalSpanCostCoefficient(upper + 1)
    elif objective != "sum":
        raise ValueError(objective)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(500)
    # 기본 삽입 해법은 빈 차량을 남길 수 있으므로 모든 차량을 쓰는 실행 가능 해에서 시작합니다.
    bins, loads = [[] for _ in range(trucks)], [0] * trucks
    order = sorted(range(1, len(demands)), key=lambda i: (-demands[i], i))

    def pack(index):
        if index == len(order):
            return all(bins)
        if len(order)-index < sum(not group for group in bins):
            return False
        customer, tried = order[index], set()
        for k in sorted(range(trucks), key=lambda k: (loads[k], k)):
            if loads[k] in tried or loads[k] + demands[customer] > capacity:
                continue
            tried.add(loads[k])
            bins[k].append(customer)
            loads[k] += demands[customer]
            if pack(index + 1):
                return True
            loads[k] -= demands[customer]
            bins[k].pop()
        return False

    if not pack(0):
        return infeasible()
    seed = []
    for group in bins:
        remaining, route, previous = set(group), [], 0
        while remaining:
            next_stop = min(remaining, key=lambda i: (distances[previous][i], i))
            route.append(next_stop)
            remaining.remove(next_stop)
            previous = next_stop
        seed.append(route)
    initial = routing.ReadAssignmentFromRoutes(seed, True)
    solution = routing.SolveFromAssignmentWithParameters(initial, params) if initial else None
    if solution is None:
        result = infeasible()
        result["status"] = "NO_SOLUTION_FOUND"
        return result
    routes = []
    for k in range(trucks):
        index, route = routing.Start(k), []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        routes.append(route + [0])
    return route_result(routes, distances, demands, "FEASIBLE_HEURISTIC")
