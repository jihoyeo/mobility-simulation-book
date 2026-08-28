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

# 부록 B DTUMOS 서버 운영

이 책의 코드는 서버 없이도 돌아갑니다. 저장소에 실행 결과가 녹화되어 있기 때문입니다.

그런데 파일럿 프로젝트에서는 조건을 바꿔 가며 직접 돌려야 합니다. 그때는 서버가 필요합니다. 이 부록은 서버를 띄우는 방법과 수업에서 운영할 때 걸리는 것들을 정리합니다.

## B.1 세 가지 사용 방식

| 방식 | 언제 | 준비 |
|---|---|---|
| 녹화본 | 서버 없이 복습 | 없음 (`SMARTMOB_OFFLINE=1`) |
| 공용 서버 | 수업 중, 무거운 시뮬레이션 | 교수자가 띄움. 학생은 주소만 |
| 로컬 Docker | 엔진 코드를 직접 열어 볼 때 | 사전 빌드 이미지 + 도시 데이터 |

`smartmob` 은 셋을 환경변수 하나로 전환합니다.

```{code-cell} python
:tags: [skip-execution]

import os

os.environ["SMARTMOB_DTUMOS_URL"] = "http://dtumos.example.ac.kr:8003"
os.environ.pop("SMARTMOB_OFFLINE", None)

from smartmob import Dtumos
dt = Dtumos()
print(dt.mode, dt.health())
```

`mode` 가 `live` 로 나오면 서버에 붙은 것입니다. `fixture` 면 녹화본입니다.

## B.2 로컬에서 띄우기

`docker compose up --build` 는 Rust 크레이트 두 개를 릴리스 빌드하고 프론트엔드를 번들합니다. 15~25분이 걸리고 메모리가 8GB 필요합니다. **수업 중에는 하지 않습니다.**

사전 빌드 이미지를 씁니다.

```bash
docker pull ghcr.io/camus-lab/dtumos:course-2026-1
```

