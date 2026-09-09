---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 6장 대중교통 경로 탐색 — RAPTOR

하남시청에서 오전 8시에 출발해 미사역까지 대중교통으로 가면 몇 시에 도착할까요.

3장의 다익스트라를 그대로 적용할 수는 없습니다. 도로 엣지에는 42초처럼 고정된 비용이 있었습니다. 대중교통에서는 정류장 도착시각에 따라 대기시간이 달라집니다. 오전 8시 3분에 도착해 8시 1분 차를 놓치면 다음 차까지 12분을 기다리지만, 8시 정각에 도착하면 1분만 기다립니다.

이 장에서 시간표를 직접 훑는 알고리즘 RAPTOR 를 구현합니다. 직접 구현하는 세 가지 중 두 번째입니다. 빈칸 세 자리를 채우면 150줄쯤 됩니다.

## 학습 목표

- 대중교통 경로 탐색이 그래프 최단경로와 왜 다른지 설명합니다
- GTFS 를 RAPTOR 가 쓰는 네 개의 자료구조로 바꿉니다
- 라운드 기반 탐색을 구현하고, 복원된 경로를 읽습니다
- 손으로 답을 아는 작은 시간표로 구현을 검증합니다

## 6.1 시간표를 그래프로 표현하면

“정류장 A의 오전 8시 10분”과 “정류장 A의 오전 8시 22분”을 서로 다른 노드로 만들 수 있습니다. 시각-정류장 쌍을 노드로 삼는 시간 확장 그래프(time-expanded graph)입니다.

문제는 크기입니다.

```{code-cell} python
from smartmob.data import load_gtfs

feed = load_gtfs("hanam")
print(f"정류장 {len(feed['stops']):,}개")
print(f"시각표 행 {len(feed['stop_times']):,}개")
```

시각표 행마다 도착·출발 사건을 노드로 만들면 하남 자료만으로도 수십만 개가 필요합니다. 출발시각마다 그래프를 다시 만들 필요는 없지만, 질의는 656,385개 시각표 행에서 만든 사건 그래프를 탐색합니다.

RAPTOR는 시각 사건을 노드로 만들지 않고 환승 횟수를 기준으로 라운드를 나눕니다.

- 라운드 0: 걸어서 갈 수 있는 정류장
- 라운드 1: 한 번 타고 갈 수 있는 정류장
- 라운드 2: 두 번 타고 갈 수 있는 정류장
- …

라운드마다 직전 라운드에서 도착시각이 개선된 정류장을 표시하고, 해당 정류장을 지나는 패턴을 훑습니다. 이 장에서는 `max_rounds=5` 로 운행 탑승 횟수를 제한합니다.

탐색하는 동안에는 우선순위 큐를 쓰지 않고 노선을 순서대로 훑기만 합니다. 정렬은 탐색 전에 시간표를 준비하면서 한 번만 합니다. 이 단순함이 RAPTOR 가 빠른 이유입니다.

## 6.2 준비 1 — 노선이 아니라 패턴으로 묶습니다

하남 자료에서는 `route_id` 하나에 정류장 순서가 다른 운행이 들어 있을 수 있습니다. RAPTOR 입력을 만들 때 `route_id` 만으로 운행을 묶으면 정류장 순서를 하나로 정할 수 없습니다.

정류장 순서가 같은 운행끼리 다시 묶은 단위를 패턴(pattern)이라고 합니다. 한 패턴에 속한 운행은 같은 정류장을 같은 순서로 방문합니다.

```{code-cell} python
from collections import defaultdict

st = feed["stop_times"].copy()
st["stop_sequence"] = st["stop_sequence"].astype(int)
st = st.sort_values(["trip_id", "stop_sequence"])

route_of = dict(zip(feed["trips"]["trip_id"], feed["trips"]["route_id"]))

patterns = defaultdict(list)
for trip_id, rows in st.groupby("trip_id", sort=False):
    key = (route_of.get(trip_id), tuple(rows["stop_id"]))
    patterns[key].append(trip_id)

print(f"노선 {feed['routes']['route_id'].nunique()}개")
print(f"운행 {len(feed['trips']):,}개")
print(f"패턴 {len(patterns)}개")
```

