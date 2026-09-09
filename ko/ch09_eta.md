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

# 9장 통행시간 예측 모델(ETA)

배차 단계에서는 대기 요청과 빈 차량의 조합마다 픽업 소요시간이 필요합니다. 후보 조합이 많아지면 각 조합을 다익스트라로 계산하는 비용도 커집니다.

이 장에서는 출발지·목적지 좌표와 출발 시각으로 다익스트라의 소요시간을 근사하는 모델을 만듭니다. 이 모델은 경로를 반환하지 않으며, 정해진 하남 도로망과 속도 자료에서 계산한 값을 학습 대상으로 사용합니다.

## 학습 목표

- 라우팅 결과를 정답으로 삼는 학습 데이터를 만듭니다
- 직선거리 기준선부터 시작해 모델을 단계적으로 개선합니다
- 평균절대오차(MAE)와 결정계수(R²)로 모델을 평가합니다
- 예측 속도와 정확도의 거래를 숫자로 확인합니다

## 9.1 학습 자료 만들기

도로망 노드에서 O-D 쌍과 시간대를 무작위로 뽑고, 3장의 다익스트라로 소요시간을 계산합니다. 여기서 계산한 소요시간을 학습 목표값으로 사용합니다.

```{code-cell} python
:tags: [skip-execution]

from smartmob.teaching.eta import build_dataset

# 실행 시간은 시스템에 따라 달라집니다. 결과 파일은 저장소에 포함되어 있습니다.
df = build_dataset("hanam", n=20_000, seed=0)
df.to_parquet("data/hanam/eta_samples.parquet", index=False)
```

만들어 둔 것을 읽습니다.

```{code-cell} python
import pandas as pd
from smartmob.data import data_path

df = pd.read_parquet(data_path("hanam/eta_samples.parquet"))
print(f"{len(df):,}건")
df.head(3)
```

`duration_min`이 목표값입니다. `network_km`도 다익스트라를 실행해야 얻을 수 있으므로 입력 특징에서는 제외합니다. 모델을 사용할 시점에 계산할 수 없는 값을 학습 특징으로 쓰면 평가 결과를 실제 사용 조건에 적용할 수 없습니다.

```{code-cell} python
from smartmob.teaching.eta import FEATURES, TARGET

print("특징:", FEATURES)
print("정답:", TARGET)
```

특징 여덟 개는 전부 좌표와 시각만으로 구합니다.

| 특징 | 입력값 |
|---|---|
| `straight_km` | 두 좌표 사이의 직선거리 |
| `hour` | 출발 시간대 |
| `sin_bearing`, `cos_bearing` | 출발지에서 목적지로 향하는 방향 |
| `origin_lat/lon`, `dest_lat/lon` | 출발지와 목적지의 공간적 위치 |

방위각을 그대로 넣지 않고 `sin`, `cos` 두 개로 나눈 이유가 있습니다. 방위각은 359도와 1도가 거의 같은 방향인데, 숫자로는 358만큼 떨어져 있습니다. 원 위의 각도를 좌표 두 개로 바꾸면 이 문제가 없어집니다.

```{code-cell} python
X = df[FEATURES]
y = df[TARGET]

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"학습 {len(X_train):,}건, 검증 {len(X_test):,}건")
```

검증 데이터는 모델 학습에 사용하지 않고 성능 계산에만 씁니다. 이 무작위 분할은 같은 도로망과 같은 시간대 분포에서 새 O-D 쌍을 예측하는 조건만 평가합니다. 다른 도시나 날짜의 성능은 이 결과에 포함되지 않습니다.

## 9.2 기준선 — 직선거리를 평균 속도로 나누기

모델을 비교할 기준선을 먼저 계산합니다.

가장 단순한 예측은 "직선거리 ÷ 평균 속도"입니다.

```{code-cell} python
from sklearn.metrics import mean_absolute_error, r2_score

avg_speed = X_train["straight_km"].sum() / (y_train.sum() / 60)
baseline = X_test["straight_km"] / avg_speed * 60

print(f"평균 속도 {avg_speed:.1f} km/h")
print(f"MAE {mean_absolute_error(y_test, baseline):.2f}분   R² {r2_score(y_test, baseline):.3f}")
```

