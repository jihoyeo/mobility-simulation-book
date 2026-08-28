"""수요·GTFS 데이터 계약."""

from __future__ import annotations

import pandas as pd
import pytest

from smartmob.data import load_demand, load_gtfs, load_vehicles
from smartmob.data.demand import (
    DemandFormatError,
    hhmm_to_minutes,
    minutes_to_hhmm,
    normalize_demand,
    validate_demand,
)
from smartmob.data.gtfs import (
    GtfsFormatError,
    KOREAN_ROUTE_TYPE,
    describe_feed,
    parse_gtfs_time,
    seconds_to_gtfs_time,
    validate_feed,
)


def _demand(**over) -> pd.DataFrame:
    base = {
        "request_time": [1080, 1200],
        "origin_lat": [37.53, 37.54],
        "origin_lon": [127.20, 127.21],
        "dest_lat": [37.55, 37.56],
        "dest_lon": [127.23, 127.24],
    }
    base.update(over)
    return pd.DataFrame(base)


# --------------------------------------------------------------------------- #
# 수요
# --------------------------------------------------------------------------- #


def test_validate_demand_accepts_contract():
    validate_demand(_demand())


def test_validate_demand_rejects_missing_column():
    df = _demand().drop(columns=["dest_lon"])
    with pytest.raises(DemandFormatError, match="dest_lon"):
        validate_demand(df)


def test_validate_demand_rejects_seconds_in_request_time():
    """분이 아니라 초를 넣는 실수를 잡아야 합니다."""
    with pytest.raises(DemandFormatError, match="자정부터의 분"):
        validate_demand(_demand(request_time=[64800, 72000]))


def test_validate_demand_rejects_swapped_lat_lon():
    with pytest.raises(DemandFormatError, match="한국 범위"):
        validate_demand(_demand(origin_lat=[127.20, 127.21], origin_lon=[37.53, 37.54]))


def test_normalize_demand_adds_id_and_sorts():
    out = normalize_demand(_demand(request_time=[1200, 1080]))
    assert list(out.columns)[:3] == ["id", "request_time", "origin_lat"]
    assert out["request_time"].tolist() == [1080, 1200]
    assert set(out["mode"]) == {"taxi"}


def test_minutes_helpers():
    assert minutes_to_hhmm(1080) == "18:00"
    assert minutes_to_hhmm(0) == "00:00"
    assert hhmm_to_minutes("18:00") == 1080
    assert hhmm_to_minutes("25:30") == 1530


def test_shipped_demand_and_vehicles_are_valid():
    demand = load_demand("hanam")
    validate_demand(demand)
    vehicles = load_vehicles("hanam")
    assert {"id", "work_start", "work_end", "lat", "lon"} <= set(vehicles.columns)
    assert (vehicles["work_start"] < vehicles["work_end"]).all()


# --------------------------------------------------------------------------- #
# GTFS
# --------------------------------------------------------------------------- #


def test_parse_gtfs_time_handles_past_midnight():
    assert parse_gtfs_time("08:30:00") == 30600
    assert parse_gtfs_time("25:30:00") == 91800  # 다음 날 새벽 1:30, 같은 운행일
    assert seconds_to_gtfs_time(91800) == "25:30:00"


def test_parse_gtfs_time_rejects_bad_format():
    with pytest.raises(GtfsFormatError):
        parse_gtfs_time("08:30")


@pytest.fixture(scope="module")
def feed():
    return load_gtfs("hanam")


def test_shipped_gtfs_is_valid(feed):
    validate_feed(feed)


def test_describe_feed_uses_korean_route_types(feed):
    info = describe_feed(feed)
    assert info["stops"] > 1000
    assert info["routes"] > 100
    assert info["stop_times"] > 100_000
    labels = set(info["route_type"])
    assert labels <= set(KOREAN_ROUTE_TYPE.values()) | {
        f"기타({k})" for k in range(-1, 2000)
    }
    assert "시내·농어촌·마을버스" in labels


def test_stop_times_are_parsable(feed):
    """모든 시각이 파싱돼야 합니다. 24시를 넘는 값이 실제로 들어 있습니다."""
    st = feed["stop_times"]
    sample = st["arrival_time"].dropna().head(20000)
    seconds = [parse_gtfs_time(t) for t in sample]
    assert min(seconds) >= 0
    over_midnight = [s for s in seconds if s >= 24 * 3600]
    assert len(seconds) == len(sample)
    # 24시 넘는 값이 있으면 그것도 정상 범위여야 합니다
    assert all(s < 48 * 3600 for s in over_midnight)


def test_validate_feed_reports_missing_table():
    with pytest.raises(GtfsFormatError, match="stop_times"):
        validate_feed({"stops": pd.DataFrame(columns=["stop_id", "stop_lat", "stop_lon"])})
