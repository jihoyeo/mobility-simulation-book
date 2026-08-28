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

# 10장 배차와 할당 문제

승객 세 명이 거의 동시에 택시를 부르고, 근처에 빈 차가 세 대 있습니다. 누구에게 어느 차를 보낼까요.

당연해 보이는 답은 "각자 가장 가까운 차"입니다. 그런데 세 사람의 가장 가까운 차가 같은 차일 수 있습니다. 먼저 부른 사람에게 주면 나머지 둘은 멀리 있는 차를 받습니다.

전체를 놓고 보면 더 나은 짝이 있을 수 있습니다. 이 장에서 그 짝을 찾습니다.

## 학습 목표

- 배차를 비용행렬 문제로 정식화합니다
- 탐욕 배차와 할당 문제 해법을 비교하고 차이를 잽니다
- 9장의 ETA 모델을 비용행렬에 넣습니다
- 같은 수학이 물류 배송 경로에도 쓰인다는 것을 확인합니다

## 10.1 비용행렬

문제를 표로 적으면 명확해집니다. 행이 승객, 열이 차량, 칸이 그 차가 그 승객에게 가는 데 걸리는 시간입니다.

```{code-cell} python
import numpy as np
from smartmob.teaching.dispatch import cost_matrix

passengers = [(37.539, 127.215), (37.545, 127.190), (37.552, 127.205)]
vehicles = [(37.541, 127.212), (37.560, 127.198), (37.535, 127.230)]

costs = cost_matrix(passengers, vehicles)
np.round(costs, 2)
```

승객 0은 차량 0이 가장 가깝습니다(0.6분). 승객 1도 차량 0이 가장 가깝습니다(3.7분). 겹칩니다.

```{code-cell} python
for i in range(len(passengers)):
    j = int(costs[i].argmin())
    print(f"승객 {i} 의 최근접 차량: {j} ({costs[i, j]:.2f}분)")
```

## 10.2 탐욕 배차 — 먼저 부른 사람부터

가장 단순한 규칙입니다. 호출 순서대로, 남은 차 중 가장 가까운 것을 줍니다.

```{code-cell} python
from smartmob.teaching.dispatch import greedy_match

result = greedy_match(costs)
for m in result.matches:
    print(f"승객 {m.passenger} ← 차량 {m.vehicle}  {m.cost:.2f}분")
print(f"\n총 대기 {result.total_cost:.2f}분")
```

승객 0이 차량 0을 가져갑니다. 승객 1은 차량 0이 없어졌으므로 차선을 받습니다.

공정해 보입니다. 먼저 부른 사람이 먼저 받으니까요. 그런데 **전체 대기시간의 합**을 보면 더 나은 배치가 있을 수 있습니다.

## 10.3 할당 문제

모든 짝짓기를 다 해 보고 합이 가장 작은 것을 고르면 됩니다. 승객 3명, 차량 3대면 경우의 수가 6가지뿐입니다.

```{code-cell} python
from itertools import permutations

best = min(permutations(range(3)), key=lambda p: sum(costs[i, p[i]] for i in range(3)))
print(f"최선의 짝: {best}, 총 대기 {sum(costs[i, best[i]] for i in range(3)):.2f}분")
```

문제는 규모입니다. 승객이 20명이면 경우의 수가 20 팩토리얼, 약 2조 4천억 가지입니다. 전부 세는 것은 불가능합니다.

다행히 이 문제에는 이름과 해법이 있습니다. **할당 문제(assignment problem)** 이고, 헝가리안 알고리즘으로 다항 시간에 풉니다. `scipy` 가 구현을 제공하므로 직접 짜지 않습니다.

```{code-cell} python
from smartmob.teaching.dispatch import optimal_match

opt = optimal_match(costs)
for m in opt.matches:
    print(f"승객 {m.passenger} ← 차량 {m.vehicle}  {m.cost:.2f}분")
print(f"\n총 대기 {opt.total_cost:.2f}분 (탐욕은 {result.total_cost:.2f}분)")
```

## 10.4 얼마나 차이가 나는가