검증 자료의 MAE는 2.52분입니다. 전체 자료의 평균 통행시간 11.8분과 비교하면 오차의 절대적인 크기를 가늠할 수 있습니다. 이 비율은 통행별 백분율 오차의 평균은 아닙니다.

지표 두 개를 씁니다.

- MAE(평균절대오차) — 각 통행의 절대오차를 평균한 값입니다. 이 예에서는 단위가 분입니다
- R²(결정계수) — 1에 가까울수록 관측값의 변동을 잘 재현합니다. 검증 자료의 평균을 항상 예측하면 0이고, 그보다 못하면 음수가 될 수 있습니다

## 9.3 선형회귀

직선거리와 소요시간의 관계를 직선으로 맞춥니다.

```{code-cell} python
from sklearn.linear_model import LinearRegression

lr1 = LinearRegression().fit(X_train[["straight_km"]], y_train)
pred1 = lr1.predict(X_test[["straight_km"]])

print(f"기울기 {lr1.coef_[0]:.2f}분/km, 절편 {lr1.intercept_:.2f}분")
print(f"MAE {mean_absolute_error(y_test, pred1):.2f}분   R² {r2_score(y_test, pred1):.3f}")
```

직선거리 하나를 사용한 선형회귀의 MAE는 2.19분입니다. 기준선과 달리 기울기와 절편을 각각 자료에서 추정합니다. 이 절편은 표본에 맞춘 회귀계수이며, 별도의 승하차 시간을 뜻하지 않습니다.

특징 여덟 개를 다 넣어 봅니다.

```{code-cell} python
lr2 = LinearRegression().fit(X_train, y_train)
pred2 = lr2.predict(X_test)
print(f"MAE {mean_absolute_error(y_test, pred2):.2f}분   R² {r2_score(y_test, pred2):.3f}")
```

여덟 특징을 모두 사용하면 MAE는 2.16분입니다. 좌표와 시간대를 선형 항으로 추가했을 때의 개선 폭은 0.03분입니다. 이 모형에는 임곗값이나 특징 사이의 상호작용 항이 없으므로, 위치에 따라 거리 효과가 달라지는 관계를 직접 표현하지 못합니다.

## 9.4 그래디언트 부스팅

그래디언트 부스팅 회귀는 특징의 임곗값과 상호작용을 의사결정나무의 분기로 표현합니다. LightGBM은 앞 단계까지 남은 오차를 줄이도록 나무를 순서대로 추가합니다.

```{code-cell} python
import time
import lightgbm as lgb

model = lgb.LGBMRegressor(
    n_estimators=400, learning_rate=0.05, num_leaves=31,
    random_state=42, verbose=-1,
)

t0 = time.perf_counter()
model.fit(X_train, y_train)
train_time = time.perf_counter() - t0

pred3 = model.predict(X_test)
print(f"MAE {mean_absolute_error(y_test, pred3):.2f}분   R² {r2_score(y_test, pred3):.3f}")
print(f"학습 {train_time:.1f}초")
```

검증 자료에서 MAE는 0.89분, R²는 0.954입니다. 같은 분할에서 선형회귀의 MAE 2.16분보다 1.27분 작습니다.

## 9.5 특징별 분할 횟수

LightGBM이 나무를 나눌 때 각 특징을 사용한 횟수를 확인합니다.

```{code-cell} python
importance = sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1])
for name, score in importance:
    bar = "█" * int(score / 100)
    print(f"{name:14s} {score:5d} {bar}")
```

이 실행에서는 네 좌표의 분할 횟수가 많고 `hour`의 분할 횟수가 가장 적습니다. 분할 횟수는 인과효과나 해당 특징을 제거했을 때의 성능 저하량이 아닙니다. 서로 연관된 특징이 있으면 중요도가 여러 특징에 나뉠 수도 있습니다. 특징을 하나씩 제외해 다시 학습하는 제거 실험은 연습문제 9.2에서 수행합니다.

```{code-cell} python
df.groupby("hour")[TARGET].mean().round(2)
```

