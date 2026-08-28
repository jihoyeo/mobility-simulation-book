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

# 부록 A 스마트카드 데이터

5장에서 GTFS 시간표를 봤습니다. 시간표는 "버스가 언제 어디를 지나는가"이고, 스마트카드 데이터는 "사람이 실제로 언제 어디서 타고 내렸는가"입니다.

이 부록은 강의에서 다루지 않습니다. 과제와 프로젝트에서 실제 이용 데이터를 쓰고 싶을 때 참고하세요.

```{warning}
여기 쓰는 데이터는 정류장 위치는 실제이지만 이용 내역은 실제 데이터에 잡음을 섞은 가상 자료입니다. 개인 통행 기록은 민감정보이므로 원본을 그대로 다루지 않습니다.
```

## A.1 파일 두 개

```{code-cell} python
import pandas as pd
from smartmob.data import data_path

trips = pd.read_parquet(data_path("smartcard/TCD_20240923_modify.parquet"))
stops = pd.read_parquet(data_path("smartcard/STTN_20240923.parquet"))
print(f"이용 내역 {len(trips):,}건, 정류장 {len(stops):,}행")
```

`TCD` 는 통행 한 건이 한 줄입니다. 환승을 여러 번 해도 한 줄입니다.

```{code-cell} python
[c for c in trips.columns if c.startswith(("시작", "종료"))]
```

컬럼 이름이 `시작`/`종료` 로 시작합니다. 한 통행 안에서 처음 탄 것과 마지막 내린 것을 뜻합니다. 중간 환승은 `지역 N 코드`, `교통수단 N 코드` 처럼 번호가 붙은 컬럼에 최대 10개까지 들어 있습니다.

```{code-cell} python
trips[["시작 승차 일시", "시작 승차 역 ID", "종료 하차 일시",
       "종료 하차 역 ID", "환승 건수", "총 통행 거리", "총 소요 시간"]].head(3)
```

## A.2 첫 번째 함정 — 좌표가 뒤바뀌어 있습니다

정류장 표를 봅니다.

```{code-cell} python
stops[["정류장 ID", "정류장 명칭", "정류장 X 좌표", "정류장 Y 좌표", "시군구명"]].head(3)
```

`X 좌표` 가 35.5이고 `Y 좌표` 가 129.4입니다. 보통 X는 경도, Y는 위도인데 값이 반대입니다. 한국의 위도는 33~39도, 경도는 124~132도이므로 **컬럼 이름과 내용이 어긋나 있습니다.**

```{code-cell} python
x = pd.to_numeric(stops["정류장 X 좌표"], errors="coerce")
y = pd.to_numeric(stops["정류장 Y 좌표"], errors="coerce")
print(f"X 좌표 범위 {x.min():.1f} ~ {x.max():.1f}   (위도라면 33~39)")
print(f"Y 좌표 범위 {y.min():.1f} ~ {y.max():.1f}   (경도라면 124~132)")
```

이름을 믿지 말고 값을 확인해야 합니다. 8장의 `validate_demand` 가 이런 실수를 잡도록 만들어진 이유입니다.

```{code-cell} python
stops = stops.assign(lat=x, lon=y)
stops = stops[stops["lat"].between(33, 39.5) & stops["lon"].between(124, 132)]
print(f"좌표가 정상인 정류장 {len(stops):,}행")
```

## A.3 정류장 표에는 중복이 있습니다

```{code-cell} python
print(f"행 {len(stops):,}개, 고유 정류장 ID {stops['정류장 ID'].nunique():,}개")
unique_stops = stops.drop_duplicates(subset="정류장 ID").set_index("정류장 ID")
unique_stops[["정류장 명칭", "시군구명", "lat", "lon"]].head(3)
```

같은 정류장이 정산사별로 여러 번 들어 있습니다. 통행 데이터와 붙이기 전에 하나로 줄입니다.

## A.4 O-D 표 만들기

통행 한 건에서 출발 정류장·도착 정류장·시각을 뽑아 O-D 형태로 만듭니다.

