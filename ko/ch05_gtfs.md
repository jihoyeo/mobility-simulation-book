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

# 5장 GTFS와 한국 대중교통 데이터

하남시청에서 미사역까지 버스로 가면 몇 분 걸릴까요.

차와 달리 버스는 아무 때나 출발하지 않습니다. 시간표가 있습니다. 오후 6시 3분에 정류장에 도착했는데 버스가 6시 1분에 떠났다면 다음 차까지 기다려야 합니다. 도로망만으로는 이 계산을 할 수 없습니다.

전 세계 대중교통 시간표는 GTFS 라는 공통 형식으로 공개됩니다. 이 장에서 그 형식을 열어 봅니다.

## 학습 목표

- GTFS 다섯 개 표의 관계를 그림으로 설명합니다
- 한국 GTFS 의 `route_type` 이 국제 표준과 다르다는 것을 확인하고 올바르게 해석합니다
- 24시를 넘는 시각 표기를 처리합니다
- 경계를 그려 노선 전체를 잘라 냅니다

## 5.1 표 다섯 개

GTFS 는 텍스트 파일 여덟 개짜리 zip 입니다. 이 책에서 쓰는 것은 다섯 개입니다.

```{code-cell} python
from smartmob.data import load_gtfs

feed = load_gtfs("hanam")
for name, table in feed.items():
    print(f"{name:12s} {len(table):>8,}행   {list(table.columns)[:5]}")
```

관계는 이렇습니다.

```
routes.txt      노선          "340번 버스"
   ↓ route_id
trips.txt       운행          "340번의 오전 7시 12분 차"
   ↓ trip_id
stop_times.txt  시각표        "그 차가 각 정류장에 몇 시에 서는가"
   ↓ stop_id
stops.txt       정류장        "그 정류장의 이름과 위경도"

calendar.txt    운행일        "이 운행이 무슨 요일에 다니는가"
```

핵심은 **노선(route)과 운행(trip)이 다르다**는 것입니다. 340번 버스는 노선 하나이지만, 하루에 수십 번 다닙니다. 각각이 별개의 운행입니다.

```{code-cell} python
feed["routes"].head(3)
```

```{code-cell} python
trips_per_route = feed["trips"].groupby("route_id").size()
print(f"노선 {len(trips_per_route)}개")
print(f"노선당 운행 수  중앙값 {trips_per_route.median():.0f}회, 최대 {trips_per_route.max()}회")
```

가장 많이 다니는 노선은 하루 293회입니다. 3분에 한 대꼴입니다.

```{code-cell} python
stops_per_trip = feed["stop_times"].groupby("trip_id").size()
print(f"운행당 정류장 수  중앙값 {stops_per_trip.median():.0f}개, 최대 {stops_per_trip.max()}개")
```

## 5.2 route_type 이 국제 표준과 다릅니다

`routes.txt` 의 `route_type` 이 수단을 나타냅니다. GTFS 국제 명세로는 `0`=트램, `1`=지하철, `2`=철도, `3`=버스입니다.

한국 데이터는 다릅니다.

```{code-cell} python
feed["routes"]["route_type"].value_counts().sort_index()
```

`0` 이 132개로 가장 많습니다. 국제 명세대로 읽으면 하남시에 트램이 132개 노선 있다는 뜻이 됩니다. 물론 아닙니다.

한국 GTFS 는 국토교통부 TAGO 코드를 씁니다.

```{code-cell} python
from smartmob.data import KOREAN_ROUTE_TYPE

for code, label in KOREAN_ROUTE_TYPE.items():
    print(f"{code}  {label}")
```

`0` 은 시내·농어촌·마을버스입니다. 그러면 말이 됩니다.

```{code-cell} python
from smartmob.data import describe_feed

describe_feed(feed)["route_type"]
```

시내버스 132개, 도시철도 15개, 공항리무진 8개, 일반철도 6개. 하남시에는 5호선과 9호선이 지나고, 인근 철도역이 포함되어 있습니다.

