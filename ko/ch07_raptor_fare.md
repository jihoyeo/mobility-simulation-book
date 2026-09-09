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

# 7장 환승·요금과 대중교통 지표

6장에서 하남시청→미사역이 23분으로 나왔습니다. 그 안에 걷는 시간이 11분, 기다리는 시간이 5분이었습니다.

6장의 계산에는 세 가지 설정값이 들어 있습니다. 허용할 탑승 횟수, 도보로 연결할 정류장 사이의 거리, 통행에 적용할 요금 규칙입니다.

이 장에서는 각 설정값을 바꿔 도달 정류장 수와 통행시간이 어떻게 달라지는지 계산합니다.

## 학습 목표

- 환승 허용 횟수와 도보 환승 거리가 결과에 미치는 영향을 잽니다
- 수도권 통합환승요금을 단순화한 모형을 구현하고 손으로 검산합니다
- 통행시간·차내시간·도보·대기·환승·요금 여섯 지표의 분포를 봅니다
- 평균 하나로는 안 보이는 것을 분포에서 찾아냅니다

## 7.1 환승 몇 번까지

6장의 `max_rounds` 는 5였습니다. 환승 4회까지 허용한다는 뜻입니다. 이 값이 결과를 얼마나 바꿀까요.

```{code-cell} python
from smartmob.data import load_gtfs
from smartmob.teaching.raptor import TransitData, raptor, INF

data = TransitData.from_gtfs(load_gtfs("hanam"))
origins = data.access_stops(37.5393, 127.2148)      # 하남시청

for k in range(1, 6):
    result = raptor(data, origins, 8 * 3600, max_rounds=k)
    reached = sum(1 for t in result.best if t < INF)
    print(f"{k - 1}회 환승까지  {reached:,}개 정류장 도달")
```

환승 없이 도달하는 정류장은 1,679개입니다. 환승을 한 번 허용하면 4,152개, 두 번 허용하면 4,156개가 됩니다. 세 번부터는 이 출발지와 시간에서 더 늘지 않습니다.

하남시청 오전 8시 질의에서는 `max_rounds=2` 이후 도달 정류장 수의 증가가 4개뿐입니다.

```{tip}
대상 지역, 출발지, 출발시각이 달라지면 필요한 라운드 수도 달라질 수 있습니다. 프로젝트에서는 같은 실험으로 `max_rounds` 를 정합니다.
```

## 7.2 도보 환승 몇 미터까지

6장에서 500m로 두었습니다. 이 값을 바꿔 봅니다.

```{code-cell} python
import time

for metres in (200, 500, 1000):
    t0 = time.perf_counter()
    d = TransitData.from_gtfs(load_gtfs("hanam"), max_transfer_m=metres)
    build = time.perf_counter() - t0
    r = raptor(d, d.access_stops(37.5393, 127.2148), 8 * 3600)
    pairs = sum(len(x) for x in d.transfers)
    reached = sum(1 for t in r.best if t < INF)
    print(f"{metres:5d}m  환승 {pairs:7,}쌍  도달 {reached:,}개  (빌드 {build:.1f}초)")
```

200 m에서 1,000 m로 늘리면 환승 쌍은 7,818개에서 92,574개로 늘어납니다. 도달 정류장은 4,147개에서 4,162개로 15개 늘어납니다.

두 설정에서 모두 도달하는 정류장 가운데 1,414개는 1,000 m 설정에서 더 일찍 도착합니다. 개선된 정류장의 도착시각 차이 중앙값은 약 6분입니다. 반면 최대 환승거리가 커질수록 직선거리로만 연결한 환승 쌍도 늘어납니다.

`TransitData.from_gtfs` 의 기본값은 500 m이며, 보행 속도 1.2 m/s와 우회계수 1.35를 적용하면 최대 약 9분입니다.

```{warning}
6장의 도보 환승은 직선거리 기반입니다. 강이나 철길로 막힌 두 정류장의 직선거리가 400 m라면 보행로가 없어도 환승 쌍에 들어갑니다. 최대 거리를 늘릴 때는 보행 네트워크로 연결 여부를 함께 확인해야 합니다.
```

## 7.3 요금

수도권에서는 교통카드로 버스와 지하철을 환승하면 이용 수단과 총 이동거리에 따라 요금을 계산합니다. [서울시 통합환승할인 안내][seoul-fare]를 바탕으로 이 장에서 쓸 단순화 모형을 만듭니다.

이 장의 모형은 다음 세 규칙만 반영합니다.

1. 기본요금은 탄 수단 중 기본요금이 가장 비싼 것 하나만 냅니다
2. 총 이동거리 10km 까지는 기본요금만 냅니다
3. 10km 를 넘으면 5km 마다 100원씩 붙습니다 (GTX 를 탔으면 250원)

버스 1,500원, 도시철도 1,550원, GTX 3,200원이 기본요금입니다.

