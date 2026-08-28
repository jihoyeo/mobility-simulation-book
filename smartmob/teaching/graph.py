"""도로망 그래프.

2장에서 유도한 코드의 정돈본입니다. 3장 이후에서는 여기서 가져다 씁니다.

    from smartmob.teaching.graph import RoadGraph
    G = RoadGraph.from_parquet("hanam")

핵심은 두 가지입니다.

1. **엣지 parquet 에는 `source`/`target` 컬럼이 없습니다.** 양 끝 노드는
   `edge_id` 에 들어 있습니다. `e{way_id}_{f|r}_{출발 osm id}_{도착 osm id}` 형식이고,
   노드 표의 `node_id` 는 `"n" + osm id` 입니다.

2. **엣지의 45%가 보도·자전거도로입니다.** 하남 기준 59,873개 중 `footway` 22,064개,
   `cycleway` 5,100개입니다. 걸러 내지 않고 최단경로를 구하면 자동차가 인도로 다닙니다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

# 자동차가 다닐 수 있는 highway 태그
DRIVE_HIGHWAYS = frozenset(
    {
        "motorway", "motorway_link",
        "trunk", "trunk_link",
        "primary", "primary_link",
        "secondary", "secondary_link",
        "tertiary", "tertiary_link",
        "residential", "living_street", "unclassified", "service", "road",
    }
)

# 걸어서 다닐 수 있는 highway 태그
WALK_HIGHWAYS = frozenset(
    {
        "footway", "path", "pedestrian", "steps", "living_street",
        "residential", "unclassified", "service", "track", "road",
    }
)

BIKE_HIGHWAYS = frozenset({"cycleway"}) | WALK_HIGHWAYS

MODE_FILTERS = {"drive": DRIVE_HIGHWAYS, "walk": WALK_HIGHWAYS, "bike": BIKE_HIGHWAYS}

EARTH_RADIUS_KM = 6371.0088


def parse_edge_id(edge_id: str) -> tuple[str, str]:
    """`edge_id` 에서 양 끝 노드 id 를 꺼냅니다.

    >>> parse_edge_id("e37375263_f_445273230_436257996")
    ('n445273230', 'n436257996')
    """
    parts = edge_id.rsplit("_", 2)
    if len(parts) != 3:
        raise ValueError(f"엣지 id 형식이 다릅니다: {edge_id!r}")
    _, source_osm, target_osm = parts
    return f"n{source_osm}", f"n{target_osm}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이의 대권 거리(km)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class RoadGraph:
    """인접 리스트로 표현한 도로망.

    ``adj[u]`` 는 ``(v, 소요시간_초, edge_idx)`` 목록입니다.
    좌표는 ``coord[node_id] = (lat, lon)`` 로 들고 있습니다.
    """

    adj: dict[str, list[tuple[str, float, int]]]
    coord: dict[str, tuple[float, float]]
    edges: object  # pandas.DataFrame
    speed_column: str

    # -- 만들기 -------------------------------------------------------------- #

    @classmethod
    def from_parquet(
        cls,
        city: str = "hanam",
        modes: Sequence[str] = ("drive",),
        speed_column: str = "free_flow_speed_kmh",
        root: str | Path | None = None,
    ) -> "RoadGraph":
        """`data/<city>/road_graph_{nodes,edges}.parquet` 에서 그래프를 만듭니다."""
        import pandas as pd

        base = Path(root) if root else None
        if base is None:
            from smartmob.data.paths import data_path

            nodes_path = data_path(f"{city}/road_graph_nodes.parquet")
            edges_path = data_path(f"{city}/road_graph_edges.parquet")
        else:
            nodes_path = base / "road_graph_nodes.parquet"
            edges_path = base / "road_graph_edges.parquet"

        nodes = pd.read_parquet(nodes_path, columns=["node_id", "lat", "lon"])
        edges = pd.read_parquet(edges_path)
        return cls.from_frames(nodes, edges, modes=modes, speed_column=speed_column)

    @classmethod
    def from_frames(
        cls,
        nodes,
        edges,
        modes: Sequence[str] = ("drive",),
        speed_column: str = "free_flow_speed_kmh",
    ) -> "RoadGraph":
        allowed: set[str] = set()
        for mode in modes:
            if mode not in MODE_FILTERS:
                raise ValueError(f"모르는 통행수단 '{mode}'. {sorted(MODE_FILTERS)} 중에서 고르세요.")
            allowed |= MODE_FILTERS[mode]

        edges = edges[edges["highway"].isin(allowed)].reset_index(drop=True)
        if speed_column not in edges.columns:
            raise KeyError(
                f"속도 컬럼 '{speed_column}' 이 없습니다. "
                f"쓸 수 있는 것: {[c for c in edges.columns if 'speed' in c]}"
            )

        coord = {
            row.node_id: (float(row.lat), float(row.lon))
            for row in nodes.itertuples(index=False)
        }

        adj: dict[str, list[tuple[str, float, int]]] = {}
        speeds = edges[speed_column].fillna(edges["free_flow_speed_kmh"]).fillna(30.0)
        lengths = edges["length"].astype(float)
        for idx, (edge_id, length_m, speed_kmh) in enumerate(
            zip(edges["edge_id"], lengths, speeds)
        ):
            try:
                u, v = parse_edge_id(edge_id)
            except ValueError:
                continue
            if u not in coord or v not in coord:
                continue  # 경계에서 잘린 엣지
            seconds = length_m / (max(float(speed_kmh), 1.0) * 1000 / 3600)
            adj.setdefault(u, []).append((v, seconds, idx))
            adj.setdefault(v, [])

        return cls(adj=adj, coord=coord, edges=edges, speed_column=speed_column)

    # -- 조회 ---------------------------------------------------------------- #

    @property
    def nodes(self) -> Iterable[str]:
        return self.adj.keys()

    @property
    def n_nodes(self) -> int:
        return len(self.adj)

    @property
    def n_edges(self) -> int:
        return sum(len(v) for v in self.adj.values())

    def neighbors(self, node: str) -> list[tuple[str, float, int]]:
        return self.adj.get(node, [])

    def nearest_node(self, lat: float, lon: float) -> str:
        """좌표에서 가장 가까운 노드. 그래프에 실제로 연결된 노드만 봅니다.

        노드가 2만 개가 넘으므로 전부 훑으면 한 건당 수십 ms 가 듭니다.
        KD-트리를 한 번 만들어 두면 그 뒤로는 마이크로초 단위입니다.
        """
        if not self.adj:
            raise ValueError("그래프가 비어 있습니다.")
        tree, ids = self._kdtree()
        if tree is None:  # scipy 가 없으면 그냥 다 훑습니다
            best, best_d = None, float("inf")
            for node in self.adj:
                nlat, nlon = self.coord[node]
                d = (nlat - lat) ** 2 + (nlon - lon) ** 2  # 비교만 하므로 제곱거리로 충분
                if d < best_d:
                    best, best_d = node, d
            return best  # type: ignore[return-value]
        _, idx = tree.query([lat, lon])
        return ids[int(idx)]

    def _kdtree(self):
        cached = getattr(self, "_kdtree_cache", None)
        if cached is not None:
            return cached
        try:
            from scipy.spatial import cKDTree
        except ModuleNotFoundError:
            cached = (None, [])
        else:
            ids = list(self.adj)
            points = [self.coord[n] for n in ids]
            cached = (cKDTree(points), ids)
        object.__setattr__(self, "_kdtree_cache", cached)
        return cached

    def max_speed_kmh(self) -> float:
        """A* 휴리스틱에 쓰는 상한 속도."""
        return float(self.edges[self.speed_column].max())

    def with_speed_column(self, speed_column: str) -> "RoadGraph":
        """같은 도로망을 다른 속도 컬럼으로 다시 만듭니다(시간대별 비교용)."""
        import pandas as pd

        nodes = pd.DataFrame(
            [{"node_id": k, "lat": v[0], "lon": v[1]} for k, v in self.coord.items()]
        )
        return RoadGraph.from_frames(
            nodes, self.edges, modes=("drive", "walk", "bike"), speed_column=speed_column
        )

    def __repr__(self) -> str:  # pragma: no cover - 표시용
        return f"<RoadGraph 노드 {self.n_nodes:,}개, 엣지 {self.n_edges:,}개, 속도={self.speed_column}>"