운행 8,923개가 패턴 349개로 묶입니다. 패턴당 운행 수를 단순 평균하면 25.6개입니다.

노선은 169개이고 패턴은 349개입니다. `route_id` 당 패턴 수의 단순 평균은 2.1개입니다.

```{code-cell} python
by_route = defaultdict(int)
for (route_id, _), trips in patterns.items():
    by_route[route_id] += 1

from collections import Counter
print("노선당 패턴 수:", dict(sorted(Counter(by_route.values()).items())))
```

96개 노선은 패턴이 하나, 61개는 둘(상행·하행)입니다. 나머지 12개 노선이 4개에서 22개까지 가집니다.

패턴이 22개인 노선도 있습니다. 이 결과만으로 지선, 구간 운행, 회차 방식 중 무엇이 원인인지는 알 수 없습니다. 다만 같은 `route_id` 안에 서로 다른 정류장 순서가 22개 있다는 것은 확인할 수 있습니다.

패턴 안의 운행은 첫 정류장 출발 시각 순으로 정렬해 둡니다. GTFS 의 시각은 `"08:03:00"` 같은 문자열이라 먼저 초로 바꿉니다. 5장의 `parse_gtfs_time` 이 24시를 넘는 표기까지 받습니다.

```{code-cell} python
from smartmob.data import parse_gtfs_time

st["dep_s"] = st["departure_time"].map(parse_gtfs_time)
first_dep = st.groupby("trip_id")["dep_s"].first()      # 운행별 첫 정류장 출발 시각

for trips in patterns.values():
    trips.sort(key=first_dep.get)

busiest_key = max(patterns, key=lambda k: len(patterns[k]))
deps = [int(first_dep[t]) for t in patterns[busiest_key]]
print(f"운행이 가장 많은 패턴: 노선 {busiest_key[0]}, {len(deps)}회")
print("앞의 다섯 출발:", [f"{d // 3600:02d}:{d % 3600 // 60:02d}" for d in deps[:5]])
```

정렬해 두면 "8시 3분 이후에 오는 첫 차"를 전부 훑지 않고 이분 탐색으로 찾습니다. 정렬된 목록에서 어떤 값이 들어갈 자리를 찾는 `bisect_left` 를 씁니다.

```{code-cell} python
from bisect import bisect_left

i = bisect_left(deps, 8 * 3600 + 180)                     # 08:03 이후 첫 운행의 번호
print(f"{len(deps)}회 중 {i}번째 운행, 출발 {deps[i] // 3600:02d}:{deps[i] % 3600 // 60:02d}")
```

실습 파일의 `earliest_trip` 이 하는 일이 이 두 줄입니다. 정류장 위치마다 출발 시각 열을 하나씩 두고, 거기에 `bisect_left` 를 겁니다.

## 6.3 준비 2 — 정류장에서 노선을 거꾸로 찾기

라운드마다 "이 정류장을 지나는 노선이 무엇인가"를 물어야 합니다. 매번 349개 패턴을 훑을 수는 없으니, 미리 뒤집어 둡니다.

```{code-cell} python
routes_by_stop = defaultdict(list)
for pattern_idx, ((route_id, stop_seq), trips) in enumerate(patterns.items()):
    for position, stop_id in enumerate(stop_seq):
        routes_by_stop[stop_id].append((pattern_idx, position))

busiest = max(routes_by_stop.items(), key=lambda kv: len(kv[1]))
name = feed["stops"].set_index("stop_id").loc[busiest[0], "stop_name"]
print(f"가장 많은 패턴이 지나는 정류장: {name} ({len(busiest[1])}개)")
```

`position` 은 해당 정류장이 패턴에서 몇 번째인지 나타냅니다. 라운드에서는 이 위치부터 패턴을 훑습니다.

## 6.4 준비 3 — 도보 환승

이 실습 파일에는 `transfers.txt` 가 없습니다. 정류장 사이의 도보 환승 목록을 좌표로 만듭니다.

500 m 안의 정류장 쌍을 찾고 직선거리에 우회계수 1.35를 곱합니다. 도보시간은 이 거리를 보행 속도 1.2 m/s로 나눈 값입니다.

```{code-cell} python
from smartmob.teaching.raptor import TransitData

data = TransitData.from_gtfs(feed)
data.describe()
```

