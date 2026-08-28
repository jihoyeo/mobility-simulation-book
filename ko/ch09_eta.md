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

4장에서 계산했습니다. 시뮬레이션 한 번에 라우팅 질의가 3만 번 넘게 필요하고, 우리 다익스트라로는 몇 분이 걸립니다.

축약 계층을 쓰면 빨라지지만 우리가 직접 만들지는 않기로 했습니다. 다른 길이 있습니다. **정확한 답을 계산하는 대신 예측하는 것**입니다.

출발지·목적지 좌표와 시각만 있으면 사람은 대충 압니다. "5km 정도니까 15분쯤". 이 어림을 데이터로 학습시킵니다.

## 학습 목표

- 라우팅 결과를 정답으로 삼는 학습 데이터를 만듭니다
- 직선거리 기준선부터 시작해 모델을 단계적으로 개선합니다
- 평균절대오차(MAE)와 결정계수(R²)로 모델을 평가합니다
- 예측 속도와 정확도의 거래를 숫자로 확인합니다

## 9.1 정답을 만듭니다

지도학습에는 정답이 필요합니다. 다행히 우리에게는 정답을 만드는 장치가 있습니다. 3장의 다익스트라입니다.

무작위 O-D 쌍을 뽑아 실제 소요시간을 계산해 두면 그것이 학습 데이터가 됩니다.

```{code-cell} python
:tags: [skip-execution]

from smartmob.teaching.eta import build_dataset

# 2만 건에 약 3분 걸립니다. 결과는 data/hanam/eta_samples.parquet 에 저장해 두었습니다.
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

`duration_min` 이 정답입니다. 나머지 중 `network_km`(실제 도로 거리)도 라우팅을 해야 알 수 있으므로 특징으로 쓸 수 없습니다. **예측할 때 얻을 수 없는 값을 특징에 넣으면 안 됩니다.**

```{code-cell} python
from smartmob.teaching.eta import FEATURES, TARGET

print("특징:", FEATURES)
print("정답:", TARGET)
```

특징 여덟 개는 전부 좌표와 시각만으로 구합니다.

| 특징 | 왜 넣는가 |
|---|---|
| `straight_km` | 멀수록 오래 걸립니다. 가장 중요한 신호입니다 |
| `hour` | 4장에서 봤듯 시간대마다 속도가 다릅니다 |
| `sin_bearing`, `cos_bearing` | 방향. 한강을 건너는 남북 방향과 강변을 따르는 동서 방향은 다릅니다 |
| `origin_lat/lon`, `dest_lat/lon` | 어느 지역인지. 시가지와 외곽의 도로 사정이 다릅니다 |

방위각을 그대로 넣지 않고 `sin`, `cos` 두 개로 나눈 이유가 있습니다. 방위각은 359도와 1도가 거의 같은 방향인데, 숫자로는 358만큼 떨어져 있습니다. 원 위의 각도를 좌표 두 개로 바꾸면 이 문제가 없어집니다.

```{code-cell} python
X = df[FEATURES]
y = df[TARGET]

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"학습 {len(X_train):,}건, 검증 {len(X_test):,}건")
```

검증 데이터를 떼어 두는 이유는 하나입니다. 학습에 쓴 데이터로 평가하면 외운 것과 이해한 것을 구분할 수 없습니다.

## 9.2 기준선 — 직선거리를 평균 속도로 나누기

모델을 만들기 전에 기준선을 정합니다. 기준선보다 못하면 그 모델은 쓸모가 없습니다.

가장 단순한 예측은 "직선거리 ÷ 평균 속도"입니다.

```{code-cell} python
from sklearn.metrics import mean_absolute_error, r2_score

avg_speed = X_train["straight_km"].sum() / (y_train.sum() / 60)
baseline = X_test["straight_km"] / avg_speed * 60

print(f"평균 속도 {avg_speed:.1f} km/h")
print(f"MAE {mean_absolute_error(y_test, baseline):.2f}분   R² {r2_score(y_test, baseline):.3f}")
```

평균 2분 32초 틀립니다. 통행 자체가 평균 11.8분이므로 20% 넘게 틀리는 셈입니다.

지표 두 개를 씁니다.

- **MAE**(평균절대오차) — 평균 몇 분 틀리는가. 단위가 분이라 바로 해석됩니다
- **R²**(결정계수) — 정답의 변동 중 몇 %를 설명하는가. 1에 가까울수록 좋고, 0이면 평균값을 답하는 것과 같습니다

## 9.3 선형회귀

직선거리와 소요시간의 관계를 직선으로 맞춥니다.

```{code-cell} python
from sklearn.linear_model import LinearRegression

