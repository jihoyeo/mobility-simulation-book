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

# 4장 시간대별 속도와 실제 라우팅 엔진

3장에서 하남시청에서 미사역까지 5분 30초가 나왔습니다. 오전 8시에도 그럴까요.

그럴 리가 없습니다. 우리가 쓴 `free_flow_speed_kmh` 는 **막히지 않았을 때의 속도**입니다. 도로 표지판에 적힌 제한속도에 가깝고, 실제로 그 속도로 달릴 수 있는 시간대는 새벽뿐입니다.

이 장에서 시간대별 실측 속도로 바꿔 봅니다. 그리고 시뮬레이터가 이 계산을 어떻게 감당하는지 봅니다.

## 학습 목표

- 시간대별 속도 컬럼을 갈아 끼우고 소요시간이 얼마나 달라지는지 잽니다
- 속도를 바꾸면 최단"경로" 자체가 달라진다는 것을 확인합니다
- 관측이 없는 엣지를 어떻게 처리할지 정합니다
- 시뮬레이션이 필요로 하는 질의 수를 세어 보고, 실제 엔진이 왜 필요한지 설명합니다

## 4.1 속도 컬럼이 여러 개입니다

2장에서 엣지 표를 볼 때 지나쳤던 컬럼들이 있습니다.

```{code-cell} python
import pandas as pd
from smartmob.data import data_path

edges = pd.read_parquet(data_path("hanam/road_graph_edges.parquet"))
[c for c in edges.columns if "speed" in c or "weekday" in c]
```

`weekday_*_p50` 여덟 개가 주중 시간대별 관측 속도입니다. `p50` 은 중앙값이라는 뜻입니다. 국가교통DB 계열의 속도 통계에서 왔습니다.

시간대 구분은 이렇습니다.

| 슬롯 | 시간 | 성격 |
|---|---|---|
| `offpeak` | 06–07 | 새벽, 거의 자유류 |
| `am_peak` | 07–09 | 오전 첨두 |
| `am_shoulder` | 09–10 | 첨두 직후 |
| `midday` | 10–12 | 낮 |
| `afternoon` | 12–17 | 오후 |
| `pm_peak` | 17–19 | 오후 첨두 |
| `pm_shoulder` | 19–22 | 저녁 |
| `night` | 22–06 | 심야 |

중앙값을 비교해 봅니다.

```{code-cell} python
cols = ["free_flow_speed_kmh"] + [f"weekday_{s}_p50" for s in
        ["offpeak", "am_peak", "midday", "afternoon", "pm_peak", "night"]]

for c in cols:
    print(f"{c:26s} 중앙값 {edges[c].median():5.1f} km/h   결측 {edges[c].isna().mean():5.1%}")
```

자유류 30km/h 였던 도로의 실제 중앙값은 19~22km/h입니다. 오후 첨두가 18.9km/h로 가장 느립니다.

그리고 **21.7%가 비어 있습니다.** 관측 장비가 없거나 통행량이 적어 통계를 못 낸 도로입니다. 이런 엣지는 자유류 속도로 채웁니다. 완벽하지 않지만, 비워 두면 그 도로를 아예 못 쓰게 되므로 더 나쁩니다.

```{code-cell} python
missing = edges["weekday_pm_peak_p50"].isna()
edges.loc[missing, "highway"].value_counts().head(5)
```

빠진 도로는 대부분 `service`(이면도로)와 `residential`(주택가)입니다. 간선도로는 거의 다 관측이 있습니다. 결측을 자유류로 채우는 것이 그럭저럭 타당한 이유입니다.

## 4.2 같은 구간, 다른 시간

`load_road_graph` 에 `speed_column` 을 주면 그 컬럼으로 비용을 계산합니다.

```{code-cell} python
from smartmob.data import load_road_graph
from smartmob.teaching.dijkstra import NoPath, dijkstra

SLOTS = {
    "자유류":      "free_flow_speed_kmh",
    "새벽 6시":    "weekday_offpeak_p50",
    "오전 8시":    "weekday_am_peak_p50",
    "낮 11시":     "weekday_midday_p50",
    "오후 6시":    "weekday_pm_peak_p50",
    "심야 23시":   "weekday_night_p50",
}

graphs = {label: load_road_graph("hanam", modes=("drive",), speed_column=col)
          for label, col in SLOTS.items()}

base = graphs["자유류"]
start = base.nearest_node(37.5393, 127.2148)   # 하남시청
goal = base.nearest_node(37.5606, 127.1930)    # 미사역
```

```{code-cell} python
results = {}
for label, g in graphs.items():
    p = dijkstra(g, start, goal)
    results[label] = p
    print(f"{label:8s} {p.duration_s / 60:5.2f}분   경로 노드 {len(p.nodes)}개")
```

자유류로 5분 34초였던 구간이 오후 첨두에는 8분 59초입니다. **62% 더 걸립니다.**

