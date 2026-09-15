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

3장에서 하남시청에서 미사역까지 5분 32초가 나왔습니다. 오전 8시에도 그럴까요.

이 장에서는 `free_flow_speed_kmh` 대신 시간대별 관측 속도로 통행시간과 경로를 계산합니다. 이어서 시뮬레이션에서 반복되는 경로 질의를 전용 엔진에 맡기는 방법을 살펴봅니다.

## 학습 목표

- 시간대별 속도 컬럼을 적용하고 소요시간 차이를 계산합니다
- 엣지 비용에 따라 최단경로가 달라지는지 확인합니다
- 관측이 없는 엣지를 어떻게 처리할지 정합니다
- 배차 과정에서 계산하는 차량·승객 간 비용의 수를 추정합니다

## 4.1 속도 컬럼이 여러 개입니다

2장에서 읽은 엣지 표에는 자유류 속도와 시간대별 관측 속도가 함께 들어 있습니다. 자동차가 통행할 수 있는 엣지만 골라 컬럼 이름을 확인합니다.

```{code-cell} python
import pandas as pd
from smartmob.data import data_path
from smartmob.teaching.graph import DRIVE_HIGHWAYS

edges = pd.read_parquet(data_path("hanam/road_graph_edges.parquet"))
edges = edges[edges["highway"].isin(DRIVE_HIGHWAYS)]      # 2장처럼 자동차 도로만 남깁니다
[c for c in edges.columns if "speed" in c or "weekday" in c]
```

`weekday_*_p50` 여덟 개는 주중 시간대별 속도 중앙값입니다. `p50` 은 50번째 백분위수, 즉 중앙값을 뜻합니다.

시간대 구분은 이렇습니다.

| 슬롯 | 시간 | 성격 |
|---|---|---|
| `offpeak` | 06–07 | 오전 비첨두 |
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

자동차 통행 엣지의 자유류 속도 중앙값은 30.0 km/h입니다. 시간대별 관측값의 중앙값은 18.9~22.3 km/h이며, 오후 첨두가 18.9 km/h로 가장 낮습니다.

오후 첨두 속도는 엣지의 21.7%에서 빠져 있습니다. 이 파일만으로는 개별 결측 원인을 알 수 없습니다. `load_road_graph` 는 결측값을 같은 엣지의 `free_flow_speed_kmh` 로 채워 연결을 유지합니다.

```{code-cell} python
missing = edges["weekday_pm_peak_p50"].isna()
edges.loc[missing, "highway"].value_counts().head(5)
```

결측 엣지 수는 `residential` 이 2,997개, `service` 가 1,556개로 가장 많습니다. 자유류 속도로 대체하면 이 도로들의 통행시간을 짧게 계산할 수 있습니다. 이 때문에 4.3절에서는 경로 변화와 `free_flow_speed_kmh` 대체 효과를 함께 확인합니다.

## 4.2 같은 구간, 다른 시간

`load_road_graph` 에 `speed_column` 을 주면 그 컬럼으로 비용을 계산합니다. 여기서 부르는 `dijkstra` 는 3.8절에서 본 정리된 판입니다. `Path` 객체를 돌려주고, 길이 없으면 `NoPath` 를 던집니다.

```{code-cell} python
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

자유류로 5분 32초였던 구간이 오후 첨두에는 8분 59초입니다. **62% 더 걸립니다.**

심야는 7분 57초로 오후 첨두보다 1분 2초 짧습니다. 하루 종일 자유류 속도를 쓰면 이 구간의 오후 6시 통행시간을 3분 27초 작게 계산합니다. 이 오차는 차량 도착시각과 다음 배차 가능 시각에도 이어집니다.

## 4.3 시간대별 경로를 비교합니다

소요시간뿐 아니라 선택된 노드열도 달라질 수 있습니다. 각 시간대의 결과를 자유류 경로와 비교합니다.

```{code-cell} python
free_flow_path = results["자유류"].nodes
for label, p in results.items():
    same = "같음" if p.nodes == free_flow_path else "다름"
    print(f"{label:8s} 자유류 경로와 {same}")
```

실측 속도를 넣는 순간 전부 다른 길로 갑니다. 어느 길을 버리고 어느 길을 택했는지 도로 종류별 거리로 봅니다.

```{code-cell} python
from collections import Counter


