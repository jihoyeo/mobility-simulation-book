# 12장 실습 — 통행 애니메이션 뷰어

DTUMOS 화면의 핵심만 남긴 것입니다. 이 책에서 파이썬이 아닌 코드를 채우는 유일한 자리입니다.

DTUMOS 프론트엔드는 React 와 deck.gl 로 통행 컴포넌트 하나가 1,800줄이 넘습니다.
그중 차가 움직이는 것을 보여 주는 부분은 셋뿐입니다.
좌표열과 시각열을 `TripsLayer` 에 전달하고, 매 프레임 시각을 조금 늘리고, 다시 그립니다.
나머지는 패널과 필터와 테마와 차트입니다.

이 프로젝트는 그 셋만 합니다. 의존성은 deck.gl 세 개와 Vite 하나입니다.

## 준비

Node 20.19 이상 또는 22.12 이상이 필요합니다. <https://nodejs.org> 에서 LTS 를 설치합니다.

```bash
node --version
```

## 실행

```bash
cd labs/ch12_viewer
npm install        # 처음 한 번만
npm run dev        # npm start 도 같습니다
```

브라우저가 자동으로 열립니다. 열리지 않으면 터미널에 뜬 주소를 직접 엽니다.

처음에는 지도와 배경만 나오고 차가 움직이지 않습니다. 빈칸이 다섯 자리 있기 때문입니다.
화면 왼쪽 패널이 무엇이 남았는지 알려 줍니다.

`src/main.js` 를 고치고 저장하면 브라우저가 알아서 다시 그립니다. 새로고침도 필요 없습니다.

## 채울 것

`src/main.js` 하나만 고칩니다. 다섯 함수가 전부 한두 줄입니다.

| 함수 | 하는 일 |
|---|---|
| `tripPath` | 구간의 좌표열을 꺼냅니다 |
| `tripTimestamps` | 각 좌표의 시각을 꺼냅니다 |
| `tripColor` | 탑승과 공차의 색을 나눕니다 |
| `waitingPassengers` | 지금 기다리는 승객만 고릅니다 |
| `nextTime` | 한 프레임만큼 시간을 흘립니다 |

`src/viewer.js` 는 이 다섯 함수를 deck.gl 레이어로 엮는 배선입니다. 고칠 것이 없습니다.
`src/palette.js` 의 색은 바꿔도 됩니다. 채점 대상이 아닙니다.

## 채점

저장소 뿌리에서 실행합니다.

```bash
node tools/check_viewer.mjs
```

빈칸 다섯 자리를 일곱 가지 기준으로 봅니다. `labs/check.py` 가 파이썬 실습을 채점하는 것과 같은 자리입니다.

## 데이터

`public/data/` 에 네 파일이 들어갑니다. 노트북에서 만듭니다.

```python
from smartmob.viz import export_viewer

export_viewer(engine, "ch12_viewer/public/data", sample=200)   # labs/ 에서 실행할 때
```

파일 이름과 키 이름은 DTUMOS 가 내는 것 그대로입니다.
서버에서 받은 결과 디렉터리를 `public/data/` 에 그대로 복사해도 돌아갑니다.
11장에서 직접 짠 루프의 결과도 같은 함수로 내보낼 수 있습니다.
그쪽은 도로망 위를 달리지 않으므로 통행이 직선 하나로 나옵니다.

저장소에는 하남시 택시 200구간 표본이 들어 있습니다. 그래서 `npm run dev` 만 해도 화면이 나옵니다.

## 배포

발표나 제출에 쓸 주소가 필요하면 정적 파일로 만듭니다.

```bash
npm run build      # dist/ 에 생깁니다
npm run preview    # 만든 결과를 확인합니다
```

`dist/` 를 깃허브 페이지에 올리면 공개 주소가 나옵니다.
`vite.config.js` 의 `base` 가 상대경로라서 하위 경로에 올려도 됩니다.

## 배경지도

브이월드 지도를 씁니다. 기본값은 공개 시험용 키라 가끔 느립니다.
자기 키는 <https://www.vworld.kr> 에서 무료로 받고, 프로젝트 안에 `.env` 를 만들어 넣습니다.

```
VITE_VWORLD_KEY=여기에-발급받은-키
```

키가 없어도 통행은 그려집니다. 배경만 비어 있습니다.

## npm audit 경고

`npm install` 이 취약점 경고를 냅니다. deck.gl 이 3D 타일과 텍스처를 읽으려고 딸려 오는
`image-size` 와 `fflate` 때문입니다. 이 실습은 그 경로를 부르지 않고, 빌드할 때 걷어냅니다.

`npm audit fix --force` 는 deck.gl 을 낮춰 버려서 빌드가 깨집니다. 실행하지 마세요.