lr1 = LinearRegression().fit(X_train[["straight_km"]], y_train)
pred1 = lr1.predict(X_test[["straight_km"]])

print(f"기울기 {lr1.coef_[0]:.2f}분/km, 절편 {lr1.intercept_:.2f}분")
print(f"MAE {mean_absolute_error(y_test, pred1):.2f}분   R² {r2_score(y_test, pred1):.3f}")
```

기준선보다 조금 나아졌습니다. 절편이 있다는 것이 이유입니다. 거리가 0이어도 시간이 0이 아니라는 사실(출발과 도착에 드는 시간)을 반영합니다.

특징 여덟 개를 다 넣어 봅니다.

```{code-cell} python
lr2 = LinearRegression().fit(X_train, y_train)
pred2 = lr2.predict(X_test)
print(f"MAE {mean_absolute_error(y_test, pred2):.2f}분   R² {r2_score(y_test, pred2):.3f}")
```

거의 나아지지 않았습니다. 특징을 일곱 개나 더 줬는데 왜일까요.

선형회귀는 각 특징이 결과에 일정한 비율로 기여한다고 가정합니다. 위도가 0.01 올라가면 시간이 항상 얼마 늘어난다는 식입니다. 실제로는 그렇지 않습니다. 시가지 안에서 0.01은 신호가 여럿이지만 외곽에서는 뻥 뚫린 도로입니다. **위치는 다른 특징과 얽혀서 작동합니다.**

## 9.4 그래디언트 부스팅

특징이 서로 얽힌 관계를 다루려면 모델을 바꿔야 합니다.

의사결정나무는 "위도가 37.55보다 크고, 직선거리가 4km보다 길면, 예상 12분" 같은 규칙을 만듭니다. 얽힌 조건을 자연스럽게 표현합니다. 나무 하나는 약하지만, 앞 나무가 틀린 만큼을 다음 나무가 맞추도록 여러 개를 이어 붙이면 강해집니다. 이것이 그래디언트 부스팅입니다.

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

**MAE 0.89분, R² 0.954.** 선형회귀의 2.16분에서 절반 이하로 줄었습니다. 평균 1분 이내로 맞힙니다.

## 9.5 무엇이 예측에 쓰였는가

어떤 특징이 많이 쓰였는지 봅니다.

```{code-cell} python
importance = sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1])
for name, score in importance:
    bar = "█" * int(score / 100)
    print(f"{name:14s} {score:5d} {bar}")
```

좌표 네 개가 가장 많이 쓰였습니다. 직선거리보다도 많습니다.

처음에는 이상해 보입니다. 거리가 가장 중요할 것 같은데요. 그런데 좌표 네 개만 있으면 거리도 계산됩니다. 게다가 지역별 도로 사정까지 함께 배울 수 있습니다. 나무가 좌표를 여러 번 쪼개면서 두 가지를 동시에 담습니다.

`hour` 가 가장 적게 쓰였습니다. 4장에서 시간대별 속도 차이가 컸는데 왜일까요.

```{code-cell} python
df.groupby("hour")[TARGET].mean().round(2)
```

시간대별 평균이 11.0분에서 12.7분 사이입니다. 1.7분 차이입니다. 4장에서 본 62% 차이는 특정 구간의 이야기였고, 도시 전체 평균으로 보면 훨씬 작습니다. 무작위 O-D 쌍의 대부분은 이면도로를 쓰는 짧은 통행이고, 이면도로는 시간대별 속도 차이가 작기 때문입니다.

## 9.6 얼마나 빨라졌는가

이 모델을 만든 이유는 정확도가 아니라 속도였습니다.

```{code-cell} python
sample = X_test.head(2000)

t0 = time.perf_counter()
model.predict(sample)
per_query_us = (time.perf_counter() - t0) / len(sample) * 1e6

