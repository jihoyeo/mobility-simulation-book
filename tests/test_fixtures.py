"""녹화본(fixture) 회귀 검사.

책의 본문에 적힌 숫자가 조용히 바뀌지 않도록, 대표 녹화본의 지표를 고정합니다.
값이 바뀌면 본문도 같이 고쳐야 한다는 뜻입니다.
"""

from __future__ import annotations

import pytest

from smartmob import Dtumos
from smartmob.fixtures import load_index

HANAM_PAYLOAD = {
    "city": "hanam",
    "mode": "taxi",
    "fleet_size": 80,
    "num_passengers": 1000,
    "time_start": 1080,
    "time_end": 1440,
    "dispatch_mode": "optimization",
    "matrix_mode": "street_distance",
    "vehicle_capacity": 1,
    "random_seed": 42,
}


@pytest.fixture(scope="module")
def sim(monkeypatch_module=None):
    import os

    os.environ["SMARTMOB_OFFLINE"] = "1"
    return Dtumos().run_simulation(**HANAM_PAYLOAD)


def test_index_and_directories_agree():
    from smartmob.config import fixtures_dir

    index = load_index()
    assert index, "녹화본이 하나도 등록되지 않았습니다."
    for key, entry in index.items():
        assert (fixtures_dir() / entry["dir"]).is_dir(), f"{key}: {entry['dir']} 없음"


def test_hanam_fixture_replays(sim):
    assert sim.from_fixture
    assert sim.id == "hanam_taxi_V80_1000p_seed42"


def test_hanam_fixture_tables(sim):
    assert len(sim.record) == 360  # 18:00~24:00, 1분 간격
    assert list(sim.record.columns) == [
        "time",
        "waiting_passenger_cnt",
        "fail_passenger_cnt",
        "empty_vehicle_cnt",
        "driving_vehicle_cnt",
    ]
    assert len(sim.result) == 360
    assert len(sim.passengers) == 990
    assert len(sim.trips) > 100


def test_hanam_fixture_summary_is_stable(sim):
    """본문에 인용하는 숫자입니다. 바뀌면 본문도 고쳐야 합니다."""
    s = sim.summary()
    assert s["total_passengers"] == 990
    assert s["served_passengers"] == 990
    assert s["service_rate"] == pytest.approx(1.0)
    assert s["failed_passengers"] == 0
    assert s["avg_waiting_time_min"] == pytest.approx(4.08, abs=0.01)
    assert s["utilization"] == pytest.approx(0.265, abs=0.001)


def test_every_trip_leg_normalizes(sim):
    """모든 구간에 공통 키가 있어야 합니다."""
    for leg in sim.trips:
        assert set(leg) >= {"vehicle_id", "cartype", "board", "trip", "timestamp"}


def test_some_legs_have_no_geometry(sim):
    """실제 결과에는 좌표가 빈 구간이 섞여 있습니다.

    차량이 이미 승객 위치에 있어 이동이 없었던 경우입니다. 좌표는 비었는데
    timestamp 는 한 개 들어 있어서, 길이가 같다고 가정하면 시각화가 터집니다.
    """
    degenerate = [t for t in sim.trips if len(t["trip"]) != len(t["timestamp"])]
    assert degenerate, "이 녹화본에는 빈 구간이 있어야 합니다(방어 코드의 근거)."
    assert all(len(t["trip"]) == 0 for t in degenerate)


def test_prepare_trips_drops_degenerate_legs(sim):
    """viz 는 그런 구간을 걸러 내고 나머지만 그려야 합니다."""
    from smartmob.viz import prepare_trips

    prepared = prepare_trips(sim.trips, sample=None)
    assert 0 < len(prepared) < len(sim.trips)
    for p in prepared:
        assert len(p["path"]) == len(p["timestamps"]) >= 2


def test_no_absolute_paths_in_fixture_config(sim):
    """녹화본에 개인 머신 경로가 남아 있으면 안 됩니다."""
    for key, value in sim.config.items():
        if isinstance(value, str):
            assert ":\\" not in value, f"{key} 에 절대경로가 남아 있습니다: {value}"
