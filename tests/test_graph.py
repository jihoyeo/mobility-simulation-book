"""도로망 그래프 — 2장 검증 기준."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from smartmob.data.paths import data_path
from smartmob.teaching.graph import (
    DRIVE_HIGHWAYS,
    RoadGraph,
    haversine_km,
    parse_edge_id,
)


@pytest.fixture(scope="module")
def edges() -> pd.DataFrame:
    return pd.read_parquet(data_path("hanam/road_graph_edges.parquet"))


@pytest.fixture(scope="module")
def nodes() -> pd.DataFrame:
    return pd.read_parquet(data_path("hanam/road_graph_nodes.parquet"))


@pytest.fixture(scope="module")
def graph(nodes, edges) -> RoadGraph:
    return RoadGraph.from_frames(nodes, edges, modes=("drive",))


def test_parse_edge_id():
    assert parse_edge_id("e37375263_f_445273230_436257996") == ("n445273230", "n436257996")
    assert parse_edge_id("e37394521_r_9045447448_436679681") == ("n9045447448", "n436679681")
    with pytest.raises(ValueError):
        parse_edge_id("nonsense")


def test_edge_id_matches_osm_node_seq(edges):
    """edge_id 에서 뽑은 양 끝 노드가 osm_node_seq_json 의 첫/끝과 100% 일치해야 합니다."""
    sample = edges.head(3000)
    mismatched = 0
    for edge_id, seq_json in zip(sample["edge_id"], sample["osm_node_seq_json"]):
        seq = json.loads(seq_json) if isinstance(seq_json, str) else list(seq_json)
        u, v = parse_edge_id(edge_id)
        if u != f"n{seq[0]}" or v != f"n{seq[-1]}":
            mismatched += 1
    assert mismatched == 0


def test_drive_filter_removes_footways(nodes, edges):
    """필터 없이 만들면 보도가 절반 가까이 섞입니다."""
    all_modes = RoadGraph.from_frames(nodes, edges, modes=("drive", "walk", "bike"))
    drive_only = RoadGraph.from_frames(nodes, edges, modes=("drive",))
    assert drive_only.n_edges < all_modes.n_edges
    assert set(drive_only.edges["highway"].unique()) <= DRIVE_HIGHWAYS
    assert "footway" not in set(drive_only.edges["highway"].unique())


def test_graph_size_matches_meta(graph, nodes):
    """meta 의 전체 규모 안에 들어와야 합니다(필터를 걸었으므로 더 작습니다)."""
    meta = json.loads(data_path("hanam/road_graph.meta.json").read_text(encoding="utf-8"))
    assert graph.n_nodes <= meta["node_count"]
    assert graph.n_edges <= meta["edge_count"]
    assert graph.n_nodes > 1000
    assert graph.n_edges > 5000


def test_edge_weight_is_travel_time(graph):
    """가중치는 소요시간(초)이어야 합니다. 30km/h 로 300m 면 36초."""
    for _u, out in graph.adj.items():
        for _v, seconds, idx in out:
            row = graph.edges.iloc[idx]
            speed = float(row["free_flow_speed_kmh"])
            expected = float(row["length"]) / (speed * 1000 / 3600)
            assert seconds == pytest.approx(expected, rel=1e-9)
            return
    pytest.fail("엣지가 하나도 없습니다.")


def test_nearest_node(graph):
    """하남시청 부근 좌표를 스냅하면 500m 안의 노드가 나와야 합니다."""
    lat, lon = 37.5393, 127.2148  # 하남시청
    node = graph.nearest_node(lat, lon)
    nlat, nlon = graph.coord[node]
    assert haversine_km(lat, lon, nlat, nlon) < 0.5


def test_haversine_known_distance():
    """서울시청 -> 하남시청 직선거리는 약 19km 입니다."""
    d = haversine_km(37.5665, 126.9780, 37.5393, 127.2148)
    assert 18.0 < d < 22.0


def test_unknown_mode_raises(nodes, edges):
    with pytest.raises(ValueError, match="모르는 통행수단"):
        RoadGraph.from_frames(nodes, edges, modes=("hovercraft",))
