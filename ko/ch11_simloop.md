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

# 11장 이산시간 시뮬레이션 루프

앞 장까지 만든 도로망, 최단경로, 수요, 소요시간 모형, 배차 방법을 1분 단위 루프에 연결합니다. 0장에서 함수 한 번으로 실행했던 시뮬레이션의 축약형을 직접 구현합니다.

## 학습 목표

- 이산시간 시뮬레이션의 한 스텝이 무엇을 하는지 순서대로 씁니다
- 상태를 클래스가 아니라 값 몇 개로 표현하는 방법을 봅니다
- 직접 짠 루프와 DTUMOS 녹화본의 입력 조건과 결과를 비교합니다
- 대기시간이 두 부분으로 나뉜다는 것을 확인합니다

## 11.1 분 단위 처리 순서

시간을 1분씩 밉니다. 매 분에 하는 일은 다섯 가지입니다.

```
매 분마다:
    1. 이번 분에 들어온 호출을 대기 목록에 넣는다
    2. 너무 오래 기다린 호출을 포기 처리한다
    3. 대기 승객과 빈 차가 둘 다 있으면 배차한다
    4. 배차된 차의 다음 가용 시각을 계산한다
    5. 이번 분의 상태를 기록한다
```

3번이 10장에서 만든 것입니다. 나머지가 이 장의 일입니다.

1분은 이 교육용 모형에서 정한 시간 간격입니다. 간격을 줄이면 같은 구간의 반복 횟수가 늘어나고, 간격을 늘리면 호출 접수와 배차 시각의 이산화 오차가 커질 수 있습니다.

## 11.2 차량과 요청 상태

차량은 대기 중이거나, 승객을 태우러 가는 중이거나, 태우고 가는 중입니다. 상태 세 개를 열거형으로 만들고 싶어집니다.

이 구현에서는 차량 위치와 다음 배차 가능 시각으로 대기 여부를 계산합니다.

```{code-cell} python
from dataclasses import dataclass

@dataclass
class Vehicle:
    id: int
    location: tuple           # (위도, 경도)
    work_start: int           # 근무 시작 (자정부터의 분)
    work_end: int
    free_at: float = 0.0      # 이 시각 이후 다시 배차받을 수 있습니다

    def idle(self, minute):
        return self.work_start <= minute < self.work_end and self.free_at <= minute
```

`free_at`이 현재 시각보다 크면 운행 중이고, 그렇지 않으면 근무시간 안에서 대기 중입니다. 별도 상태 변수와 가용 시각을 중복해 저장하지 않습니다.

승객도 비슷합니다.

```{code-cell} python
@dataclass
class Request:
    id: int
    origin: tuple
    dest: tuple
    request_time: int
    assigned_time: int | None = None    # 배차가 확정된 시각
    pickup_time: float | None = None    # 차가 실제로 도착한 시각
    dropoff_time: float | None = None
    failed: bool = False
```

`assigned_time` 과 `pickup_time` 을 따로 두는 이유가 있습니다. 11.6절에서 봅니다.

## 11.3 루프

```{code-cell} python
:tags: [remove-output]

# smartmob/teaching/simloop.py 의 simulate() 를 간추린 것입니다.
from smartmob.teaching.dispatch import optimal_match

BOARD_MIN = ALIGHT_MIN = 1.0

def run_loop(requests, fleet, time_start, time_end, travel_time, fail_after_min=10):
    arrivals = {}
    for req in requests:
        arrivals.setdefault(req.request_time, []).append(req)

    waiting, rows = [], []

    for minute in range(time_start, time_end):
        waiting.extend(arrivals.get(minute, []))          # 1) 호출 접수

        keep = []                                          # 2) 포기 처리
        for req in waiting:
            if minute - req.request_time >= fail_after_min:
                req.failed = True
            else:
                keep.append(req)
        waiting = keep

        idle = [v for v in fleet if v.idle(minute)]        # 3) 배차
        if waiting and idle:
            costs = build_costs(waiting, idle, minute, travel_time)
            result = optimal_match(costs)
            for m in result.matches:
                assign(waiting[m.passenger], idle[m.vehicle], minute, m.cost, travel_time)
            done = {m.passenger for m in result.matches}
            waiting = [r for i, r in enumerate(waiting) if i not in done]

        rows.append({                                      # 5) 기록
            "time": minute,
            "waiting_passenger_cnt": len(waiting),
            "fail_passenger_cnt": sum(1 for r in requests if r.failed),
            "empty_vehicle_cnt": sum(1 for v in fleet if v.idle(minute)),
            "driving_vehicle_cnt": sum(1 for v in fleet
                                       if v.work_start <= minute < v.work_end and v.free_at > minute),
        })
    return rows
```

