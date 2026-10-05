"""Assignment 2 loaders, route reconstruction and offline map playback.

The routing algorithms are imported from the teaching modules.
"""
from pathlib import Path
import json
import math
from zipfile import ZipFile

import pandas as pd

from smartmob.teaching.graph import RoadGraph, haversine_km
from smartmob.teaching.dijkstra import dijkstra
from smartmob.teaching.raptor import TransitData, raptor, INF

START = 9 * 3600
DATA = Path(__file__).resolve().parents[1] / 'assignment' / 'data'


def load_data(root=DATA):
    root = Path(root)
    with ZipFile(root / 'songpa_network.zip') as archive:
        read = lambda name: pd.read_parquet(archive.open(name))
        graph = RoadGraph.from_frames(read('road_graph_nodes.parquet'), read('road_graph_edges.parquet'), speed_kmh=30)
        feed = {name: read(f'gtfs/{name}.parquet') for name in ('stops','routes','trips','stop_times','calendar')}
    transit = TransitData.from_gtfs(feed, max_transfer_m=500)
    od = pd.read_csv(root / 'od.csv') if (root / 'od.csv').exists() else None
    return graph, transit, od


def load_boundary(root=DATA):
    with ZipFile(Path(root) / 'songpa_network.zip') as archive:
        return json.loads(archive.read('songpa.geojson'))


def line_coords(wkt):
    return [[float(v) for v in xy.strip().split()[:2]] for xy in wkt[wkt.index('(')+1:wkt.rindex(')')].split(',')]


def _segment(start, end, coords, state):
    if end < start:
        raise ValueError(f'Non-monotone itinerary: {start} > {end}')
    return {'start': float(start), 'end': float(end), 'coords': coords, 'state': state}


def taxi_route(graph, origin_node, destination_node):
    path = dijkstra(graph, origin_node, destination_node)
    segments, distance, now = [], 0.0, float(START)
    for u, v in zip(path.nodes, path.nodes[1:]):
        _, seconds, idx = min((e for e in graph.neighbors(u) if e[0] == v), key=lambda e: (e[1], e[2]))
        edge = graph.edges.iloc[idx]
        coords = line_coords(edge.geometry_wkt)
        lat, lon = graph.coord[u]
        if haversine_km(lat, lon, coords[-1][1], coords[-1][0]) < haversine_km(lat, lon, coords[0][1], coords[0][0]):
            coords.reverse()
        segments.append(_segment(now, now+seconds, coords, '탑승'))
        now += seconds
        distance += float(edge.length) / 1000
    assert math.isclose(now-START, path.duration_s, abs_tol=1e-6)
    return {'success': True, 'duration_min': path.duration_min, 'distance_km': distance,
            'segments': segments, 'arrival': now}


def _trace_transit(data, result, target):
    k = next(k for k, row in enumerate(result.rounds) if row[target] == result.best[target])
    stop, seen, legs = target, set(), []
    while True:
        key = (k, stop)
        if key in seen:
            raise ValueError('Cycle in RAPTOR parents')
        seen.add(key)
        entry = result.parent.get(key)
        if entry is None:
            if k == 0:
                break
            k -= 1
            continue
        if entry[0] == 'access':
            legs.append(('access', stop, entry[1]))
            break
        if entry[0] == 'walk':
            _, previous, seconds = entry
            legs.append(('walk', previous, stop, seconds))
            stop = previous
        else:
            _, pi, trip, board, alight = entry
            legs.append(('ride', pi, trip, board, alight))
            stop = data.patterns[pi].stops[board]
            k -= 1
    return list(reversed(legs))


