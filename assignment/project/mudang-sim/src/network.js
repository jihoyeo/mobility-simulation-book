import roads from './campus-roads.json' with { type: 'json' };
// x=경도, y=위도. OSM way의 모든 형상 노드를 유지해 도로 굴곡을 따라 이동합니다.
export const network = { nodes: roads.nodes, edges: roads.edges };
// 건물 인근 도로 노드를 고른 실습용 정차점이며 실제 승강장 위치는 아닙니다.
export const stopNodes = roads.stopNodes;
