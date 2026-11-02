// 작은 도로망에서 읽기 쉽게 작성한 다익스트라입니다. 비용 단위는 미터입니다.
export function shortestPath(network, source, target) {
  if (!network.nodes[source] || !network.nodes[target]) throw new Error('정류장의 도로망 연결 노드가 없습니다.');
  if (network.edges.some(e => !network.nodes[e.from] || !network.nodes[e.to]
    || !Number.isFinite(e.meters) || e.meters <= 0)) throw new Error('도로 링크와 양의 거리를 확인합니다.');
  const distance = new Map([[source, 0]]), previous = new Map(), done = new Set();
  while (true) {
    const next = [...distance].filter(([node]) => !done.has(node)).sort((a, b) => a[1] - b[1])[0];
    if (!next) throw new Error(`도로망에서 경로를 찾을 수 없습니다: ${source} → ${target}`);
    const [node, meters] = next;
    if (node === target) {
      const nodes = [target], links = [];
      while (nodes[0] !== source) {
        const edge = previous.get(nodes[0]); links.unshift(edge); nodes.unshift(edge.from);
      }
      return { nodes, links, meters };
    }
    done.add(node);
    for (const edge of network.edges.filter(e => e.from === node)) {
      const candidate = meters + edge.meters;
      if (candidate < (distance.get(edge.to) ?? Infinity)) {
        distance.set(edge.to, candidate); previous.set(edge.to, edge);
      }
    }
  }
}

export function connectRoute(route, network, stopNodes) {
  return route.visits.slice(1).map((visit, i) =>
    shortestPath(network, stopNodes[route.visits[i].stopId], stopNodes[visit.stopId]));
}

export function positionOnPath(path, network, progress) {
  let remaining = Math.max(0, Math.min(1, progress)) * path.meters;
  for (const edge of path.links) {
    if (remaining <= edge.meters) {
      const a = network.nodes[edge.from], b = network.nodes[edge.to], p = remaining / edge.meters;
      return [a.x + (b.x - a.x) * p, a.y + (b.y - a.y) * p];
    }
    remaining -= edge.meters;
  }
  const last = network.nodes[path.nodes.at(-1)]; return [last.x, last.y];
}
