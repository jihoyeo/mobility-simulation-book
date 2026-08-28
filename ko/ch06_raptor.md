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

# 6장 밑바닥부터 RAPTOR

하남시청에서 오전 8시에 출발해 미사역까지 대중교통으로 가면 몇 시에 도착할까요.

3장의 다익스트라를 그대로 쓸 수 없습니다. 도로에서는 "이 엣지를 지나는 데 42초"가 정해져 있었는데, 대중교통에서는 정해져 있지 않습니다. 정류장에 8시 3분에 도착했는데 버스가 8시 1분에 떠났다면 다음 차까지 12분을 기다립니다. 8시 정각에 도착했다면 1분만 기다립니다. **같은 구간의 비용이 언제 도착했느냐에 따라 달라집니다.**

이 장에서 시간표를 직접 훑는 알고리즘을 짭니다. 150줄입니다.

## 학습 목표

- 대중교통 경로 탐색이 그래프 최단경로와 왜 다른지 설명합니다
- GTFS 를 RAPTOR 가 쓰는 네 개의 자료구조로 바꿉니다
- 라운드 기반 탐색을 구현하고 경로를 복원합니다
- 손으로 답을 아는 작은 시간표로 구현을 검증합니다

## 6.1 그래프로 풀면 왜 안 되는가

억지로 그래프를 만들 수는 있습니다. "정류장 A에서 8시 10분"과 "정류장 A에서 8시 22분"을 서로 다른 노드로 두면 됩니다. 시각-정류장 쌍을 노드로 삼는 방식입니다.

문제는 크기입니다.

```{code-cell} python
from smartmob.data import load_gtfs

feed = load_gtfs("hanam")
print(f"정류장 {len(feed['stops']):,}개")
print(f"시각표 행 {len(feed['stop_times']):,}개")
```

시각표 행 하나가 노드 하나가 되므로 65만 개짜리 그래프입니다. 게다가 출발 시각이 바뀔 때마다 다시 만들어야 합니다.

RAPTOR 는 다르게 봅니다. 환승 횟수를 기준으로 라운드를 나눕니다.

- 라운드 0: 걸어서 갈 수 있는 정류장
- 라운드 1: 한 번 타고 갈 수 있는 정류장
- 라운드 2: 두 번 타고 갈 수 있는 정류장
- …

라운드마다 "이번 라운드에서 새로 도달한 정류장"을 들고, 그 정류장을 지나는 노선을 훑습니다. 환승은 대개 네다섯 번을 넘지 않으므로 라운드도 그만큼만 돌면 됩니다.

우선순위 큐가 없습니다. 정렬도 없습니다. 그냥 노선을 순서대로 훑을 뿐입니다. 이게 RAPTOR 가 빠른 이유입니다.

## 6.2 준비 1 — 노선이 아니라 패턴으로 묶습니다

GTFS 의 `route_id` 를 그대로 쓰면 안 됩니다. 같은 340번 버스라도 상행과 하행은 정류장 순서가 반대이고, 지선이 있으면 중간에 갈라집니다.

RAPTOR 가 필요로 하는 것은 "이 정류장 다음은 반드시 저 정류장"이 정해진 묶음입니다. 그래서 **정류장 순서가 완전히 같은 운행끼리 다시 묶습니다.** 이것을 패턴이라고 부릅니다.

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

운행 8,923개가 패턴 349개로 묶였습니다. 패턴 하나당 평균 26번 다닌다는 뜻입니다.

노선 169개보다 패턴이 두 배 많은 것이 핵심입니다. 노선 하나가 평균 두 개의 서로 다른 정류장 순서를 가진다는 뜻입니다.

```{code-cell} python
by_route = defaultdict(int)
for (route_id, _), trips in patterns.items():
    by_route[route_id] += 1

from collections import Counter
print("노선당 패턴 수:", dict(sorted(Counter(by_route.values()).items())))
```

96개 노선은 패턴이 하나, 61개는 둘(상행·하행)입니다. 나머지 12개 노선이 4개에서 22개까지 가집니다.

패턴이 22개인 노선은 무엇일까요. 지선이 여럿이거나, 시간대에 따라 일부 구간을 건너뛰거나, 회차 지점이 여러 개인 노선입니다. 이런 노선을 `route_id` 하나로 묶어 놓고 "이 정류장 다음은 저 정류장"을 정하려 하면 답이 하나로 정해지지 않습니다. 패턴으로 나누는 이유가 이것입니다.

