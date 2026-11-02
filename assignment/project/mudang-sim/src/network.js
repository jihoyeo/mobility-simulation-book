// 화면 좌표와 거리 모두 실습용입니다. 실제 교내 도로망·위경도가 아닙니다.
export const network = {
  nodes: {
    A: { x: 120, y: 225 }, U1: { x: 280, y: 125 }, U2: { x: 500, y: 125 },
    B: { x: 680, y: 225 }, L1: { x: 280, y: 325 }, L2: { x: 500, y: 325 },
  },
  // 양방향 도로도 두 개의 유향 링크로 표현합니다.
  edges: [ ['A', 'U1', 180], ['U1', 'U2', 220], ['U2', 'B', 180],
    ['A', 'L1', 210], ['L1', 'L2', 250], ['L2', 'B', 210] ]
    .flatMap(([from, to, meters]) => [{ from, to, meters }, { from: to, to: from, meters }]),
};
// GTFS stop_id와 도로망 노드의 연결은 실제 프로젝트에서 학생이 구축합니다.
export const stopNodes = { S0: 'A', S1: 'B' };