```{warning}
국제 명세대로 `route_type == 3` 을 버스로 걸러 내면 하남시 버스가 4개(시외버스)만 나오고, 코드는 오류 없이 잘 돌아갑니다. 결과 숫자가 이상해야 알아차립니다. 다른 나라 데이터로 만든 코드를 한국 데이터에 그대로 쓰면 이런 일이 생깁니다.
```

## 5.3 시각이 24시를 넘습니다

시각표를 봅니다.

```{code-cell} python
feed["stop_times"].head(3)[["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]]
```

`arrival_time` 이 `HH:MM:SS` 문자열입니다. 그대로 `datetime` 으로 파싱하면 터집니다.

```{code-cell} python
times = feed["stop_times"]["arrival_time"].dropna()
hours = times.str.split(":").str[0].astype(int)
print(f"시(hour) 최댓값: {hours.max()}")
print(f"24 이상인 행: {(hours >= 24).sum():,}개")
```

30시가 나옵니다. 새벽 6시라는 뜻입니다.

왜 이렇게 쓸까요. 밤 11시 50분에 출발해 새벽 0시 20분에 도착하는 버스를 생각해 봅시다. 도착 시각을 `00:20:00` 으로 쓰면 출발보다 **이른** 시각이 되어 순서가 뒤집힙니다. 운행일도 애매해집니다. 그날 밤차인지 다음날 첫차인지 알 수 없습니다.

`24:20:00` 으로 쓰면 둘 다 해결됩니다. 시각은 계속 증가하고, 운행일은 출발일 하나로 고정됩니다.

그래서 파싱은 이렇게 합니다.

```{code-cell} python
def parse_gtfs_time(text):
    h, m, s = (int(p) for p in str(text).split(":"))
    return h * 3600 + m * 60 + s

print(parse_gtfs_time("08:30:00"), "초 = 오전 8시 30분")
print(parse_gtfs_time("25:30:00"), "초 = 다음 날 새벽 1시 30분")
```

`smartmob.data.parse_gtfs_time` 이 같은 일을 합니다. 6장에서 이 함수를 계속 씁니다.

## 5.4 정류장 지도

정류장 4,203개를 지도에 찍어 봅니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
stops = feed["stops"]

fig, ax = plt.subplots(figsize=(7, 6))
ax.scatter(stops["stop_lon"], stops["stop_lat"], s=3, alpha=0.5, color="tab:blue")
ax.set_xlabel("경도"); ax.set_ylabel("위도")
ax.set_title(f"하남 GTFS 정류장 {len(stops):,}개")
ax.set_aspect(1 / 0.79)   # 위도 37도에서 경도 1도가 더 짧습니다
fig.tight_layout();
```

하남시 밖까지 넓게 퍼져 있습니다. 하남시를 지나는 노선의 정류장 전체가 들어 있어서입니다. 340번 버스가 서울 강변역까지 간다면 강변역 정류장도 함께 들어옵니다.

## 5.5 잘라 낼 때 노선 전체를 남깁니다

프로젝트에서는 특정 지역만 다룹니다. 경계 밖을 잘라 내야 합니다.

가장 단순한 방법은 경계 안의 정류장만 남기는 것입니다. 그런데 이렇게 하면 문제가 생깁니다. 340번 버스의 정류장이 경계 안에 10개, 밖에 15개 있다고 해 봅시다. 잘라 낸 뒤에는 10개짜리 노선이 됩니다. 경계 근처에서 갑자기 끊긴 노선으로 경로를 찾으면 실제로는 갈 수 있는 곳을 못 간다고 답합니다.

그래서 **정류장이 아니라 노선 단위로 남깁니다.**

```
경계 안 정류장 찾기
   ↓ 그 정류장을 지나는
운행 찾기
   ↓ 그 운행이 속한
노선 찾기
   ↓ 그 노선의
운행 전부 남기기 (경계 밖 구간까지)
```

`smartmob.data.gtfs.clip_to_boundary` 가 이 순서로 되어 있습니다.

```{code-cell} python
:tags: [skip-execution]

import geopandas as gpd
from smartmob.data import data_path
from smartmob.data.gtfs import clip_to_boundary

boundary = gpd.read_file(data_path("hanam/boundary.geojson")).geometry.iloc[0]
clipped = clip_to_boundary(feed, boundary, buffer_m=500)

