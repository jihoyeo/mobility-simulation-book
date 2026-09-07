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

이 책의 코드는 전부 실행됩니다. 화면에 보이는 숫자와 그림은 여러분의 노트북에서도 똑같이 나와야 합니다. 그러려면 세 가지가 필요합니다. 파이썬 환경, 실습 데이터, 그리고 시뮬레이션 엔진입니다.

이 장에서 셋을 준비하고, 마지막에 하남시 택시 시뮬레이션을 한 번 돌려 봅니다.

막히는 자리마다 「AI 에게 물어보기」 상자를 넣어 두었습니다. 명령이 무슨 뜻인지, 오류가 왜 났는지 물을 때 어떤 말을 붙여야 하는지 적어 두었습니다. 상자 안의 문장은 그대로 복사해 쓰고, 자기 환경을 한 줄 덧붙입니다. 운영체제와 파이썬 버전이면 충분합니다.

AI 가 준 명령이 맞는지는 실행해 보면 압니다. 책에 적힌 것과 같은 숫자가 나오면 맞은 것이고, 다르면 그 차이를 다시 묻습니다.

## 학습 목표

- 실습 환경을 설치하고 `smartmob` 이 불러와지는지 확인합니다
- 하남시 도로망을 읽어 노드와 엣지 수를 셉니다
- DTUMOS 엔진에 연결하거나, 연결이 안 될 때 무엇이 일어나는지 확인합니다
- 시뮬레이션을 한 번 돌리고 서비스율과 평균 대기시간을 읽습니다
- 막혔을 때 AI 에게 무엇을 붙여넣어야 하는지 익힙니다

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

```{admonition} AI 에게 물어보기 — 설치
:class: tip

설치는 컴퓨터마다 다른 자리에서 막힙니다. 명령의 뜻을 모르겠거나 오류가 나면 그대로 물어봅니다.

> `pip install -r requirements.txt` 가 무슨 일을 하는 명령인지 한 줄씩 설명해 줘.

> 파이썬 가상환경이 왜 필요한지, 윈도우에서 만드는 명령이 무엇인지 알려 줘.

> 아래 오류가 났어. 윈도우 11 이고 파이썬은 3.11 이야. (오류 메시지를 통째로 붙여넣기)

클로드 코드나 커서 같은 AI 코딩 도구를 쓴다면 설치를 통째로 맡겨도 됩니다.

> 이 저장소를 받아서 파이썬 3.11 가상환경을 만들고 `requirements.txt` 를 설치해 줘. 끝나면 `import smartmob` 이 되는지 확인해 줘.

맡기더라도 마지막 확인은 직접 합니다. `import smartmob` 이 오류 없이 지나가면 다음 절로 넘어갑니다.
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

```{admonition} AI 에게 물어보기 — 데이터
:class: tip

경로 오류는 대부분 노트북을 연 위치 때문에 납니다. 무엇을 확인해야 하는지부터 묻습니다.

> `FileNotFoundError` 가 났어. 파이썬에서 지금 작업 디렉터리를 확인하는 방법을 알려 줘.

> parquet 파일이 CSV 와 무엇이 다른지, 왜 도로망 데이터에 이걸 쓰는지 알려 줘.

> `G` 를 출력했더니 `MultiDiGraph` 라고 나왔어. 이게 무슨 자료구조인지 알려 줘.
```

## 0.3 엔진에 연결하기

최단경로나 시뮬레이션을 실제로 돌리는 것은 **DTUMOS** 라는 별도 프로그램입니다. Rust로 짜여 있고 Docker 컨테이너로 돕니다. 이 책에서는 그 안을 들여다보지 않고 HTTP로 부르기만 합니다.

연결 방법은 세 가지입니다.

| 방법 | 언제 쓰는가 | 설정 |
|---|---|---|
| 공용 서버 | 수업 중 무거운 시뮬레이션 | `SMARTMOB_DTUMOS_URL=http://<주소>:<팀별 포트>` |
| 로컬 Docker | 엔진 코드를 직접 열어 볼 때 | `docker compose up -d` 후 기본값 그대로 |
| 녹화본 | 서버 없이 복습할 때 | `SMARTMOB_OFFLINE=1` |

세 번째가 중요합니다. 서버에 못 붙어도 책이 멈추지 않습니다. 저장소에는 실제 실행 결과가 `data/fixtures/` 에 녹화되어 있고, 연결이 안 되면 그것을 대신 돌려줍니다.

```{code-cell} python
from smartmob import Dtumos

dt = Dtumos()
dt.health()
```

`status` 가 `fixture` 로 나오면 녹화본을 쓰는 중입니다. 실서버에 붙었다면 서버가 돌려준 상태가 그대로 나옵니다.

