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

필요한 재료가 다 모였습니다. 도로망(2장), 최단경로(3~4장), 수요(8장), 소요시간 예측(9장), 배차(10장).

이 장에서 이들을 시간 축 위에서 결합합니다. 만드는 것은 0장에서 `dt.run_simulation()` 한 줄로 불렀던 시뮬레이션 루프이고, 직접 구현하는 세 가지 중 마지막입니다. 150줄 정도입니다.

## 학습 목표

- 이산시간 시뮬레이션의 한 스텝이 무엇을 하는지 순서대로 씁니다
- 상태를 클래스가 아니라 값 몇 개로 표현하는 방법을 봅니다
- 직접 짠 루프를 실제 엔진과 대조하고 어디서 갈라지는지 찾습니다
- 대기시간이 두 부분으로 나뉜다는 것을 확인합니다

## 11.1 한 스텝에 무엇을 하는가

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

1분이라는 단위는 정한 것입니다. 더 짧게 하면 정밀해지지만 느려지고, 길게 하면 반대입니다. 택시 배차에서 1분은 사람이 체감하는 단위와 비슷해 적당합니다.

## 11.2 상태를 무엇으로 들고 있을 것인가

차량은 대기 중이거나, 승객을 태우러 가는 중이거나, 태우고 가는 중입니다. 상태 세 개를 열거형으로 만들고 싶어집니다.

그런데 잘 생각해 보면 필요한 것은 두 가지뿐입니다. 지금 어디 있는가와 언제 다시 자유로워지는가입니다.

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

`free_at` 하나로 "운행 중"과 "대기 중"이 표현됩니다. 상태를 따로 관리하면 상태와 시각이 어긋나는 버그가 생기는데, 이렇게 하면 그럴 수가 없습니다.

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

```{note}
실제 DTUMOS 는 이것을 클래스가 아니라 pandas DataFrame 여러 개로 들고 있습니다. 승객 1만 명을 다룰 때는 파이썬 객체 1만 개보다 DataFrame 하나가 훨씬 빠르기 때문입니다. 읽기는 우리 방식이 쉽고, 돌리기는 그쪽이 빠릅니다.
```

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

마지막 두 줄이 중요합니다. 차량은 승객을 내려 준 자리에 머뭅니다. 다음 호출은 거기서 출발합니다. 실제 택시 기사는 손님이 많은 곳으로 빈 차를 옮기는데, 그것을 **재배치(relocation)** 라고 합니다. 이 책에서는 다루지 않습니다.

기록에 남기는 컬럼 다섯 개는 DTUMOS 의 `record.csv` 와 똑같이 맞췄습니다. 같은 형식이라야 대조할 수 있습니다.

## 11.4 돌려 봅니다

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

0.4초입니다. 4장에서 걱정했던 "몇 분"이 아닙니다. 소요시간을 직선거리로 근사했기 때문입니다.

```{code-cell} python
run.summary()
```

```{code-cell} python
run.record.head()
```

## 11.5 엔진과 맞춰 보기

같은 도시, 같은 수요, 같은 차량으로 실제 엔진을 돌린 결과가 있습니다.

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

평균 대기시간이 4.28분 대 4.08분입니다. 0.2분 차이입니다.

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

모양이 거의 겹칩니다.

대기 승객 시계열도 비교하고 싶어집니다. 그런데 여기에 함정이 있습니다.

```{code-cell} python
mine_wait = run.record["waiting_passenger_cnt"]
their_wait = engine.record["waiting_passenger_cnt"]
print(f"내 루프: 0인 분이 {(mine_wait == 0).mean():.0%}, 평균 {mine_wait.mean():.2f}명")
print(f"엔진:    0인 분이 {(their_wait == 0).mean():.0%}, 평균 {their_wait.mean():.2f}명")
print(f"상관계수 {np.corrcoef(mine_wait, their_wait)[0, 1]:.3f}")
```

상관계수가 0에 가깝습니다. 그렇다고 두 결과가 다른 것이 아닙니다. **양쪽 다 거의 항상 0이기 때문입니다.** 값이 거의 변하지 않는 두 계열의 상관계수는 남은 잡음끼리의 상관이라 아무 의미가 없습니다.

이런 경우에는 상관계수 대신 분포를 비교합니다. 0인 비율과 평균이 비슷하면 같은 결과입니다.

```{warning}
지표를 고를 때 "그 지표가 무엇을 잴 수 있는 상태인가"를 먼저 봐야 합니다. 대기 승객이 거의 0인 시나리오에서 상관계수를 보고하면, 숫자는 나오지만 뜻이 없습니다. 프로젝트 보고서에서 자주 나오는 실수입니다.
```

## 11.6 대기시간은 두 부분입니다

`fail_after_min` 은 10분입니다. 10분을 기다려도 배차가 안 되면 포기합니다. 그런데 총 대기시간의 최댓값을 보면 26분입니다.

