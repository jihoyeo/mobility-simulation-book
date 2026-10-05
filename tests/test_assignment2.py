"""Assignment-specific edge distance and schedule reconstruction checks."""
import math

import pandas as pd

from smartmob.assignment2 import taxi_route, transit_route, START, _segment
from smartmob.teaching.graph import RoadGraph
from smartmob.teaching.raptor import TransitData


def test_taxi_parallel_edges_use_fastest_edge_length_and_geometry():
    edges = pd.DataFrame([
        {'edge_id':'e1_f_1_2','length':1000,'geometry_wkt':'LINESTRING (127 37, 127.001 37.001, 127.002 37)'},
        {'edge_id':'e2_f_1_2','length':2000,'geometry_wkt':'LINESTRING (127 37, 127.003 37.001, 127.002 37)'},
    ])
    graph = RoadGraph({'n1':[('n2',120,0),('n2',240,1)],'n2':[]},
                      {'n1':(37,127),'n2':(37,127.002)},edges,'constant')
    result = taxi_route(graph,'n1','n2')
    assert result['distance_km'] == 1
    assert result['duration_min'] == 2
    assert len(result['segments'][0]['coords']) == 3


def test_destination_walk_is_included_and_stop_dwell_is_preserved():
    # A-B-C, with a one-minute dwell at B and a walk from C to destination.
    feed = {
        'stops':pd.DataFrame({'stop_id':['A','B','C'],'stop_name':['A','B','C'],
                             'stop_lat':[37,37,37], 'stop_lon':[127,127.015,127.03]}),
        'trips':pd.DataFrame({'trip_id':['T'],'route_id':['R']}),
        'routes':pd.DataFrame({'route_id':['R'],'route_short_name':['1'],'route_type':[0]}),
        'stop_times':pd.DataFrame({'trip_id':['T']*3,'stop_id':['A','B','C'],'stop_sequence':[1,2,3],
             'arrival_time':['09:02:00','09:06:00','09:11:00'],
             'departure_time':['09:02:00','09:07:00','09:11:00']}),
    }
    data = TransitData.from_gtfs(feed, max_transfer_m=500)
    r = transit_route(data,(37,127),(37,127.031))
    assert r['wait_min'] == 2
    assert r['in_vehicle_min'] == 9
    assert r['arrival'] > START+11*60
    assert any(s['state']=='정차' and s['end']-s['start']==60 for s in r['segments'])
    assert r['segments'][-1]['coords'][-1] == [127.031,37]
    assert math.isclose(r['duration_min'],r['walk_min']+r['wait_min']+r['in_vehicle_min'])
    for a,b in zip(r['segments'],r['segments'][1:]):
        assert a['end'] == b['start']


def test_negative_segment_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        _segment(10,9,[[127,37],[127,37]],'대기')
