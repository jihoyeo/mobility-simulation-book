"""Write the student starter notebook; no instructor results are embedded."""
import json
from pathlib import Path


cells = []


def md(s):
    cells.append({'cell_type':'markdown','metadata':{},'source':s.strip().splitlines(keepends=True)})


def code(s):
    cells.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
                  'source':s.strip().splitlines(keepends=True)})


md('''## 실행 준비

이 노트북에서 과제 안내를 읽고 제공 코드를 실행한 뒤 답안을 작성합니다.
데이터는 이 노트북 옆의 `data/`에 두 파일로 들어 있습니다. `od.csv`는 30명의 통행 목록이고, `songpa_network.zip`은 도로망과 시간표입니다. ZIP은 풀지 않아도 됩니다. 별도 서버나 DTUMOS 설치는 필요하지 않습니다.
저장소의 `requirements.txt`에 있는 패키지를 설치한 환경에서 실행합니다.

다익스트라와 RAPTOR는 기존 함수를 import합니다. 한 사람의 경로 계산과 지도 재생까지 제공하며,
30명 반복 계산, 비교표·그래프 작성, 결과 해석은 각 문제 아래의 학생 작업 셀에서 진행합니다.''')
code('''from pathlib import Path
import sys

ROOT = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "smartmob").is_dir())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from IPython.display import display
from smartmob.assignment2 import load_data, load_boundary, taxi_route, transit_route, export_playback

DATA = ROOT / "assignment" / "data"
OUTPUT = ROOT / "outputs" / "assignment2_student"
OUTPUT.mkdir(parents=True, exist_ok=True)''')
md('''### 데이터 불러오기

2024년 GTFS에서 2024년 10월 7일의 운행을 골랐습니다. 출발시각은 오전 9시입니다.
O-D 30건은 난수 시드 42로 만든 가상 통행이며, 두 수단 모두 경로가 있는 경우만 남겼습니다.
따라서 송파구 주민의 실제 통행 분포를 나타내지 않습니다.

도로망은 서울 캐시 중 송파구와 주변 4km에 걸치는 도로입니다. 경기도 쪽 도로는 완전하지 않습니다.
송파구 안팎 판정에는 2013년 공개 경계를 사용했습니다. 최신 행정경계로 해석하지 않습니다.
GTFS 노선은 경계에서 자르지 않고 전체 정류장 순서를 보존했습니다.
[데이터 설명서](https://github.com/jihoyeo/mobility-simulation-book/blob/main/docs/ASSIGNMENT2_DATA.md)에 출처와 나머지 계산 조건이 있습니다.

시간표를 RAPTOR 자료구조로 바꾸는 첫 실행에는 수십 초 정도 걸릴 수 있습니다.''')
code('''graph, transit, od = load_data(DATA)
display(od.head())
print("인원:", od.person_id.nunique())
print("도로 노드:", len(graph.coord), "도로 엣지:", len(graph.edges))
print(transit.describe())''')
md('''출발지와 목적지의 원래 좌표는 `origin_raw_lat/lon`, `destination_raw_lat/lon`입니다.
경로 계산에는 스냅한 `origin_lat/lon`, `destination_lat/lon`을 사용합니다.
`origin_snap_m`, `destination_snap_m`은 옮긴 거리입니다.

다음은 출발지와 목적지를 그리는 기본 지도입니다. 도로와 경계는 로컬 파일에서 읽습니다.''')
code('''import geopandas as gpd
import matplotlib.pyplot as plt

boundary = gpd.GeoDataFrame.from_features(load_boundary(DATA)["features"], crs="EPSG:4326")
fig, ax = plt.subplots(figsize=(8, 8))
boundary.boundary.plot(ax=ax, color="gray", linewidth=1)
ax.scatter(od.origin_lon, od.origin_lat, label="Origin", s=25)
ax.scatter(od.destination_lon, od.destination_lat, label="Destination", marker="x", s=30)
ax.set(xlabel="Longitude", ylabel="Latitude", title="Assignment 2: synthetic O-D")
ax.legend()
fig.savefig(OUTPUT / "od_map.png", dpi=150, bbox_inches="tight")
plt.show()''')
md('''### 제공 예제: 한 사람의 경로

`taxi_route`는 다익스트라를 호출하고, 선택한 도로 엣지의 길이와 통행시간을 합합니다.
속도는 모든 엣지에서 30km/h입니다. 도로 형상도 함께 반환합니다.

`transit_route`는 RAPTOR를 호출합니다. 마지막 정류장에서 목적지까지 걷는 시간을 더해
가장 일찍 목적지에 도착하는 경로를 고릅니다. 접근·도착 도보는 각각 800m, 환승 도보는 500m,
환승은 2회까지 허용합니다. 걷는 거리는 직선거리의 1.35배이고 보행속도는 1.2m/s입니다.

내부에서는 `smartmob.teaching.dijkstra.dijkstra`와 `smartmob.teaching.raptor.raptor`를 사용합니다.
과제에서는 아래 호출 방법을 그대로 사용해도 됩니다.''')
code('''person = od.iloc[0]
taxi = taxi_route(graph, person.origin_node, person.destination_node)
public = transit_route(
    transit,
    (person.origin_lat, person.origin_lon),
    (person.destination_lat, person.destination_lon),
)
example = {"person_id": person.person_id, "taxi": taxi, "transit": public}
display(pd.DataFrame([
    {"mode": "taxi", "minutes": taxi["duration_min"], "km": taxi["distance_km"]},
    {"mode": "transit", "minutes": public["duration_min"], "km": public["distance_km"]},
]))''')
md('''`duration_min`은 총 통행시간(분), `distance_km`는 이동거리(km)입니다.
대중교통 결과에는 `walk_min`, `wait_min`, `in_vehicle_min`, `transfers`,
`walk_km`, `in_vehicle_km`, `routes`도 들어 있습니다.
`segments`는 지도 재생에 쓰는 구간별 시각·좌표이므로 그대로 보관합니다.

도보·대기·차내시간을 더하면 총 통행시간이 되는지 확인합니다.''')
code('''parts = {k: public[k] for k in ("walk_min", "wait_min", "in_vehicle_min", "transfers", "routes")}
print(parts)
total = sum(public[k] for k in ("walk_min", "wait_min", "in_vehicle_min"))
print("시간 합:", total, "총 통행시간:", public["duration_min"])
assert abs(total - public["duration_min"]) < 1e-6''')
md('''### 제공 예제: 한 사람의 이동 재생

저장된 HTML을 브라우저에서 엽니다. 외부 지도 타일이나 인터넷 연결이 필요하지 않습니다.
두 지도에서 같은 번호의 점이 같은 사람입니다. 09:00·09:10·09:20 버튼으로 시각을 바꾸고,
사람 번호를 선택하면 두 수단의 경로와 현재 상태를 볼 수 있습니다.
`화면 PNG 저장`으로 현재 장면을 저장합니다.''')
code('''preview = export_playback(
    graph, od.iloc[:1], [example], OUTPUT / "one_person.html"
)
print("재생 파일:", preview.relative_to(ROOT).as_posix())''')
md('''### 답안 작성: 30명 비교

위의 한 사람 계산을 반복합니다. 결과 목록에는 각 사람의 `person_id`, `taxi`, `transit` 결과를 넣습니다.
경로를 찾지 못한 경우에는 실패 이유를 기록하고, 지표에는 결측값을 사용합니다.
`smartmob.assignment2.compare_person`을 사용하면 실패 기록까지 같은 형식으로 받을 수 있습니다.

1. `od`의 각 행에 대해 두 수단의 경로를 계산해 `results`에 모읍니다.
2. 결과에서 지표를 꺼내 사람당 한 행인 비교표를 만듭니다.
3. 대중교통 값에서 택시 값을 빼 시간·거리 차이를 계산합니다.
4. 두 수단 모두 성공한 사람들의 평균을 구하고 사람별 차이를 그래프로 그립니다.

아래 셀에 작성합니다. 비교표를 `comparison.csv`로 저장하고, 해석은 별도 Markdown 셀에 적습니다.''')
code('''from smartmob.assignment2 import compare_person

results = []
# 여기에 30명 반복 계산과 비교표 작성을 추가합니다.
''')
md('''### 답안 작성: 30명 지도 재생

`results`를 완성하면 아래 셀에서 재생 파일을 만듭니다.
지도에서 저장한 장면 세 장과 과제의 질문에 대한 답을 제출 노트북에 넣습니다.''')
code('''if len(results) == 30:
    playback = export_playback(graph, od, results, OUTPUT / "playback.html")
    print("저장:", playback)
else:
    print("30명 비교 셀에서 results를 먼저 작성합니다.")''')