for name in ["stops", "routes", "trips", "stop_times"]:
    print(f"{name:12s} {len(feed[name]):>8,} → {len(clipped[name]):>8,}")
```

버퍼 500m를 두는 이유는 경계 바로 바깥의 정류장 때문입니다. 시 경계에서 30m 떨어진 정류장은 사실상 그 동네 사람이 쓰는 정류장인데, 딱 잘라 내면 사라집니다.

## 5.6 실습: 우리 동네 노선 세어 보기

기말 프로젝트에서 할 일의 축소판입니다. 특정 정류장을 지나는 노선을 찾아봅니다.

```{code-cell} python
target = stops[stops["stop_name"].str.contains("하남시청", na=False)]
target[["stop_id", "stop_name", "stop_lat", "stop_lon"]]
```

```{code-cell} python
stop_ids = set(target["stop_id"])
st = feed["stop_times"]
trip_ids = set(st[st["stop_id"].isin(stop_ids)]["trip_id"])

trips = feed["trips"]
route_ids = set(trips[trips["trip_id"].isin(trip_ids)]["route_id"])

routes = feed["routes"]
here = routes[routes["route_id"].isin(route_ids)]
print(f"하남시청 정류장을 지나는 노선 {len(here)}개")
here[["route_short_name", "route_type"]].head(10)
```

운행 횟수까지 세면 그 정류장의 공급 수준이 나옵니다.

```{code-cell} python
n_trips = trips[trips["route_id"].isin(route_ids)].groupby("route_id").size()
summary = here[["route_id", "route_short_name"]].copy()
summary["운행수"] = summary["route_id"].map(n_trips)
summary.sort_values("운행수", ascending=False).head(8)[["route_short_name", "운행수"]]
```

## 정리

- GTFS 는 `routes`(노선) → `trips`(운행) → `stop_times`(시각표) → `stops`(정류장) 순으로 이어집니다
- 노선과 운행은 다릅니다. 340번은 노선 하나이고 하루에 수십 번 다닙니다
- 한국 GTFS 의 `route_type` 은 TAGO 코드입니다. `0` 이 시내버스이고 트램이 아닙니다
- 시각은 24시를 넘습니다. `25:30:00` 은 다음 날 새벽 1시 30분이며 같은 운행일입니다
- 경계로 자를 때는 정류장이 아니라 노선 단위로 남깁니다. 안 그러면 노선이 경계에서 끊깁니다
- 6장에서 이 시간표 위에서 경로를 찾습니다. 도로망 최단경로와는 다른 알고리즘을 씁니다

## 연습문제

```{admonition} 연습 5.1  ★
:class: tip

하남 GTFS 에서 첫차와 막차 시각을 구해 봅시다.
`parse_gtfs_time` 으로 초로 바꾼 뒤 최솟값과 최댓값을 찾고, 다시 `HH:MM` 으로 표시합니다.
24시를 넘는 값을 어떻게 표시할지 정해야 합니다.

산출물: 첫차 시각, 막차 시각, 24시 넘는 표기를 어떻게 처리했는지 한 문장.
```

```{admonition} 연습 5.2  ★★
:class: tip

시간대별 운행 편수를 그려 봅시다.
각 운행의 첫 정류장 출발 시각을 기준으로 1시간 단위로 세고, 히스토그램으로 그립니다.
첨두가 언제인지, 심야에 다니는 노선이 있는지 확인합니다.

산출물: 히스토그램 1장, 첨두 시간대와 심야 운행 유무를 적은 문장 2~3줄.
```

```{admonition} 연습 5.3  ★★★
:class: tip

같은 노선의 운행들이 실제로 같은 정류장 순서를 따르는지 확인해 봅시다.
`route_id` 별로 운행들의 정류장 순서를 모아 몇 종류가 나오는지 셉니다.
한 노선에 여러 순서가 나오면 그것이 무엇을 뜻하는지(상행/하행, 지선, 회차) 설명합니다.
6장에서 이 "순서가 같은 운행 묶음"이 중요해집니다.

산출물: 노선당 정류장 순서 종류 수의 분포, 가장 많은 노선의 사례 설명.
```
