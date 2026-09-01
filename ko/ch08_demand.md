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

지금까지는 한 사람의 경로를 구했습니다. 시뮬레이션에는 수천 명이 들어갑니다.

0장에서 돌린 시뮬레이션은 승객 990명이 하남시 어딘가에서 어딘가로 가려 했습니다. 그 990명은 어디서 왔을까요. 누가 정했을까요.

이 장에서 통행 수요가 무엇인지 보고, 실제 데이터를 읽고, 데이터가 없을 때 만드는 방법을 봅니다.

## 학습 목표

- 수도권 생활이동 O-D 데이터를 읽고 시간대·공간 패턴을 뽑습니다
- 시뮬레이터가 받는 수요 형식(컬럼 다섯 개)을 압니다
- 수요 생성기의 세 단계를 비교하고 각각이 무엇을 개선하는지 설명합니다
- 실제 데이터에서 뽑은 시간대 프로파일로 수요를 만듭니다

## 8.1 O-D 데이터

통행 수요를 담는 가장 흔한 형태는 O-D 표입니다. **어디서(Origin) 어디로(Destination) 몇 명이 갔는가**를 적습니다.

수도권 생활이동 데이터는 통신사 기지국 접속 기록으로 만든 O-D 자료입니다. 하남시가 걸린 행만 뽑아 두었습니다.

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

행 하나가 "이 동에서 저 동으로, 이 시간대에, 몇 명"입니다. 개인 기록이 아니라 집계값입니다.

```{code-cell} python
od[["CNT", "MOVE_DIST", "MOVE_TIME"]].describe().round(0)
```

이동거리 중앙값이 5.2km, 이동시간 중앙값이 1,223초(20분)입니다.

```{note}
집계 데이터라는 점이 중요합니다. "이 사람이 8시 12분에 미사동에서 출발했다"는 정보가 없습니다. 있는 것은 "8시대에 미사동에서 신장동으로 47.3명이 갔다"뿐입니다. 시뮬레이터는 개인 단위로 돌아가므로, 이 집계값을 다시 개인으로 쪼개야 합니다. 8.4절에서 합니다.
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

봉우리가 둘입니다. 오전 8시가 가장 높고, 오후 5~6시가 두 번째입니다. 출퇴근입니다.

```{code-cell} python
top = by_hour.sort_values(ascending=False).head(5)
for hour, count in top.items():
    print(f"{hour:2d}시  {count:>9,.0f}명")