```{code-cell} python
od = trips[[
    "시작 승차 역 ID", "종료 하차 역 ID", "시작 승차 일시", "종료 하차 일시",
    "교통카드 사용자 구분 코드", "환승 건수", "총 통행 거리", "총 소요 시간",
]].rename(columns={
    "시작 승차 역 ID": "출발 정류장",
    "종료 하차 역 ID": "도착 정류장",
    "교통카드 사용자 구분 코드": "이용자코드",
})

od["출발시각"] = pd.to_datetime(
    od["시작 승차 일시"].astype(str).str.replace(r"\.0$", "", regex=True),
    format="%Y%m%d%H%M%S", errors="coerce",
)
od["도착시각"] = pd.to_datetime(
    od["종료 하차 일시"].astype(str).str.replace(r"\.0$", "", regex=True),
    format="%Y%m%d%H%M%S", errors="coerce",
)
od = od.dropna(subset=["출발시각", "도착시각"])
print(f"시각이 정상인 통행 {len(od):,}건")
```

`.0` 을 떼는 것이 필요합니다. 일시가 실수형으로 저장되어 있어 `20240923221246.0` 처럼 되기 때문입니다.

숫자 컬럼도 정리합니다. 문자열로 들어 있고 결측이 섞여 있습니다.

```{code-cell} python
for col in ("총 통행 거리", "총 소요 시간", "환승 건수"):
    od[col] = pd.to_numeric(od[col], errors="coerce")

od = od[(od["총 통행 거리"] > 0) & (od["총 소요 시간"] > 0)]
print(f"거리·시간이 정상인 통행 {len(od):,}건")
od[["총 통행 거리", "총 소요 시간", "환승 건수"]].describe().round(0)
```

## A.5 시간대별 이용 패턴

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
board = od["출발시각"].dt.hour.value_counts().sort_index()
alight = od["도착시각"].dt.hour.value_counts().sort_index()

