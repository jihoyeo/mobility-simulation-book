# 도로·지도 자료

- 출처: [OpenStreetMap](https://www.openstreetmap.org/#map=17/37.453/127.131), © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright).
- 추출 범위: 서경계 127.126, 남경계 37.449, 동경계 127.136, 북경계 37.456. 조회일 2026-11-03.
- `src/campus-roads.json`: OSM way의 연속 노드를 유향 링크로 변환한 도로 자료. 거리 단위 m, 좌표는 WGS84 경도·위도임. 원본 way ID를 링크에 남김.
- `src/campus-buildings.json`: 같은 범위의 건물 외곽선. 위 두 데이터 파일은 ODbL로 제공함.
- service/residential/unclassified/tertiary/secondary/primary/living_street 도로를 포함함. access=no/private, motor_vehicle=no를 제외하고 oneway 및 회전교차로 방향을 반영함. 모든 조건부 제한·회전 제한·현장 차단시설을 처리하는 차량용 라우터는 아님.
- 반도체대학·AI공학관의 OSM 건물 중심 근처 도로 노드를 예시 정차점으로 선택함. 실제 승강장 위치나 공식 무당이 경로를 뜻하지 않음.
- 배경지도는 OSM 표준 타일을 사용함. [타일 이용 정책](https://operations.osmfoundation.org/policies/tiles/)에 따라 화면에 출처를 표시하고 현재 화면의 타일만 요청함.
- 지도 표시: [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/). 별도 API 키나 DTUMOS 설치는 필요 없음.

## 자료 재구축

일상적인 실행은 Node.js만 필요함. 도로 자료를 다시 추출할 때만 Python 3을 사용함.
프로젝트 폴더에서 다음을 실행함. 데이터 갱신으로 도로 연결과 경로가 바뀔 수 있음.

```bash
curl --fail 'https://www.openstreetmap.org/api/0.6/map?bbox=127.126,37.449,127.136,37.456' -o campus.osm
python3 scripts/import-osm.py campus.osm
npm run gtfs
```

자료를 갱신한 뒤 왕복 경로·정차점·통행 제한을 확인함.