세 명으로는 감이 안 옵니다. 무작위 상황을 200번 만들어 비교합니다.

```{code-cell} python
import random

rng = random.Random(0)

def random_points(n):
    return [(37.50 + rng.random() * 0.10, 127.13 + rng.random() * 0.14) for _ in range(n)]

gaps = []
for _ in range(200):
    c = cost_matrix(random_points(8), random_points(10))
    g = greedy_match(c)
    o = optimal_match(c)
    assert o.total_cost <= g.total_cost + 1e-9      # 최적해가 더 나쁠 수는 없습니다
    gaps.append((g.total_cost - o.total_cost) / o.total_cost)

print(f"평균 개선 {np.mean(gaps):.1%}")
print(f"최대 개선 {max(gaps):.1%}")
print(f"차이가 없던 경우 {sum(1 for x in gaps if x < 1e-9)}/200")
```

평균 14% 줄어듭니다. 운이 나쁠 때는 79%까지 차이가 납니다.

`assert` 를 넣은 이유가 있습니다. 최적해는 정의상 탐욕보다 나쁠 수 없습니다. 한 번이라도 어긋나면 구현이 틀린 것입니다. 이런 확인을 코드에 박아 두면 나중에 고치다 깨뜨렸을 때 바로 알 수 있습니다.

## 10.5 그런데 최적해가 더 빠릅니다

느릴 것 같지만 재 봅시다.

```{code-cell} python
import time

for n in (10, 50, 200, 500):
    c = cost_matrix(random_points(n), random_points(n))
    t0 = time.perf_counter(); greedy_match(c); tg = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter(); optimal_match(c); to = (time.perf_counter() - t0) * 1000
    print(f"n={n:3d}   탐욕 {tg:7.2f} ms   헝가리안 {to:7.2f} ms")
```

n이 50을 넘으면 헝가리안이 더 빠릅니다.

3장에서 A\*가 다익스트라보다 느렸던 것과 반대 상황입니다. 이유는 같습니다. **구현이 어느 언어로 되어 있는가.** 우리 탐욕 배차는 파이썬 이중 루프이고, `scipy` 의 헝가리안은 C로 짜여 있습니다.

더 좋은 답을 더 빨리 내니 고민할 것이 없습니다. 실제 시뮬레이터의 기본값도 헝가리안입니다.

```{tip}
그래도 탐욕이 필요한 경우가 있습니다. 승객이 수만 명이면 헝가리안도 느려집니다(O(n³)). 그럴 때는 후보를 미리 추려서(각 승객마다 가까운 차 20대만) 행렬을 작게 만듭니다. 실제 엔진의 `dispatch_top_k` 인자가 이것입니다.
```

## 10.6 비용을 무엇으로 잴 것인가

지금까지 비용은 직선거리를 시속 25km로 나눈 값이었습니다. 이게 얼마나 나쁠까요.

세 가지를 비교합니다.

```{code-cell} python
:tags: [remove-output]

import pandas as pd
import lightgbm as lgb
from smartmob.data import data_path, load_road_graph
from smartmob.teaching.eta import FEATURES, TARGET

eta = pd.read_parquet(data_path("hanam/eta_samples.parquet"))
model = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.05, random_state=42, verbose=-1)
model.fit(eta[FEATURES], eta[TARGET])

G = load_road_graph("hanam", modes=("drive",))
```

```{code-cell} python
from smartmob.teaching.dispatch import cost_matrix_from_model, cost_matrix_from_router

rng = random.Random(3)
P, V = random_points(6), random_points(8)

t0 = time.perf_counter(); c_straight = cost_matrix(P, V);                       t_s = time.perf_counter() - t0
t0 = time.perf_counter(); c_model = cost_matrix_from_model(P, V, model.predict); t_m = time.perf_counter() - t0
t0 = time.perf_counter(); c_router = cost_matrix_from_router(P, V, G);           t_r = time.perf_counter() - t0

print(f"직선거리   {t_s * 1000:7.1f} ms")
print(f"ETA 모델   {t_m * 1000:7.1f} ms")
print(f"실제 라우팅 {t_r * 1000:7.1f} ms")
```

