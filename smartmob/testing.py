"""자가 채점.

`labs/` 의 빈칸을 채운 뒤 스스로 확인할 때 씁니다.
`tests/` 가 쓰는 기준과 같은 것을 봅니다. 여기를 통과하면 과제 채점도 통과합니다.

    python labs/check.py ch03

돌아간다고 맞는 것은 아닙니다. 3장에서 말한 그대로, 답을 아는 것과 대조해야 합니다.
"""

from __future__ import annotations

import math
import random
import traceback
from dataclasses import dataclass, field


@dataclass
class Result:
    """검사 하나의 결과."""

    name: str
    passed: bool
    detail: str = ""

    def render(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        line = f"  [{mark}] {self.name}"
        return f"{line}\n         {self.detail}" if self.detail else line


@dataclass
class Report:
    title: str
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.results.append(Result(name, passed, detail))

    def check(self, name: str, fn) -> None:
        """``fn`` 을 부르고 예외 없이 True 를 내면 통과로 봅니다."""
        try:
            outcome = fn()
        except NotImplementedError:
            self.add(name, False, "아직 구현하지 않았습니다")
        except Exception as exc:  # noqa: BLE001 - 학생 코드의 어떤 예외든 보고합니다
            first = traceback.format_exc().strip().splitlines()[-1]
            self.add(name, False, f"{type(exc).__name__}: {first[:120]}")
        else:
            if isinstance(outcome, tuple):
                passed, detail = outcome
            else:
                passed, detail = bool(outcome), ""
            self.add(name, passed, detail)

    @property
    def ok(self) -> bool:
        return all(r.passed for r in self.results)

    def show(self) -> bool:
        print(f"\n{self.title}")
        print("-" * max(len(self.title), 40))
        for r in self.results:
            print(r.render())
        n_ok = sum(1 for r in self.results if r.passed)
        print(f"\n{n_ok}/{len(self.results)} 통과")
        if not self.ok:
            print("실패한 항목의 detail 을 보고 고친 뒤 다시 실행하세요.")
        return self.ok


# --------------------------------------------------------------------------- #
# 3장 — 최단경로
# --------------------------------------------------------------------------- #


def check_dijkstra(shortest, city: str = "hanam", n_pairs: int = 30, seed: int = 42) -> Report:
    """``shortest(graph, source, target) -> (초, 노드목록, 확정노드수)`` 를 검사합니다.

    경로가 없으면 ``smartmob.teaching.dijkstra.NoPath``를 발생시켜야 합니다.
    다른 예외는 구현 오류로 보고합니다.
    """
    import networkx as nx
    import pandas as pd

    from smartmob.data import load_road_graph
    from smartmob.teaching.dijkstra import NoPath
    from smartmob.teaching.graph import RoadGraph

    report = Report("3장 최단경로 자가 채점")
    G = load_road_graph(city, modes=("drive",))

    nxG = nx.DiGraph()
    for u, out in G.adj.items():
        for v, w, _ in out:
            if not nxG.has_edge(u, v) or nxG[u][v]["weight"] > w:
                nxG.add_edge(u, v, weight=w)

    rng = random.Random(seed)
    nodes = [n for n in G.adj if G.adj[n]]
    pairs = []
    while len(pairs) < n_pairs:
        s, t = rng.choice(nodes), rng.choice(nodes)
        if s != t and nx.has_path(nxG, s, t):
            pairs.append((s, t))

    def returns_triple():
        out = shortest(G, *pairs[0])
        if not (isinstance(out, tuple) and len(out) == 3):
            return False, "(소요시간, 경로 노드 목록, 확정 노드 수) 세 개를 돌려줘야 합니다"
        return True, ""

    def matches_networkx():
        worst, worst_pair = 0.0, None
        for s, t in pairs:
            mine = shortest(G, s, t)[0]
            theirs = nx.shortest_path_length(nxG, s, t, weight="weight")
            gap = abs(mine - theirs)
            if not math.isfinite(gap):
                return False, f"통행시간은 유한한 값이어야 합니다: {mine}"
            if gap > worst:
                worst, worst_pair = gap, (s, t)
        if worst > 1e-6:
            return False, f"{n_pairs}쌍 중 최대 오차 {worst:.4f}초 ({worst_pair[0]} → {worst_pair[1]})"
        return True, f"{n_pairs}쌍 전부 일치"

    def path_is_connected():
        for s, t in pairs[:5]:
            _, path, _ = shortest(G, s, t)
            if path[0] != s or path[-1] != t:
                return False, f"경로가 {s} 로 시작해 {t} 로 끝나야 합니다"
            for u, v in zip(path, path[1:]):
                if not any(nb == v for nb, _, _ in G.neighbors(u)):
                    return False, f"{u} → {v} 는 실제 엣지가 아닙니다"
        return True, ""

    def sums_to_total():
        s, t = pairs[0]
        total, path, _ = shortest(G, s, t)
        again = 0.0
        for u, v in zip(path, path[1:]):
            again += min(w for nb, w, _ in G.neighbors(u) if nb == v)
        if not math.isclose(again, total, rel_tol=0.0, abs_tol=1e-6):
            return False, f"엣지 합 {again:.3f} 초 vs 반환값 {total:.3f} 초"
        return True, ""

    def raises_when_disconnected():
        toy_nodes = pd.DataFrame([
            {"node_id": f"n{i}", "lat": 37.5, "lon": 127.2 + i * 0.001}
            for i in range(1, 5)
        ])
        toy_edges = pd.DataFrame([
            {"edge_id": "e1_f_1_2", "length": 100.0},
            {"edge_id": "e2_f_3_4", "length": 100.0},
        ]).assign(highway="residential", free_flow_speed_kmh=36.0)
        toy = RoadGraph.from_frames(toy_nodes, toy_edges)
        cases = [
            (G, "n_없는노드", pairs[0][1]),
            (G, pairs[0][0], "n_없는노드"),
            (toy, "n1", "n3"),  # 노드는 있지만 연결되지 않은 두 구간
            (toy, "n2", "n1"),  # 역방향 이동은 불가능
        ]
        for graph, source, target in cases:
            try:
                shortest(graph, source, target)
            except NoPath:
                continue
            return False, f"{source} → {target}: NoPath를 발생시켜야 합니다"
        return True, "없는 노드·연결 단절·역방향 이동을 구분해 확인"

    report.check("세 값을 돌려준다", returns_triple)
    report.check("NetworkX 와 결과가 같다", matches_networkx)
    report.check("경로가 실제로 이어져 있다", path_is_connected)
    report.check("엣지 비용의 합이 반환값과 같다", sums_to_total)
    report.check("연결되지 않은 경우 예외를 던진다", raises_when_disconnected)
    return report


# --------------------------------------------------------------------------- #
# 6장 — RAPTOR
# --------------------------------------------------------------------------- #


def toy_feed() -> dict:
    """답을 손으로 아는 작은 시간표. `smartmob.teaching.raptor.toy_feed` 와 같은 것입니다."""
    from smartmob.teaching.raptor import toy_feed as _toy_feed

    return _toy_feed()


def check_raptor(build, search, city: str = "hanam") -> Report:
    """``build(feed) -> data`` 와 ``search(data, origins, 출발초) -> best 리스트`` 를 검사합니다.

    ``origins`` 는 ``(정류장 인덱스, 접근 도보 초)`` 목록입니다.
    ``best[i]`` 는 정류장 i 까지의 가장 이른 도착시각(초)이고, 못 가면 ``float("inf")`` 입니다.
    """
    from smartmob.data import load_gtfs

    INF = float("inf")
    report = Report("6장 RAPTOR 자가 채점")

    try:
        toy = build(toy_feed())
    except NotImplementedError:
        report.add("작은 시간표로 자료구조를 만든다", False, "아직 구현하지 않았습니다")
        return report
    except Exception as exc:  # noqa: BLE001
        report.add("작은 시간표로 자료구조를 만든다", False, f"{type(exc).__name__}: {exc}")
        return report
    report.add("작은 시간표로 자료구조를 만든다", True, f"패턴 {len(toy.patterns)}개")

    def at(stop_id: str) -> int:
        index = getattr(toy, "index_of", None)
        if index and stop_id in index:
            return index[stop_id]
        return list(toy.stop_ids).index(stop_id)

    def direct_ride():
        best = search(toy, [(at("A"), 0)], 8 * 3600)
        got = best[at("C")]
        if got != 8 * 3600 + 20 * 60:
            return False, f"A 08:00 출발 → C 는 08:20 이어야 하는데 {got} 초가 나왔습니다"
        return True, "08:20 도착"

    def one_transfer():
        best = search(toy, [(at("A"), 0)], 8 * 3600)
        got = best[at("E")]
        if got != 8 * 3600 + 25 * 60:
            return False, f"B 에서 걸어 D 로 갈아타면 E 는 08:25 인데 {got} 초가 나왔습니다"
        return True, "08:25 도착 (환승 1회)"

    def missed_first_trip():
        best = search(toy, [(at("A"), 0)], 8 * 3600 + 5 * 60)
        got = best[at("C")]
        if got != 8 * 3600 + 50 * 60:
            return False, f"08:05 출발이면 첫 차를 놓쳐 08:50 인데 {got} 초가 나왔습니다"
        return True, "08:50 도착"

    def access_walk_counts():
        best = search(toy, [(at("A"), 600)], 8 * 3600 - 300)   # 07:55 + 도보 10분
        if best[at("C")] != 8 * 3600 + 50 * 60:
            return False, "접근 도보 시간을 출발 시각에 더해야 합니다"
        return True, ""

    def after_service():
        best = search(toy, [(at("A"), 0)], 23 * 3600)
        if best[at("C")] != INF:
            return False, "막차 이후에는 도달할 수 없어야 합니다"
        return True, ""

    report.check("직통 — A 08:00 → C 08:20", direct_ride)
    report.check("환승 — A 08:00 → E 08:25", one_transfer)
    report.check("첫 차를 놓치면 다음 차", missed_first_trip)
    report.check("접근 도보가 출발 시각에 더해진다", access_walk_counts)
    report.check("막차 이후에는 못 간다", after_service)

    try:
        real = build(load_gtfs(city))
    except Exception as exc:  # noqa: BLE001
        report.add("실제 피드로 만들 수 있다", False, f"{type(exc).__name__}: {exc}")
        return report
    report.add("실제 피드로 만들 수 있다", True, f"정류장 {len(real.stop_ids):,}개")

    origins = real.access_stops(37.5393, 127.2148)     # 하남시청

    def reaches_most():
        best = search(real, origins, 8 * 3600)
        reached = sum(1 for t in best if t < INF)
        share = reached / len(real.stop_ids)
        if share < 0.9:
            return False, f"오전 8시 출발인데 {share:.0%} 만 도달했습니다"
        return True, f"{reached:,}개 도달 ({share:.0%})"

    def monotone_in_departure():
        early = search(real, origins, 8 * 3600)
        late = search(real, origins, 8 * 3600 + 1800)
        bad = sum(1 for a, b in zip(early, late) if a < INF and b < INF and b < a)
        if bad:
            return False, f"늦게 출발했는데 더 일찍 도착한 정류장 {bad}개"
        return True, "30분 늦게 출발하면 절대 더 일찍 도착하지 않는다"

    report.check("실제 피드에서 대부분 도달한다", reaches_most)
    report.check("늦게 출발하면 더 일찍 도착하지 않는다", monotone_in_departure)
    return report


# --------------------------------------------------------------------------- #
# 11장 — 시뮬레이션 루프
# --------------------------------------------------------------------------- #


def check_simloop(simulate, city: str = "hanam") -> Report:
    """``simulate(demand, vehicles, time_start, time_end) -> 결과`` 를 검사합니다.

    결과는 `record`(DataFrame)와 `summary()` 를 가져야 합니다.
    """
    from smartmob import Dtumos
    from smartmob.data import load_demand, load_vehicles

    report = Report("11장 시뮬레이션 루프 자가 채점")
    demand, vehicles = load_demand(city), load_vehicles(city)
    run = simulate(demand, vehicles, 1080, 1440)
    summary = run.summary()

    COLUMNS = ["time", "waiting_passenger_cnt", "fail_passenger_cnt",
               "empty_vehicle_cnt", "driving_vehicle_cnt"]

    def record_shape():
        cols = list(run.record.columns)
        if cols != COLUMNS:
            return False, f"컬럼이 달라야 할 이유가 없습니다. 기대: {COLUMNS}, 실제: {cols}"
        if len(run.record) != 360:
            return False, f"18:00~24:00 은 360분인데 {len(run.record)}행입니다"
        return True, "record.csv 와 같은 형식"

    def fleet_bound():
        total = run.record["empty_vehicle_cnt"] + run.record["driving_vehicle_cnt"]
        if (total > len(vehicles)).any():
            return False, f"근무 차량 합이 보유 대수 {len(vehicles)}대를 넘습니다"
        return True, ""

    def fails_monotone():
        fails = run.record["fail_passenger_cnt"].tolist()
        for a, b in zip(fails, fails[1:]):
            if b < a:
                return False, "누적 실패 건수가 줄어들었습니다"
        return True, ""

    def fewer_vehicles_hurt():
        small = simulate(demand, vehicles.head(30), 1080, 1440).summary()
        if small["service_rate"] >= summary["service_rate"]:
            return False, "차량을 30대로 줄였는데 서비스율이 떨어지지 않았습니다"
        return True, (f"80대 {summary['service_rate']:.3f} → "
                      f"30대 {small['service_rate']:.3f}")

    def close_to_engine():
        engine = Dtumos().run_simulation(
            city=city, mode="taxi", fleet_size=80, num_passengers=1000,
            time_start=1080, time_end=1440, random_seed=42,
        )
        mine = summary["avg_waiting_time_min"]
        theirs = engine.summary()["avg_waiting_time_min"]
        if abs(mine - theirs) >= 1.5:
            return False, f"내 루프 {mine:.2f}분 vs 엔진 {theirs:.2f}분 — 1.5분 이상 벌어졌습니다"
        return True, f"내 루프 {mine:.2f}분, 엔진 {theirs:.2f}분"

    report.check("record 형식이 엔진과 같다", record_shape)
    report.check("근무 차량이 보유 대수를 넘지 않는다", fleet_bound)
    report.check("누적 실패가 줄어들지 않는다", fails_monotone)
    report.check("차량을 줄이면 서비스율이 떨어진다", fewer_vehicles_hurt)
    report.check("평균 대기가 엔진과 1.5분 이내", close_to_engine)
    return report
