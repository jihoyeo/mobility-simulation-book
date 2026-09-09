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

여러 요청을 여러 빈 차량에 동시에 배정하려면 요청마다 차량 한 대를 선택해야 합니다. 각 요청을 따로 처리하면 같은 차량이 여러 요청의 최근접 차량일 때 처리 순서에 따라 결과가 달라집니다.

이 장에서는 요청과 차량 사이의 픽업 시간을 비용행렬로 만들고, 처리 순서에 따른 탐욕 배차와 총비용을 최소화하는 할당 문제 해법을 비교합니다.

## 학습 목표

- 배차를 비용행렬 문제로 정식화합니다
- 탐욕 배차와 할당 문제 해법을 비교하고 차이를 잽니다
- 9장의 ETA 모델을 비용행렬에 넣습니다
- 같은 수학이 물류 배송 경로에도 쓰인다는 것을 확인합니다

## 10.1 비용행렬

비용행렬의 행은 승객, 열은 차량이며 각 칸에는 해당 차량의 픽업 소요시간이 들어갑니다.

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

승객 0에게 차량 0을 배정하면 이후 승객은 남은 차량 중에서 선택합니다. 입력 순서가 앞선 요청을 먼저 처리하지만, 전체 픽업 시간의 합을 최소화하지는 않습니다.

## 10.3 할당 문제

모든 짝짓기를 다 해 보고 합이 가장 작은 것을 고르면 됩니다. 승객 3명, 차량 3대면 경우의 수가 6가지뿐입니다.

```{code-cell} python
from itertools import permutations

best = min(permutations(range(3)), key=lambda p: sum(costs[i, p[i]] for i in range(3)))
print(f"최선의 짝: {best}, 총 대기 {sum(costs[i, best[i]] for i in range(3)):.2f}분")
```

승객과 차량이 각각 20이면 일대일 배정은 20!, 약 243경 가지입니다. 완전탐색으로 모두 계산할 수 없는 규모입니다.

이 문제를 선형합 할당 문제(linear sum assignment problem)라고 합니다. `scipy.optimize.linear_sum_assignment`는 수정 Jonker–Volgenant 알고리즘으로 최적 배정을 계산합니다.[^scipy-lsa]

```{code-cell} python
from smartmob.teaching.dispatch import optimal_match

opt = optimal_match(costs)
for m in opt.matches:
    print(f"승객 {m.passenger} ← 차량 {m.vehicle}  {m.cost:.2f}분")
print(f"\n총 대기 {opt.total_cost:.2f}분 (탐욕은 {result.total_cost:.2f}분)")
```

## 10.4 무작위 표본의 총비용 차이

승객 8명과 차량 10명의 위치를 무작위로 생성한 200개 비용행렬에서 두 방법을 비교합니다.

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

200개 표본에서 탐욕 배차의 총비용은 최적해보다 평균 14.4% 높고, 가장 큰 차이는 78.8%입니다. 이 수치는 위 좌표 범위와 표본 크기에서 나온 결과입니다.

두 방법을 같은 비용행렬에서 비교하면 최적해의 총비용은 탐욕 배차보다 클 수 없습니다. `assert`는 이 조건을 매 표본에서 확인합니다.

## 10.5 구현별 실행시간

정사각 비용행렬의 크기를 바꿔 두 구현의 실행시간을 측정합니다.

```{code-cell} python
import time

for n in (10, 50, 200, 500):
    c = cost_matrix(random_points(n), random_points(n))
    t0 = time.perf_counter(); greedy_match(c); tg = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter(); optimal_match(c); to = (time.perf_counter() - t0) * 1000
    print(f"n={n:3d}   탐욕 {tg:7.2f} ms   SciPy 할당 {to:7.2f} ms")
```

이 실행에서는 50×50부터 SciPy 할당 해법이 더 빠릅니다. 탐욕 배차는 파이썬 반복문이고 SciPy 해법은 컴파일된 구현입니다. 따라서 알고리즘의 점근 복잡도만으로 이 구간의 실행시간을 설명할 수 없습니다. 교차 지점은 하드웨어와 라이브러리 버전에 따라 달라집니다.

```{tip}
문제 규모가 커지면 비용행렬을 만들고 최적 배정을 구하는 시간도 늘어납니다. 가까운 차량만 후보로 남기거나 공간을 나누면 행렬 크기를 줄일 수 있지만, 제외한 배정에 더 낮은 총비용이 있을 수 있습니다.
```

## 10.6 픽업 소요시간 계산 방법

지금까지 비용은 직선거리를 시속 25km로 나눈 값이었습니다.

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

G = load_road_graph(
    "hanam", modes=("drive",), speed_column="weekday_pm_peak_p50"
)
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
print(f"도로망 라우팅 {t_r * 1000:7.1f} ms")
```

출력은 48개 조합을 한 번에 예측한 시간과 다익스트라를 48번 실행한 시간을 비교합니다. 도로망 적재와 모델 학습 시간은 포함하지 않습니다.

세 비용행렬로 각각 배정한 뒤, 18시 도로망 비용으로 만든 배정과 일치하는 쌍의 수를 셉니다.

```{code-cell} python
choice_straight = optimal_match(c_straight)
choice_model = optimal_match(c_model)
choice_router = optimal_match(c_router)