def transit_route(data, origin, destination, max_transfers=2):
    # Include all stops within the distance threshold, not just the first 30.
    access = data.access_stops(*origin, max_walk_m=800, limit=data.n_stops)
    egress = data.access_stops(*destination, max_walk_m=800, limit=data.n_stops)
    if not access or not egress:
        raise ValueError('800m 안에 출발 또는 도착 정류장이 없습니다.')
    result = raptor(data, access, START, max_rounds=max_transfers+1)
    choices = [(result.best[s] + sec, s, sec) for s,sec in egress if result.best[s] < INF]
    if not choices:
        raise ValueError('환승 상한 안에서 도착 가능한 경로가 없습니다.')
    arrival, target, egress_s = min(choices)
    legs = _trace_transit(data, result, target)
    if not any(l[0] == 'ride' for l in legs):
        raise ValueError('최단 경로가 도보만으로 구성됩니다.')
    coord = lambda s: [data.stop_lons[s], data.stop_lats[s]]
    now, walk_s, ride_s, wait_s, walk_km, ride_km, boardings = START, 0, 0, 0, 0.0, 0.0, 0
    segments = []
    route_names = []
    for leg in legs:
        if leg[0] in ('access', 'walk'):
            if leg[0] == 'access':
                _, end, seconds = leg
                points = [[origin[1], origin[0]], coord(end)]
            else:
                _, start, end, seconds = leg
                points = [coord(start), coord(end)]
            segments.append(_segment(now, now+seconds, points, '도보'))
            now += seconds
            walk_s += seconds
            walk_km += haversine_km(points[0][1], points[0][0], points[-1][1], points[-1][0]) * 1.35
        else:
            _, pi, trip, board, alight = leg
            p = data.patterns[pi]
            depart = p.departures[trip][board]
            if depart < now:
                raise ValueError('복원 경로의 환승 연결 시간이 맞지 않습니다.')
            segments.append(_segment(now, depart, [coord(p.stops[board])]*2, '대기'))
            wait_s += depart-now
            ride_s += p.arrivals[trip][alight]-depart
            boardings += 1
            route_names.append(p.name)
            for pos in range(board, alight):
                a, b = p.stops[pos:pos+2]
                segments.append(_segment(p.departures[trip][pos], p.arrivals[trip][pos+1], [coord(a), coord(b)], '탑승'))
                ride_km += haversine_km(data.stop_lats[a], data.stop_lons[a], data.stop_lats[b], data.stop_lons[b])
                if pos+1 < alight:
                    segments.append(_segment(p.arrivals[trip][pos+1], p.departures[trip][pos+1], [coord(b)]*2, '정차'))
            now = p.arrivals[trip][alight]
    segments.append(_segment(now, now+egress_s, [coord(target), [destination[1], destination[0]]], '도보'))
    now += egress_s
    walk_s += egress_s
    walk_km += haversine_km(data.stop_lats[target], data.stop_lons[target], *destination)*1.35
    assert math.isclose(now, arrival, abs_tol=1e-6)
    assert math.isclose(now-START, walk_s+wait_s+ride_s, abs_tol=1e-6)
    assert boardings <= max_transfers+1
    return {'success': True, 'duration_min': (now-START)/60, 'distance_km': walk_km+ride_km,
            'walk_min': walk_s/60, 'wait_min': wait_s/60, 'in_vehicle_min': ride_s/60,
            'walk_km': walk_km, 'in_vehicle_km': ride_km, 'transfers': boardings-1,
            'routes': route_names, 'segments': segments, 'arrival': now}


def compare_person(graph, data, row):
    row = dict(row)
    result = {'person_id': row['person_id']}
    origin = (float(row['origin_lat']), float(row['origin_lon']))
    dest = (float(row['destination_lat']), float(row['destination_lon']))
    for mode, fn in [('taxi', lambda: taxi_route(graph, row['origin_node'], row['destination_node'])),
                     ('transit', lambda: transit_route(data, origin, dest))]:
        try:
            result[mode] = fn()
        except (ValueError, RuntimeError) as e:
            result[mode] = {'success': False, 'reason': str(e)}
    return result


def results_table(results):
    rows = []
    fields = ['duration_min','distance_km','walk_min','wait_min','in_vehicle_min','walk_km','in_vehicle_km','transfers']
    for item in results:
        row = {'person_id': item['person_id']}
        for mode in ['taxi','transit']:
            r = item[mode]
            row[mode+'_success'] = r['success']
            row[mode+'_reason'] = r.get('reason', '')
            for field in fields:
                if mode == 'transit' or field in fields[:2]:
                    row[mode+'_'+field] = r.get(field, float('nan'))
        row['time_difference_min'] = row['transit_duration_min']-row['taxi_duration_min']
        row['distance_difference_km'] = row['transit_distance_km']-row['taxi_distance_km']
        rows.append(row)
    return pd.DataFrame(rows)


def export_playback(graph, od, results, path='outputs/assignment2_playback.html'):
    """Write a self-contained map with no tile-server or JS-library dependency."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    roads = [line_coords(wkt) for wkt in graph.edges.geometry_wkt.drop_duplicates()]
    payload = {'od': od.to_dict('records'), 'results': results, 'roads': roads}
    template = Path(__file__).with_name('viz') / 'assignment2_playback.html'
    html = template.read_text('utf-8').replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('</', '<\\/'))
    path.write_text(html, encoding='utf-8')
    return path