시간대별 평균은 11.0~12.7분입니다. 4장의 62%는 하남시청에서 미사역까지 한 구간의 자유류와 오후 첨두 결과를 비교한 값입니다. 여기서는 여러 O-D의 시간대별 평균을 계산하므로 두 수치를 직접 비교할 수 없습니다.

## 9.6 얼마나 빨라졌는가

같은 컴퓨터에서 모델의 일괄 예측과 다익스트라 반복 실행 시간을 각각 잽니다.

```{code-cell} python
from smartmob.data import load_road_graph
from smartmob.teaching.dijkstra import dijkstra

sample = X_test.head(2000)

t0 = time.perf_counter()
model.predict(sample)
per_query_us = (time.perf_counter() - t0) / len(sample) * 1e6

G_bench = load_road_graph("hanam", modes=("drive",))
bench_rows = df.sample(n=100, random_state=1)
node_pairs = [
    (G_bench.nearest_node(r.origin_lat, r.origin_lon),
     G_bench.nearest_node(r.dest_lat, r.dest_lon))
    for r in bench_rows.itertuples()
]
t0 = time.perf_counter()
for start, goal in node_pairs:
    dijkstra(G_bench, start, goal)
per_route_us = (time.perf_counter() - t0) / len(node_pairs) * 1e6

print(f"모델 일괄 예측  {per_query_us:8.1f} µs/건")
print(f"다익스트라 반복 {per_route_us:8.1f} µs/건")
print(f"측정 비율       {per_route_us / per_query_us:8.0f}배")
```

측정값은 하드웨어, 표본, 일괄 예측 크기에 따라 달라집니다. 위 비교에는 모델 학습 시간과 도로망 적재 시간은 포함하지 않습니다. 속도 차이와 함께 검증 자료의 MAE 0.89분도 고려해야 합니다.

- 배차에 사용하려면 차량 순위와 최종 할당이 라우팅 결과와 얼마나 일치하는지 확인합니다
- 승객 안내에 사용하려면 시간대와 거리 구간별 오차 및 과소예측 비율을 확인합니다
- 차량의 이동 궤적이 필요하면 경로를 반환하는 라우터를 별도로 사용합니다

## 9.7 오차 분포

실제 소요시간과 직선거리별 오차를 확인합니다.

```{code-cell} python
import matplotlib.pyplot as plt
from smartmob.viz import use_korean_font

use_korean_font()
error = pred3 - y_test

fig, axes = plt.subplots(1, 2, figsize=(11, 4))

axes[0].scatter(y_test, pred3, s=3, alpha=0.2, color="tab:blue")
lim = [0, y_test.max()]
axes[0].plot(lim, lim, color="tab:red", linewidth=1.2, linestyle="--")
axes[0].set_xlabel("실제 (분)"); axes[0].set_ylabel("예측 (분)")
axes[0].set_title("예측 대 실제")

axes[1].scatter(X_test["straight_km"], error, s=3, alpha=0.2, color="tab:blue")
axes[1].axhline(0, color="tab:red", linewidth=1.2, linestyle="--")
axes[1].set_xlabel("직선거리 (km)"); axes[1].set_ylabel("오차 (분)")
axes[1].set_title("거리별 오차")

for ax in axes:
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout();
```

왼쪽 그림은 실제값과 예측값의 관계를, 오른쪽 그림은 직선거리와 예측오차의 관계를 보여 줍니다.

```{code-cell} python
bins = pd.cut(X_test["straight_km"], [0, 2, 4, 6, 8, 20])
pd.DataFrame({
    "MAE": abs(error).groupby(bins, observed=True).mean().round(2),
    "건수": error.groupby(bins, observed=True).size(),
})
```

거리 구간별 MAE는 0.85~0.94분이며 직선거리에 따라 단조롭게 증가하지 않습니다. 이 표본에서는 거리만으로 오차 크기의 변화를 설명하기 어렵습니다.

```{code-cell} python
worst = abs(error).nlargest(5).index
df.loc[worst, ["straight_km", "network_km", "hour", "duration_min"]].assign(
    예측=pred3[[X_test.index.get_loc(i) for i in worst]].round(1)
)
```