`from_gtfs` 는 지금까지 한 일을 한 번에 합니다. 6.2절의 패턴 묶기·시각 파싱·운행 정렬, 6.3절의 역색인, 그리고 여기서 말한 도보 환승입니다. 실습 파일에서 여러분이 채우는 것이 이 함수이고, 순서가 그 자리에 여섯 줄로 적혀 있습니다.

도보 환승이 28,818쌍입니다. 정류장 4,203개당 평균 7개꼴입니다. 버스 정류장이 도로 양쪽에 하나씩 있는 경우가 많아서 그렇습니다.

```{warning}
직선거리만으로 만든 환승에는 건널 수 없는 하천이나 도로가 반영되지 않습니다. 예를 들어 강을 사이에 둔 두 정류장의 직선거리가 400 m라면 실제 보행로가 없어도 환승 쌍에 들어갈 수 있습니다. 결과를 사용할 때는 보행 네트워크로 연결 여부와 거리를 다시 확인해야 합니다.
```

## 6.5 알고리즘

준비가 끝났습니다. 하남 GTFS 로 가기 전에 답을 손으로 아는 작은 시간표로 생각합니다. 정류장 다섯 개, 노선 둘입니다.

```
A --(1호선)--> B --(1호선)--> C     1호선  08:00 A → 08:10 B → 08:20 C
               |                            08:30 A → 08:40 B → 08:50 C
           도보 100m
               |
               D --(2호선)--> E     2호선  08:15 D → 08:25 E
```

8시에 A에서 출발합니다. 환승 횟수를 라운드로 삼으면 이렇게 진행됩니다.

| 라운드 | 무엇을 하는가 | 새로 도달한 정류장 |
|---|---|---|
| 0 | 출발지 A 에 08:00 을 적습니다 | A 08:00 |
| 1 | A 를 지나는 1호선을 훑습니다. 08:00 차를 타고 B, C 에 내려 봅니다. 내린 B 에서 걸어서 D 로 갑니다 | B 08:10, C 08:20, D 08:11 |
| 2 | B, C, D 를 지나는 노선을 훑습니다. D 에서 08:15 2호선을 타고 E 에 내립니다. B 에서 다시 1호선을 타도 C 가 나아지지 않습니다 | E 08:25 |
| 3 | E 를 지나는 노선을 훑어도 나아지는 곳이 없습니다 | 없음, 끝 |

C 는 라운드 1에서 08:20, E 는 라운드 2에서 08:25 입니다. 라운드 번호가 곧 탄 횟수이므로 E 는 환승 1회입니다. 8시 5분에 출발하면 08:00 차를 놓쳐 08:30 차를 타고 C 에 08:50 에 닿습니다.

이 표를 코드로 옮깁니다.

상태

- `best[정류장]` — 지금까지 알아낸 가장 이른 도착시각
- `rounds[k][정류장]` — k번 타고 도달했을 때의 도착시각
- `marked` — 직전 라운드에서 개선된 정류장 집합

라운드 0

출발지에서 걸어갈 수 있는 정류장에 `출발시각 + 도보시간` 을 적고 표시합니다.

라운드 k

1. 표시된 정류장을 지나는 패턴을 모읍니다. 같은 패턴이 여러 정류장에서 걸리면 가장 앞 위치에서 시작합니다
2. 각 패턴을 그 위치부터 끝까지 훑습니다. 손에 든 차가 있으면 내려 보고, 여기서 더 이른 차를 탈 수 있으면 갈아탑니다
3. 이번 라운드에 도달한 정류장에서 걸어갈 수 있는 곳을 채웁니다
4. 개선된 정류장이 없으면 끝냅니다

2번의 "손에 든 차"는 패턴을 훑는 동안 현재 타고 있는 운행 번호 하나를 뜻합니다. 타고 있으면 계속 타고, 더 이른 차가 있으면 갈아탑니다.

네 단계를 함수 하나씩으로 씁니다. 먼저 1번, 표시된 정류장을 지나는 패턴을 모읍니다. 같은 패턴이 여러 정류장에서 걸리면 가장 앞 위치 하나만 남깁니다.