패턴 안의 운행은 첫 정류장 출발 시각 순으로 정렬해 둡니다. 그래야 "8시 3분 이후에 오는 첫 차"를 이분 탐색으로 찾을 수 있습니다.

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

`position` 을 같이 저장하는 것이 중요합니다. 패턴의 몇 번째 정류장인지 알아야 그 지점부터 훑을 수 있습니다.

## 6.4 준비 3 — 도보 환승

버스에서 내려 지하철로 갈아타려면 걸어야 합니다. 한국 GTFS 에는 `transfers.txt` 가 대부분 없으므로 직접 만듭니다.

500m 안의 정류장 쌍을 찾아 직선거리에 1.35를 곱하고(실제 도보는 직선보다 돌아갑니다) 초속 1.2m로 나눕니다.

```{code-cell} python
from smartmob.teaching.raptor import TransitData

data = TransitData.from_gtfs(feed)
data.describe()
```

도보 환승이 28,818쌍입니다. 정류장 4,203개당 평균 7개꼴입니다. 버스 정류장이 도로 양쪽에 하나씩 있는 경우가 많아서 그렇습니다.

```{warning}
직선거리에 계수를 곱한 값은 낙관적입니다. 한강을 사이에 둔 두 정류장이 직선으로 400m라면 도보 환승이 만들어지지만 실제로는 다리를 건너야 합니다. 실제 엔진은 보행 네트워크에서 다익스트라를 돌려 이런 쌍을 걸러 냅니다. 우리 구현에서는 그대로 두되, 결과를 볼 때 이 점을 기억합니다.
```

## 6.5 알고리즘

준비가 끝났습니다. 알고리즘은 이렇습니다.

상태

- `best[정류장]` — 지금까지 알아낸 가장 이른 도착시각
- `rounds[k][정류장]` — k번 타고 도달했을 때의 도착시각
- `marked` — 직전 라운드에서 개선된 정류장 집합

**라운드 0**

출발지에서 걸어갈 수 있는 정류장에 `출발시각 + 도보시간` 을 적고 표시합니다.

**라운드 k**

1. 표시된 정류장을 지나는 패턴을 모읍니다. 같은 패턴이 여러 정류장에서 걸리면 가장 앞 위치에서 시작합니다
2. 각 패턴을 그 위치부터 끝까지 훑습니다. 손에 든 차가 있으면 내려 보고, 여기서 더 이른 차를 탈 수 있으면 갈아탑니다
3. 이번 라운드에 도달한 정류장에서 걸어갈 수 있는 곳을 채웁니다
4. 개선된 정류장이 없으면 끝냅니다

2번의 "손에 든 차"가 이 알고리즘의 전부입니다. 패턴을 한 번 훑으면서 타고 있으면 계속 타고, 더 이른 차가 있으면 갈아탑니다.

```{code-cell} python
:tags: [remove-output]

# smartmob/teaching/raptor.py 의 raptor() 를 간추린 것입니다.
INF = float("inf")

def raptor_core(data, origins, departure, max_rounds=5):
    n = data.n_stops
    best = [INF] * n
    rounds = [[INF] * n]

    marked = set()
    for stop, walk in origins:                      # 라운드 0: 접근 도보
        t = departure + walk
        if t < rounds[0][stop]:
            rounds[0][stop] = best[stop] = t
            marked.add(stop)

    for k in range(1, max_rounds + 1):
        prev, cur = rounds[k - 1], list(rounds[k - 1])
        rounds.append(cur)
        new_marked = set()

        queue = {}                                   # 1) 훑을 패턴 모으기
        for stop in marked:
            for pattern_idx, pos in data.routes_by_stop[stop]:
                if pattern_idx not in queue or pos < queue[pattern_idx]:
                    queue[pattern_idx] = pos

        for pattern_idx, start_pos in queue.items():  # 2) 패턴 훑기
            p = data.patterns[pattern_idx]
            trip = None
            for pos in range(start_pos, len(p.stops)):
                stop = p.stops[pos]
                if trip is not None:                  # 내려 보기
                    arrive = p.arrivals[trip][pos]
                    if arrive < best[stop]:
                        best[stop] = cur[stop] = arrive
                        new_marked.add(stop)
                ready = prev[stop]                    # 더 이른 차로 갈아타기
                if ready < INF:
                    cand = p.earliest_trip(pos, int(ready))
                    if cand is not None and (
                        trip is None
                        or p.departures[cand][pos] < p.departures[trip][pos]
                    ):
                        trip = cand

        for stop in list(new_marked):                 # 3) 도보 환승
            for other, seconds in data.transfers[stop]:
                arrive = cur[stop] + seconds
                if arrive < best[other]:
                    best[other] = cur[other] = arrive
                    new_marked.add(other)

        if not new_marked:                            # 4) 더 나아지지 않으면 끝
            break
        marked = new_marked

    return best, rounds
```

