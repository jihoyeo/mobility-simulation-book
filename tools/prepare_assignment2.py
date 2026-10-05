"""Extract Assignment 2 inputs from the instructor's local DTUMOS data archive.

Run from the repository root. Never modifies the source archive.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from smartmob.teaching.graph import DRIVE_HIGHWAYS, parse_edge_id


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main(source):
    out = Path('outputs/assignment2_source')
    out.mkdir(exist_ok=True, parents=True)
    features = json.loads((out / 'seoul_districts_2013.geojson').read_text('utf-8'))['features']
    feature = next(f for f in features if f['properties']['name'] == '송파구')
    (out / 'songpa.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': [feature]}, ensure_ascii=False), encoding='utf-8')
    polygon = shape(feature['geometry'])
    # A 4 km surrounding area permits cross-boundary paths; complete road edges are kept.
    area = gpd.GeoSeries([polygon], crs=4326).to_crs(5179).buffer(4000).to_crs(4326).iloc[0]
    road_source = source / 'cities/seoul/road_graph.gpkg'
    edges = gpd.read_file(road_source, bbox=area.bounds)
    edges = edges[edges.highway.isin(DRIVE_HIGHWAYS) & edges.geometry.intersects(area)].copy()
    nodes = {}
    for r in edges.itertuples():
        u, v = parse_edge_id(r.edge_id)
        a, b = list(r.geometry.coords)[0], list(r.geometry.coords)[-1]
        nodes[u] = (a[1], a[0])
        nodes[v] = (b[1], b[0])
    pd.DataFrame([{'node_id': k, 'lat': v[0], 'lon': v[1]} for k,v in sorted(nodes.items())]).to_parquet(out / 'road_graph_nodes.parquet', index=False)
    frame = pd.DataFrame(edges[['edge_id','highway','length','free_flow_speed_kmh','name']])
    frame['geometry_wkt'] = edges.geometry.to_wkt().values
    frame.to_parquet(out / 'road_graph_edges.parquet', index=False)
    print('Road:', len(nodes), 'nodes,', len(frame), 'edges', flush=True)

    archive = source / 'gtfs_cache/GTFS_Korea_2024.zip'
    gtfs = out / 'gtfs'
    gtfs.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        prefix = 'GTFS_Korea_2024/'
        read = lambda name: pd.read_csv(z.open(prefix + name + '.txt'), dtype=str)
        stops, trips, routes, calendar = (read(n) for n in ('stops','trips','routes','calendar'))
        for f in (stops, trips, routes, calendar):
            for c in f.columns:
                if f[c].dtype == object:
                    f[c] = f[c].str.strip()
        day = pd.Timestamp('2024-10-07')
        active = set(calendar.loc[(calendar.start_date <= '20241007') & (calendar.end_date >= '20241007') & (calendar.monday == '1'), 'service_id'])
        exceptions_present = prefix + 'calendar_dates.txt' in z.namelist()
        if exceptions_present:
            exceptions = read('calendar_dates')
            for r in exceptions[exceptions.date == '20241007'].itertuples():
                (active.add if r.exception_type == '1' else active.discard)(r.service_id)
        trips = trips[trips.service_id.isin(active)].copy()
        stops['stop_lat'] = stops.stop_lat.astype(float)
        stops['stop_lon'] = stops.stop_lon.astype(float)
        near = gpd.GeoSeries(gpd.points_from_xy(stops.stop_lon, stops.stop_lat), crs=4326).within(area)
        local_ids = set(stops.loc[near, 'stop_id'])
        route_by_trip = dict(zip(trips.trip_id, trips.route_id))
        route_ids = set()
        with z.open(prefix + 'stop_times.txt') as f:
            for chunk in pd.read_csv(f, dtype=str, chunksize=500000, usecols=['trip_id','stop_id']):
                hit = chunk.loc[chunk.stop_id.str.strip().isin(local_ids), 'trip_id'].str.strip()
                route_ids.update(route_by_trip[t] for t in hit.unique() if t in route_by_trip)
        trips = trips[trips.route_id.isin(route_ids)].copy()
        selected = set(trips.trip_id)
        print('GTFS routes:', len(route_ids), 'trips:', len(selected), flush=True)
        chunks = []
        with z.open(prefix + 'stop_times.txt') as f:
            for chunk in pd.read_csv(f, dtype=str, chunksize=500000):
                chunk['trip_id'] = chunk.trip_id.str.strip()
                keep = chunk[chunk.trip_id.isin(selected)].copy()
                for c in keep.columns:
                    keep[c] = keep[c].str.strip()
                chunks.append(keep)
        times = pd.concat(chunks, ignore_index=True)
        stops = stops[stops.stop_id.isin(times.stop_id)].copy()
        routes = routes[routes.route_id.isin(route_ids)].copy()
        for name, f in [('stops', stops), ('trips', trips), ('routes', routes), ('stop_times', times), ('calendar', calendar[calendar.service_id.isin(active)])]:
            f.to_parquet(gtfs / (name + '.parquet'), index=False)
        print('GTFS:', len(stops), 'stops,', len(times), 'stop times', flush=True)
    manifest = {
        'service_date': str(day.date()), 'departure_time': '09:00:00', 'seed': 42,
        'source_road': 'DTUMOS data/cities/seoul/road_graph.gpkg',
        'source_road_sha256': sha256(road_source),
        'road_collection_date': 'unknown: not recorded in supplied cache',
        'source_gtfs': 'GTFS_Korea_2024.zip', 'source_gtfs_sha256': sha256(archive),
        'gtfs_url': 'https://huggingface.co/datasets/CAMUS-LAB/GTFS-2024',
        'calendar_dates_present': exceptions_present,
        'boundary_url': 'https://github.com/southkorea/seoul-maps/blob/master/kostat/2013/json/seoul_municipalities_geo.json',
        'boundary_year': 2013, 'road_buffer_m': 4000,
        'road_scope': 'Available Seoul road cache intersecting Songpa + 4 km buffer; not all Gyeonggi roads are available.',
        'gtfs_scope': 'All active trips and complete stop sequences on routes touching the buffer.',
        'route_types': {str(k): int(v) for k,v in routes.route_type.value_counts().items()},
        'crs': 'EPSG:4326', 'taxi_speed_kmh': 30, 'walk_speed_mps': 1.2,
        'walk_detour_factor': 1.35, 'access_egress_max_m': 800, 'transfer_max_m': 500, 'max_transfers': 2,
    }
    manifest['files'] = {str(p.relative_to(out)): {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    main(parser.parse_args().source)