```{code-cell} python
INF = float("inf")


def collect_patterns(data, marked):
    queue = {}                                   # 패턴 번호 → 훑기 시작할 위치
    for stop in marked:
        for pattern_idx, pos in data.routes_by_stop[stop]:
            if pattern_idx not in queue or pos < queue[pattern_idx]:
                queue[pattern_idx] = pos
    return queue
```

2번, 패턴 하나를 그 위치부터 끝까지 훑습니다. `trip` 이 손에 든 차입니다. 정류장마다 먼저 내려 보고, 그다음 더 이른 차로 갈아탈 수 있는지 봅니다. 갈아타는 판단에는 직전 라운드의 도착시각 `prev` 를 씁니다.

```{code-cell} python
def scan_pattern(p, start_pos, prev, cur, best, new_marked):
    trip = None
    for pos in range(start_pos, len(p.stops)):
        stop = p.stops[pos]
        if trip is not None:                      # 내려 보기
            arrive = p.arrivals[trip][pos]
            if arrive < best[stop]:
                best[stop] = cur[stop] = arrive
                new_marked.add(stop)
        ready = prev[stop]                        # 더 이른 차로 갈아타기
        if ready < INF:
            cand = p.earliest_trip(pos, int(ready))
            if cand is not None and (
                trip is None or p.departures[cand][pos] < p.departures[trip][pos]
            ):
                trip = cand
```

순서가 중요합니다. 갈아타기를 먼저 하면 방금 탄 차에서 같은 정류장에 바로 내리는 셈이 됩니다. `prev` 대신 이번 라운드의 `cur` 를 쓰면 한 라운드에 여러 번 갈아타게 되어 라운드 번호가 환승 횟수가 아니게 됩니다.

3번, 이번 라운드에 내린 정류장에서 걸어갈 수 있는 곳을 채웁니다.

```{code-cell} python
def walk_transfers(data, cur, best, new_marked):
    for stop in list(new_marked):
        for other, seconds in data.transfers[stop]:
            arrive = cur[stop] + seconds
            if arrive < best[other]:
                best[other] = cur[other] = arrive
                new_marked.add(other)
```

셋을 라운드 안에 넣습니다. 라운드 0은 출발지에서 걸어갈 수 있는 정류장에 시각을 적는 것이고, 4번은 새로 나아진 정류장이 없으면 끝내는 것입니다.

```{code-cell} python
# smartmob/teaching/raptor.py 의 raptor() 를 간추린 것입니다.
def raptor_core(data, origins, departure, max_rounds=5):
    n = data.n_stops
    best = [INF] * n
    rounds = [[INF] * n]

    marked = set()
    for stop, walk in origins:                       # 라운드 0: 접근 도보
        t = departure + walk
        if t < rounds[0][stop]:
            rounds[0][stop] = best[stop] = t
            marked.add(stop)

    for k in range(1, max_rounds + 1):
        prev, cur = rounds[k - 1], list(rounds[k - 1])
        rounds.append(cur)
        new_marked = set()
        for pattern_idx, start_pos in collect_patterns(data, marked).items():
            scan_pattern(data.patterns[pattern_idx], start_pos, prev, cur, best, new_marked)
        walk_transfers(data, cur, best, new_marked)
        if not new_marked:                           # 4) 더 나아지지 않으면 끝
            break
        marked = new_marked

    return best, rounds
```

작은 시간표로 먼저 확인합니다. 그림의 시간표가 `toy_feed()` 에 GTFS 표 네 개로 들어 있습니다.

```{code-cell} python
from smartmob.teaching.raptor import toy_feed

toy = TransitData.from_gtfs(toy_feed(), max_transfer_m=300)
a = toy.index_of["A"]
best, rounds = raptor_core(toy, [(a, 0)], 8 * 3600)

for k, row in enumerate(rounds):
    reached = {toy.stop_ids[i]: f"{int(t) // 3600:02d}:{int(t) % 3600 // 60:02d}"
               for i, t in enumerate(row) if t < INF}
    print(f"라운드 {k}: {reached}")
```

표와 같습니다. 라운드 1에 B, C, D 가 나오고 라운드 2에 E 가 나옵니다. 이제 하남 GTFS 로 돌립니다.

