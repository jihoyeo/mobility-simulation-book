import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
maplibregl.setWorkerUrl(workerUrl);
import buildings from './campus-buildings.json';
import { positionOnPath } from './routing.js';

export function createRouteMap(network, paths, visits, stopNodes, colors) {
  const coordinate = id => { const p = network.nodes[id]; return [p.x, p.y]; };
  const collection = features => ({ type: 'FeatureCollection', features });
  const line = coordinates => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates } });
  const map = new maplibregl.Map({ container: 'route-map', center: coordinate(stopNodes.S0), zoom: 16,
    style: { version: 8, sources: {
      osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256,
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' },
      buildings: { type: 'geojson', data: buildings },
      roads: { type: 'geojson', data: collection(network.edges.map(e => line([coordinate(e.from), coordinate(e.to)]))) },
      route: { type: 'geojson', data: collection(paths.map(p => line(p.nodes.map(coordinate)))) },
    }, layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#edf1e9' } },
      { id: 'basemap', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.7 } },
      { id: 'buildings', type: 'fill', source: 'buildings', paint: { 'fill-color': '#bbc6bf', 'fill-opacity': 0.55 } },
      { id: 'roads', type: 'line', source: 'roads', paint: { 'line-color': '#fff', 'line-width': 5 } },
      { id: 'route-border', type: 'line', source: 'route', paint: { 'line-color': '#fff', 'line-width': 9 } },
      { id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#187e79', 'line-width': 5 } },
    ] } });
  map.addControl(new maplibregl.NavigationControl(), 'top-right');
  const bounds = new maplibregl.LngLatBounds();
  paths.flatMap(p => p.nodes).forEach(id => bounds.extend(coordinate(id)));
  map.fitBounds(bounds, { padding: { top: 70, bottom: 60, left: 70, right: 70 }, duration: 0 });
  const queues = visits.slice(0, -1).map(v => {
    const element = document.createElement('div'); element.className = 'stop-marker';
    const name = document.createElement('strong'); name.textContent = v.name;
    const queue = document.createElement('span'); element.append(name, queue);
    new maplibregl.Marker({ element, anchor: 'bottom', offset: [0, -12] }).setLngLat(coordinate(stopNodes[v.stopId])).addTo(map);
    return queue;
  });
  const buses = [];
  map.on('error', event => { console.warn(event.error); document.querySelector('#map-note').textContent = '배경지도 연결 확인 필요 · 저장된 도로·건물로 운행 재생 중'; });
  return {
    update(snap) {
      queues.forEach((el, i) => { el.textContent = `대기 ${snap.queues[i]}명`; });
      while (buses.length > snap.vehicles.length) buses.pop().marker.remove();
      snap.vehicles.forEach((v, i) => {
        if (!buses[i]) {
          const element = document.createElement('div'); element.className = 'bus-marker'; element.style.background = colors[i % colors.length];
          buses.push({ element, marker: new maplibregl.Marker({ element }).setLngLat(coordinate(stopNodes.S0)).addTo(map) });
        }
        const bus = buses[i];
        bus.element.textContent = `${i + 1}호 · ${v.load}명`;
        bus.element.title = v.active ? '운행 중' : '출발 대기';
        bus.element.style.opacity = v.active ? '1' : '0.55';
        bus.marker.setLngLat(v.active ? positionOnPath(paths[v.from], network, v.progress) : coordinate(stopNodes.S0));
      });
    },
  };
}
