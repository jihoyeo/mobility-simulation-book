# 용어 표

새 용어를 정할 때마다 **즉시** 여기에 기록합니다. 세션 간 용어 표류는 문체 표류보다 눈에 덜 띄고 더 오래 갑니다.

표기 원칙은 [STYLE.md](STYLE.md) S6에 있습니다. 최초 1회 `한국어(english)`, 이후 한국어만. 약어는 최초 1회 `한국어(ABBR, full name)`, 이후 약어만.

## 모빌리티 서비스

| 개념 | 본문 표기 | 최초 1회 | 쓰지 않는 말 |
|---|---|---|---|
| dispatch | 배차 | 배차(dispatch) | 디스패치, 배정 |
| relocation / rebalancing | 재배치 | 재배치(relocation) | 릴로케이션, 리밸런싱 |
| trip | 통행 | 통행(trip) | **여행**, 트립 |
| trip leg | 구간 | 구간(leg) | 레그 |
| deadheading | 공차 운행 | 공차 운행(빈 차로 움직이는 것) | 데드헤딩 |
| fleet size | 차량 대수 | 차량 대수(fleet size) | 플릿 사이즈 |
| ride-hailing | 호출형 택시 | 호출형 택시(ride-hailing) | 라이드헤일링 |
| DRT | DRT | 수요응답형 교통(DRT, demand-responsive transit) | 수요응답버스와 혼용 |
| headway | 배차간격 | 배차간격(headway) | 헤드웨이 |
| inter-stop running time | 구간 주행시간 | 이전 정류장 출발부터 다음 정류장 도착까지 걸리는 시간 | 정차시간과 혼용 |
| dwell time | 정차시간 | 정차시간(dwell time, 정류장 도착부터 출발까지 걸리는 시간) | 구간 주행시간과 혼용 |
| in-vehicle time | 차내시간 | 차내시간(in-vehicle time, 승차부터 하차까지 차량 안에서 보낸 시간) | 구간 주행시간과 혼용 |
| occupancy | 재차 인원 | 재차 인원(occupancy) | 점유율 |
| detour ratio | 우회율 | 우회율(detour ratio) | 디투어 |

## 데이터

| 개념 | 본문 표기 | 최초 1회 | 쓰지 않는 말 |
|---|---|---|---|
| O-D | O-D | 출발지-목적지(O-D) | 기종점, OD/O-D 혼용 |
| demand | 수요 | 수요(demand) | 디맨드 |
| GTFS | GTFS | GTFS(General Transit Feed Specification) | 지티에프에스 |
| GTFS trip | 운행 | 운행(trip, 시간표의 출발편 하나) | 승객 통행과 혼용 |
| service day | 운행일 | 운행일(service day) | 자정 이후의 달력 날짜와 혼용 |
| smartcard data | 스마트카드 데이터 | 스마트카드 데이터(교통카드 이용 이력) | 교통카드 데이터와 혼용 |
| observation unit | 관측 단위 | 관측 단위(observation unit, 한 행이 나타내는 대상) | 행 수와 통행량을 혼용 |
| trip chain | 통행사슬 | 통행사슬(trip chain) | 승차 구간 수와 혼용 |
| expanded trip count | 전수화 통행량 | 전수화 통행량(표본을 전체 규모로 환산한 추정치) | 실제 관측 인원과 혼용 |
| GPS trajectory | GPS 궤적 | GPS(Global Positioning System) 궤적 | GPS 점 수를 통행 건수로 사용 |
| uniform sampling | 균등 표집 | 균등 표집(uniform sampling) | 실제 수요 분포와 혼용 |
| boundary | 경계 | 경계(boundary) | 바운더리 |
| parquet / GeoPackage | parquet, GeoPackage | — | 파케이 |

## 네트워크와 경로