돌려 봅니다.

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

**80밀리초에 4,156개 정류장까지의 도착시각을 전부 구했습니다.** 하나가 아니라 전부입니다. 다익스트라로 한 쌍씩 4,156번 물었다면 훨씬 오래 걸립니다.

이것이 RAPTOR 의 성질입니다. 한 번 돌리면 일대다(one-to-all) 답이 나옵니다. 접근성 지도를 그릴 때 이 성질이 그대로 쓰입니다.

## 6.6 경로 복원

도착시각만으로는 부족합니다. 어떤 버스를 타고 어디서 갈아탔는지 알아야 합니다.

라운드마다 "이 정류장에 어떻게 왔는가"를 기록해 두면 거꾸로 따라갈 수 있습니다. 정리된 구현이 그렇게 되어 있습니다.

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

23분 걸립니다. 4장에서 같은 구간을 차로 가면 오전 첨두에 8분이었습니다. 세 배 가까이 차이가 납니다.

내역을 보면 이유가 보입니다. 차에 타 있던 시간은 6.6분뿐이고 도보가 11.2분, 대기가 5.1분입니다. **이동 시간보다 이동하지 않는 시간이 깁니다.** 대중교통 개선이 배차간격 단축과 정류장 접근성에 집중되는 이유입니다.

## 6.7 맞는지 어떻게 아는가

실제 GTFS 로는 답을 손으로 확인할 수 없습니다. 그래서 답을 아는 작은 시간표를 만듭니다.

```
A --(1호선)--> B --(1호선)--> C     1호선  08:00 A → 08:10 B → 08:20 C
               |                            08:30 A → 08:40 B → 08:50 C
           도보 100m
               |
               D --(2호선)--> E     2호선  08:15 D → 08:25 E
```

8시에 A에서 출발하면 C에는 8시 20분에 직통으로 도착합니다. E에는 B에서 내려 D까지 걸어가 2호선을 타야 하므로 8시 25분, 환승 1회입니다.

8시 5분에 출발하면 8시 차를 놓치므로 다음 차를 타고 8시 50분에 도착합니다.

이 세 가지를 `tests/test_raptor.py` 가 확인합니다.

```{code-cell} python
:tags: [skip-execution]

# pytest tests/test_raptor.py -v
# test_toy_direct_ride                        08:20 도착, 환승 0
# test_toy_one_transfer                       08:25 도착, 환승 1
# test_toy_later_departure_takes_second_trip  08:50 도착
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
before_service = raptor(data, origins, 3 * 3600)   # 새벽 3시
print(f"새벽 3시 출발 도달 정류장: {sum(1 for t in before_service.best if t < INF):,}개")
print(f"오전 8시 출발 도달 정류장: {reached:,}개")
```

새벽에는 거의 못 갑니다. 도보로 닿는 정류장에만 표시가 남습니다.

## 정리

- 대중교통은 같은 구간의 비용이 도착 시각에 따라 달라집니다. 그래서 그래프 최단경로를 쓸 수 없습니다
- RAPTOR 는 환승 횟수를 라운드로 삼습니다. 우선순위 큐도 정렬도 없습니다
- GTFS 노선을 그대로 쓰면 안 됩니다. 정류장 순서가 같은 운행끼리 다시 묶어 패턴을 만듭니다. 하남은 운행 8,923개가 패턴 349개로 묶입니다
- 정류장→패턴 역색인과 도보 환승 목록을 미리 만들어 둡니다
- 한 번 돌리면 4,203개 정류장 전부의 도착시각이 80밀리초에 나옵니다
- 하남시청→미사역 오전 8시는 23분입니다. 차내 6.6분, 도보 11.2분, 대기 5.1분입니다
- 검증은 손으로 답을 아는 작은 시간표로 합니다. 실제 피드에서는 불변식만 확인합니다
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

더 나아가, 출발지를 하남시청이 아니라 미사역으로 바꿔 두 지도를 비교해 봅시다.
어느 쪽이 더 넓게 닿나요? 그것이 무엇을 뜻하나요?

산출물: 등시선 지도 2장, 비교 해석 3~4줄.
```