```{code-cell} python
print(f"최대 대기 {run.summary()['max_waiting_time_min']:.1f}분")
print(f"포기 기준 {run.config['fail_after_min']}분")
```

모순처럼 보입니다. 대기시간이 두 부분으로 나뉘기 때문입니다.

```{code-cell} python
print(f"호출 → 배차 확정  평균 {run.summary()['avg_assign_wait_min']:.2f}분")
print(f"배차 → 차 도착    평균 {run.summary()['avg_pickup_travel_min']:.2f}분")
print(f"합계              평균 {run.summary()['avg_waiting_time_min']:.2f}분")
```

**포기 기준은 앞부분에만 걸립니다.** 배차가 확정된 뒤에는 차가 아무리 멀어도 기다립니다. 멀리 있는 차가 배차되면 총 대기가 10분을 훌쩍 넘습니다.

```{code-cell} python
over = [r for r in run.requests if r.wait_min and r.wait_min > 10]
print(f"총 대기가 10분을 넘은 승객 {len(over)}명")
worst = max(over, key=lambda r: r.wait_min)
print(f"  최악: 배차까지 {worst.assign_wait_min:.0f}분 + 차 오는 데 {worst.pickup_travel_min:.1f}분")
```

실제 엔진도 같은 구조입니다. 지표를 읽을 때 이 둘을 구분해야 합니다. "평균 대기 4분"이라는 보고를 받으면 어느 대기인지 물어야 합니다.

## 11.7 조건을 바꿔 보기

시뮬레이터를 만든 이유가 이것입니다. 1장의 질문으로 돌아갑니다. 차량을 줄이면 어떻게 될까요.

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

이 표가 1장에서 던진 질문의 답입니다.

차량을 80대에서 40대로 줄이면 가동률이 크게 오르지만 서비스율이 떨어지고 대기시간이 늡니다. 20대에서는 상당수가 배차를 못 받습니다.

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

어느 지점을 고를지는 이 그림이 정해 주지 않습니다. 승객의 대기시간과 운영자의 차량 비용 중 무엇을 얼마나 중히 볼지는 사람이 정합니다. 시뮬레이터가 하는 일은 **선택지마다 대가가 무엇인지 숫자로 보여 주는 것**까지입니다.

## 11.8 배차 방법을 바꿔 보기

10장에서 헝가리안이 탐욕보다 낫다고 했습니다. 시뮬레이션 전체에서도 그럴까요.

```{code-cell} python
for method in ("optimal", "greedy"):
    s = simulate(demand, vehicles, 1080, 1440, match=method).summary()
    print(f"{method:8s} 평균대기 {s['avg_waiting_time_min']:.3f}분  "
          f"최대 {s['max_waiting_time_min']:5.1f}분  공차 {s['empty_km']:7.1f}km")
```

차이가 작습니다. 10장에서 14%였던 것이 여기서는 1% 남짓입니다.

왜일까요. 10장 실험에서는 승객 8명과 차량 10대가 동시에 있었습니다. 지금 시뮬레이션에서는 대부분의 분에 대기 승객이 0~1명입니다. 짝지을 것이 하나면 탐욕이든 최적이든 같은 답이 나옵니다.

**배차 알고리즘은 수요가 공급을 압박할 때만 의미가 있습니다.** 차량을 줄여 보면 확인됩니다.

```{code-cell} python
for method in ("optimal", "greedy"):
    s = simulate(demand, vehicles.head(25), 1080, 1440, match=method).summary()
    print(f"차량 25대 {method:8s} 평균대기 {s['avg_waiting_time_min']:.3f}분  "
          f"서비스율 {s['service_rate']:.3f}")
```

## 정리

- 한 스텝은 다섯 가지입니다. 호출 접수 → 포기 처리 → 배차 → 차량 상태 갱신 → 기록
- 차량 상태는 `location` 과 `free_at` 두 값이면 충분합니다. 별도 상태 변수를 두면 어긋납니다
- 하남 6시간 시뮬레이션이 0.4초에 끝납니다. 직선거리 근사 덕분입니다
- 우리 루프의 평균 대기 4.28분, 엔진 4.08분. 운행 차량 시계열 상관 0.9 이상입니다
- 대기 승객 시계열은 양쪽 다 거의 0이라 상관계수로 비교하면 안 됩니다. 분포를 봅니다
- 대기시간은 "배차까지"와 "차가 오는 동안"으로 나뉩니다. 포기 기준은 앞부분에만 걸립니다
- 배차 알고리즘의 차이는 수요가 공급을 압박할 때만 드러납니다
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

직선거리 근사와 비교해 (a) 실행 시간, (b) 평균 대기시간, (c) 서비스율이 어떻게 달라지는지 재 봅시다.
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
