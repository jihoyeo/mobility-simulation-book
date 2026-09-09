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

# 0장 환경 준비

실습에는 파이썬 환경, 예제 데이터, 시뮬레이션 엔진이 필요합니다. 이 장에서는 패키지 설치와 데이터 경로를 확인하고, 엔진 연결 상태에 따라 하남시 택시 시뮬레이션 또는 저장된 실행 결과를 불러옵니다.

운영체제와 라이브러리 버전에 따라 설치 로그와 실행 시간이 다를 수 있습니다. 각 절에 적힌 확인 코드와 데이터 규모, 테스트 결과를 기준으로 환경을 점검합니다.

## 학습 목표

- 실습 환경을 설치하고 `smartmob` 이 불러와지는지 확인합니다
- 하남시 도로망을 읽어 노드와 엣지 수를 셉니다
- DTUMOS 엔진에 연결하거나, 연결이 안 될 때 무엇이 일어나는지 확인합니다
- 시뮬레이션을 한 번 돌리고 서비스율과 평균 대기시간을 읽습니다

## 0.1 설치

파이썬 3.11을 씁니다. 저장소를 받고 의존성을 설치합니다.

```bash
git clone https://github.com/jihoyeo/mobility-simulation-book.git
cd mobility-simulation-book
pip install -r requirements.txt
```

`requirements.txt` 는 버전을 전부 고정해 두었습니다. 같은 버전을 쓰면 같은 그림이 나옵니다.

9장의 통행시간 예측 모델은 `scikit-learn` 과 `LightGBM` 이 더 필요합니다. 그 장에 가서 설치해도 됩니다.

```bash
pip install -r requirements-heavy.txt
```

