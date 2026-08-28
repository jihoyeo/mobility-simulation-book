"""데이터 읽기와 내려받기."""

from smartmob.data.boundary import list_sigungu, load_sigungu, sigungu_info
from smartmob.data.demand import (
    REQUIRED_COLUMNS as DEMAND_COLUMNS,
    hhmm_to_minutes,
    load_demand,
    load_vehicles,
    minutes_to_hhmm,
    normalize_demand,
    validate_demand,
)
from smartmob.data.gtfs import (
    KOREAN_ROUTE_TYPE,
    clip_to_boundary,
    describe_feed,
    load_gtfs,
    load_gtfs_feed,
    parse_gtfs_time,
    save_gtfs,
    seconds_to_gtfs_time,
    validate_feed,
)
from smartmob.data.paths import DataNotFound, data_path, ensure

__all__ = [
    "DEMAND_COLUMNS",
    "DataNotFound",
    "KOREAN_ROUTE_TYPE",
    "clip_to_boundary",
    "data_path",
    "describe_feed",
    "ensure",
    "hhmm_to_minutes",
    "list_sigungu",
    "load_demand",
    "load_gtfs",
    "load_gtfs_feed",
    "load_road_graph",
    "load_sigungu",
    "load_vehicles",
    "minutes_to_hhmm",
    "normalize_demand",
    "parse_gtfs_time",
    "save_gtfs",
    "seconds_to_gtfs_time",
    "sigungu_info",
    "validate_demand",
    "validate_feed",
]


def load_road_graph(city: str = "hanam", modes=("drive",), speed_column="free_flow_speed_kmh"):
    """도로망을 :class:`~smartmob.teaching.graph.RoadGraph` 로 읽습니다."""
    from smartmob.teaching.graph import RoadGraph

    return RoadGraph.from_parquet(city, modes=modes, speed_column=speed_column)