def km_by_highway(g, p):
    km = Counter()
    for u, v in zip(p.nodes, p.nodes[1:]):
        idx = next(i for nb, _, i in g.neighbors(u) if nb == v)
        km[g.edges.loc[idx, "highway"]] += g.edges.loc[idx, "length"] / 1000
    return {h: round(float(d), 2) for h, d in km.most_common(3)}


for label in ["자유류", "오후 6시"]:
    print(f"{label:6s} {km_by_highway(graphs[label], results[label])}")
```

자유류 경로는 4.2km 중 3.1km 가 2차 간선(`secondary`)입니다. 실측 속도를 넣으면 그 길을 버리고 1차 간선(`primary`)과 3차 도로(`tertiary`)를 잇는 길로 갑니다. 큰길이 막혀 골목으로 가는 것이 아니라, 관측 속도가 낮게 잡힌 구간을 피해 다른 큰길로 가는 것입니다.

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

오전 첨두와 심야의 경로가 달라진 경우는 무작위 50쌍 중 21쌍입니다. 이 값에는 실제 속도 차이와 결측치 처리의 영향이 함께 들어 있습니다.

```{warning}
최단경로를 미리 계산해 두더라도 시간대별 비용이 달라지면 같은 결과를 재사용할 수 없습니다. 모든 출발지·목적지 조합을 시간대마다 저장하는 대신, 실제 엔진은 반복 질의를 줄이는 자료구조와 알고리즘을 사용합니다. 4.5절에서 그 방법을 살펴봅니다.
```

## 4.4 배차에 필요한 비용을 몇 번 계산할까

0장의 시뮬레이션에는 승객 990명과 차량 80대가 있습니다. 운행 시간은 오후 6시부터 자정까지입니다.

승객 한 명을 배차하려면 대기 차량별 도착 비용을 비교해야 합니다. 대기 차량이 30대라면 차량·승객 조합 30개의 비용이 필요합니다.

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

호출 수와 평균 대기 차량 수를 곱하면 약 3만 1천 개입니다. 모든 후보 비용을 개별 최단경로 질의로 구한다고 가정한 추정치입니다.

질의 한 건이 7.4ms 걸린다고 가정해 전체 계산시간을 추정합니다. 아래 값은 3장 실습에서 직접 측정한 값으로 바꿀 수 있습니다.

```{code-cell} python
python_ms = 7.4
total_seconds = n_requests * avg_idle * python_ms / 1000
print(f"파이썬 다익스트라로만 하면 {total_seconds / 60:.0f}분")
```

시뮬레이션 한 번에 몇 분입니다. 차량 대수를 바꿔 가며 스무 번 돌리려면 한 시간이 넘습니다. 기말 프로젝트에서 차량 대수와 배차 규칙을 훑으려면 이 속도로는 부족합니다.

## 4.5 실제 엔진이 하는 일

이 책의 `Dtumos.route` 는 최단경로 계산을 HTTP 서버에 요청합니다. [공개된 DTUMOS 구현][dtumos-repo]을 보면 차량 경로 계산에는 OSRM(Open Source Routing Machine)을 사용합니다.

첫째, 축약 계층(Contraction Hierarchies)을 미리 만듭니다. 3장 끝에서 이름만 말한 방법입니다. 질의를 받기 전에 그래프를 한 번 전처리해서, 중요하지 않은 노드를 하나씩 없애면서 그 자리를 대신하는 지름길 엣지를 넣습니다. 이렇게 만든 계층 위에서 출발점과 도착점 양쪽에서 위로만 탐색하면 확정 노드가 크게 줄어듭니다. 전처리에 몇 초가 들지만 시뮬레이션은 같은 도로망에 수만 번 질의하므로 곧 회수됩니다.

둘째, 한 대 한 대 묻지 않고 행렬로 한 번에 계산합니다. "승객 20명 × 대기 차량 30대"는 600번의 개별 질의가 아니라 20×30 행렬 하나입니다. 출발지 하나에서 모든 도착지까지를 한 번의 탐색으로 얻으면 600번이 아니라 20번이면 됩니다.

셋째, 시간대가 바뀔 때 속도만 갈아 끼웁니다. 4.3절에서 본 문제입니다. 시뮬레이션 시각이 오후 7시를 넘으면 `pm_peak` 에서 `pm_shoulder` 로 넘어갑니다. 이때 그래프를 새로 만들지 않고 엣지 속도 배열만 바꿔 축약 계층을 갱신합니다. 처음부터 다시 만드는 것보다 빠릅니다.

여기서는 엔진 내부 알고리즘을 구현하지 않고 경로 한 건을 요청합니다.

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

같은 좌표에 대해 4.2절의 다익스트라 결과와 서버 응답을 출력합니다.

```{code-cell} python
:tags: [skip-execution]