fig, ax = plt.subplots(figsize=(9, 3.6))
ax.plot(board.index, board.values, "-o", label="승차", markersize=4)
ax.plot(alight.index, alight.values, "-s", label="하차", markersize=4)
ax.set_xlabel("시각 (시)"); ax.set_ylabel("건수")
ax.set_xticks(range(0, 24, 2)); ax.legend()
ax.grid(alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

8장에서 본 O-D 데이터의 첨두와 같은 모양입니다. 서로 다른 출처의 자료가 같은 패턴을 보이면 둘 다 믿을 만하다는 신호입니다.

## A.6 교통약자의 통행은 어떻게 다른가

이 데이터의 쓸모는 여기 있습니다. `교통카드 사용자 구분 코드` 로 이용자를 나눌 수 있습니다.

```{code-cell} python
USER_TYPE = {"1": "일반", "2": "어린이", "3": "청소년", "4": "경로", "5": "장애인"}

od["이용자"] = od["이용자코드"].astype(str).map(USER_TYPE)
od["이용자"].value_counts()
```

```{code-cell} python
stat = od.dropna(subset=["이용자"]).groupby("이용자").agg(
    통행수=("이용자", "size"),
    평균거리_km=("총 통행 거리", lambda s: s.mean() / 1000),
    평균소요_분=("총 소요 시간", lambda s: s.mean() / 60),
    평균환승=("환승 건수", "mean"),
).round(2)
stat.sort_values("통행수", ascending=False)
```

```{code-cell} python
fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
order = stat.sort_values("평균거리_km").index

for ax, col, label in zip(
    axes, ["평균거리_km", "평균소요_분", "평균환승"], ["평균 통행거리 (km)", "평균 소요시간 (분)", "평균 환승 횟수"]
):
    ax.bar(order, stat.loc[order, col], color="tab:blue", width=0.55)
    ax.set_title(label, fontsize=11)
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

세 지표를 같이 봐야 해석이 됩니다. 어느 집단이 더 멀리 가고, 더 오래 걸리고, 더 많이 갈아타는지가 서로 다를 수 있습니다.

```{code-cell} python
stat["분당_km"] = (stat["평균거리_km"] / stat["평균소요_분"]).round(3)
stat[["평균거리_km", "평균소요_분", "분당_km"]].sort_values("분당_km")
```

`분당_km` 는 문 대 문 평균 속도입니다. 같은 거리를 가는 데 더 오래 걸린다면 대기와 환승에서 시간을 쓴다는 뜻입니다.

## A.7 공간으로 옮기기

스마트카드 데이터에는 좌표가 없습니다. 정류장 ID 로 붙여야 합니다.

```{code-cell} python
# 양쪽 다 문자열입니다. 숫자로 바꾸면 붙지 않습니다.
print("통행 쪽 ID 타입:", od["출발 정류장"].dtype)
print("정류장 쪽 ID 타입:", unique_stops.index.dtype)

joined = od.join(
    unique_stops[["lat", "lon", "시군구명"]].rename(
        columns={"lat": "o_lat", "lon": "o_lon", "시군구명": "o_시군구"}
    ),
    on="출발 정류장",
)
matched = joined["o_lat"].notna().mean()
print("좌표가 붙은 통행", f"{matched:.1%}")
```

`dtype` 을 먼저 찍어 본 이유가 있습니다. 한쪽을 숫자로 바꾸면 `pandas` 가 "int64 와 object 를 붙일 수 없다"며 거절합니다. 정류장 ID 는 코드이지 수량이 아니므로 문자열로 두는 것이 맞습니다.

이번에는 전부 붙었습니다. 그래도 **붙는 비율을 매번 확인하고 보고서에 적으세요.** 다른 날짜나 다른 지역 자료에서는 정류장 표에 없는 ID 가 나옵니다. 절반만 붙었는데 그 사실을 밝히지 않으면 분석 전체가 흔들립니다.

```{code-cell} python
top = joined["o_시군구"].value_counts().head(10)
top
```

## A.8 두 번째 함정 — 같은 지역이 두 이름으로 들어옵니다

위 목록을 보면 `성남시 분당구` 와 `성남시분당구` 가 따로 세어져 있습니다. 띄어쓰기만 다릅니다.

```{code-cell} python
names = joined["o_시군구"].dropna().unique()
with_space = [n for n in names if " " in n]
print(f"시군구 표기 {len(names)}종 중 공백이 든 것 {len(with_space)}종")
print(with_space[:6])
```

이대로 집계하면 성남시 분당구의 통행량이 절반으로 갈라집니다. 공백을 지워 맞춥니다.

```{code-cell} python
joined["시군구"] = joined["o_시군구"].str.replace(" ", "", regex=False)
joined["시군구"].value_counts().head(6)
```

숫자가 합쳐졌습니다. 이 자료는 성남시 일대가 중심이라는 것도 이제 보입니다.

```{warning}
이런 표기 흔들림은 한국 행정구역 데이터에서 흔합니다. 문자열로 집계하기 전에 고유값을 한 번 훑어보세요. `value_counts()` 상위 20개만 봐도 대부분 드러납니다.
```

## A.9 지도에 찍기

```{code-cell} python
sample = joined.sample(20000, random_state=42)

fig, ax = plt.subplots(figsize=(6, 6))
ax.scatter(sample["o_lon"], sample["o_lat"], s=2, alpha=0.15, color="tab:blue")
ax.set_xlim(127.02, 127.24); ax.set_ylim(37.30, 37.52)
ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect(1 / 0.79)
ax.set_title("승차 지점 (성남시 일대)")
fig.tight_layout();
```

## A.10 과제로 이어가기

여기까지가 준비입니다. 실제로 답할 만한 질문은 이런 것들입니다.

- 경로 이용자의 승차가 집중되는 정류장은 어디인가. 그곳의 배차간격은 적절한가
- 환승 횟수가 3회 이상인 통행은 어디에서 어디로 가는가. 그 구간에 직통 노선이 필요한가
- 같은 O-D 를 6장의 RAPTOR 로 계산한 값과 실제 소요시간을 비교하면 얼마나 차이 나는가

마지막 질문이 특히 유용합니다. 우리 RAPTOR 는 시간표대로 움직인다고 가정하는데, 실제 통행은 지연과 혼잡을 겪습니다. 그 차이가 곧 모형의 한계입니다.

## 정리

- 스마트카드 데이터는 통행 한 건이 한 줄이고, 중간 환승은 번호가 붙은 컬럼에 들어 있습니다
- 정류장 표의 `X 좌표`/`Y 좌표` 는 이름과 내용이 어긋나 있습니다. 값의 범위로 확인합니다
- 정류장 표에는 중복이 있으므로 `정류장 ID` 기준으로 줄인 뒤 붙입니다
- 일시가 실수형으로 저장되어 `.0` 이 붙습니다. 파싱 전에 떼어냅니다
- 좌표를 붙일 때 매칭률을 확인하고 보고서에 밝힙니다
- 시군구명이 `성남시 분당구` 와 `성남시분당구` 두 표기로 들어옵니다. 집계 전에 맞춥니다
- 이용자 구분 코드로 교통약자의 통행 패턴을 따로 볼 수 있습니다