print(f"모델 예측     {per_query_us:8.1f} µs/건")
print(f"다익스트라    {7400:8.1f} µs/건  (3장에서 측정)")
print(f"                 {7400 / per_query_us:,.0f}배 빠릅니다")
```

3천 배입니다. 4장에서 계산했던 "시뮬레이션 한 번에 몇 분"이 몇 초가 됩니다.

대신 1분쯤 틀립니다. 이 거래를 받아들일지는 무엇에 쓰느냐에 달렸습니다.

- **배차 결정**: 받아들입니다. 30대 중 누가 가장 가까운지만 알면 되고, 1분 오차로 순위가 뒤집히는 경우는 드뭅니다
- **승객에게 보여 주는 도착 예정시간**: 곤란합니다. 실제 경로를 계산해야 합니다
- **차량이 실제로 움직이는 경로**: 안 됩니다. 좌표열이 나와야 지도에 그립니다

그래서 시뮬레이터는 둘을 섞어 씁니다. **후보를 고를 때는 예측, 확정된 통행을 그릴 때는 라우팅**입니다.

## 9.7 어디서 틀리는가

오차를 뜯어 봅니다.

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

왼쪽 그림에서 점들이 대각선에 붙어 있습니다. 다만 오른쪽 위, 즉 오래 걸리는 통행에서 흩어집니다.

```{code-cell} python
bins = pd.cut(X_test["straight_km"], [0, 2, 4, 6, 8, 20])
pd.DataFrame({
    "MAE": abs(error).groupby(bins, observed=True).mean().round(2),
    "건수": error.groupby(bins, observed=True).size(),
})
```

거리가 멀수록 오차가 큽니다. 먼 통행일수록 지날 수 있는 경로가 많아지고, 좌표만으로는 어느 길로 갈지 알 수 없기 때문입니다.

```{code-cell} python
worst = abs(error).nlargest(5).index
df.loc[worst, ["straight_km", "network_km", "hour", "duration_min"]].assign(
    예측=pred3[[X_test.index.get_loc(i) for i in worst]].round(1)
)
```

가장 많이 틀린 통행을 보면 `network_km` 이 `straight_km` 보다 훨씬 큽니다. 직선으로는 가까운데 도로로는 크게 돌아가는 경우입니다. 강 건너편이거나 산을 우회해야 하는 곳입니다. 좌표만 보는 모델이 이걸 알아내기 어렵습니다.

```{tip}
개선하려면 "이 두 지점 사이에 장애물이 있는가"를 알려 주는 특징이 필요합니다. 강 통과 여부, 두 지점 사이 도로 밀도 같은 것입니다. 연습문제 9.3에서 시도해 봅니다.
```

## 정리

- 배차에 필요한 것은 정확한 경로가 아니라 "어느 차가 가장 빠른가"입니다. 그래서 예측으로 갈음할 수 있습니다
- 학습 데이터의 정답은 3장의 라우팅으로 만듭니다. 특징은 예측 시점에 얻을 수 있는 것만 씁니다
- 방위각처럼 원 위의 값은 `sin`, `cos` 두 개로 나눠 넣습니다
- 기준선(직선거리÷평균속도) MAE 2.52분 → 선형회귀 2.16분 → LightGBM 0.89분
- 선형회귀는 특징을 더 줘도 나아지지 않습니다. 위치는 다른 특징과 얽혀 작동하기 때문입니다
- 모델은 다익스트라보다 3천 배 빠릅니다. 대신 1분쯤 틀립니다
- 오차는 먼 통행과 우회가 큰 통행에서 큽니다
- 10장에서 이 예측을 배차 비용행렬에 넣습니다

## 연습문제

```{admonition} 연습 9.1  ★
:class: tip

`n_estimators` 를 50, 100, 200, 400, 800 으로 바꿔 가며 MAE 와 학습 시간을 재 봅시다.
어디서부터 나아지지 않나요?

산출물: 나무 개수별 MAE·학습시간 표, 적정 값과 그 근거 2줄.
```

```{admonition} 연습 9.2  ★★
:class: tip

`hour` 를 빼고 학습하면 MAE 가 얼마나 나빠지나요?
반대로 `straight_km` 을 빼면 얼마나 나빠지나요?
특징 하나씩 빼 가며 MAE 변화를 재는 것을 제거 실험(ablation)이라고 합니다.

9.5절의 중요도 순서와 제거 실험 결과가 일치하는지 확인합니다. 다르면 왜 다를지 생각해 봅니다.

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
모델을 쓰는 이유가 속도였으므로, 특징 계산이 라우팅만큼 비싸지면 의미가 없습니다.

산출물: 새 특징 구현, MAE 변화, 예측 1건당 시간 변화, 쓸 만한지에 대한 판단.
```