```{code-cell} python
import time

origins = data.access_stops(37.5393, 127.2148)      # 하남시청에서 걸어갈 수 있는 정류장
print(f"접근 가능한 정류장 {len(origins)}개, 가장 가까운 곳까지 {origins[0][1]}초")

t0 = time.perf_counter()
best, rounds = raptor_core(data, origins, 8 * 3600)
elapsed = (time.perf_counter() - t0) * 1000

reached = sum(1 for t in best if t < INF)
print(f"{elapsed:.0f} ms 에 {reached:,}/{data.n_stops:,} 정류장 도달")
```

**80밀리초에 4,156개 정류장까지의 도착시각을 전부 구했습니다.** 3장의 다익스트라는 한 쌍에 7ms 였습니다. 그 속도로 4,156번 물었다면 30초가 넘습니다.

한 번의 RAPTOR 질의는 출발지에서 도달 가능한 모든 정류장의 도착시각을 반환합니다. 이 일대다(one-to-all) 결과로 시간 한도별 도달 정류장을 구할 수 있습니다.

## 6.6 경로 복원

도착시각만으로는 부족합니다. 어떤 버스를 타고 어디서 갈아탔는지 알아야 합니다.

라운드마다 "이 정류장에 어떻게 왔는가"를 기록해 두면 거꾸로 따라갈 수 있습니다. 정리된 구현 `raptor` 는 `raptor_core` 와 같은 일을 하면서, 정류장이 나아질 때마다 기록을 하나 남깁니다. 차를 타고 왔으면 (어느 패턴, 몇 번째 운행, 어디서 탔는지), 걸어왔으면 (어느 정류장에서, 몇 초)입니다. 목적지에서 이 기록을 거꾸로 따라가는 것이 `journey` 입니다.

반환값도 다릅니다. `raptor_core` 는 튜플 둘을 돌려줬지만 `raptor` 는 객체 하나를 돌려주고, 도착시각 목록은 `result.best` 로 꺼냅니다.

```{code-cell} python
from smartmob.teaching.raptor import raptor, journey, summarize

result = raptor(data, origins, 8 * 3600)
target = data.nearest_stop(37.5606, 127.1930)       # 미사역 부근
print(f"도착 정류장: {data.stop_names[target]}")

legs = journey(data, result, target)
for leg in legs:
    if leg["kind"] == "transit":
        board = leg["board_time"]
        alight = leg["alight_time"]
        print(f"  {leg['mode']:7s} {leg['route']:10s} "
              f"{board // 3600:02d}:{board % 3600 // 60:02d} → "
              f"{alight // 3600:02d}:{alight % 3600 // 60:02d}  "
              f"({leg['n_stops']}개 정류장)")
    else:
        print(f"  도보    {leg['seconds'] // 60}분 {leg['seconds'] % 60}초 ({leg['kind']})")
```

지표로 요약합니다.

```{code-cell} python
summarize(data, legs, 8 * 3600)
```

미사역 좌표에서 가장 가까운 GTFS 정류장은 `미사강변브라운스톤`이고 계산된 통행시간은 22.9분입니다. 4장의 자동차 경로와는 도착 노드와 이동 조건이 다르므로 수치를 직접 비교하지 않습니다.

22.9분 가운데 차내시간은 6.6분, 도보시간은 11.2분, 대기시간은 5.1분입니다. 이 경로에서는 도보와 대기가 전체 통행시간의 71%를 차지합니다.

## 6.7 맞는지 어떻게 아는가

실제 GTFS 로는 답을 손으로 확인할 수 없습니다. 그래서 6.5절의 작은 시간표를 `tests/test_raptor.py` 가 그대로 씁니다. C 08:20 환승 0회, E 08:25 환승 1회, 8시 5분 출발이면 C 08:50 세 가지입니다.

```bash
pytest tests/test_raptor.py -v -k toy
```

```
tests/test_raptor.py::test_toy_direct_ride PASSED
tests/test_raptor.py::test_toy_one_transfer PASSED
tests/test_raptor.py::test_toy_later_departure_takes_second_trip PASSED
```

실제 피드에서는 답 대신 불변식을 확인합니다.

```{code-cell} python
later = raptor(data, origins, 8 * 3600 + 1800)     # 30분 늦게 출발

violations = sum(
    1 for early, late in zip(result.best, later.best)
    if late < INF and early < INF and late < early
)
print(f"늦게 출발했는데 더 일찍 도착한 정류장: {violations}개")
```