```{warning}
녹화본에는 이 책에 나오는 요청만 들어 있습니다. 차량 대수를 80대에서 81대로 바꿔 보는 식으로 값을 바꾸면 `FixtureMissing` 오류가 납니다. 실서버가 필요하다는 뜻이지, 코드가 틀린 것이 아닙니다.
```

```{admonition} AI 에게 물어보기 — 연결 설정
:class: tip

환경변수를 두는 방법은 운영체제와 셸마다 다릅니다. 자기 환경을 밝혀야 맞는 답이 옵니다.

> 윈도우 파워셸에서 환경변수 `SMARTMOB_OFFLINE` 을 1 로 두고 주피터를 켜는 방법을 알려 줘.

> 맥 터미널에서는 같은 것을 어떻게 하는지 알려 줘.

> `docker compose up -d` 가 무엇을 하는 명령인지 설명해 줘. 도커는 처음 써.
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

숫자를 하나씩 읽어 봅니다.

- `service_rate` 가 1.0입니다. 990건의 호출이 전부 배차됐습니다.
- `avg_waiting_time_min` 이 약 4.1분입니다. 호출하고 차가 올 때까지 평균 4분 걸렸습니다.
- `utilization` 이 약 0.27입니다. 차량이 승객을 태우고 있던 시간이 전체의 27%뿐입니다.

마지막 값이 흥미롭습니다. 대기시간이 4분이면 승객 입장에서는 괜찮은데, 차량의 4분의 3은 놀고 있었습니다. 80대가 너무 많은 것은 아닐까요? 40대로 줄이면 대기시간이 얼마나 늘어날까요?

이 질문에 답하려면 같은 수요와 같은 도로망 위에서 차량 대수만 바꿔 다시 돌려 봐야 합니다. 그 도구를 이 책에서 만듭니다.

## 0.5 시간에 따라 무슨 일이 있었는지 보기

`sim.record` 는 1분마다 한 줄씩 기록된 표입니다.

```{code-cell} python
sim.record.head()
```

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

```{admonition} AI 에게 물어보기 — 표와 그림
:class: tip

`sim.record` 는 pandas 데이터프레임입니다. 표를 다루는 문법은 필요할 때 물어보면서 익히는 편이 빠릅니다.

> 판다스 데이터프레임에서 특정 컬럼이 가장 큰 행을 찾는 방법을 알려 줘.

> 이 그래프의 x축을 분 대신 `HH:MM` 으로 바꾸려면 어떻게 하는지 알려 줘.
```

## 이 장의 실습

노트북 `labs/ch00_setup.ipynb` 를 열어 함께 돌립니다.

설치 확인부터 첫 시뮬레이션까지 이 장의 순서를 그대로 따라갑니다. 마지막에 빈칸이 하나 있습니다.

```bash
jupyter lab labs/ch00_setup.ipynb
```

```{admonition} AI 에게 물어보기 — 빈칸이 안 풀릴 때
:class: tip

답을 그대로 받으면 배울 자리가 사라집니다. 무엇을 모르는지 좁혀 달라고 부탁합니다.

> 아래 코드에서 오류가 났어. 원인이 어디인지만 짚어 주고 고친 코드는 주지 마.

> 이 빈칸을 채우려면 어떤 함수를 찾아봐야 하는지 이름만 알려 줘.

> 내가 쓴 코드가 왜 이 값을 내는지 한 줄씩 따라가면서 설명해 줘.
```

## 정리

- `pip install -r requirements.txt` 로 환경을 만들고, `smartmob` 을 통해 데이터와 엔진에 접근합니다
- `load_road_graph("hanam")` 이 도로망을, `Dtumos()` 가 시뮬레이션 엔진을 담당합니다
- 엔진에 못 붙으면 `data/fixtures/` 의 녹화본으로 자동 전환됩니다
- `sim.summary()` 는 서비스율·평균 대기시간·차량 가동률을, `sim.record` 는 분 단위 시계열을 줍니다
- 막히면 명령과 오류 전문을 붙여넣고 AI 에게 묻습니다. `import smartmob` 이 지나가는지가 설치의 기준입니다
- 1장에서는 이 장치가 왜 필요한지, 기존 시뮬레이터로는 왜 안 되는지를 봅니다

## 연습문제

```{admonition} 연습 0.1  ★
:class: tip

`sim.record` 에서 대기 승객 수가 가장 많았던 시각과 그때의 인원을 구해 봅시다.
`smartmob.data.minutes_to_hhmm` 을 쓰면 분을 `HH:MM` 으로 바꿀 수 있습니다.

산출물: 시각 1개, 인원 1개.
```
