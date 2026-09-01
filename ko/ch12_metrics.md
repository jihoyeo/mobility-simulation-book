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

# 12장 결과 읽기 — 지표와 시각화

11장에서 차량 20대부터 80대까지 돌려 봤습니다. 표를 다시 보면 이상한 줄이 있습니다.

차량 20대일 때 평균 대기시간이 7.32분, 60대일 때 7.21분입니다. 차를 세 배로 늘렸는데 대기시간이 거의 그대로입니다. 게다가 20대에서는 승객의 61%가 배차를 못 받았습니다.

숫자가 틀린 것이 아니라 **읽는 방법이 틀린 것**입니다. 이 장에서 그 이유를 찾습니다.

## 학습 목표

- 지표를 승객·운영자·도시 세 관점으로 나눠 정리합니다
- 평균 하나로 판단할 때 생기는 편향을 찾아냅니다
- 시나리오 여러 개를 한 표로 비교하고 파레토 프론트를 그립니다
- `trip.json` 을 pydeck 으로 재생해 차량이 움직이는 것을 봅니다

## 12.1 지표 세 무리

1장에서 좋은 모빌리티 시스템은 보는 사람에 따라 다르다고 했습니다. 지표도 그렇습니다.

| 관점 | 무엇을 보는가 | 지표 |
|---|---|---|
| 승객 | 탈 수 있었나, 얼마나 기다렸나 | 서비스율, 대기시간 중앙값·90분위·최댓값 |
| 운영자 | 차가 일했나, 몇 명을 태웠나 | 가동률, 차량당 처리 건수 |
| 도시 | 도로를 얼마나 썼나 | 총 주행거리, 공차 비율 |

```{code-cell} python
from smartmob.data import load_demand, load_vehicles
from smartmob.teaching.simloop import simulate
from smartmob.teaching.metrics import kpi_table

demand = load_demand("hanam")
vehicles = load_vehicles("hanam")

run = simulate(demand, vehicles, 1080, 1440)
kpi_table(run)
```

한 줄씩 읽습니다.

- `service_rate` 1.0 — 전원 배차받았습니다
- `wait_p50` 3.05분, `wait_p90` 8.27분 — 절반은 3분 안에 탔고, 열 명 중 아홉은 8분 안에 탔습니다
- `wait_max` 26.45분 — 가장 오래 기다린 사람입니다
- `utilization` 0.67 — 근무 중 차량의 3분의 2가 항상 움직이고 있었습니다
- `empty_share` 0.19 — 총 주행거리의 19%가 빈 차 주행입니다

마지막 값이 도시가 신경 쓰는 것입니다. 승객을 태우지 않고 도로를 차지한 거리입니다.

## 12.2 평균은 왜 위험한가

11장의 표를 다시 만들어 봅니다.

```{code-cell} python
from smartmob.teaching.metrics import compare

runs = {f"{n}대": simulate(demand, vehicles.head(n), 1080, 1440) for n in (20, 40, 60, 80)}
table = compare(runs)
table[["service_rate", "wait_mean", "wait_p50", "wait_max", "utilization", "empty_share"]]
```

`wait_mean` 열을 봅니다. 20대에서 7.32분, 80대에서 4.28분. 차이가 크지 않습니다.

그런데 `service_rate` 를 같이 보면 이야기가 달라집니다. 20대에서는 **39%만 탔습니다.**

여기에 함정이 있습니다. 대기시간은 배차받은 사람만 계산됩니다. 못 탄 사람은 통계에서 빠집니다. 차가 적으면 가까운 승객만 배차되고 멀리 있는 승객은 포기 처리되므로, 남은 사람들의 평균 대기가 짧게 나옵니다.

이것을 **생존 편향(survivorship bias)** 이라고 합니다.

```{code-cell} python
for n in (20, 80):
    result = runs[f"{n}대"]
    served = [r for r in result.requests if r.pickup_time is not None]
    failed = [r for r in result.requests if r.failed]
    print(f"차량 {n}대: 배차 {len(served)}명, 포기 {len(failed)}명")
```

포기한 승객을 어떻게 셀지 정해야 합니다. 세 가지 방법이 있습니다.

```{code-cell} python
import numpy as np
import pandas as pd

rows = []
for label, result in runs.items():
    served = [r.wait_min for r in result.requests if r.pickup_time is not None]
    n_failed = sum(1 for r in result.requests if r.failed)
    penalty = result.config["fail_after_min"]
    rows.append({
        "시나리오": label,
        "배차된 사람만": round(np.mean(served), 2),
        "포기=30분으로": round(np.mean(served + [30] * n_failed), 2),
        "서비스율": round(len(served) / len(result.requests), 3),
    })
pd.DataFrame(rows)
```