같은 하루 안에서도 심야(7분 58초)와 오후 첨두(8분 59초)가 1분 차이납니다. 이 차이를 무시하고 하루 종일 같은 속도로 시뮬레이션하면, 저녁 시간대 배차가 실제보다 훨씬 잘 되는 것처럼 나옵니다.

## 4.3 경로 자체가 달라집니다

시간만 달라진 게 아닙니다. 지나가는 길이 바뀌었습니다.

```{code-cell} python
free_flow_path = results["자유류"].nodes
for label, p in results.items():
    same = "같음" if p.nodes == free_flow_path else "다름"
    print(f"{label:8s} 자유류 경로와 {same}")
```

실측 속도를 넣는 순간 전부 다른 길로 갑니다. 자유류에서는 큰길이 빨랐는데, 큰길이 막히는 시간대에는 골목이 나아지기 때문입니다.

한 쌍만으로는 우연일 수 있으니 여러 쌍으로 확인합니다.

```{code-cell} python
import random

am = graphs["오전 8시"]
night = graphs["심야 23시"]
rng = random.Random(1)
nodes = [n for n in base.adj if base.adj[n]]

changed, tested = 0, 0
while tested < 50:
    s, t = rng.choice(nodes), rng.choice(nodes)
    if s == t:
        continue
    try:
        p_am = dijkstra(am, s, t)
        p_night = dijkstra(night, s, t)
    except NoPath:
        continue          # 3장에서 본 "경로 없음"
    tested += 1
    if p_am.nodes != p_night.nodes:
        changed += 1

print(f"오전 첨두와 심야에서 경로가 달라진 쌍: {changed}/{tested}")
```

절반 가까이가 달라집니다.

```{warning}
"최단경로를 미리 계산해 캐시해 두면 되지 않나"라는 생각이 자연스럽게 듭니다. 그런데 시간대마다 경로가 달라지므로, 캐시하려면 시간대 수만큼 따로 저장해야 합니다. 시뮬레이터는 이 문제를 다르게 풉니다. 4.5절에서 봅니다.
```

## 4.4 시뮬레이션은 질의를 몇 번 할까

0장에서 돌린 시뮬레이션을 다시 떠올려 봅시다. 승객 990명, 차량 80대, 저녁 6시부터 자정까지.

배차가 일어날 때마다 시뮬레이터는 "지금 비어 있는 차 중 누가 이 승객에게 가장 빨리 도착하는가"를 알아야 합니다. 비어 있는 차가 30대면 질의가 30번입니다.

```{code-cell} python
from smartmob import Dtumos

sim = Dtumos().run_simulation(
    city="hanam", mode="taxi", fleet_size=80, num_passengers=1000,
    time_start=1080, time_end=1440, random_seed=42,
)

n_requests = len(sim.passengers)
avg_idle = sim.result["empty_vehicle_num"].mean()
print(f"호출 {n_requests}건 × 대기 차량 평균 {avg_idle:.0f}대 = 약 {n_requests * avg_idle:,.0f}회 질의")
```

3만 번이 넘습니다. 여기에 실제 주행 경로까지 뽑아야 하므로 더 늘어납니다.

우리 다익스트라는 한 번에 7밀리초쯤 걸렸습니다.

```{code-cell} python
python_ms = 7.4
total_seconds = n_requests * avg_idle * python_ms / 1000
print(f"파이썬 다익스트라로만 하면 {total_seconds / 60:.0f}분")
```

시뮬레이션 한 번에 몇 분입니다. 차량 대수를 바꿔 가며 스무 번 돌리려면 한 시간이 넘습니다. 파일럿 프로젝트에서 파라미터를 훑을 때 이건 곤란합니다.

## 4.5 실제 엔진이 하는 일

DTUMOS 의 라우팅 엔진은 세 가지를 다르게 합니다.

**첫째, 축약 계층을 미리 만듭니다.** Contraction Hierarchies 라고 부릅니다. 3장 끝에서 말한 그것입니다. 도로망을 한 번 전처리해 지름길을 넣어 두면, 질의당 확정 노드가 수백 개로 줄어듭니다. 전처리에 몇 초가 들지만 시뮬레이션은 같은 도로망에 수만 번 질의하므로 곧 회수됩니다.

둘째, 한 대 한 대 묻지 않고 행렬로 한 번에 계산합니다. "승객 20명 × 대기 차량 30대"는 600번의 개별 질의가 아니라 20×30 행렬 하나입니다. 출발지 하나에서 모든 도착지까지를 한 번의 탐색으로 얻는 방법(PHAST)이 있습니다. 600번이 아니라 20번이면 됩니다.

셋째, 시간대가 바뀔 때 속도만 갈아 끼웁니다. 4.3절에서 본 문제입니다. 시뮬레이션 시각이 오후 7시를 넘으면 `pm_peak` 에서 `pm_shoulder` 로 넘어갑니다. 이때 그래프를 새로 만들지 않고 엣지 속도 배열만 바꿔 축약 계층을 갱신합니다. 처음부터 다시 만드는 것보다 다섯 배 빠릅니다.