4번(배차된 차의 다음 가용 시각)은 `assign` 안에 있습니다.

```{code-cell} python
:tags: [remove-output]

def assign(req, veh, minute, pickup_min, travel_time):
    ride_min = travel_time(req.origin, req.dest, minute)

    req.assigned_time = minute
    req.pickup_time = minute + pickup_min + BOARD_MIN
    req.dropoff_time = req.pickup_time + ride_min + ALIGHT_MIN

    veh.free_at = req.dropoff_time     # 내려 주고 나서야 다음 손님을 받습니다
    veh.location = req.dest            # 그 자리에 섭니다
```

이 모형에서 차량은 승객을 내려 준 위치에 머물며 다음 배차는 그 위치에서 시작합니다. 수요가 예상되는 위치로 빈 차량을 미리 옮기는 재배치(relocation)는 포함하지 않습니다.

기록의 다섯 컬럼 이름은 DTUMOS의 `record.csv`에 맞춥니다. 같은 이름과 시간 단위를 사용하면 지표와 시계열을 나란히 비교할 수 있습니다.

## 11.4 6시간 실행

```{code-cell} python
import time
from smartmob.data import load_demand, load_vehicles
from smartmob.teaching.simloop import simulate

demand = load_demand("hanam")
vehicles = load_vehicles("hanam")
print(f"수요 {len(demand):,}건, 차량 {len(vehicles)}대")

t0 = time.perf_counter()
run = simulate(demand, vehicles, time_start=1080, time_end=1440)
print(f"실행 {time.perf_counter() - t0:.2f}초")
```

실행시간은 위 셀에서 측정합니다. 이 루프는 도로망 라우팅 대신 직선거리와 고정 평균속도로 소요시간을 계산합니다.

```{code-cell} python
run.summary()
```

```{code-cell} python
run.record.head()
```

## 11.5 DTUMOS 녹화본과 비교

같은 도시, 차량 대수, 요청 목표 건수와 시간 구간으로 실행한 DTUMOS 녹화본을 불러옵니다. 녹화본 결과에는 990건이 포함되고 로컬 입력에는 1,000건이 있으므로 완전히 같은 요청 집합의 대조는 아닙니다.

```{code-cell} python
from smartmob import Dtumos

engine = Dtumos().run_simulation(
    city="hanam", mode="taxi", fleet_size=80, num_passengers=1000,
    time_start=1080, time_end=1440, random_seed=42,
)

mine, theirs = run.summary(), engine.summary()
for key in ("total_passengers", "served_passengers", "service_rate", "avg_waiting_time_min"):
    m, t = mine.get(key), theirs.get(key)
    fmt = (lambda x: f"{x:.3f}") if isinstance(m, float) else (lambda x: f"{x}")
    print(f"{key:24s} 내 루프 {fmt(m):>8s}   엔진 {fmt(t):>8s}")
```

로컬 루프의 평균 대기시간은 4.28분이고 녹화본은 4.08분입니다. 요청 수와 소요시간 모형이 다르므로 이 차이만으로 두 구현의 일치 여부를 판정하지 않습니다.

시계열도 봅니다.

