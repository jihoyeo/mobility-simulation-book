"""GTFS 읽기.

GTFS 는 대중교통 시간표의 사실상 표준입니다. 파일 여덟 개짜리 zip 또는 폴더인데,
이 책에서 쓰는 것은 다섯 개입니다.

    stops.txt       정류장 — stop_id, stop_name, stop_lat, stop_lon
    routes.txt      노선   — route_id, route_short_name, route_type
    trips.txt       운행   — trip_id, route_id, service_id
    stop_times.txt  시각표 — trip_id, stop_id, stop_sequence, arrival_time, departure_time
    calendar.txt    운행일 — service_id, monday..sunday

주의할 점 두 가지입니다.

1. **시각이 24시를 넘습니다.** ``"25:30:00"`` 은 다음 날 새벽 1시 30분이고,
   같은 운행일에 속합니다. ``datetime`` 으로 파싱하면 터집니다.
   :func:`parse_gtfs_time` 을 씁니다.
2. **한국 GTFS 의 `route_type` 은 국제 표준과 다릅니다.** TAGO 코드입니다.
   :data:`KOREAN_ROUTE_TYPE` 을 보세요.
"""

from __future__ import annotations

from pathlib import Path

GTFS_TABLES = ("stops", "routes", "trips", "stop_times", "calendar")

REQUIRED_COLUMNS = {
    "stops": {"stop_id", "stop_lat", "stop_lon"},
    "routes": {"route_id", "route_type"},
    "trips": {"route_id", "service_id", "trip_id"},
    "stop_times": {"trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"},
}

# 국토교통부 TAGO 코드. 국제 GTFS 명세(0=트램, 1=지하철, 2=철도, 3=버스)와 다릅니다.
KOREAN_ROUTE_TYPE = {
    0: "시내·농어촌·마을버스",
    1: "도시철도",
    2: "해운",
    3: "시외버스",
    4: "일반철도",
    5: "공항리무진",
    6: "고속철도",
    7: "항공",
    8: "GTX",
}


class GtfsFormatError(ValueError):
    pass


def parse_gtfs_time(text: str) -> int:
    """``"HH:MM:SS"`` 를 자정부터의 초로. 24시를 넘는 값도 그대로 받습니다.

    >>> parse_gtfs_time("08:30:00")
    30600
    >>> parse_gtfs_time("25:30:00")
    91800
    """
    parts = str(text).strip().split(":")
    if len(parts) != 3:
        raise GtfsFormatError(f"'HH:MM:SS' 형식이어야 합니다: {text!r}")
    h, m, s = (int(p) for p in parts)
    return h * 3600 + m * 60 + s


def seconds_to_gtfs_time(seconds: int) -> str:
    """91800 -> '25:30:00'."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_gtfs(city: str = "hanam", tables=GTFS_TABLES) -> dict:
    """`data/<city>/gtfs/` 의 표들을 DataFrame dict 로 읽습니다.

    parquet 이 있으면 그것을, 없으면 txt 를 읽습니다.
    """
    import pandas as pd

    from smartmob.data.paths import data_path

    base = data_path(f"{city}/gtfs")
    feed: dict[str, "pd.DataFrame"] = {}
    for name in tables:
        pq, txt = base / f"{name}.parquet", base / f"{name}.txt"
        if pq.exists():
            feed[name] = pd.read_parquet(pq)
        elif txt.exists():
            feed[name] = pd.read_csv(txt, dtype=str, encoding="utf-8-sig")
        else:
            continue
    if not feed:
        raise GtfsFormatError(f"{base} 에 GTFS 표가 하나도 없습니다.")
    return feed


def validate_feed(feed: dict) -> None:
    """필수 표와 컬럼이 있는지 검사합니다."""
    problems: list[str] = []
    for name, needed in REQUIRED_COLUMNS.items():
        if name not in feed:
            problems.append(f"{name}.txt 가 없습니다")
            continue
        missing = needed - set(feed[name].columns)
        if missing:
            problems.append(f"{name}.txt 에 컬럼이 없습니다: {sorted(missing)}")
    if problems:
        raise GtfsFormatError("GTFS 형식 오류:\n  - " + "\n  - ".join(problems))


def describe_feed(feed: dict) -> dict:
    """정류장·노선·운행 수와 수단별 노선 분포."""
    out: dict[str, object] = {
        "stops": len(feed.get("stops", [])),
        "routes": len(feed.get("routes", [])),
        "trips": len(feed.get("trips", [])),
        "stop_times": len(feed.get("stop_times", [])),
    }
    routes = feed.get("routes")
    if routes is not None and "route_type" in routes:
        counts = routes["route_type"].astype(int).value_counts().sort_index()
        out["route_type"] = {
            KOREAN_ROUTE_TYPE.get(int(k), f"기타({k})"): int(v) for k, v in counts.items()
        }
    return out


def clip_to_boundary(feed: dict, boundary, buffer_m: float = 500.0) -> dict:
    """경계 안의 정류장을 지나는 **노선 전체**를 남깁니다.

    정류장만 잘라 내면 노선이 시 경계에서 끊겨 환승 계산이 어긋납니다.
    그래서 정류장 → 운행 → 노선 → 그 노선의 모든 운행 순으로 되짚어 올립니다.
    """
    import geopandas as gpd

    validate_feed(feed)
    stops = feed["stops"].copy()
    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)

    gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs="EPSG:4326",
    )
    area = gpd.GeoSeries([boundary], crs="EPSG:4326").to_crs(5179).buffer(buffer_m).to_crs(4326)
    inside = gdf[gdf.within(area.iloc[0])]

    seed_stops = set(inside["stop_id"])
    st = feed["stop_times"]
    seed_trips = set(st[st["stop_id"].isin(seed_stops)]["trip_id"])
    trips = feed["trips"]
    keep_routes = set(trips[trips["trip_id"].isin(seed_trips)]["route_id"])
    keep_trips = trips[trips["route_id"].isin(keep_routes)]
    keep_st = st[st["trip_id"].isin(set(keep_trips["trip_id"]))]

    out = dict(feed)
    out["routes"] = feed["routes"][feed["routes"]["route_id"].isin(keep_routes)]
    out["trips"] = keep_trips
    out["stop_times"] = keep_st
    out["stops"] = feed["stops"][feed["stops"]["stop_id"].isin(set(keep_st["stop_id"]))]
    return out