라우팅이 압도적으로 느립니다. 6×8=48칸을 채우는 데만 이만큼 걸립니다.

세 방법이 같은 결정을 내리는지 봅니다. 중요한 것은 비용의 절댓값이 아니라 **어느 차를 고르는가**입니다.

```{code-cell} python
choice_straight = optimal_match(c_straight)
choice_model = optimal_match(c_model)
choice_router = optimal_match(c_router)

def pairs(r):
    return {(m.passenger, m.vehicle) for m in r.matches}

print(f"직선거리 vs 라우팅  일치 {len(pairs(choice_straight) & pairs(choice_router))}/{len(pairs(choice_router))}")
print(f"ETA 모델 vs 라우팅  일치 {len(pairs(choice_model) & pairs(choice_router))}/{len(pairs(choice_router))}")
```

실제 라우팅으로 매긴 비용으로 각 결정을 채점해 봅니다.

```{code-cell} python
def score(result):
    return sum(c_router[m.passenger, m.vehicle] for m in result.matches
               if np.isfinite(c_router[m.passenger, m.vehicle]))

print(f"직선거리로 정한 배차의 실제 총 대기  {score(choice_straight):.1f}분")
print(f"ETA 모델로 정한 배차의 실제 총 대기  {score(choice_model):.1f}분")
print(f"라우팅으로 정한 배차의 실제 총 대기  {score(choice_router):.1f}분")
```

라우팅으로 정한 것이 가장 낫습니다. 당연합니다. 자기가 채점하는 기준으로 정했으니까요.

중요한 것은 **ETA 모델이 라우팅에 얼마나 가까운가**입니다. 라우팅의 3천분의 1 시간으로 거의 같은 결정을 내린다면 쓸 만합니다.

## 10.7 같은 문제, 물류

지금 푼 문제를 다시 봅시다. 여러 개의 A와 여러 개의 B를 짝지어 총 비용을 가장 작게 만드는 문제입니다.

물류에서 그대로 나옵니다.

- 창고 3곳과 매장 5곳 사이의 배송량 배정
- 배송기사 10명과 배송 구역 10개의 배정
- 주문 100건과 배송차 20대의 배정

승객을 주문으로, 차량을 배송차로 바꾸기만 하면 같은 코드가 돕니다.

한 가지가 다릅니다. 택시는 한 사람을 태우고 목적지로 갑니다. 배송차는 여러 곳을 차례로 돕니다. 이때 정할 것은 짝짓기가 아니라 **방문 순서**입니다.

배송지 12곳을 도는 가장 짧은 순서를 찾아봅시다. 외판원 문제(TSP)입니다.

```{code-cell} python
from smartmob.teaching.dispatch import nearest_neighbour, route_length_km, two_opt

stops = random_points(12)

naive = list(range(12))                      # 주어진 순서 그대로
nn = nearest_neighbour(stops)                # 가장 가까운 곳부터
improved = two_opt(stops, nn)                # 교차하는 구간을 뒤집어 개선

for label, order in [("무작정", naive), ("최근접 이웃", nn), ("2-opt", improved)]:
    print(f"{label:10s} {route_length_km(stops, order):6.2f} km")
```

가장 가까운 곳부터 도는 것만으로도 크게 줄고, 2-opt로 한 번 더 줄어듭니다.

2-opt는 단순합니다. 경로에서 두 지점을 골라 그 사이를 뒤집어 봅니다. 짧아지면 채택하고, 더 이상 짧아지지 않을 때까지 반복합니다. 경로가 스스로 교차하는 부분을 푸는 효과가 있습니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
for ax, (label, order) in zip(axes, [("최근접 이웃", nn), ("2-opt", improved)]):
    seq = order + [order[0]]
    ax.plot([stops[i][1] for i in seq], [stops[i][0] for i in seq],
            "-o", color="tab:blue", markersize=5, linewidth=1.2)
    ax.scatter(stops[order[0]][1], stops[order[0]][0], s=90, color="tab:red", zorder=3)
    ax.set_title(f"{label}  {route_length_km(stops, order):.1f} km")
    ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect(1 / 0.79)
