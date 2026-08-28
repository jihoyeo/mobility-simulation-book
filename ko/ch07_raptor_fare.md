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

그런데 그 계산에는 정하지 않고 넘어간 값이 몇 개 있습니다. 환승을 몇 번까지 허용할 것인가. 정류장 사이 몇 미터까지를 걸어서 갈아탈 수 있다고 볼 것인가. 그리고 그 통행에 요금은 얼마인가.

이 장에서 그 값들을 정하고, 정한 값이 결과를 얼마나 바꾸는지 봅니다.

## 학습 목표

- 환승 허용 횟수와 도보 환승 거리가 결과에 미치는 영향을 잽니다
- 수도권 통합환승요금을 구현하고 손으로 검산합니다
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

환승 없이 갈 수 있는 곳은 1,679개입니다. **한 번 갈아타면 4,152개로 뜁니다.** 두 번째 환승부터는 4개밖에 늘지 않습니다.

하남처럼 좁은 지역에서는 환승 한 번이면 거의 다 갑니다. 그래서 `max_rounds` 를 크게 잡아도 계산만 늘고 얻는 게 없습니다.

```{tip}
서울 전체나 수도권으로 넓히면 사정이 달라집니다. 파일럿 프로젝트에서 대상지를 정한 뒤에는 이 실험을 먼저 해 보고 `max_rounds` 를 정하세요. 값을 아무렇게나 두는 것보다 재 보고 두는 편이 낫습니다.
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

200m에서 1,000m로 늘리면 환승 쌍이 12배가 되는데 도달 정류장은 15개 늘 뿐입니다.

그런데 늘어난 것은 "도달 여부"가 아니라 도착 시각입니다. 더 먼 환승을 허용하면 더 빠른 조합이 생깁니다. 대신 실제로는 걷기 힘든 환승이 섞입니다. 1km를 걸어 갈아타라고 안내하는 앱은 아무도 쓰지 않습니다.

500m는 도보 7분 남짓입니다. 이 정도가 사람이 실제로 감수하는 선입니다.

```{warning}
6장에서 말했듯 우리 도보 환승은 직선거리 기반입니다. 강이나 철길로 막힌 두 정류장이 직선 400m면 환승이 생깁니다. 이 오류는 500m를 1km로 늘릴수록 심해집니다. 거리를 늘리려면 보행 네트워크로 실제 경로를 확인해야 합니다.
```

## 7.3 요금

한국 대중교통 요금은 "타는 횟수 × 기본요금"이 아닙니다. **수도권 통합환승요금**이라고 부르는 거리 비례 방식입니다.

규칙은 세 줄입니다.

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

버스를 타고 지하철로 갈아타도 1,550원 한 번만 냅니다. 이것이 통합요금의 핵심입니다.

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
이 구현은 성인 카드 기준이고 광역버스 할증, 심야 할증, 청소년·어린이 할인, 30분 환승 제한 시간을 넣지 않았습니다. 실제 요금과 몇백 원 차이가 날 수 있습니다. 파일럿 프로젝트에서 요금을 주요 지표로 쓸 거라면 규칙을 더 넣어야 합니다.
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

평균 통행시간이 65분입니다. 그런데 표준편차가 66분이고 최댓값이 1,007분입니다. **16시간짜리 통행이 있습니다.**

이건 오류가 아닙니다. 아침 8시에 출발해서 그 정류장까지 가려면 다음 날 첫차를 기다려야 하는 경우입니다. 하루에 몇 번 안 다니는 시외 노선의 종점 같은 곳입니다.

```{code-cell} python
long_trips = df[df["total_min"] > 180]
print(f"3시간 넘는 통행 {len(long_trips)}개")
long_trips[["total_min", "wait_min", "in_vehicle_min", "transfers"]].head()
```

대기시간이 대부분입니다. 이런 값이 섞이면 평균이 망가집니다. 분포를 보지 않고 평균만 보고했다면 "하남시 평균 통행시간 65분"이라는 틀린 결론을 냈을 것입니다.

중앙값과 분위를 봅니다.

```{code-cell} python
for q in (0.25, 0.5, 0.75, 0.9):
    print(f"{q:>5.0%} 분위  {df['total_min'].quantile(q):6.1f}분")
```

중앙값 56분이 훨씬 대표적입니다.

## 7.5 무엇이 시간을 잡아먹는가

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

차내시간은 넓게 퍼져 있고 도보와 대기는 좁게 몰려 있습니다. 목적지가 멀수록 차내시간이 늘지만, 걷는 시간과 기다리는 시간은 어디를 가든 비슷하다는 뜻입니다.

```{code-cell} python
share = normal[parts].sum()
for col, label in zip(parts, labels):
    print(f"{label}  {share[col] / share.sum():5.1%}")
```

차내가 3분의 2, 나머지 3분의 1이 걷고 기다리는 시간입니다.

이 숫자가 정책으로 이어집니다. 버스를 빠르게 하는 것(차내시간 단축)과 배차를 촘촘히 하는 것(대기시간 단축) 중 어느 쪽이 나은가. 대기시간 비중이 이 정도면 배차 개선의 여지가 큽니다. 프로젝트에서 개선 시나리오를 고를 때 이 분해를 근거로 삼으세요.

## 7.6 환승 횟수와 요금

```{code-cell} python
df["transfers"].value_counts().sort_index()
```

환승 0회가 24개뿐입니다. 대부분 한 번에서 세 번 갈아탑니다.

```{code-cell} python
df.groupby("transfers")[["total_min", "fare"]].median().round(0)
```

환승이 늘수록 통행시간은 길어지는데 요금은 거의 그대로입니다. 통합요금이므로 거리에만 반응하기 때문입니다.

## 7.7 실제 엔진과 대조하기

서버가 있으면 우리 구현과 맞춰 볼 수 있습니다.

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

값이 정확히 같지는 않습니다. 실제 엔진은 도보 환승을 보행 네트워크로 계산하고, 승하차에 걸리는 시간을 더하고, 환승 저항(갈아타기 싫어하는 정도)을 비용에 넣기 때문입니다.

**중요한 것은 얼마나 다른가입니다.** 5분 차이면 우리 구현이 대체로 맞습니다. 30분 차이가 나면 어딘가 틀렸습니다. 파일럿 프로젝트에서 이 대조표를 제출합니다.

## 정리

- 하남에서는 환승 한 번이면 도달 정류장이 1,679개에서 4,152개로 늡니다. 두 번째부터는 거의 늘지 않습니다
- 도보 환승 거리를 200m→1km로 늘리면 환승 쌍이 12배가 되지만 도달 정류장은 거의 그대로입니다. 대신 걷기 힘든 환승이 섞입니다
- 수도권 통합환승요금은 "가장 비싼 기본요금 한 번 + 10km 초과분 5km당 100원"입니다
- 도달 가능한 300곳의 평균 통행시간은 65분인데 중앙값은 56분입니다. 16시간짜리 통행이 평균을 끌어올립니다
- 통행시간의 3분의 1이 걷고 기다리는 시간입니다. 배차 개선의 여지가 여기 있습니다
- 환승이 늘어도 요금은 거의 그대로입니다. 통합요금은 거리에만 반응합니다
- 8장에서 통행 수요를 다룹니다. 지금까지는 한 사람의 경로였고, 이제 수천 명을 만듭니다

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
