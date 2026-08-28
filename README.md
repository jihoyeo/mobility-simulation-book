# mobility-simulation-book

가천대학교 스마트시티학과 '스마트 교통물류' 강의 교재의 소스입니다.
읽기만 할 목적이라면 [웹으로 보는 편](https://jihoyeo.github.io/mobility-simulation-book/)이 낫습니다.

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `ko/` | 본문. MyST Markdown 이며 `{code-cell}` 블록이 빌드할 때 실행됩니다 |
| `smartmob/` | 실습 헬퍼 패키지. 엔진 클라이언트, 데이터 로더, 교육용 구현체, 시각화 |
| `data/hanam/` | 하남시 실습 데이터(도로망 parquet, GTFS parquet, 수요·차량 CSV) |
| `data/fixtures/` | DTUMOS 실행 결과 녹화본. 서버 없이 책을 빌드할 때 씁니다 |
| `exercises/` | 학생 배포용 스켈레톤 |
| `projects/` | 파일럿 프로젝트 안내와 스타터 코드 |
| `tests/` | 교육용 구현체의 검증 기준 |
| `tools/` | 문체 린터(`kolint.py`), 녹화본 드리프트 검사 |
| `docs/` | 집필 스타일 가이드. 책에는 포함되지 않습니다 |

## 빌드

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
SMARTMOB_OFFLINE=1 jupyter-book build .
open _build/html/index.html
```

`SMARTMOB_OFFLINE=1` 은 시뮬레이션 엔진에 접속하지 않고 `data/fixtures/` 의 녹화본을 쓰라는 뜻입니다. CI 도 이 모드로 빌드합니다.

실서버에 붙여 빌드하려면 DTUMOS 를 띄운 뒤 주소를 지정합니다.

```bash
SMARTMOB_DTUMOS_URL=http://localhost:8000 jupyter-book build .
```

## 테스트

```bash
pip install pytest
SMARTMOB_OFFLINE=1 pytest          # 서버 없이 도는 전체 테스트
pytest -m live                      # DTUMOS 서버가 필요한 대조 테스트
```

## 데이터

15MB 이하의 실습 데이터는 저장소에 들어 있습니다. 그보다 큰 자산은 `data/MANIFEST.toml` 에 주소와 sha256 이 적혀 있고, 처음 쓸 때 내려받습니다.

```python
from smartmob.data import ensure
path = ensure("GTFS_Korea_2024.zip")
```

## 집필 규칙

원고를 고치기 전에 [`docs/STYLE-CHEATSHEET.md`](docs/STYLE-CHEATSHEET.md) 를 읽습니다. 전문은 [`docs/STYLE.md`](docs/STYLE.md) 입니다.

커밋 전에 문체 검사를 통과시킵니다.

```bash
python tools/kolint.py ko/ intro.md --baseline .kolint-baseline.json
```

## 라이선스

본문과 코드는 MIT 입니다. `data/` 의 원본 데이터는 각 출처의 조건을 따릅니다. 자세한 것은 `data/MANIFEST.toml` 을 보세요.
