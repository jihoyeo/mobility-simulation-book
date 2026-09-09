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

# 8장 통행 수요와 수요 생성기

0장에서는 출발 시각과 출발지·목적지가 적힌 하남시 호출 1,000건을 입력으로 사용했습니다. 이 요청 목록이 통행 수요입니다. 이 장에서는 집계 O-D 자료를 읽고 시뮬레이션용 요청 목록을 만드는 방법을 다룹니다.

## 학습 목표

- 수도권 생활이동 O-D 데이터를 읽고 시간대·공간 패턴을 뽑습니다
- 시뮬레이터가 받는 수요 형식(컬럼 다섯 개)을 압니다
- 수요 생성기의 세 단계를 비교하고 각각이 무엇을 개선하는지 설명합니다
- 실제 데이터에서 뽑은 시간대 프로파일로 수요를 만듭니다

## 8.1 O-D 데이터

통행 수요는 흔히 O-D 표로 정리합니다. 출발지(Origin), 목적지(Destination), 통행량을 한 행에 기록합니다.

예제 파일은 서울시와 KT가 개발한 수도권 생활이동 자료에서 출발지나 목적지가 하남시인 행을 추린 것입니다. 원자료는 이동 인구를 행정동과 시간대별로 집계해 제공합니다.[^living-mobility]

```{code-cell} python
import pandas as pd
from smartmob.data import data_path

od = pd.read_parquet(data_path("hanam/od_2024.parquet"))
print(f"{len(od):,}행")
od.head(3)
```

컬럼은 여섯 개입니다.

| 컬럼 | 뜻 |
|---|---|
| `O_ADMDONG_CD` | 출발 행정동 코드 |
| `D_ADMDONG_CD` | 도착 행정동 코드 |
| `ST_TIME_CD` | 출발 시간대 (0~23시) |
| `CNT` | 통행량 (명). 소수점이 있는 것은 추정치이기 때문입니다 |
| `MOVE_DIST` | 평균 이동거리 (m) |
| `MOVE_TIME` | 평균 이동시간 (초) |

행 하나에는 행정동 O-D 한 쌍의 시간대별 통행량과 평균 이동거리·이동시간이 들어 있습니다. 개인별 이동 기록은 없습니다.

```{code-cell} python
od[["CNT", "MOVE_DIST", "MOVE_TIME"]].describe().round(0)
```

이동거리 중앙값이 5.2km, 이동시간 중앙값이 1,223초(20분)입니다.

```{note}
이 자료만으로는 개인의 정확한 출발 시각과 위치를 알 수 없습니다. 시뮬레이터에 넣으려면 집계 통행량을 개별 요청으로 변환하고, 각 요청의 시각과 좌표를 따로 정해야 합니다. 8.4절부터 그 형식을 확인합니다.
```

## 8.2 시간대 패턴

시간대별 통행량을 봅니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
by_hour = od.groupby("ST_TIME_CD")["CNT"].sum()