```{warning}
이미지에는 **도시 데이터가 들어 있지 않습니다.** `.dockerignore` 가 `data/*` 를 제외합니다. 컨테이너만 띄우면 도시 목록이 비어 있고, 시뮬레이션을 돌리면 실패합니다.
```

도시 데이터를 따로 받아 마운트합니다.

```bash
# 강의용 도시 묶음 (하남 + 성남, 약 300MB)
curl -LO https://<배포주소>/cities-mini.tar.zst
mkdir -p ~/dtumos/cities && tar --zstd -xf cities-mini.tar.zst -C ~/dtumos/cities
```

`docker-compose.course.yml`:

```yaml
services:
  dtumos:
    image: ghcr.io/camus-lab/dtumos:course-2026-1
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      MAPBOX_TOKEN: ${MAPBOX_TOKEN}
      DTUMOS_REQUIRE_AUTH: "false"
    volumes:
      - ~/dtumos/cities:/app/data/cities
      - ~/dtumos/results:/app/simul_result
```

```bash
docker compose -f docker-compose.course.yml up -d
curl http://localhost:8000/health
```

`127.0.0.1:` 접두사가 중요합니다. 없으면 같은 네트워크의 아무나 접속할 수 있습니다.

## B.3 공용 서버 — 팀당 컨테이너 하나

DTUMOS API 는 **프로세스당 시뮬레이션을 한 번에 하나만** 돌립니다. `api/routers/simulation.py` 의 실행자가 `max_workers=1` 이고 모듈 수준 잠금이 걸려 있습니다. 설정으로 바꿀 수 없습니다.

컨테이너 하나로 수업 전체를 받으면 30명이 한 줄로 기다립니다. 팀마다 컨테이너를 따로 띄웁니다.

```bash
for i in 1 2 3 4 5 6; do
  DTUMOS_API_PORT=800$i \
  docker compose -p team0$i -f docker-compose.course.yml up -d
done
```

학생에게는 팀 번호에 맞는 주소를 줍니다.

```bash
export SMARTMOB_DTUMOS_URL=http://dtumos.example.ac.kr:8003
```

## B.4 열어 두면 안 되는 것

기본 설정은 인증이 없습니다(`DTUMOS_REQUIRE_AUTH=false`). 교내망 밖으로 그대로 노출하면 안 됩니다.

특히 두 경로가 위험합니다.

- `POST /api/algorithm/create` — 사용자가 보낸 코드를 서버에서 실행합니다
- `POST /api/data/region/build` — 전국 OpenStreetMap 원본(약 1GB)을 내려받습니다

교내망 안에서만 쓰거나, 인증 프록시를 앞에 둡니다. 프록시에서 위 두 경로를 막는 것이 가장 간단합니다.

Colab 을 쓰는 학생은 교내망에 닿지 못합니다. 공개 주소를 내주는 터널을 하나 열어 줍니다.

```bash
cloudflared tunnel --url http://localhost:8003
```

## B.5 도시 데이터 준비하기

실제로 준비된 도시는 넷뿐입니다. 하남·성남·서울·수원입니다. 나머지는 경계 파일만 있습니다.

새 도시를 준비하려면 시간이 걸립니다.

```bash
docker compose exec dtumos dtumos data status
docker compose exec dtumos dtumos data prepare --city gwangju
docker compose exec dtumos dtumos data generate-demand --city gwangju --count 5000
docker compose exec dtumos dtumos data generate-vehicles --city gwangju --count 200
```

`prepare` 는 해당 국가의 OpenStreetMap 원본을 받아 자르고 그래프를 만듭니다. 한국 전체를 받으므로 처음 한 번은 오래 걸립니다.

```{warning}
학생 30명이 각자 `data prepare` 를 부르면 1GB짜리 다운로드가 30번 일어납니다. **학기 시작 전에 필요한 도시를 미리 준비해 두고, 학생은 준비된 목록에서 고르게 합니다.**

기말 프로젝트 대상지를 미리 설문으로 받아 상위 10개 시군구를 준비해 두는 것을 권합니다.
```

프로젝트의 대중교통 부분은 GTFS 만 있으면 되므로 도로망 없이도 대부분 진행됩니다. 6~7장의 RAPTOR 는 GTFS 만 씁니다.

## B.6 서버 한도

서버가 막는 값들입니다. 넘으면 요청 자체가 거부됩니다.

| 환경변수 | 기본값 | 뜻 |
|---|---|---|
| `DTUMOS_MAX_PASSENGERS` | 10,000 | 시뮬레이션 한 번의 승객 수 |
| `DTUMOS_MAX_FLEET_SIZE` | 1,000 | 차량 대수 |
| `DTUMOS_MAX_TIME_RANGE_MINUTES` | 1,440 | 시뮬레이션 시간 범위 |
| `DTUMOS_MAX_CONCURRENT_JOBS` | 1 | 동시 작업 수 |

`smartmob` 은 앞의 세 가지를 요청 전에 확인합니다. 서버까지 갔다가 거절당하는 것보다 빠릅니다.

```{code-cell} python
from smartmob import Dtumos

try:
    Dtumos().run_simulation(city="hanam", num_passengers=50_000)
except ValueError as exc:
    print("걸림:", exc)
```

## B.7 녹화본 만들기

수업에서 쓸 시나리오를 미리 녹화해 두면 학생이 서버 없이도 복습할 수 있습니다.

```{code-cell} python
:tags: [skip-execution]

import os
os.environ["SMARTMOB_DTUMOS_URL"] = "http://localhost:8000"
os.environ.pop("SMARTMOB_OFFLINE", None)

from smartmob import Dtumos
from smartmob.fixtures import record

payload = dict(city="hanam", mode="taxi", fleet_size=40, num_passengers=1000,
               time_start=1080, time_end=1440, dispatch_mode="optimization",
               matrix_mode="street_distance", vehicle_capacity=1, random_seed=42)

sim = Dtumos(mode="live").run_simulation(**payload)
saved = sim.save("simul_result/hanam_V40")
record("simulation", payload, saved, label="hanam_taxi_V40_1000p_seed42")
```

녹화본 목록과 무결성은 이렇게 확인합니다.

```{code-cell} python
:tags: [skip-execution]

# python -m smartmob.fixtures list
# python -m smartmob.fixtures check
```

## B.8 녹화본이 낡지 않게

엔진이 바뀌면 녹화본과 실제 결과가 갈라집니다. CI 는 녹화본으로 빌드하므로 **초록불인 채로 낡은 숫자를 가르치게 됩니다.**

주 1회 대조하는 작업이 저장소에 있습니다.

```bash
SMARTMOB_DTUMOS_URL=http://localhost:8000 python tools/check_fixture_drift.py
```

허용 오차를 넘으면 종료코드 1 을 내고, GitHub Actions 가 이슈를 만듭니다. 그때는 녹화본을 다시 만듭니다. 본문에 인용한 숫자와 `tests/test_fixtures.py` 의 고정값도 **같이 고쳐야 합니다.**

## 정리

- 서버 없이 읽을 때는 `SMARTMOB_OFFLINE=1`, 서버가 있으면 `SMARTMOB_DTUMOS_URL` 하나만 설정합니다
- `docker compose up --build` 는 20분이 걸립니다. 사전 빌드 이미지를 씁니다
- 이미지에 도시 데이터가 없습니다. `/app/data/cities` 를 마운트해야 합니다
- API 는 프로세스당 시뮬레이션 하나만 돌립니다. 팀마다 컨테이너를 따로 띄웁니다
- 인증 없이 외부에 열지 않습니다. `/api/algorithm/create` 는 코드 실행 경로입니다
- 준비된 도시는 넷뿐입니다. 학기 전에 필요한 도시를 미리 준비합니다
- 녹화본은 주 1회 실제 엔진과 대조합니다
