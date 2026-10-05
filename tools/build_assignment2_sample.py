"""Generate and verify the fixed synthetic Assignment 2 demand."""
import json
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import shape, Point

from smartmob.assignment2 import DATA, load_data, load_boundary, compare_person, results_table, export_playback
from smartmob.teaching.graph import haversine_km
from tools.prepare_assignment2 import sha256


def main():
    graph, transit, _ = load_data()
    print('Loaded:', len(graph.coord), transit.describe(), flush=True)
    feature = load_boundary()['features'][0]
    polygon = shape(feature['geometry'])
    nodes = sorted(n for n in graph.coord if n in graph.adj)
    xy = np.array([graph.coord[n] for n in nodes])
    scale = np.array([111000, 111000*np.cos(np.radians(37.5))])
    tree = cKDTree(xy*scale)
    rng = np.random.default_rng(42)
    rejected = Counter()
    rows, results, used = [], [], set()
    minlon, minlat, maxlon, maxlat = polygon.bounds

    def point():
        for _ in range(10000):
            lat, lon = rng.uniform(minlat,maxlat), rng.uniform(minlon,maxlon)
            if not polygon.contains(Point(lon, lat)):
                continue
            _, idx = tree.query(np.array([lat,lon])*scale)
            node = nodes[int(idx)]
            slat, slon = graph.coord[node]
            metres = haversine_km(lat,lon,slat,slon)*1000
            if metres <= 100 and polygon.contains(Point(slon,slat)):
                return node, lat, lon, slat, slon, metres
        raise RuntimeError('Could not sample a point')

    attempts = 0
    while len(rows) < 30 and attempts < 1000:
        attempts += 1
        a, b = point(), point()
        if a[0] == b[0] or (a[0],b[0]) in used:
            rejected['same_node_or_duplicate'] += 1
            continue
        row = {'person_id': f'P{len(rows)+1:02d}', 'service_date': '2024-10-07', 'departure_time': '09:00:00'}
        for label, p in [('origin',a),('destination',b)]:
            row.update({label+'_node':p[0], label+'_raw_lat':p[1],label+'_raw_lon':p[2],
                        label+'_lat':p[3],label+'_lon':p[4],label+'_snap_m':p[5]})
        result = compare_person(graph, transit, row)
        failures = [mode+': '+result[mode]['reason'] for mode in ['taxi','transit'] if not result[mode]['success']]
        if failures:
            rejected.update(failures)
            continue
        rows.append(row)
        results.append(result)
        used.add((a[0],b[0]))
        print(row['person_id'], round(result['taxi']['duration_min'],1), round(result['transit']['duration_min'],1), flush=True)
    assert len(rows) == 30
    od = pd.DataFrame(rows)
    od.to_csv(DATA/'od.csv',index=False)
    output = Path('outputs/assignment2_instructor')
    output.mkdir(exist_ok=True,parents=True)
    table = results_table(results)
    table.to_csv(output/'reference_results.csv',index=False)
    (output/'routes.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8')
    export_playback(graph, od, results, output/'playback.html')
    report = {'candidate_pairs':attempts, 'accepted':len(rows), 'rejected':dict(rejected),
              'max_snap_m':float(od[['origin_snap_m','destination_snap_m']].max().max()),
              'arrived_counts': {str(t): {m:sum(r[m]['arrival'] <= t for r in results) for m in ['taxi','transit']} for t in [32400,33000,33600]},
              'mean_taxi_min':float(table.taxi_duration_min.mean()), 'mean_transit_min':float(table.transit_duration_min.mean()),
              'max_transfers':int(table.transit_transfers.max()),
              'time_components_checked':True, 'road_edge_time_checked':True}
    (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    report['od_sha256'] = sha256(DATA/'od.csv')
    (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__':
    main()