target = Path('assignment/assignment_2.ipynb')
existing = json.loads(target.read_text(encoding='utf-8'))
guide = {c['id']:c for c in existing['cells'] if c.get('id','').startswith('a2-')}
assert len(guide) == 5, 'Expected five assignment instruction cells'
for cell in guide.values():
    s = ''.join(cell['source'])
    s = s.replace('> [기초코드 노트북](../labs/assignment_2.ipynb)에서 시작합니다.', '> 이 노트북의 제공 코드를 실행하고 각 문제 아래에 답안을 작성합니다.')
    s = s.replace('../data/assignment2/README.md', 'https://github.com/jihoyeo/mobility-simulation-book/blob/main/docs/ASSIGNMENT2_DATA.md').replace('data/assignment2/README.md', 'https://github.com/jihoyeo/mobility-simulation-book/blob/main/docs/ASSIGNMENT2_DATA.md')
    cell['source'] = s.splitlines(keepends=True)
for i, cell in enumerate(cells):
    cell['id'] = f'assignment2-starter-{i:02d}'
def answer_cell(name):
    return {'cell_type':'markdown','id':name,'metadata':{},'source':['### 해석과 답안\n','\n','이곳에 계산 결과와 해석을 작성합니다.']}
combined = [guide['a2-00'],guide['a2-01'],*cells[:6],
            guide['a2-02'],*cells[6:10],*cells[12:14],answer_cell('answer-comparison'),
            guide['a2-03'],*cells[10:12],*cells[14:16],answer_cell('answer-playback'),guide['a2-04']]
notebook = {'cells':combined,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
            'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
target.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
