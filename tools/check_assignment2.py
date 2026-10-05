"""Validate packaged inputs and instructor playback, then capture the browser."""
import json
import math
import hashlib
from zipfile import ZipFile
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape

from smartmob.assignment2 import DATA, export_playback, load_boundary, START
from smartmob.teaching.graph import RoadGraph
from tools.prepare_assignment2 import sha256


def main():
    out = Path('outputs/assignment2_instructor')
    with ZipFile(DATA/'songpa_network.zip') as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for name, info in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == info['sha256'], name
    od = pd.read_csv(DATA/'od.csv')
    polygon = shape(load_boundary()['features'][0]['geometry'])
    assert len(od) == od.person_id.nunique() == 30
    for label in ['origin','destination']:
        assert od[label+'_snap_m'].max() <= 100
        assert all(polygon.contains(Point(lon,lat)) for lon,lat in zip(od[label+'_lon'],od[label+'_lat']))
    results = json.loads((out/'routes.json').read_text('utf-8'))
    assert [r['person_id'] for r in results] == od.person_id.tolist()
    for r in results:
        row = od.set_index('person_id').loc[r['person_id']]
        for mode in ['taxi','transit']:
            route = r[mode]
            assert route['success']
            ss = route['segments']
            assert ss[0]['start'] == START
            assert math.isclose(ss[-1]['end'],route['arrival'])
            for a,b in zip(ss,ss[1:]):
                assert math.isclose(a['end'],b['start'],abs_tol=1e-6)
                assert math.dist(a['coords'][-1],b['coords'][0]) < 1e-5
            assert math.dist(ss[0]['coords'][0],[row.origin_lon,row.origin_lat]) < 1e-5
            assert math.dist(ss[-1]['coords'][-1],[row.destination_lon,row.destination_lat]) < 1e-5
            assert all(s['end'] >= s['start'] for s in ss)
            assert all(s['coords'][0] == s['coords'][-1] for s in ss if s['state'] in ['대기','정차'])
        p = r['transit']
        assert p['transfers'] <= 2
        assert math.isclose(p['duration_min'],p['walk_min']+p['wait_min']+p['in_vehicle_min'])
    with ZipFile(DATA/'songpa_network.zip') as archive:
        graph = RoadGraph.from_frames(pd.read_parquet(archive.open('road_graph_nodes.parquet')),
                                     pd.read_parquet(archive.open('road_graph_edges.parquet')), speed_kmh=30)
    html = export_playback(graph,od,results,out/'playback.html')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge',headless=True)
        page = browser.new_page(viewport={'width':1600,'height':1200},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(html.resolve().as_uri())
        page.get_by_role('button',name='09:10',exact=True).click()
        assert page.locator('#clock').inner_text() == '09:10:00'
        assert page.evaluate("D.results.filter(r=>r.taxi.success&&r.taxi.arrival<=time).length") == 19
        page.get_by_role('button',name='09:20',exact=True).click()
        assert page.evaluate("D.results.filter(r=>r.transit.success&&r.transit.arrival<=time).length") == 8
        page.locator('#person').select_option('P01')
        assert 'P01' in page.locator('#status').inner_text()
        page.screenshot(path=str(out/'playback_0920.png'),full_page=True)
        with page.expect_download() as dl:
            page.get_by_role('button',name='화면 PNG 저장',exact=True).click()
        dl.value.save_as(str(out/'export_0920.png'))
        page.get_by_role('button',name='재생',exact=True).click()
        page.wait_for_timeout(300)
        assert page.evaluate('time') > 33600
        page.get_by_role('button',name='일시정지',exact=True).click()
        assert not errors, errors
        browser.close()
    print('Verified 30 O-Ds / 60 routes, checksums, segment continuity, browser controls, counts and PNG export.')


if __name__ == '__main__':
    main()