```{code-cell} python
import matplotlib.pyplot as plt
import numpy as np
from smartmob.viz import use_korean_font

use_korean_font()
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(run.record["time"], run.record["driving_vehicle_cnt"], label="내 루프", linewidth=1.2)
ax.plot(engine.record["time"], engine.record["driving_vehicle_cnt"],
        label="DTUMOS 엔진", linewidth=1.2, alpha=0.8)
ax.set_xlabel("시각 (자정부터의 분)"); ax.set_ylabel("운행 중 차량")
ax.legend(); ax.grid(alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

```{code-cell} python
r = np.corrcoef(run.record["driving_vehicle_cnt"], engine.record["driving_vehicle_cnt"])[0, 1]
print(f"운행 차량 시계열 상관계수 {r:.3f}")
```

운행 차량 수 시계열의 상관계수는 약 0.915입니다.

대기 승객 시계열도 같은 방식으로 계산합니다.

```{code-cell} python
mine_wait = run.record["waiting_passenger_cnt"]
their_wait = engine.record["waiting_passenger_cnt"]
print(f"내 루프: 0인 분이 {(mine_wait == 0).mean():.0%}, 평균 {mine_wait.mean():.2f}명")
print(f"엔진:    0인 분이 {(their_wait == 0).mean():.0%}, 평균 {their_wait.mean():.2f}명")
print(f"상관계수 {np.corrcoef(mine_wait, their_wait)[0, 1]:.3f}")
```

상관계수는 약 -0.007입니다. 로컬 기록은 99.4%, 녹화본은 98.9%의 분에서 대기 승객이 0명입니다. 값의 변동이 거의 없는 시계열에서는 작은 차이에도 상관계수가 크게 달라질 수 있으므로, 0인 비율과 평균 대기 인원도 함께 제시합니다.

```{warning}
상관계수를 제시할 때는 두 시계열의 분산과 표본 수를 함께 확인합니다. 값이 거의 일정하면 상관계수만으로 시계열의 유사성을 평가하기 어렵습니다.
```

## 11.6 대기시간은 두 부분입니다

`fail_after_min`은 10분이며 배차 확정 전의 포기 기준입니다. 총 대기시간의 최댓값은 26분입니다.

```{code-cell} python
print(f"최대 대기 {run.summary()['max_waiting_time_min']:.1f}분")
print(f"포기 기준 {run.config['fail_after_min']}분")
```

포기 기준은 배차 확정 전 대기에 적용되고, 총 대기시간에는 배차 뒤 픽업 차량의 이동시간도 포함됩니다.

```{code-cell} python
print(f"호출 → 배차 확정  평균 {run.summary()['avg_assign_wait_min']:.2f}분")
print(f"배차 → 차 도착    평균 {run.summary()['avg_pickup_travel_min']:.2f}분")
print(f"합계              평균 {run.summary()['avg_waiting_time_min']:.2f}분")
```

배차 확정 뒤에는 `fail_after_min`을 다시 검사하지 않습니다. 따라서 픽업 이동시간이 길면 총 대기시간은 10분을 넘을 수 있습니다.

```{code-cell} python
over = [r for r in run.requests if r.wait_min and r.wait_min > 10]
print(f"총 대기가 10분을 넘은 승객 {len(over)}명")
worst = max(over, key=lambda r: r.wait_min)
print(f"  최악: 배차까지 {worst.assign_wait_min:.0f}분 + 차 오는 데 {worst.pickup_travel_min:.1f}분")
```

이 장의 `avg_waiting_time_min`은 요청부터 픽업까지의 시간입니다. 배차 확정까지의 시간은 `avg_assign_wait_min`, 배차 뒤 차량 이동시간은 `avg_pickup_travel_min`으로 따로 확인합니다.

## 11.7 차량 대수별 결과

차량 대수를 20대부터 80대까지 바꿔 서비스율과 대기시간을 계산합니다.

```{code-cell} python
import pandas as pd

rows = []
for n in (20, 40, 60, 80):
    result = simulate(demand, vehicles.head(n), 1080, 1440)
    s = result.summary()
    rows.append({
        "차량": n,
        "서비스율": round(s["service_rate"], 3),
        "평균대기(분)": round(s["avg_waiting_time_min"], 2),
        "최대대기(분)": round(s["max_waiting_time_min"], 1),
        "가동률": round(s["utilization"], 3),
        "공차(km)": s["empty_km"],
    })
pd.DataFrame(rows)
```

차량을 80대에서 40대로 줄이면 서비스율은 1.000에서 0.720으로 낮아집니다. 평균 대기시간은 배차된 요청만 대상으로 계산하므로, 실패 요청이 늘어나는 시나리오에서는 서비스율과 함께 읽어야 합니다.

```{code-cell} python
df = pd.DataFrame(rows)
fig, ax1 = plt.subplots(figsize=(7, 4))
ax1.plot(df["차량"], df["평균대기(분)"], "o-", color="tab:red", label="평균 대기")
ax1.set_xlabel("차량 대수"); ax1.set_ylabel("평균 대기 (분)", color="tab:red")
ax1.tick_params(axis="y", labelcolor="tab:red")

ax2 = ax1.twinx()
ax2.plot(df["차량"], df["서비스율"], "s--", color="tab:blue", label="서비스율")
ax2.set_ylabel("서비스율", color="tab:blue")
ax2.tick_params(axis="y", labelcolor="tab:blue")
ax1.grid(alpha=0.25, linewidth=0.6)
fig.tight_layout();
```

차량 대수를 선택하려면 서비스 목표와 차량 운영비 조건이 추가로 필요합니다. 위 표는 각 차량 대수에서 계산된 서비스율, 대기시간, 가동률을 제공합니다.

## 11.8 배차 방법별 결과

SciPy 할당 해법과 탐욕 배차를 같은 수요와 차량 조건에서 비교합니다.

```{code-cell} python
for method in ("optimal", "greedy"):
    s = simulate(demand, vehicles, 1080, 1440, match=method).summary()
    print(f"{method:8s} 평균대기 {s['avg_waiting_time_min']:.3f}분  "
          f"최대 {s['max_waiting_time_min']:5.1f}분  공차 {s['empty_km']:7.1f}km")