```{code-cell} python
from smartmob.teaching.fare import BASE_FARE, calc_fare, fare_detail

print("따로 냈다면:", BASE_FARE["BUS"] + BASE_FARE["SUBWAY"], "원")
print("통합요금:  ", calc_fare([{"mode": "BUS", "km": 3.0},
                                 {"mode": "SUBWAY", "km": 4.0}]), "원")
```

예제의 버스 3 km와 지하철 4 km를 합치면 기본거리 10 km 이내입니다. 두 수단 중 기본요금이 더 높은 지하철 요금 1,550원을 반환합니다.

거리가 늘면 어떻게 되는지 봅니다.

```{code-cell} python
for km in (5, 10, 10.1, 15, 15.1, 23):
    d = fare_detail([{"mode": "BUS", "km": km}])
    print(f"{km:5.1f}km  {d['fare']:5,}원   (초과 {d['over_km']:4.1f}km, {d['blocks']}블록)")
```

10km 정확히까지는 1,500원이고, 10.1km부터 한 블록이 붙습니다. **거리는 5km 단위로 올림**합니다. 15.1km와 20km가 같은 요금인 이유입니다.

계산을 풀어 보면 검산할 수 있습니다.

```{code-cell} python
fare_detail([{"mode": "BUS", "km": 4.0}, {"mode": "SUBWAY", "km": 12.0}])
```

버스 4km + 지하철 12km = 16km. 기본요금은 더 비싼 지하철 1,550원. 초과 6km는 5km 블록으로 두 개(올림). 1,550 + 200 = 1,750원입니다.

6장에서 구한 통행에 붙여 봅니다.

```{code-cell} python
from smartmob.teaching.raptor import journey, summarize

result = raptor(data, origins, 8 * 3600)
target = data.nearest_stop(37.5606, 127.1930)
legs = journey(data, result, target)

fare_detail(legs)
```

3.4km 통행이라 기본요금 1,550원입니다. 버스와 지하철을 둘 다 탔지만 한 번만 냅니다.

```{note}
이 구현은 성인 교통카드 기준의 일부 규칙만 담습니다. 버스 유형별 기본거리, 수도권 전철 50 km 이후의 가산 단위, 조조·청소년·어린이 할인은 제외합니다. 하차 태그와 환승 인정 시간도 확인하지 않으므로 실제 청구액을 계산하는 용도로 사용할 수 없습니다.
```

## 7.4 지표 여섯 개의 분포

한 통행만 보면 알 수 없습니다. 도달 가능한 정류장 300개를 뽑아 지표를 모읍니다.

```{code-cell} python
import random
import pandas as pd

rng = random.Random(7)
reachable = [i for i, t in enumerate(result.best) if t < INF]

rows = []
for stop in rng.sample(reachable, 300):
    legs = journey(data, result, stop)
    s = summarize(data, legs, 8 * 3600)
    if s.get("reachable"):
        s["fare"] = calc_fare(legs)
        rows.append(s)

df = pd.DataFrame(rows)
cols = ["total_min", "in_vehicle_min", "walk_min", "wait_min", "transfers", "fare"]
df[cols].describe().round(1)
```

표본의 평균 통행시간은 65.5분, 중앙값은 56.2분입니다. 표준편차는 65.8분이고 최댓값은 1,007.4분입니다.

최댓값은 `명륜3가.성대입구`까지 가는 경로입니다. 오전 8시에 출발해 오후 11시 31분의 N31번을 탈 때까지 기다리면서 대기시간이 856.2분으로 늘어납니다.

```{code-cell} python
long_trips = df[df["total_min"] > 180]
print(f"3시간 넘는 통행 {len(long_trips)}개")
long_trips[["total_min", "wait_min", "in_vehicle_min", "transfers"]].head()
```

3시간을 넘는 통행은 300개 중 7개입니다. 이 표본은 GTFS에 포함된 도달 가능 정류장에서 균등 추출했으며 하남시 주민의 목적지 분포를 반영하지 않습니다. 따라서 65.5분을 하남시 평균 통행시간으로 해석할 수 없습니다.

중앙값과 분위를 봅니다.

```{code-cell} python
for q in (0.25, 0.5, 0.75, 0.9):
    print(f"{q:>5.0%} 분위  {df['total_min'].quantile(q):6.1f}분")
```

이 표본의 중앙값은 56.2분입니다. 평균과 함께 분위수와 3시간 초과 통행 수를 제시해야 분포를 확인할 수 있습니다.

## 7.5 통행시간 구성

통행시간을 셋으로 나눠 봅니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
normal = df[df["total_min"] <= 180]        # 극단값 제외

parts = ["in_vehicle_min", "walk_min", "wait_min"]
labels = ["차내", "도보", "대기"]

fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
for ax, col, label in zip(axes, parts, labels):
    ax.hist(normal[col], bins=25, color="tab:blue", alpha=0.8)
    ax.set_title(f"{label}  중앙값 {normal[col].median():.0f}분", fontsize=11)
    ax.set_xlabel("분")
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_ylabel("통행 수")
fig.tight_layout();
```

3시간 이하 표본에서 차내시간의 분포가 도보시간과 대기시간보다 넓습니다. 이 그림만으로 목적지 거리와 각 시간 요소의 관계를 판단할 수는 없습니다.

```{code-cell} python
share = normal[parts].sum()
for col, label in zip(parts, labels):
    print(f"{label}  {share[col] / share.sum():5.1%}")