12장의 웹 뷰어는 파이썬이 아니라 Node 로 돕니다. 이 책에서 유일한 예외입니다. 12주차에 가서 설치해도 됩니다. [nodejs.org](https://nodejs.org) 에서 LTS 판을 받습니다. 20.19 이상이면 됩니다.

```{note}
구글 코랩에서 읽는다면 각 장 위쪽의 Colab 배지를 누르고, 첫 셀에서 `smartmob.colab.bootstrap()` 을 실행합니다. 한글 폰트를 깔고 패키지를 설치합니다.
```

```{note}
설치에 실패하면 실행한 명령, 오류 전문, 운영체제, 파이썬 버전을 함께 기록합니다. 설치 확인 기준은 다음 절의 `import smartmob`이 오류 없이 실행되는지입니다.
```

## 0.2 데이터가 있는지 확인하기

실습 도시는 **하남시**입니다. 서울과 붙어 있으면서 노트북에서 다루기 좋은 크기라 골랐습니다. 도로망과 대중교통 시간표가 저장소에 이미 들어 있습니다.

```{code-cell} python
from smartmob.data import data_path

for name in ["road_graph_nodes.parquet", "road_graph_edges.parquet", "demand.csv"]:
    p = data_path(f"hanam/{name}")
    print(f"{name:28s} {p.stat().st_size / 1e6:6.2f} MB")
```

도로망을 읽어 봅니다. `modes=("drive",)` 는 자동차가 다닐 수 있는 도로만 남기라는 뜻입니다. 왜 이 인자가 필요한지는 2장에서 다룹니다.

```{code-cell} python
from smartmob.data import load_road_graph

G = load_road_graph("hanam", modes=("drive",))
G
```

노드가 12,566개, 엣지가 28,589개입니다. 하남시 전체 도로망치고는 적어 보이지만, 교차로와 막다른 길만 노드로 잡고 그 사이 직선 구간은 엣지 하나로 묶은 결과입니다.

```{note}
`FileNotFoundError`가 나면 노트북의 현재 작업 디렉터리와 `data/hanam/` 경로를 먼저 확인합니다.
```

## 0.3 엔진에 연결하기

최단경로나 시뮬레이션을 실제로 돌리는 것은 **DTUMOS** 라는 별도 프로그램입니다. Rust로 짜여 있고 Docker 컨테이너로 돕니다. 이 책에서는 그 안을 들여다보지 않고 HTTP로 부르기만 합니다.

연결 방법은 세 가지입니다.

| 방법 | 언제 쓰는가 | 설정 |
|---|---|---|
| 공용 서버 | 수업 중 무거운 시뮬레이션 | `SMARTMOB_DTUMOS_URL=http://<주소>:<팀별 포트>` |
| 로컬 Docker | 엔진 코드를 직접 열어 볼 때 | `docker compose up -d` 후 기본값 그대로 |
| 내장 엔진 | 서버 없이 그 자리에서 돌릴 때 | 없음. 서버에 못 붙으면 자동 |

세 번째가 중요합니다. 서버에 못 붙어도 책이 멈추지 않습니다. `smartmob` 안에 파이썬으로 짠 작은 엔진이 들어 있어서, 연결이 안 되면 그 자리에서 직접 계산합니다. 승객 1,000명·차량 80대면 1초 안에 끝납니다. 책의 기준 실험 하나는 실제 엔진의 실행 결과가 `data/fixtures/` 에 녹화되어 있고, 그 조건이면 녹화본을 그대로 돌려줍니다.

```{code-cell} python
from smartmob import Dtumos

dt = Dtumos()
dt.health()
```

`status` 가 `local` 로 나오면 서버 없이 내장 엔진으로 도는 중입니다. 실서버에 붙었다면 서버가 돌려준 상태가 그대로 나옵니다. 둘 다 정상입니다.

```{note}
내장 엔진은 도로망을 달리지 않습니다. 두 점 사이 직선거리를 시속 25km 로 나눈 시간을 씁니다. 차량 대수를 80대에서 40대로 바꿔 보는 식으로 값을 바꾸면 이 엔진이 새로 계산합니다. 기준 실험(80대·1,000건·seed 42)만 녹화된 실제 엔진 결과입니다. 11장에서 이 근사가 실제 엔진과 얼마나 가까운지 직접 확인합니다.
```

```{note}
환경변수 설정 명령은 운영체제와 셸에 따라 다릅니다. 설정 뒤에는 주피터 커널을 다시 시작하고 `dt.health()`의 `status`를 확인합니다.
```

## 0.4 첫 시뮬레이션

하남시에서 저녁 6시부터 자정까지, 택시 80대로 1,000건의 호출을 처리해 봅니다. `1080` 은 자정부터의 분이고 18:00입니다. 이 책의 시간은 전부 이 단위입니다.

```{code-cell} python
sim = dt.run_simulation(
    city="hanam",
    mode="taxi",
    fleet_size=80,
    num_passengers=1000,
    time_start=1080,   # 18:00
    time_end=1440,     # 24:00
    random_seed=42,
)
sim.summary()
```

```{note}
`Dtumos` 는 시뮬레이션 서버에 요청을 보내는 **클래스**입니다. `dt = Dtumos()` 는 이 클래스에서 객체 `dt` 를 만듭니다. `dt.run_simulation(...)` 은 객체에 정의된 동작인 메서드이고, 실행 결과는 `sim` 이라는 새 객체에 담깁니다.

`sim.summary()` 처럼 괄호가 붙은 것은 값을 계산하는 메서드입니다. `sim.record` 처럼 괄호가 없으면 객체가 이미 가지고 있는 자료를 속성으로 꺼냅니다.
```

숫자를 하나씩 읽어 봅니다.

- `service_rate` 가 1.0입니다. 990건의 호출이 전부 배차됐습니다. 1,000건을 넣었는데 990건인 것은, 마지막 열 건이 23시 56분 이후에 들어온 호출이라 자정에 끝나는 시뮬레이션이 세지 않기 때문입니다. 이 990이라는 숫자는 뒤의 장에서 계속 나옵니다.
- `avg_waiting_time_min` 이 약 4.1분입니다. 호출하고 차가 올 때까지 평균 4분 걸렸습니다.
- `utilization` 이 약 0.27입니다. 차량이 승객을 태우고 있던 시간이 전체의 27%뿐입니다.

마지막 값이 흥미롭습니다. 대기시간이 4분이면 승객 입장에서는 괜찮은데, 차량의 4분의 3은 놀고 있었습니다. 80대가 너무 많은 것은 아닐까요? 40대로 줄이면 대기시간이 얼마나 늘어날까요?

이 질문에 답하려면 같은 수요와 같은 도로망 위에서 차량 대수만 바꿔 다시 돌려 봐야 합니다. 그 도구를 이 책에서 만듭니다.

## 0.5 분 단위 운행 기록 읽기

결과 객체에는 표가 둘 있습니다. `sim.record` 는 1분마다 한 줄씩 기록된 표이고, 컬럼 이름이 `_cnt` 로 끝납니다. `sim.result` 는 같은 시각을 차량 상태별로 더 잘게 나눈 표이고, 컬럼 이름이 `_num` 으로 끝납니다. 이 장에서는 `record` 만 보고, `result` 는 1장에서 씁니다.

```{code-cell} python
sim.record.head()
```

`waiting_passenger_cnt` 가 그 분에 기다리고 있던 승객 수입니다. `empty_vehicle_cnt` 는 빈 차, `driving_vehicle_cnt` 는 운행 중인 차의 수입니다. `fail_passenger_cnt` 는 배차를 못 받고 포기한 승객의 누적 수입니다.

그림으로 봅니다.

```{code-cell} python
from smartmob.viz import plot_record

plot_record(sim.record);
```

운행 중 차량이 늘어난 만큼 대기 중 차량이 줄어듭니다. 둘을 더하면 대부분의 시간에 80이 됩니다.

그런데 마지막 30분쯤에서 합이 80보다 작아지고, 대기 승객 수는 오히려 늘어납니다. 근무 시간이 끝난 차량이 하나씩 빠지기 때문입니다. 차량마다 `work_start` 와 `work_end` 가 정해져 있고, 자정이 가까워지면 남는 차가 줄어듭니다.

```{code-cell} python
on_duty = sim.record["empty_vehicle_cnt"] + sim.record["driving_vehicle_cnt"]
print("근무 중 차량 최대:", on_duty.max())
print("근무 중 차량 최소:", on_duty.min())
print("마지막 시각 대기 승객:", sim.record["waiting_passenger_cnt"].iloc[-1])
```

시뮬레이션이 "차량 80대"를 항상 80대로 다루지 않는다는 뜻입니다. 이런 것을 미리 알고 있어야 결과를 잘못 읽지 않습니다.

## 이 장의 실습

노트북 `labs/ch00_setup.ipynb` 를 열어 함께 돌립니다.

설치 확인부터 첫 시뮬레이션까지 이 장의 순서를 그대로 따라갑니다. 마지막에 빈칸이 하나 있습니다.

```bash
jupyter lab labs/ch00_setup.ipynb
```

## 정리

- `pip install -r requirements.txt` 로 환경을 만들고, `smartmob` 을 통해 데이터와 엔진에 접근합니다
- `load_road_graph("hanam")` 이 도로망을, `Dtumos()` 가 시뮬레이션 엔진을 담당합니다
- 서버에 못 붙으면 내장 파이썬 엔진으로 자동 전환됩니다
- `sim.summary()` 는 서비스율·평균 대기시간·차량 가동률을, `sim.record` 는 분 단위 시계열을 줍니다
- 설치가 끝나면 `import smartmob`과 각 절의 확인 코드를 실행합니다
- 1장에서는 이 장치가 왜 필요한지, 기존 시뮬레이터로는 왜 안 되는지를 봅니다

## 연습문제

```{admonition} 연습 0.1  ★
:class: tip

`sim.record` 에서 대기 승객 수가 가장 많았던 시각과 그때의 인원을 구해 봅시다.
`smartmob.data.minutes_to_hhmm` 을 쓰면 분을 `HH:MM` 으로 바꿀 수 있습니다.

산출물: 시각 1개, 인원 1개.
```