```

차량 80대에서는 평균 대기시간이 4.282분과 4.284분으로 가깝습니다. 대기 요청이 0~1명인 분에는 두 방법이 같은 차량을 선택할 수 있어 총 결과의 차이가 작습니다. 차량을 25대로 줄인 다음 같은 비교를 반복합니다.

```{code-cell} python
for method in ("optimal", "greedy"):
    s = simulate(demand, vehicles.head(25), 1080, 1440, match=method).summary()
    print(f"차량 25대 {method:8s} 평균대기 {s['avg_waiting_time_min']:.3f}분  "
          f"서비스율 {s['service_rate']:.3f}")
```

## 이 장의 실습

노트북 `labs/ch11_simloop.ipynb` 를 열어 함께 돌립니다.

1시간짜리로 먼저 돌려 보고 전체로 늘린 뒤, 녹화된 엔진 결과와 나란히 놓고 비교합니다.

```bash
jupyter lab labs/ch11_simloop.ipynb
```

이 장은 채점받는 실습입니다. 노트북이 아니라 옆의 `labs/ch11_simloop.py` 의 빈칸을 채웁니다.
채운 뒤 자가 채점을 돌립니다. 이 기준이 곧 과제 채점 기준입니다.

```bash
python labs/check.py ch11
```

## 정리

- 한 스텝은 다섯 가지입니다. 호출 접수 → 포기 처리 → 배차 → 차량 상태 갱신 → 기록
- 차량의 대기 여부는 `location`, `free_at`, 근무시간으로 계산합니다
- 실행시간은 직선거리 소요시간 모형을 사용한 조건에서 측정합니다
- 로컬 루프와 녹화본은 요청 수와 소요시간 모형이 다르다는 한계가 있습니다
- 값이 거의 일정한 시계열은 상관계수와 함께 0인 비율과 평균을 확인합니다
- 대기시간은 "배차까지"와 "차가 오는 동안"으로 나뉩니다. 포기 기준은 앞부분에만 걸립니다
- 이 예제에서는 차량 80대보다 25대에서 두 배차 방법의 차이가 크게 나타납니다
- 12장에서 이 결과를 지표로 정리하고 그림으로 그립니다

## 연습문제

```{admonition} 연습 11.1  ★
:class: tip

`fail_after_min` 을 3, 5, 10, 20분으로 바꿔 가며 서비스율과 평균 대기시간을 재 봅시다.
포기 기준을 늘리면 서비스율이 오르는데, 대신 무엇이 나빠지나요?

산출물: 기준별 지표 표, 어느 값이 적절한지와 그 근거 3줄.
```

```{admonition} 연습 11.2  ★★
:class: tip

`travel_time` 인자에 9장의 ETA 모델을 넣어 봅시다.

```python
def eta_time(origin, dest, minute):
    features = make_features(origin, dest, hour=minute // 60)
    return model.predict(pd.DataFrame([features])[FEATURES])[0]
```

직선거리 근사와 ETA 모델의 실행 시간, 평균 대기시간, 서비스율을 비교합니다.
한 건씩 예측하면 느립니다. 행렬 전체를 한 번에 예측하도록 고쳐 보고 얼마나 빨라지는지도 확인합니다.

산출물: 두 모형의 비교표, 배치 예측으로 얼마나 빨라졌는지.
```

```{admonition} 연습 11.3  ★★★
:class: tip

차량을 내려 준 자리에 두지 않고 **수요가 많은 곳으로 옮기는** 재배치를 넣어 봅시다.

가장 단순한 방법: 20분 이상 배차를 못 받은 빈 차를, 최근 30분간 호출이 가장 많았던
지역의 중심으로 이동시킵니다. 이동하는 동안에는 배차받지 못합니다.

재배치를 켠 경우와 끈 경우의 평균 대기시간, 서비스율, 공차 거리를 비교합니다.
공차 거리는 늘어날 텐데, 그만큼의 값어치가 있나요?

산출물: 구현 코드, 켬/끔 비교표, 값어치에 대한 판단과 근거 4~5줄.
```