```

새벽 3~4시가 가장 낮습니다. 0장에서 저녁 6시~자정을 시뮬레이션했던 이유가 여기 있습니다. 그 시간대에 통행이 많으면서 하루를 통째로 돌리지 않아도 되기 때문입니다.

## 8.3 공간 패턴

하남에서 출발한 통행이 어디로 가는지 봅니다. 행정동 코드 앞 다섯 자리가 시군구입니다.

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

**하남 안에서 끝나는 통행이 54%입니다.** 나머지 절반은 서울 동남권(강동·송파·강남)과 인접 시군으로 나갑니다.

이 비율이 시뮬레이션 설계를 좌우합니다. 하남시 경계 안만 다루면 통행의 절반을 놓칩니다. 반대로 수도권 전체를 다루면 데이터와 계산이 훨씬 커집니다. 어디까지 자를지는 답하려는 질문에 따라 정합니다.

```{code-cell} python
inside = from_hanam[from_hanam["D_ADMDONG_CD"] // 1000 == 41450]
print(f"하남 출발 총 통행  {from_hanam['CNT'].sum():>10,.0f}명")
print(f"하남 안에서 끝남   {inside['CNT'].sum():>10,.0f}명 ({inside['CNT'].sum() / from_hanam['CNT'].sum():.0%})")
print(f"하남 행정동 수     {from_hanam['O_ADMDONG_CD'].nunique():>10}개")
```

## 8.4 시뮬레이터가 받는 형식

시뮬레이터는 집계표가 아니라 **개인 목록**을 받습니다. 컬럼 다섯 개가 계약입니다.

```{code-cell} python
from smartmob.data import DEMAND_COLUMNS, load_demand

print(DEMAND_COLUMNS)
demand = load_demand("hanam")
demand.head(3)
```

`request_time` 은 자정부터의 분입니다. 1080이면 18:00입니다. 이 단위를 틀리면 조용히 이상한 결과가 나오므로 검증 함수가 잡아 줍니다.

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

실제 데이터가 없거나, 있어도 개인 단위가 아니면 만들어야 합니다.

가장 단순한 방법은 경계 안에 점을 고르게 찍는 것입니다.

```{code-cell} python
import geopandas as gpd
from smartmob.teaching.demand_gen import generate_demand

boundary = gpd.read_file(data_path("hanam/boundary.geojson")).geometry.iloc[0]
uniform = generate_demand(boundary=boundary, n=800, seed=1, hourly=None)
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

경계 안에 고르게 퍼져 있습니다. 그런데 하남시에는 검단산과 한강이 있습니다. 산 중턱에서 택시를 부르는 사람은 없습니다.

## 8.6 수요 만들기 2단계 — 도로 위에

길이 있는 곳에서만 뽑으면 이 문제가 사라집니다. 2장에서 만든 도로망을 씁니다.

긴 도로가 더 많이 뽑히도록 길이에 비례해 가중치를 줍니다.

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

산과 강이 비었습니다. 도로가 촘촘한 시가지에 점이 몰립니다. 훨씬 그럴듯합니다.

이 방법에는 숨은 가정이 하나 있습니다. **도로가 많은 곳에 사람이 많다**는 것입니다. 대체로 맞지만 항상은 아닙니다. 고속도로 구간은 도로가 길지만 거기서 택시를 부르지 않습니다.

## 8.7 수요 만들기 3단계 — 시간대 프로파일

지금까지 만든 수요는 시간에 대해 균등합니다. 8.2절에서 본 출퇴근 첨두가 없습니다.

O-D 데이터에서 시간대 비중을 뽑아 씁니다.

```{code-cell} python
from smartmob.teaching.demand_gen import hourly_profile_from_od

profile = hourly_profile_from_od(od)
for hour in (3, 8, 12, 17, 22):
    print(f"{hour:2d}시  {profile[hour]:.1%}")
```

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

8.2절의 실제 통행량 그래프와 모양이 같습니다. 오전 8시와 오후 5~6시에 봉우리가 있습니다.

```{code-cell} python
from smartmob.data import validate_demand

validate_demand(realistic)
print(f"{len(realistic):,}건, 계약 통과")
realistic.head(3)
```

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

파일럿 프로젝트도 같은 순서로 진행합니다. 대상지의 수요를 만들고, 올리고, 조건을 바꿔 가며 돌립니다.

```{note}
`upload_demand` 는 올리기 전에 `validate_demand` 를 먼저 돌립니다. 형식이 틀린 수요가 서버에 올라가 이상한 결과를 내는 것보다, 올리기 전에 막히는 편이 낫습니다.
```

## 정리

- O-D 표는 "어디서 어디로 몇 명"을 담은 집계 자료입니다. 개인 기록이 아닙니다
- 하남 통행은 오전 8시와 오후 5~6시에 봉우리가 있고, 54%가 하남 안에서 끝납니다
- 시뮬레이터가 받는 수요는 `request_time`(자정부터의 분), 출발·도착 위경도 네 개입니다
- 수요 생성은 세 단계로 그럴듯해집니다. 경계 안 균등 → 도로 위 → 시간대 프로파일 반영
- 도로 위 샘플링은 "도로가 많은 곳에 사람이 많다"를 가정합니다. 대체로 맞지만 항상은 아닙니다
- 9장에서 이 수요의 통행시간을 예측하는 모델을 만듭니다

## 연습문제

```{admonition} 연습 8.1  ★
:class: tip

하남 O-D 데이터에서 통행량이 가장 많은 행정동 쌍 상위 10개를 찾아봅시다.
시간대를 오전(7~9시)과 저녁(17~19시)으로 나눠 각각 구하고, 순서가 어떻게 뒤집히는지 봅니다.

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

수요를 몇 명으로 잡을지가 실은 큰 결정입니다.
하남 O-D 데이터의 하루 총 통행량과, 그중 택시가 담당하는 비율을 가정해
"하남시 하루 택시 수요"를 추정해 봅시다.

추정에 쓴 가정을 전부 명시하고, 가정 하나를 바꾸면 결과가 얼마나 달라지는지(민감도) 보입니다.

산출물: 추정치, 가정 목록, 민감도 표(가정별 ±50% 변화 시 결과 범위).
```