```

합계 기준 비중은 차내 72.5%, 도보 14.3%, 대기 13.2%입니다.

## 7.6 환승 횟수와 요금

```{code-cell} python
df["transfers"].value_counts().sort_index()
```

환승 횟수별 표본 수는 0회 24개, 1회 111개, 2회 83개, 3회 45개, 4회 37개입니다.

```{code-cell} python
df.groupby("transfers")[["total_min", "fare"]].median().round(0)
```

통행시간 중앙값은 환승 0회부터 4회까지 각각 38분, 72분, 59분, 47분, 55분입니다. 이 표본에서는 환승 횟수에 따라 단조롭게 늘지 않습니다. 요금 모형도 환승 횟수가 아니라 이용 수단과 총거리를 사용합니다.

## 7.7 실제 엔진과 대조하기

서버가 있으면 같은 출발지·도착지·출발시각의 결과를 나란히 출력할 수 있습니다.

```{code-cell} python
:tags: [skip-execution]

from smartmob import Dtumos

dt = Dtumos()
itineraries = dt.transit_route(
    "hanam",
    origin=(37.5393, 127.2148),
    destination=(37.5606, 127.1930),
    departure_time="08:00",
)
best = min(itineraries, key=lambda x: x["duration_s"])
print(f"DTUMOS 엔진  {best['duration_s'] / 60:.1f}분, 환승 {best['transfers']}회")

mine = summarize(data, legs, 8 * 3600)
print(f"내 RAPTOR    {mine['total_min']:.1f}분, 환승 {mine['transfers']}회")
```

두 결과가 다를 때는 먼저 도착 정류장, 도보 연결, 사용한 시간표와 환승 제한을 비교합니다. 서버 내부의 비용 항목은 API 응답만으로 단정할 수 없습니다.

차이가 작다는 사실만으로 구현이 맞다고 판정할 수는 없습니다. 프로젝트 대조표에는 두 결과의 차이와 함께 입력 조건이 같은지 확인한 내용을 적습니다.

## 이 장의 실습

노트북 `labs/ch07_raptor_fare.ipynb` 를 열어 함께 돌립니다.

통행 300건의 지표 분포를 그리고, 환승 허용 횟수를 늘려 가며 도달 범위가 언제 포화되는지 봅니다.

```bash
jupyter lab labs/ch07_raptor_fare.ipynb
```

## 정리

- 하남시청 오전 8시에는 환승을 한 번 허용할 때 도달 정류장이 1,679개에서 4,152개로 늘어납니다
- 도보 환승 거리를 200 m에서 1,000 m로 늘리면 환승 쌍은 7,818개에서 92,574개로 늘고 도달 정류장은 15개 늘어납니다
- 이 장의 요금 코드는 수도권 통합환승요금 가운데 기본요금과 10 km 초과 거리 가산만 반영합니다
- 도달 정류장 300개 표본의 평균 통행시간은 65.5분, 중앙값은 56.2분입니다
- 3시간 이하 표본의 시간 합계 비중은 차내 72.5%, 도보 14.3%, 대기 13.2%입니다
- 환승 횟수별 통행시간 중앙값은 단조롭게 증가하지 않습니다

## 연습문제

```{admonition} 연습 7.1  ★
:class: tip

`fare_detail` 로 다음 세 통행의 요금을 계산하고, 손으로 검산해 봅시다.

1. 버스만 8km
2. 버스 6km + 지하철 9km
3. 지하철 12km + GTX 20km

산출물: 각 요금과 계산 과정(기본요금 얼마 + 몇 블록 × 얼마).
```

```{admonition} 연습 7.2  ★★
:class: tip

출발지를 하남시청이 아니라 미사역으로 바꿔 같은 300개 표본 분석을 해 봅시다.
어느 쪽이 통행시간 중앙값이 짧고, 어느 쪽이 환승을 덜 하나요?
그 차이가 무엇 때문인지 정류장 주변 노선 수로 설명해 봅시다.

산출물: 두 출발지의 지표 비교표, 차이의 원인에 대한 설명 4~5줄.
```

```{admonition} 연습 7.3  ★★★
:class: tip

지금 요금 계산은 성인 기준이고 환승 제한 시간이 없습니다.
실제 규칙에는 "하차 후 30분 안에 환승해야 할인이 적용된다"는 조건이 있습니다.
`legs` 의 시각 정보를 써서 이 규칙을 넣어 봅시다.
30분을 넘긴 환승은 새 통행으로 보고 기본요금을 다시 받습니다.

300개 표본에서 요금이 달라지는 통행이 몇 개나 되는지 세어 봅시다.

산출물: 구현 코드, 요금이 달라진 통행 수와 평균 증가액, 어떤 통행이 영향을 받는지 설명.
```

[seoul-fare]: https://news.seoul.go.kr/traffic/transfer_discount