늦게 출발했는데 더 일찍 도착하는 일은 있을 수 없습니다. 하나라도 나오면 구현이 틀린 것입니다.

```{code-cell} python
before_service = raptor(data, origins, 3 * 3600)   # 새벽 3시, 첫차 전
arrive = int(before_service.best[target])
print(f"새벽 3시 출발 도달 정류장: {sum(1 for t in before_service.best if t < INF):,}개")
print(f"미사역 도착 {arrive // 3600:02d}:{arrive % 3600 // 60:02d}")
```

첫차 전에 출발해도 도달 정류장 수는 줄지 않습니다. 정류장에서 첫차를 기다렸다가 타기 때문입니다. 대신 미사역 도착이 5시 14분입니다. 8시 출발이 22분 걸린 구간에 두 시간 넘게 걸립니다. 첫차 전에 출발한 도착시각이 첫차 출발보다 이르면 구현이 틀린 것입니다.

## 이 장의 실습

노트북 `labs/ch06_raptor.ipynb` 를 열어 함께 돌립니다.

정류장 다섯 개짜리 시간표에서 시작해 하남 GTFS 로 옮기고, 불변식으로 검증합니다.

```bash
jupyter lab labs/ch06_raptor.ipynb
```

이 장은 채점받는 실습입니다. 노트북이 아니라 옆의 `labs/ch06_raptor.py` 의 빈칸을 채웁니다.
채운 뒤 자가 채점을 돌립니다. 이 기준이 곧 과제 채점 기준입니다.

```bash
python labs/check.py ch06
```

## 정리

- 대중교통은 같은 구간의 비용이 도착 시각에 따라 달라집니다. 그래서 그래프 최단경로를 쓸 수 없습니다
- RAPTOR 는 환승 횟수를 라운드로 삼습니다. 탐색 중에는 우선순위 큐가 없고, 정렬은 준비 단계에서 한 번만 합니다
- GTFS 노선을 그대로 쓰면 안 됩니다. 정류장 순서가 같은 운행끼리 다시 묶어 패턴을 만듭니다. 하남은 운행 8,923개가 패턴 349개로 묶입니다
- 정류장→패턴 역색인과 도보 환승 목록을 미리 만들어 둡니다
- 오전 8시 질의에서는 4,203개 정류장 중 4,156개의 도착시각을 계산합니다
- 하남시청→미사역 오전 8시는 23분입니다. 차내 6.6분, 도보 11.2분, 대기 5.1분입니다
- 검증은 손으로 답을 아는 정류장 다섯 개짜리 시간표로 합니다. 실제 피드에서는 불변식만 확인합니다
- 7장에서 환승 규칙을 다듬고 요금을 계산합니다

## 연습문제

```{admonition} 연습 6.1  ★
:class: tip

출발 시각을 오전 7시부터 오후 11시까지 1시간 간격으로 바꿔 가며,
하남시청→미사역 통행시간을 구해 그래프로 그려 봅시다.

산출물: 꺾은선 그래프 1장, 가장 오래 걸리는 시각과 그 이유에 대한 추측 2~3줄.
```

```{admonition} 연습 6.2  ★★
:class: tip

`max_rounds` 를 1, 2, 3, 4, 5 로 바꿔 가며 도달 정류장 수를 세어 봅시다.
환승을 몇 번까지 허용해야 하남시 대부분에 닿을 수 있나요?

산출물: 라운드별 도달 정류장 수 표, 몇 회에서 포화되는지 한 문장.
```

```{admonition} 연습 6.3  ★★★
:class: tip

RAPTOR 의 일대다 성질을 이용해 **등시선 지도**를 그려 봅시다.
하남시청에서 오전 8시에 출발했을 때 30분·45분·60분 안에 닿는 정류장을
서로 다른 색으로 지도에 찍습니다.

출발지를 미사역으로 바꾼 지도도 만든 뒤 하남시청 결과와 비교해 봅시다.
어느 쪽이 더 넓게 닿나요? 그것이 무엇을 뜻하나요?

산출물: 등시선 지도 2장, 비교 해석 3~4줄.
```