mine = dijkstra(graphs["오후 6시"], start, goal)
print(f"내 다익스트라  {mine.duration_s / 60:.2f}분")
print(f"DTUMOS 엔진   {result['duration'] / 60:.2f}분")
```

`Dtumos.route` 호출에는 `speed_column` 인수가 없습니다. 따라서 두 계산이 같은 속도 조건을 사용했다고 볼 수 없으며, 여기서는 값의 일치 여부를 평가하지 않습니다.

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

자유류 선이 모든 시간대보다 아래에 있습니다. 이 구간에서는 어느 시간대도 자유류보다 느립니다. 자유류 속도만 쓰는 시뮬레이션은 그만큼 낙관적인 결과를 냅니다.

## 이 장의 실습

노트북 `labs/ch04_speeds_engine.ipynb` 를 열어 함께 돌립니다.

하남시청과 미사역 사이의 소요시간을 시간대별로 계산하고, 선택된 경로를 지도에서 비교합니다.

```bash
jupyter lab labs/ch04_speeds_engine.ipynb
```

## 정리

- `weekday_*_p50` 여덟 개 컬럼이 주중 시간대별 관측 속도입니다. `p50` 은 중앙값입니다
- 하남시 도로의 자유류 중앙값은 30km/h인데 실제 관측 중앙값은 19~22km/h입니다
- 하남시청→미사역은 자유류 5분 32초, 오후 첨두 8분 59초로 62% 차이가 납니다
- 속도를 바꾸면 소요시간뿐 아니라 **경로 자체**가 바뀝니다. 무작위 쌍의 절반 가까이가 달라집니다
- 관측이 없는 엣지가 21.7%이고 대부분 이면도로입니다. 자유류로 채웁니다
- 시뮬레이션 한 번에 3만 회 이상 질의합니다. 파이썬 다익스트라로는 몇 분이 걸립니다
- 실제 엔진은 축약 계층 + 행렬 질의 + 속도 교체로 이를 감당합니다. 우리는 HTTP로 부릅니다
- 5장에서는 차 대신 버스와 지하철로 갑니다. 시간표라는 새 입력이 들어옵니다

## 연습문제

```{admonition} 연습 4.1  ★
:class: tip

`highway` 종류별로 자유류 속도와 오후 첨두 관측 속도의 차이를 구해 봅시다.
어느 도로 종류가 가장 많이 느려지나요?

산출물: 도로 종류별 비교표(자유류, 오후첨두, 감소율) 상위 6행.
```

```{admonition} 연습 4.2  ★★
:class: tip

관측 속도가 없는 엣지를 자유류로 채우는 대신, 같은 `highway` 종류의 관측 중앙값으로 채워 봅시다.
두 방식으로 하남시청→미사역 소요시간을 계산해 비교하고, 어느 쪽이 더 타당한지 근거를 들어 설명합니다.

산출물: 두 방식의 소요시간, 어느 쪽을 택할지와 그 이유 3~4줄.
```

```{admonition} 연습 4.3  ★★★
:class: tip

출발 시각을 넣으면 그 시각의 속도로 라우팅하는 함수를 만들어 봅시다.
경로를 따라가는 동안 시간대가 바뀌는 경우도 반영해 봅시다
(예: 오후 6시 50분에 출발해 7시를 넘기는 경우).
이것을 시간의존 최단경로(time-dependent shortest path)라고 합니다.

산출물: 구현 코드, 시간대 고정 방식과의 소요시간 차이, 어떤 경우에 차이가 커지는지 설명.
```

[dtumos-repo]: https://github.com/HNU209/DTUMOS
[osrm-repo]: https://github.com/Project-OSRM/osrm-backend