| 개념 | 본문 표기 | 최초 1회 | 쓰지 않는 말 |
|---|---|---|---|
| node / edge | 노드 / 엣지 | 노드(node) / 엣지(edge) | 링크·간선과 혼용 |
| adjacency list | 인접 리스트 | 인접 리스트(adjacency list) | 애드제이션시 |
| shortest path | 최단경로 | 최단경로(shortest path) | 최적경로 |
| tentative travel time | 잠정 시간 | 현재까지 발견한 경로 중 가장 짧은 통행시간 | 확정된 최소 통행시간과 혼용 |
| relaxation | 완화 | 완화(relaxation) | 확정과 혼용 |
| min-heap | 최소 힙 | 최소 힙(min-heap) | 정렬된 목록과 혼용 |
| binary search | 이분 탐색 | 이분 탐색(binary search) | 정렬되지 않은 목록에 적용 |
| admissibility | 허용 가능성 | 허용 가능성(admissibility) | 일관성과 혼용 |
| consistency | 일관성 | 일관성(consistency) | 허용 가능성과 혼용 |
| routing | 라우팅 | 경로 탐색(routing) | — |
| snapping | 스냅 | 스냅(snapping, 좌표를 가까운 노드나 도로 선에 맞추는 작업) | 스냅핑 |
| free-flow speed | 자유류 속도 | 자유류 속도(free-flow speed) | 프리플로우 |
| time-dependent shortest path | 시간의존 최단경로 | 시간의존 최단경로(time-dependent shortest path) | 시간대별 고정 비용 탐색과 혼용 |
| CH | 축약 계층 | 축약 계층(CH, Contraction Hierarchies) | MLD와 혼용 |
| MLD | 다단계 다익스트라 | 다단계 다익스트라(MLD, Multi-Level Dijkstra) | 축약 계층과 혼용 |
| RAPTOR | RAPTOR | RAPTOR(Round-bAsed Public Transit Optimized Router) | 랩터 |
| pattern | 패턴 | 패턴(pattern, 같은 노선과 정류장 순서의 운행 묶음) | GTFS 노선과 혼용 |
| time-expanded graph | 시간 확장 그래프 | 시간 확장 그래프(time-expanded graph) | 시간의존 비용과 혼용 |
| RAPTOR round | 라운드 | 라운드 k: k번 이하로 탑승한 도착시각 | 환승 k회와 혼용 |
| itinerary | 경로안 | 경로안(itinerary) | 이터너리 |
| footpath / transfer | 도보 환승 | 도보 환승(footpath) | 풋패스 |
| isochrone | 등시선 | 등시선(isochrone) | 아이소크론 |

> `엣지`는 교통공학에서 **링크(link)**라고도 부릅니다. 2장 최초 등장 시 한 줄로 밝히고, 이후 책 전체에서 **엣지**로 통일합니다.

## 모델링

| 개념 | 본문 표기 | 최초 1회 | 쓰지 않는 말 |
|---|---|---|---|
| calibration | 보정 | 보정(calibration) | 캘리브레이션 |
| ETA | ETA | 도착예정시간(ETA, estimated time of arrival) | 예상도착시각 |
| agent-based | 에이전트 기반 | 에이전트 기반(agent-based) | 행위자 기반 |
| digital twin | 디지털 트윈 | 디지털 트윈(digital twin) | — |
| discrete-time | 이산시간 | 이산시간(discrete-time) | 디스크리트 |
| cost matrix | 비용행렬 | 비용행렬(cost matrix) | 코스트 매트릭스 |
| assignment problem | 할당 문제 | 할당 문제(assignment problem) | 어사인먼트 |
| mode choice | 수단 선택 | 수단 선택(mode choice) | 모드 초이스 |
| Pareto front | 파레토 프론트 | 파레토 프론트(Pareto front) | — |
| sampling with replacement | 복원추출 | 복원추출(sampling with replacement) | 중복 없이 뽑는 표집과 혼용 |
| bootstrap | 부트스트랩 | 부트스트랩(bootstrap) | 모든 난수 시뮬레이션을 부트스트랩으로 부르기 |
| multinomial distribution | 다항분포 | 다항분포(multinomial distribution) | 독립 포아송 발생과 혼용 |
| Poisson distribution | 포아송 분포 | 포아송 분포(Poisson distribution) | 포아송 과정과 구분 없이 사용 |
| arrival rate | 발생률 | 발생률(arrival rate, 단위 시간당 기대 발생 건수) | 구간의 기대 건수와 혼용 |

## 쓰지 않는 말

| 흔히 쓰이지만 | 대신 |
|---|---|
| 인사이트 | 「알게 된 것」, 「시사점」, 또는 구체적으로 무엇을 알았는지 서술 |
| 솔루션 | 「해결책」 또는 서비스의 실제 이름 |
| 플랫폼 | 실제 소프트웨어 제품일 때만. 추상적 비유로 쓰지 않음 |
| 최적화하다 (막연히) | 무엇을 무엇 기준으로 줄였는지 명시 |
| 고도화 | 무엇을 어떻게 바꿨는지 명시 |

## 소프트웨어 이름 (영문 그대로, 표기 고정)

`OSMnx` · `NetworkX` · `GeoPandas` · `pandas` · `NumPy` · `SciPy` ·
`scikit-learn` · `LightGBM` · `pydeck` · `deck.gl` · `folium` · `Mapbox` ·
`OpenStreetMap`(약어는 OSM) · `SUMO` · `VISSIM` · `AIMSUN` · `MATSim` ·
`Docker` · `FastAPI` · `Jupyter Book` · `DTUMOS`