fig.tight_layout();
```

왼쪽 그림에서 선이 교차하는 곳이 보입니다. 오른쪽에서는 풀렸습니다.

```{note}
차량이 여러 대이고 각 차에 적재 한계가 있으면 차량경로 문제(VRP)가 됩니다. 실무에서는 Google OR-Tools 같은 전용 솔버를 씁니다. 원리는 여기서 본 것과 같습니다. 좋은 해를 하나 만들고, 조금씩 바꿔 가며 개선합니다.
```

## 10.8 배차가 시뮬레이션 안에서 도는 자리

지금까지 만든 것은 "한 순간의 배차"입니다. 시뮬레이션은 이것을 1분마다 반복합니다.

```
매 분마다:
    1. 이번 분에 도착한 호출을 대기 목록에 넣는다
    2. 도착한 차량을 빈 차 목록으로 옮긴다
    3. 대기 승객과 빈 차가 둘 다 있으면 → 비용행렬을 만들고 배차한다
    4. 배차된 차를 승객 쪽으로 보낸다
    5. 기록을 남긴다
```

3번이 이 장에서 만든 것입니다. 나머지를 11장에서 만듭니다.

## 정리

- 배차는 비용행렬 문제입니다. 행이 승객, 열이 차량, 칸이 도착 예상시간입니다
- 탐욕 배차는 먼저 부른 사람부터 가장 가까운 차를 줍니다. 단순하지만 전체로는 손해입니다
- 할당 문제로 풀면 총 대기시간이 평균 14% 줄고, 나쁠 때는 79%까지 차이가 납니다
- 헝가리안은 `scipy` 구현이라 파이썬 탐욕보다 오히려 빠릅니다. n=50부터 역전됩니다
- 비용을 무엇으로 재느냐가 결정을 바꿉니다. 직선거리는 싸지만 강 건너 차를 고릅니다
- 같은 할당 문제가 물류 배정에 그대로 쓰이고, 여러 곳을 도는 문제는 TSP·VRP가 됩니다
- 11장에서 이 배차를 시간 축 위에서 반복시킵니다

## 연습문제

```{admonition} 연습 10.1  ★
:class: tip

`greedy_match` 의 처리 순서를 바꿔 봅시다.
호출 순서 대신 (a) 가장 가까운 차가 있는 승객부터, (b) 가장 먼 승객부터 처리하면
총 대기시간이 어떻게 달라지나요?

산출물: 세 가지 순서의 총 대기시간 비교(무작위 100회 평균), 어느 쪽이 나은지와 그 이유.
```

```{admonition} 연습 10.2  ★★
:class: tip

10.5절에서 "후보를 추려 행렬을 작게 만든다"고 했습니다. 직접 해 봅시다.
각 승객마다 직선거리 기준 가까운 차 `k` 대만 남기고 나머지는 무한대로 두는
`top_k` 가지치기를 구현합니다.

`k` 를 1, 3, 5, 10, 전체로 바꿔 가며 (a) 총 대기시간, (b) 계산 시간, (c) 미배차 승객 수를
재 봅시다. 승객 200명, 차량 200대로 실험합니다.

산출물: k별 세 지표 표, 적정 k 와 그 근거 3줄.
```

```{admonition} 연습 10.3  ★★★
:class: tip

지금 배차는 **대기시간의 합**을 최소로 만듭니다. 다른 목적도 가능합니다.

(a) 최대 대기시간을 가장 작게 (아무도 오래 기다리지 않게)
(b) 대기시간이 10분을 넘는 승객 수를 가장 적게

두 목적을 각각 어떻게 풀지 생각해 보고, 하나를 구현해 봅시다.
(a)는 이분 탐색 + 실행 가능성 검사로, (b)는 비용을 다시 정의해 풀 수 있습니다.

세 목적이 만드는 결과가 어떻게 다른지 비교합니다.

산출물: 구현 코드, 세 목적의 결과 비교표(총·평균·최대 대기, 10분 초과 인원), 해석 4~5줄.
```