포기한 승객에게 30분을 매기면 순서가 완전히 뒤집힙니다. 20대는 21분이 넘고 80대는 4.28분입니다.

어느 쪽이 맞을까요. 둘 다 맞습니다. 다만 답하려는 질문이 다릅니다.

- "택시를 잡은 사람은 얼마나 기다렸나" → 배차된 사람만
- "이 지역에서 택시를 부르면 얼마나 걸리나" → 포기까지 포함

보고서에는 서비스율과 대기시간을 항상 같이 적습니다. 하나만 적으면 읽는 사람이 속습니다.

```{warning}
이 함정은 프로젝트 보고서에서 가장 자주 나옵니다. "차량을 줄였는데 대기시간이 그대로였습니다"라는 결론을 보면 먼저 서비스율을 확인하세요.
```

## 12.3 분포를 봅니다

평균 대신 분포를 그립니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
fig, ax = plt.subplots(figsize=(9, 4))

for label in ("20대", "80대"):
    waits = [r.wait_min for r in runs[label].requests if r.pickup_time is not None]
    ax.hist(waits, bins=30, alpha=0.6, label=f"{label} (배차 {len(waits)}명)")

ax.set_xlabel("대기시간 (분)"); ax.set_ylabel("승객 수")
ax.legend(); ax.grid(alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

80대 쪽이 왼쪽에 몰려 있고 높이도 훨씬 높습니다. 높이 차이가 곧 배차받은 사람 수의 차이입니다. 히스토그램은 평균이 숨기는 두 가지를 동시에 보여 줍니다. 모양과 개수입니다.

## 12.4 차량을 몇 대 둘 것인가

지표 두 개를 축으로 놓으면 선택지가 한눈에 보입니다.

```{code-cell} python
fig, ax = plt.subplots(figsize=(6.5, 5))

for label, result in runs.items():
    k = kpi_table(result)
    ax.scatter(k["service_rate"], k["utilization"], s=90, color="tab:blue", zorder=3)
    ax.annotate(label, (k["service_rate"], k["utilization"]),
                textcoords="offset points", xytext=(8, 6))

ax.set_xlabel("서비스율 (승객이 좋아하는 것)")
ax.set_ylabel("차량 가동률 (운영자가 좋아하는 것)")
ax.grid(alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

오른쪽 위가 좋습니다. 그런데 그쪽에 점이 없습니다. 서비스율을 올리면 가동률이 떨어지고, 가동률을 올리면 서비스율이 떨어집니다.

이렇게 어느 쪽도 다른 쪽을 완전히 이기지 못하는 선택지들을 파레토 프론트라고 합니다. 넷 다 프론트 위에 있으므로, 어느 것을 고를지는 데이터가 아니라 사람이 정합니다.

더 촘촘히 보려면 점을 더 찍습니다.

```{code-cell} python
fine = {f"{n}대": simulate(demand, vehicles.head(n), 1080, 1440)
        for n in (20, 30, 40, 50, 60, 70, 80)}

xs, ys, labels = [], [], []
for label, result in fine.items():
    k = kpi_table(result)
    xs.append(k["service_rate"]); ys.append(k["utilization"]); labels.append(label)

fig, ax = plt.subplots(figsize=(6.5, 5))
ax.plot(xs, ys, "-o", color="tab:blue")
for x, y, label in zip(xs, ys, labels):
    ax.annotate(label, (x, y), textcoords="offset points", xytext=(8, 4), fontsize=9)
ax.set_xlabel("서비스율"); ax.set_ylabel("차량 가동률")
ax.grid(alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

곡선이 꺾이는 지점이 보입니다. 그 근처가 대개 합리적인 선택입니다. 거기서 조금 더 늘리면 서비스율은 조금 오르는데 가동률은 많이 떨어지기 때문입니다.

```{code-cell} python
summary = compare(fine)[["service_rate", "utilization", "wait_p90", "empty_share"]]
summary
```

## 12.5 엔진 결과도 같은 표로

우리 루프와 실제 엔진의 지표를 같은 함수로 뽑을 수 있습니다.

```{code-cell} python
from smartmob import Dtumos

engine = Dtumos().run_simulation(
    city="hanam", mode="taxi", fleet_size=80, num_passengers=1000,
    time_start=1080, time_end=1440, random_seed=42,
)

both = compare({"내 루프": run, "DTUMOS 엔진": engine})
both[["service_rate", "wait_p50", "wait_p90", "utilization", "empty_share"]]
```

대기시간 분위와 공차 비율이 거의 같습니다. 서로 다른 코드가 같은 답을 낸다는 것은 좋은 신호입니다.

```{code-cell} python
both[["loaded_km", "empty_km", "total_km"]]
```

거리는 두 배 넘게 차이 납니다. 우리 루프가 틀린 걸까요.

아닙니다. 엔진의 `trip.json` 은 **전체 통행의 10%만** 저장하도록 설정되어 있습니다(`viz_ratio=0.1`). 화면에 그릴 용도라 전부 저장할 필요가 없기 때문입니다.

```{code-cell} python
print("엔진 설정 메모:", engine.config.get("_fixture_note", "")[:60], "…")
print(f"엔진 viz_ratio: {engine.config.get('viz_ratio')}")
```

비율은 맞습니다. 공차 비율이 0.19 대 0.186입니다. **절댓값을 비교할 수 없을 때도 비율은 비교할 수 있습니다.**

```{tip}
남의 결과와 숫자가 다르면 먼저 "같은 것을 세고 있는가"를 확인하세요. 정의가 다르거나 표본이 다른 경우가 알고리즘이 틀린 경우보다 훨씬 많습니다.
```

## 12.6 시간대별로 보기

한 숫자로 요약하면 시간에 따른 변화가 사라집니다.

```{code-cell} python
from smartmob.viz import plot_record

plot_record(run.record);
```

```{code-cell} python
record = run.record.copy()
record["hour"] = record["time"] // 60
by_hour = record.groupby("hour").agg(
    평균_대기승객=("waiting_passenger_cnt", "mean"),
    평균_운행차량=("driving_vehicle_cnt", "mean"),
    평균_빈차=("empty_vehicle_cnt", "mean"),
).round(1)
by_hour
```

저녁 6시에 시작해 밤 10시경 운행 차량이 정점을 찍고, 자정으로 갈수록 근무 종료로 줄어듭니다.

## 12.7 차량이 움직이는 것 보기

숫자만으로는 놓치는 것이 있습니다. 어디에서 차가 부족했는지, 어느 방향으로 몰렸는지는 지도로 봐야 보입니다.

엔진 결과의 `trip.json` 을 pydeck 으로 재생합니다.

```{code-cell} python
from smartmob.viz import prepare_trips

prepared = prepare_trips(engine.trips, sample=None)
print(f"전체 구간 {len(engine.trips)}개 중 그릴 수 있는 것 {len(prepared)}개")
```

전부 그려지지 않습니다. 좌표가 빈 구간이 섞여 있기 때문입니다. 차량이 이미 승객 위치에 있어 이동이 없었던 경우입니다.

```{code-cell} python
empty_geometry = [t for t in engine.trips if len(t["trip"]) != len(t["timestamp"])]
print(f"좌표가 빈 구간 {len(empty_geometry)}개")
empty_geometry[0] if empty_geometry else None
```

`timestamp` 는 하나 있는데 `trip` 은 비어 있습니다. 길이가 같다고 가정하고 그리면 여기서 터집니다. `prepare_trips` 가 이런 구간을 걸러 냅니다.

```{code-cell} python
:tags: [skip-execution]

from smartmob.viz import trips_deck, save_deck

deck = trips_deck(engine.trips, current_time=1200, trail_length=40)
save_deck(deck, "trips.html")     # 2MB 를 넘으면 막힙니다
deck
```

```{note}
`save_deck` 은 결과 HTML 이 2MB 를 넘으면 예외를 던집니다. 인터랙티브 지도를 노트북에 그대로 저장하면 파일이 수십 MB 로 부풀기 때문입니다. 이 교재의 이전 판에서 노트북 하나가 34MB 였던 원인이 그것이었습니다.
```

정적인 그림으로도 충분한 것을 볼 수 있습니다. 승객이 어디서 탔는지 찍어 봅니다.

```{code-cell} python
pax = engine.passengers

fig, ax = plt.subplots(figsize=(6.5, 5.5))
ax.scatter(pax["origin_lon"], pax["origin_lat"], s=6, alpha=0.35,
           color="tab:blue", label="승차")
ax.scatter(pax["dest_lon"], pax["dest_lat"], s=6, alpha=0.35,
           color="tab:red", label="하차")
ax.legend(); ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect(1 / 0.79)
ax.set_title("승하차 지점")
fig.tight_layout();
```

대기시간이 긴 승객이 어디에 있었는지 보면 더 유용합니다.

```{code-cell} python
long_wait = pax[pax["wait_min"] > 10]
print(f"10분 넘게 기다린 승객 {len(long_wait)}명")

fig, ax = plt.subplots(figsize=(6.5, 5.5))
ax.scatter(pax["origin_lon"], pax["origin_lat"], s=5, alpha=0.15, color="gray")
ax.scatter(long_wait["origin_lon"], long_wait["origin_lat"], s=30,
           color="tab:red", label="10분 초과 대기")
ax.legend(); ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect(1 / 0.79)
ax.set_title("오래 기다린 승객의 호출 위치")
fig.tight_layout();
```

가장자리에 몰려 있습니다. 차량이 시가지 중심에 머무는 동안 외곽 호출이 밀린 것입니다. 재배치가 필요한 지점이 여기서 눈에 보입니다. 11장 연습문제 11.3이 이 문제입니다.

## 12.8 보고서에 무엇을 적을 것인가

파일럿 프로젝트 보고서의 결과 절은 이렇게 구성합니다.

1. **한 문장 결론** — "차량 60대가 하남시 저녁 수요에 적정하다"
2. **근거 표** — 시나리오별 서비스율·대기 분위·가동률·공차 비율
3. **분포 그림** — 평균이 숨긴 것을 보여 주는 히스토그램 한 장
4. **파레토 그림** — 선택지의 대가를 보여 주는 산점도 한 장
5. **공간 그림** — 어디가 문제였는지 보여 주는 지도 한 장
6. **한계** — 무엇을 가정했고 무엇을 넣지 않았는지

6번을 빼먹지 마세요. 우리 시뮬레이터는 재배치가 없고, 소요시간을 직선거리로 근사했고, 신호 대기를 반영하지 않았습니다. 이것을 적지 않은 보고서는 결과를 실제보다 확실한 것처럼 보이게 합니다.

## 정리

- 지표는 승객·운영자·도시 세 관점으로 나눠 봅니다. 셋은 서로 부딪힙니다
- 대기시간은 배차받은 사람만 계산됩니다. 서비스율을 같이 보지 않으면 생존 편향에 속습니다
- 포기한 승객을 어떻게 셀지 정하고 그 정의를 밝힙니다
- 평균 대신 중앙값·90분위·분포를 봅니다
- 파레토 프론트 위에서는 데이터가 답을 정해 주지 않습니다. 사람이 정합니다
- 남의 결과와 숫자가 다르면 알고리즘보다 정의와 표본을 먼저 확인합니다
- pydeck 출력은 노트북에 저장하지 않습니다. 크기 가드가 막습니다
- 오래 기다린 승객의 위치를 지도에 찍으면 개선 지점이 보입니다

## 연습문제

```{admonition} 연습 12.1  ★
:class: tip

`wait_p90` 과 `wait_max` 중 어느 쪽이 서비스 품질 지표로 낫다고 생각하나요?
차량 20~80대 시나리오에서 두 값이 어떻게 움직이는지 그려 보고, 근거를 들어 답해 봅시다.

산출물: 꺾은선 그래프 1장, 어느 지표를 택할지와 이유 3~4줄.
```

```{admonition} 연습 12.2  ★★
:class: tip

12.2절에서 포기한 승객에게 30분을 매겼습니다. 이 값을 바꾸면 결론이 바뀝니다.

벌점을 15분, 30분, 60분으로 바꿔 가며 시나리오 순위가 어떻게 달라지는지 봅시다.
순위가 뒤집히는 지점이 있나요? 있다면 그 사실을 보고서에 어떻게 써야 할까요.

산출물: 벌점별 시나리오 순위표, 뒤집히는 지점, 보고서에 쓸 문장 2~3줄.
```

```{admonition} 연습 12.3  ★★★
:class: tip

12.7절에서 오래 기다린 승객이 외곽에 몰려 있는 것을 봤습니다.
이를 지표 하나로 만들어 봅시다.

예: 하남시를 격자로 나누고 칸마다 평균 대기시간을 계산한 뒤, 칸 사이의 불균등을
지니 계수나 최댓값/중앙값 비로 잽니다. 이 지표가 차량 대수에 따라 어떻게 변하나요?

서비스율이 같아도 이 지표가 다른 두 시나리오를 만들 수 있는지 시도해 봅시다.

산출물: 지표 정의와 구현, 차량 대수별 변화 그래프, 공간 형평성이 왜 별도 지표여야 하는지 3~4줄.
```