fig, ax = plt.subplots(figsize=(9, 3.6))
ax.bar(by_hour.index, by_hour.values, color="tab:blue", width=0.7)
ax.set_xlabel("출발 시각 (시)"); ax.set_ylabel("통행량 (명)")
ax.set_xticks(range(0, 24, 2))
ax.grid(axis="y", alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

통행량은 오전 8시에 가장 많고, 17시와 18시가 그다음입니다. 이 자료만으로 개별 통행의 목적을 확인할 수는 없지만, 일반적인 출퇴근 시간대와 겹칩니다.

```{code-cell} python
top = by_hour.sort_values(ascending=False).head(5)
for hour, count in top.items():
    print(f"{hour:2d}시  {count:>9,.0f}명")
```

새벽 3~4시가 가장 낮습니다. 0장에서 저녁 6시부터 자정까지만 돌린 이유가 여기 있습니다. 오후 첨두를 포함하면서 여섯 시간이면 끝나기 때문입니다.

## 8.3 공간 패턴

하남에서 출발한 통행이 어디로 가는지 봅니다. 행정동 코드는 여덟 자리입니다. 앞 다섯 자리가 시군구, 뒤 세 자리가 동이므로 1000으로 나눈 몫이 시군구 코드입니다. 통행량이 많은 시군구 여덟 개만 이름을 붙이고 나머지는 기타로 묶습니다.

```{code-cell} python
SIGUNGU = {
    41450: "하남시", 11740: "강동구", 11710: "송파구", 11680: "강남구",
    41360: "남양주시", 41131: "성남 중원구", 41610: "광주시", 11215: "광진구",
}

from_hanam = od[od["O_ADMDONG_CD"] // 1000 == 41450].copy()
from_hanam["목적지"] = (from_hanam["D_ADMDONG_CD"] // 1000).map(SIGUNGU).fillna("기타")

dest = from_hanam.groupby("목적지")["CNT"].sum().sort_values(ascending=False)
(dest / dest.sum() * 100).round(1).head(8)
```

하남 출발 통행량의 54%는 목적지도 하남입니다. 나머지 46%는 하남 밖으로 이동합니다.

하남시 경계 안만 모델링하면 하남에서 출발해 다른 시군구로 가는 통행을 제외하게 됩니다. 분석 범위는 다루려는 통행과 사용할 수 있는 도로망 범위를 함께 고려해 정합니다.

```{code-cell} python
inside = from_hanam[from_hanam["D_ADMDONG_CD"] // 1000 == 41450]
print(f"하남 출발 총 통행  {from_hanam['CNT'].sum():>10,.0f}명")
print(f"하남 안에서 끝남   {inside['CNT'].sum():>10,.0f}명 ({inside['CNT'].sum() / from_hanam['CNT'].sum():.0%})")
print(f"하남 행정동 수     {from_hanam['O_ADMDONG_CD'].nunique():>10}개")
```

하루 57만 건 중 31만 건이 하남 안에서 끝납니다. 이 31만 건이 행정동 14개 사이를 오갑니다.

## 8.4 시뮬레이터가 받는 형식

시뮬레이터는 집계표 대신 요청별 목록을 받습니다. 필수 컬럼은 다섯 개입니다.

```{code-cell} python
from smartmob.data import DEMAND_COLUMNS, load_demand

print(DEMAND_COLUMNS)
demand = load_demand("hanam")
demand.head(3)
```

`request_time`은 자정부터 지난 분입니다. 예를 들어 1080은 18:00입니다. `validate_demand`는 값이 0~1440 범위인지 검사해 초 단위 값을 잘못 넣은 경우를 찾습니다.

```{code-cell} python
from smartmob.data import validate_demand
from smartmob.data.demand import DemandFormatError

validate_demand(demand)
print("계약 통과")

bad = demand.copy()
bad["request_time"] = bad["request_time"] * 60      # 분을 초로 잘못 넣은 경우
try:
    validate_demand(bad)
except DemandFormatError as exc:
    print("\n걸림:", str(exc).splitlines()[0])
```

위경도를 뒤바꿔 넣는 실수도 잡습니다.

```{code-cell} python
swapped = demand.copy()
swapped[["origin_lat", "origin_lon"]] = swapped[["origin_lon", "origin_lat"]].values
try:
    validate_demand(swapped)
except DemandFormatError as exc:
    print("걸림:", str(exc).splitlines()[0])
```

## 8.5 수요 만들기 1단계 — 경계 안에 균등하게

개인 단위 위치가 없을 때는 행정구역 경계 안에서 출발지와 목적지를 표집할 수 있습니다. 먼저 경계 내부의 모든 위치가 같은 확률을 갖도록 점을 뽑습니다.

```{code-cell} python
import geopandas as gpd
from smartmob.teaching.demand_gen import generate_demand

boundary = gpd.read_file(data_path("hanam/boundary.geojson")).geometry.iloc[0]
uniform = generate_demand(boundary=boundary, n=800, seed=1, hourly=None)   # hourly=None: 시각을 균등하게 뽑습니다
uniform.head(3)
```

지도에 찍어 봅니다.

```{code-cell} python
fig, ax = plt.subplots(figsize=(6, 5.5))
gpd.GeoSeries([boundary]).plot(ax=ax, facecolor="none", edgecolor="gray", linewidth=0.8)
ax.scatter(uniform["origin_lon"], uniform["origin_lat"], s=6, alpha=0.5, color="tab:red")
ax.set_title("경계 안 균등 샘플링"); ax.set_xticks([]); ax.set_yticks([])
ax.set_aspect(1 / 0.79)
fig.tight_layout();
```

이 방법은 토지 이용과 도로 접근성을 구분하지 않습니다. 따라서 하천이나 산지처럼 실제 호출이 드문 곳에도 점이 생깁니다.

## 8.6 수요 만들기 2단계 — 도로 위에

두 번째 방법은 2장에서 만든 자동차 도로망의 엣지 위에서 위치를 뽑습니다. 각 엣지는 직선 길이에 비례하는 확률로 선택합니다.

```{code-cell} python
from smartmob.data import load_road_graph

G = load_road_graph("hanam", modes=("drive",))
on_road = generate_demand(graph=G, n=800, seed=1, hourly=None)

fig, ax = plt.subplots(figsize=(6, 5.5))
gpd.GeoSeries([boundary]).plot(ax=ax, facecolor="none", edgecolor="gray", linewidth=0.8)
ax.scatter(on_road["origin_lon"], on_road["origin_lat"], s=6, alpha=0.5, color="tab:blue")
ax.set_title("도로 위 샘플링"); ax.set_xticks([]); ax.set_yticks([])
ax.set_aspect(1 / 0.79)
fig.tight_layout();
```

점은 도로가 있는 위치에만 놓이고, 도로 총연장이 긴 구역에 더 많이 배정됩니다.

이 방식도 토지 이용이나 실제 승하차 기록을 반영하지 않습니다. 자동차 전용도로나 주거 인구가 적은 구간에도 수요가 생길 수 있으며, 출발지와 목적지를 독립적으로 뽑기 때문에 실제 O-D 분포와도 다릅니다.

## 8.7 수요 만들기 3단계 — 시간대 프로파일

지금까지는 지정한 시간 범위 안에서 출발 시각을 균등하게 뽑았습니다. 다음에는 O-D 자료에서 계산한 시간대별 통행 비중을 사용합니다.

```{code-cell} python
from smartmob.teaching.demand_gen import hourly_profile_from_od

profile = hourly_profile_from_od(od)
for hour in (3, 8, 12, 17, 22):
    print(f"{hour:2d}시  {profile[hour]:.1%}")
```

하루 통행의 7.9%가 8시대에 몰리고 3시대는 0.6%입니다. 열세 배 차이입니다. 이 비율대로 호출 시각을 뽑습니다.

이 프로파일을 넣고 하루치를 만듭니다.

```{code-cell} python
realistic = generate_demand(
    graph=G, n=3000, time_range=(0, 1440), seed=42, hourly=profile
)

fig, ax = plt.subplots(figsize=(9, 3.4))
ax.hist(realistic["request_time"] / 60, bins=48, color="tab:blue")
ax.set_xlabel("호출 시각 (시)"); ax.set_ylabel("호출 수")
ax.set_xticks(range(0, 25, 2))
ax.grid(axis="y", alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
ax.set_title("시간대 프로파일을 반영한 수요 3,000건")
fig.tight_layout();
```

생성된 요청의 시간대별 분포가 원자료의 비중을 따릅니다. 무작위 표집이므로 요청 수가 적을수록 원자료 비중과 차이가 커질 수 있습니다.

시간만 실제 데이터를 따랐습니다. 공간은 여전히 도로 길이에 비례해 뽑았고, 8.3절에서 본 O-D 쌍은 쓰지 않았습니다. 출발지와 목적지를 쌍으로 뽑는 것은 연습 8.2 입니다.

```{code-cell} python
from smartmob.data import validate_demand

validate_demand(realistic)
print(f"{len(realistic):,}건, 계약 통과")
realistic.head(3)
```

만든 수요도 실제 수요와 같은 다섯 컬럼이고 같은 검사를 통과합니다. 8.8절에서 이 표를 그대로 서버에 올립니다.

## 8.8 만든 수요를 엔진에 넣기

만든 수요로 시뮬레이션을 돌리려면 서버에 올립니다.

```{code-cell} python
:tags: [skip-execution]

from smartmob import Dtumos

dt = Dtumos()
dt.upload_demand(city="hanam", df=realistic)

sim = dt.run_simulation(city="hanam", fleet_size=80, num_passengers=len(realistic))
sim.summary()
```

```{note}
`upload_demand`는 업로드 전에 `validate_demand`를 실행합니다. 필수 컬럼, 시간 범위, 좌표 범위를 통과하지 못하면 서버로 보내지 않습니다.
```

## 이 장의 실습

노트북 `labs/ch08_demand.ipynb` 를 열어 함께 돌립니다.

수요를 세 단계로 만들어 보고, 만든 수요를 그 자리에서 시뮬레이션 루프에 넣어 결과를 비교합니다.

```bash
jupyter lab labs/ch08_demand.ipynb
```

## 정리

- O-D 표는 "어디서 어디로 몇 명"을 담은 집계 자료입니다. 개인 기록이 아닙니다
- 하남 통행은 오전 8시와 오후 5~6시에 봉우리가 있고, 54%가 하남 안에서 끝납니다
- 시뮬레이터가 받는 수요는 `request_time`(자정부터의 분), 출발·도착 위경도 네 개입니다
- 경계 안 균등 표집에 도로 위치와 시간대 프로파일을 차례로 반영할 수 있습니다
- 도로 위 표집도 토지 이용과 실제 O-D 관계는 반영하지 않습니다
- 9장에서 이 수요의 통행시간을 예측하는 모델을 만듭니다

## 연습문제

```{admonition} 연습 8.1  ★
:class: tip

하남 O-D 데이터에서 통행량이 가장 많은 행정동 쌍 상위 10개를 찾아봅시다.
시간대를 오전(7~9시)과 저녁(17~19시)으로 나눠 각각 구하고, 두 시간대의 순위를 비교합니다.

산출물: 오전·저녁 상위 10쌍 표, 뒤집힌 쌍이 무엇을 뜻하는지 2~3줄.
```

```{admonition} 연습 8.2  ★★
:class: tip

`generate_demand` 는 출발지와 목적지를 서로 독립적으로 뽑습니다.
실제로는 그렇지 않습니다. 8.3절에서 봤듯 하남 출발 통행의 절반은 서울 동남권으로 갑니다.

O-D 표의 행정동 쌍 통행량을 가중치로 삼아, 출발지-목적지를 **쌍으로** 뽑도록 고쳐 봅시다.
행정동 안에서의 정확한 위치는 도로 위 샘플링으로 정합니다.

산출물: 구현 코드, 기존 방식과 새 방식의 통행거리 분포 비교 그래프.
```

```{admonition} 연습 8.3  ★★★
:class: tip

수요 건수는 시뮬레이션 결과에 직접 영향을 줍니다.
하남 O-D 데이터의 하루 총 통행량과, 그중 택시가 담당하는 비율을 가정해
"하남시 하루 택시 수요"를 추정해 봅시다.

추정에 쓴 가정을 모두 명시하고, 가정 하나를 바꿨을 때 결과가 얼마나 달라지는지 계산합니다.

산출물: 추정치, 가정 목록, 민감도 표(가정별 ±50% 변화 시 결과 범위).
```

[^living-mobility]: [서울 열린데이터광장, 수도권 생활이동](https://data.seoul.go.kr/dataList/OA-22657/F/1/datasetView.do)