절대오차가 가장 큰 다섯 건 가운데 두 건은 `network_km`가 `straight_km`의 약 10배 이상입니다. 나머지 세 건에는 같은 형태가 나타나지 않으며 모델이 소요시간을 크게 과대예측했습니다. 큰 오차를 하나의 원인으로 설명하기보다 각 O-D의 경로와 예측 방향을 함께 확인해야 합니다.

```{tip}
우회가 큰 O-D를 구분할 후보 특징으로 하천 통과 여부나 주변 도로 밀도를 시험할 수 있습니다. 특징을 추가한 뒤에는 별도 검증 자료에서 MAE와 계산 시간을 다시 측정해야 합니다. 연습문제 9.3에서 이 절차를 수행합니다.
```

## 이 장의 실습

노트북 `labs/ch09_eta.ipynb` 를 열어 함께 돌립니다.

학습 데이터를 만들고 기준선·선형회귀·LightGBM 을 비교한 뒤, 예측값으로 배차 비용행렬을 만들어 봅니다.

```bash
jupyter lab labs/ch09_eta.ipynb
```

## 정리

- ETA 모델은 좌표와 시간대로 다익스트라의 소요시간을 근사하며 경로는 반환하지 않습니다
- 학습 데이터의 정답은 3장의 라우팅으로 만듭니다. 특징은 예측 시점에 얻을 수 있는 것만 씁니다
- 방위각처럼 원 위의 값은 `sin`, `cos` 두 개로 나눠 넣습니다
- 기준선(직선거리÷평균속도) MAE 2.52분 → 선형회귀 2.16분 → LightGBM 0.89분
- 여덟 특징 선형회귀의 MAE는 2.16분이고 LightGBM은 0.89분입니다
- 실행시간 비교는 같은 환경에서 측정하며, 모델 학습과 도로망 적재의 포함 여부를 명시합니다
- 이 표본의 거리 구간별 MAE는 직선거리에 따라 단조롭게 증가하지 않습니다
- 10장에서 이 예측을 배차 비용행렬에 넣습니다

## 연습문제

```{admonition} 연습 9.1  ★
:class: tip

`n_estimators` 를 50, 100, 200, 400, 800 으로 바꿔 가며 MAE 와 학습 시간을 재 봅시다.
MAE 감소 폭이 작아지는 구간을 찾습니다.

산출물: 나무 개수별 MAE·학습시간 표, 적정 값과 그 근거 2줄.
```

```{admonition} 연습 9.2  ★★
:class: tip

`hour`를 빼고 학습했을 때와 `straight_km`을 빼고 학습했을 때의 MAE를 각각 계산합니다.
특징 하나씩 빼 가며 MAE 변화를 재는 것을 제거 실험(ablation)이라고 합니다.

9.5절의 분할 횟수 순서와 제거 실험 결과를 비교하고, 차이가 있으면 연관된 특징이 있는지 확인합니다.

산출물: 특징별 제거 시 MAE 증가량 표, 중요도 순서와의 비교 3~4줄.
```

```{admonition} 연습 9.3  ★★★
:class: tip

9.7절에서 우회가 큰 통행의 오차가 크다는 것을 봤습니다.
`network_km / straight_km` 이 우회율입니다. 이 값은 예측 시점에 알 수 없지만,
**대신 쓸 수 있는 특징**을 만들어 봅시다.

예: 출발지와 목적지를 잇는 직선 위에 일정 간격으로 점을 찍고, 각 점에서 가장 가까운
도로 노드까지의 거리를 잽니다. 이 거리가 크면 그 구간에 도로가 없다는 뜻입니다.

이 특징을 넣어 MAE 가 얼마나 줄어드는지 보고, 계산 비용이 얼마나 늘어나는지도 잽니다.
새 특징의 계산 시간이 라우팅 시간에 가까워지면 전체 계산시간을 줄이기 어렵습니다.

산출물: 새 특징 구현, MAE 변화, 예측 1건당 시간 변화, 쓸 만한지에 대한 판단.
```