이 셋 중 어느 것도 우리가 직접 짜지 않습니다. 필요할 때 HTTP로 부릅니다.

```{code-cell} python
:tags: [skip-execution]

dt = Dtumos()
result = dt.route(
    "hanam",
    origin=(37.5393, 127.2148),      # 하남시청
    destination=(37.5606, 127.1930),  # 미사역
)
print(f"{result['duration'] / 60:.2f}분, {result['distance'] / 1000:.2f}km")
print(f"경로 좌표 {len(result['route'])}개")
```

서버가 있으면 우리 구현과 나란히 놓고 비교할 수 있습니다.

```{code-cell} python
:tags: [skip-execution]

mine = dijkstra(graphs["오후 6시"], start, goal)
print(f"내 다익스트라  {mine.duration_s / 60:.2f}분")
print(f"DTUMOS 엔진   {result['duration'] / 60:.2f}분")
```

완전히 같지는 않습니다. 엔진은 승하차 시간과 회전 제한 같은 것을 더 반영하기 때문입니다. 값이 크게 벌어지면 스냅한 노드가 다른 경우가 대부분입니다.

```{note}
이 두 셀은 서버가 있어야 돌아갑니다. 서버 없이 읽는 중이라면 건너뛰어도 됩니다. 이 장의 나머지와 5장 이후는 서버 없이 진행됩니다.
```

## 4.6 실습: 하루 동안의 통행시간 곡선

같은 구간을 시간대별로 계산해 하루 곡선을 그립니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()

order = ["새벽 6시", "오전 8시", "낮 11시", "오후 6시", "심야 23시"]
minutes = [results[k].duration_s / 60 for k in order]
free = results["자유류"].duration_s / 60

fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(order, minutes, color="tab:blue", width=0.55)
ax.axhline(free, color="tab:red", linestyle="--", linewidth=1.2)
ax.text(4.4, free + 0.1, f"자유류 {free:.1f}분", color="tab:red", ha="right", fontsize=9)
ax.set_ylabel("소요시간 (분)")
ax.set_title("하남시청 → 미사역, 시간대별 소요시간")
ax.grid(axis="y", alpha=0.25, linewidth=0.6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

자유류 선이 모든 시간대보다 아래에 있습니다. 자유류 속도만 쓰는 시뮬레이션은 언제나 실제보다 낙관적인 결과를 냅니다.

## 정리

- `weekday_*_p50` 여덟 개 컬럼이 주중 시간대별 관측 속도입니다. `p50` 은 중앙값입니다
- 하남시 도로의 자유류 중앙값은 30km/h인데 실제 관측 중앙값은 19~22km/h입니다
- 하남시청→미사역은 자유류 5분 34초, 오후 첨두 8분 59초로 62% 차이가 납니다
- 속도를 바꾸면 소요시간뿐 아니라 **경로 자체**가 바뀝니다. 무작위 쌍의 절반 가까이가 달라집니다
- 관측이 없는 엣지가 21.7%이고 대부분 이면도로입니다. 자유류로 채웁니다
- 시뮬레이션 한 번에 3만 회 이상 질의합니다. 파이썬 다익스트라로는 몇 분이 걸립니다
- 실제 엔진은 축약 계층 + 행렬 질의 + 속도 교체로 이를 감당합니다. 우리는 HTTP로 부릅니다
- 5장에서는 차 대신 버스와 지하철로 갑니다. 시간표가 있는 세계는 규칙이 다릅니다

## 연습문제

```{admonition} 연습 4.1  ★
:class: tip

`highway` 종류별로 자유류 속도와 오후 첨두 관측 속도의 차이를 구해 봅시다.
어느 도로 종류가 가장 많이 느려지나요?

산출물: 도로 종류별 비교표(자유류, 오후첨두, 감소율) 상위 6행.
```

```{admonition} 연습 4.2  ★★
:class: tip

관측 속도가 없는 엣지를 자유류로 채우는 대신, **같은 `highway` 종류의 관측 중앙값**으로 채워 봅시다.
두 방식으로 하남시청→미사역 소요시간을 계산해 비교하고, 어느 쪽이 더 타당한지 근거를 들어 설명합니다.

산출물: 두 방식의 소요시간, 어느 쪽을 택할지와 그 이유 3~4줄.
```

```{admonition} 연습 4.3  ★★★
:class: tip

출발 시각을 넣으면 그 시각의 속도로 라우팅하는 함수를 만들어 봅시다.
더 나아가, 경로를 따라가는 동안 시각이 흘러 도중에 시간대가 바뀌는 것까지 반영해 봅시다
(예: 오후 6시 50분에 출발해 7시를 넘기는 경우).
이것을 시간의존 최단경로(time-dependent shortest path)라고 합니다.

산출물: 구현 코드, 시간대 고정 방식과의 소요시간 차이, 어떤 경우에 차이가 커지는지 설명.
```