def pairs(r):
    return {(m.passenger, m.vehicle) for m in r.matches}

print(f"직선거리 vs 라우팅  일치 {len(pairs(choice_straight) & pairs(choice_router))}/{len(pairs(choice_router))}")
print(f"ETA 모델 vs 라우팅  일치 {len(pairs(choice_model) & pairs(choice_router))}/{len(pairs(choice_router))}")
```

도로망 라우팅 비용으로 각 배정의 총비용을 계산합니다.

```{code-cell} python
def score(result):
    return sum(c_router[m.passenger, m.vehicle] for m in result.matches
               if np.isfinite(c_router[m.passenger, m.vehicle]))

print(f"직선거리로 정한 배차의 실제 총 대기  {score(choice_straight):.1f}분")
print(f"ETA 모델로 정한 배차의 실제 총 대기  {score(choice_model):.1f}분")
print(f"라우팅으로 정한 배차의 실제 총 대기  {score(choice_router):.1f}분")
```

라우팅 비용을 최소화한 배정은 같은 비용으로 채점할 때 가장 작습니다. 직선거리와 ETA 모델을 쓸지는 여러 배차 시점에서 배정 일치율, 라우팅 기준 총비용 차이, 계산시간을 함께 측정해 판단합니다. 한 개의 6×8 예제로 일반적인 성능을 결론 내릴 수 없습니다.

## 10.7 같은 문제, 물류

지금 푼 문제를 다시 봅시다. 여러 개의 A와 여러 개의 B를 짝지어 총 비용을 가장 작게 만드는 문제입니다.

일대일 할당이 필요한 물류 작업에도 같은 형식을 쓸 수 있습니다.

- 배송기사와 당일 담당 구역의 배정
- 한 번에 한 건씩 처리하는 주문과 배송차의 배정
- 작업과 장비의 배정

차량 한 대가 여러 배송지를 방문하는 순서를 정하는 문제는 외판원 문제(TSP)입니다. 다음 예제에서는 배송지 12곳의 순서를 계산합니다.

```{code-cell} python
from smartmob.teaching.dispatch import nearest_neighbour, route_length_km, two_opt

stops = random_points(12)

naive = list(range(12))                      # 주어진 순서 그대로
nn = nearest_neighbour(stops)                # 가장 가까운 곳부터
improved = two_opt(stops, nn)                # 교차하는 구간을 뒤집어 개선

for label, order in [("무작정", naive), ("최근접 이웃", nn), ("2-opt", improved)]:
    print(f"{label:10s} {route_length_km(stops, order):6.2f} km")
```

이 표본에서는 주어진 순서, 최근접 이웃, 2-opt 순서로 경로 길이가 줄어듭니다. 최근접 이웃과 2-opt는 휴리스틱이므로 모든 입력에서 최적 경로를 보장하지 않습니다.

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

두 그림은 최근접 이웃 경로와 2-opt를 적용한 경로를 비교합니다.

```{note}
차량이 여러 대이고 적재량이나 시간창 같은 제약이 있으면 차량경로 문제(VRP)가 됩니다. 할당 문제보다 변수와 제약이 늘어나므로 별도의 모형과 해법이 필요합니다.
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

## 이 장의 실습

노트북 `labs/ch10_dispatch.ipynb` 를 열어 함께 돌립니다.

작은 비용행렬의 모든 배정을 열거해 SciPy 할당 해법의 반환값과 비교합니다.

```bash
jupyter lab labs/ch10_dispatch.ipynb
```

## 정리

- 배차는 비용행렬 문제입니다. 행이 승객, 열이 차량, 칸이 도착 예상시간입니다
- 탐욕 배차는 입력 순서대로 남은 차량 중 비용이 가장 작은 차량을 선택합니다
- 이 장의 무작위 표본에서 탐욕 배차의 총비용은 최적해보다 평균 14.4% 높았습니다
- 실행시간의 교차 지점은 구현과 실행 환경에 따라 달라집니다
- 비용 산정 방법은 배정 결과를 바꿀 수 있으므로 같은 시간대의 라우팅 결과와 비교합니다
- 일대일 배정은 할당 문제이고, 여러 배송지의 방문 순서를 정하는 문제는 TSP·VRP입니다
- 11장에서 이 배차를 시간 축 위에서 반복시킵니다

## 연습문제

```{admonition} 연습 10.1  ★
:class: tip

`greedy_match` 의 처리 순서를 바꿔 봅시다.
호출 순서 대신 (a) 가장 가까운 차가 있는 승객부터, (b) 가장 먼 승객부터 처리하면
세 처리 순서의 총 대기시간을 비교합니다.

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

두 목적의 풀이 방법을 정리하고 하나를 구현합니다.
(a)는 이분 탐색 + 실행 가능성 검사로, (b)는 비용을 다시 정의해 풀 수 있습니다.

세 목적함수의 결과를 같은 지표로 비교합니다.

산출물: 구현 코드, 세 목적의 결과 비교표(총·평균·최대 대기, 10분 초과 인원), 해석 4~5줄.
```

[^scipy-lsa]: [SciPy `linear_sum_assignment` 문서](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html)
