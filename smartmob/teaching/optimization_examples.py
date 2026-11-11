"""10장 가상 격자 예제. 좌표는 km, 택시 시간은 분, 배송 거리는 m입니다."""
from itertools import permutations
from ortools.sat.python import cp_model
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

PASSENGERS = [(2, 1), (1, 0), (0, 3)]
VEHICLES = [(1, 1), (4, 1), (0, 4)]
STOPS = [(0, 0), (1, 1), (2, 1), (3, 2), (1, 4), (2, 5), (4, 4)]
DEMANDS = [0, 2, 2, 3, 2, 3, 2]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def taxi_costs():
    return [[3 * manhattan(p, v) for v in VEHICLES] for p in PASSENGERS]


def taxi_assignment(costs, optimal=True):
    n, m = len(costs), len(costs[0])
    if n > m:
        raise ValueError("이 예제는 승객 수 이상의 차량이 필요합니다.")
    if not optimal:
        remaining, pairs = set(range(m)), []
        for i in range(n):
            j = min(remaining, key=lambda j: (costs[i][j], j))
            pairs.append([i, j])
            remaining.remove(j)
        return {"pairs": pairs, "cost": sum(costs[i][j] for i, j in pairs), "status": "GREEDY"}
    model = cp_model.CpModel()
    x = {(i, j): model.new_bool_var(f"x_{i}_{j}") for i in range(n) for j in range(m)}
    for i in range(n):
        model.add_exactly_one(x[i, j] for j in range(m))
    for j in range(m):
        model.add_at_most_one(x[i, j] for i in range(n))
    model.minimize(sum(costs[i][j] * x[i, j] for i, j in x))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(solver.status_name(status))
    pairs = [[i, j] for i, j in x if solver.value(x[i, j])]
    return {"pairs": pairs, "cost": sum(costs[i][j] for i, j in pairs),
            "status": solver.status_name(status)}


def distance_matrix():
    return [[1000 * manhattan(a, b) for b in STOPS] for a in STOPS]


def route_distance(route, distances):
    return sum(distances[a][b] for a, b in zip(route, route[1:]))


def delivery(capacity=7, distances=None):
    distances = distance_matrix() if distances is None else distances
    manager = pywrapcp.RoutingIndexManager(len(STOPS), 2, 0)
    routing = pywrapcp.RoutingModel(manager)
    transit = routing.RegisterTransitCallback(
        lambda a, b: distances[manager.IndexToNode(a)][manager.IndexToNode(b)])
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    demand = routing.RegisterUnaryTransitCallback(lambda a: DEMANDS[manager.IndexToNode(a)])
    routing.AddDimensionWithVehicleCapacity(demand, 0, [capacity] * 2, True, "Capacity")
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GREEDY_DESCENT
    params.time_limit.seconds = 2
    solution = routing.SolveWithParameters(params)
    if solution is None:
        return {"routes": [], "cost": None, "status": "NO_SOLUTION_FOUND"}
    routes = []
    for vehicle in range(2):
        index, route = routing.Start(vehicle), []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        routes.append(route + [0])
    return {"routes": routes, "cost": sum(route_distance(r, distances) for r in routes),
            "loads": [sum(DEMANDS[i] for i in r) for r in routes],
            "status": "FEASIBLE_HEURISTIC"}


def exact_delivery(capacity=7, distances=None):
    # 6곳만 완전탐색하여 휴리스틱 결과를 독립적으로 검산합니다.
    distances = distance_matrix() if distances is None else distances
    best = None
    for order in permutations(range(1, len(STOPS))):
        for split in range(1, len(order)):
            routes = [[0, *order[:split], 0], [0, *order[split:], 0]]
            if any(sum(DEMANDS[i] for i in r) > capacity for r in routes):
                continue
            cost = sum(route_distance(r, distances) for r in routes)
            if best is None or cost < best["cost"]:
                best = {"routes": routes, "cost": cost, "status": "OPTIMAL_ENUMERATION"}
    return best
