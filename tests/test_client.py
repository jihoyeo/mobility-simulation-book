"""Dtumos 클라이언트와 결과 객체."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from smartmob.client import (
    Dtumos,
    SimulationResult,
    _check_korea,
    _check_simulation_limits,
    _unwrap_itineraries,
    normalize_trip,
    polyline_km,
)
from smartmob.fixtures import FixtureMissing, key_for


# --------------------------------------------------------------------------- #
# 입력 검사
# --------------------------------------------------------------------------- #


def test_simulation_limits_ok():
    _check_simulation_limits(
        {"num_passengers": 1000, "fleet_size": 80, "time_start": 1080, "time_end": 1440}
    )


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"num_passengers": 20000, "fleet_size": 80, "time_start": 0, "time_end": 60}, "num_passengers"),
        ({"num_passengers": 100, "fleet_size": 5000, "time_start": 0, "time_end": 60}, "fleet_size"),
        ({"num_passengers": 100, "fleet_size": 10, "time_start": 600, "time_end": 600}, "time_end"),
    ],
)
def test_simulation_limits_reject(payload, message):
    with pytest.raises(ValueError, match=message):
        _check_simulation_limits(payload)


def test_korea_bounds_accept_seoul():
    _check_korea((37.5665, 126.9780))


def test_korea_bounds_reject_swapped_coordinates():
    """(lon, lat) 순서로 넣는 실수를 잡아야 합니다."""
    with pytest.raises(ValueError, match="위도와 경도|서비스 범위"):
        _check_korea((126.9780, 37.5665))


# --------------------------------------------------------------------------- #
# 구간(leg) 정규화 — trip.json 은 런마다 키가 다릅니다
# --------------------------------------------------------------------------- #


def test_normalize_trip_fills_missing_keys():
    taxi_leg = {
        "vehicle_id": 48,
        "cartype": 0,
        "passenger_id": 112,
        "board": 0,
        "trip": [[127.2, 37.5], [127.21, 37.51]],
        "timestamp": [1121.0, 1121.5],
    }
    out = normalize_trip(taxi_leg)
    assert out["network_distance"] is None
    assert out["total_fare"] is None
    assert out["trip"] == taxi_leg["trip"]


def test_normalize_trip_handles_empty_geometry():
    out = normalize_trip({"vehicle_id": 1, "board": 0})
    assert out["trip"] == []
    assert out["timestamp"] == []


def test_polyline_km():
    """서울시청 -> 하남시청 두 점짜리 선의 길이는 약 19km 입니다."""
    d = polyline_km([[126.9780, 37.5665], [127.2148, 37.5393]])
    assert 18.0 < d < 22.0
    assert polyline_km([]) == 0.0
    assert polyline_km([[127.0, 37.5]]) == 0.0


def test_unwrap_itineraries_renames_kickboard_key():
    assert _unwrap_itineraries({"kickboard": [{"duration_s": 100}], "walk": None}) == [
        {"duration_s": 100}
    ]
    assert _unwrap_itineraries({"itineraries": [1, 2]}) == [1, 2]
    assert _unwrap_itineraries({}) == []


# --------------------------------------------------------------------------- #
# 결과 객체
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_run(tmp_path):
    """작은 시뮬레이션 결과 한 벌을 만듭니다."""
    d = tmp_path / "hanam_ridehail_V2_hungarian_18h-19h"
    d.mkdir()
    (d / "config.json").write_text(json.dumps({"city": "hanam"}), encoding="utf-8")
    pd.DataFrame(
        {
            "time": [1080, 1081, 1082],
            "waiting_passenger_cnt": [2, 1, 0],
            "fail_passenger_cnt": [0, 0, 1],
            "empty_vehicle_cnt": [2, 1, 1],
            "driving_vehicle_cnt": [0, 1, 1],
        }
    ).to_csv(d / "record.csv", index=False)
    (d / "result.json").write_text(
        json.dumps(
            [
                {"time": 1080, "average_waiting_time": 0.0,
                 "occupied_vehicle_num": 0, "empty_vehicle_num": 2},
                {"time": 1081, "average_waiting_time": 2.0,
                 "occupied_vehicle_num": 1, "empty_vehicle_num": 1},
            ]
        ),
        encoding="utf-8",
    )
    (d / "trip.json").write_text(
        json.dumps(
            [
                {"vehicle_id": 0, "cartype": 0, "passenger_id": 0, "board": 0,
                 "trip": [[127.20, 37.53], [127.21, 37.54]], "timestamp": [1080.0, 1080.8]},
                {"vehicle_id": 0, "cartype": 0, "passenger_id": 0, "board": 1,
                 "trip": [[127.21, 37.54], [127.23, 37.55]], "timestamp": [1080.8, 1082.0],
                 "network_distance": 2.5},
            ]
        ),
        encoding="utf-8",
    )
    (d / "passenger_marker.json").write_text(
        json.dumps(
            [
                {"passenger_id": 0, "status": 1, "location": [127.20, 37.53],
                 "destination": [127.23, 37.55], "timestamp": [1080, 1081], "chosen_mode": "taxi"},
                {"passenger_id": 1, "status": 0, "location": [127.19, 37.52],
                 "destination": [127.25, 37.56], "timestamp": [1081, 1081]},
            ]
        ),
        encoding="utf-8",
    )
    return SimulationResult(path=d, id=d.name)


def test_result_loads_tables(fake_run):
    assert list(fake_run.record.columns)[0] == "time"
    assert len(fake_run.record) == 3
    assert len(fake_run.result) == 2
    assert len(fake_run.trips) == 2
    assert len(fake_run.passengers) == 2
    assert fake_run.config["city"] == "hanam"


def test_result_summary(fake_run):
    s = fake_run.summary()
    assert s["total_passengers"] == 2
    assert s["served_passengers"] == 1
    assert s["service_rate"] == pytest.approx(0.5)
    assert s["avg_waiting_time_min"] == pytest.approx(1.0)
    assert s["failed_passengers"] == 1
    assert s["utilization"] == pytest.approx(0.25)
    assert s["occupied_km"] == pytest.approx(2.5)  # network_distance 를 그대로 씀
    assert s["deadhead_km"] > 0  # 없으면 좌표로 계산


def test_result_passengers_wait_time(fake_run):
    assert fake_run.passengers.loc[0, "wait_min"] == 1


def test_result_save_roundtrip(fake_run, tmp_path):
    dest = fake_run.save(tmp_path / "copy")
    again = SimulationResult(path=dest, id="copy")
    assert again.summary()["service_rate"] == pytest.approx(0.5)


def test_missing_files_are_tolerated(tmp_path):
    empty = SimulationResult(path=tmp_path, id="empty")
    assert empty.record.empty
    assert empty.trips == []
    s = empty.summary()
    assert s["service_rate"] is None
    assert s["occupied_km"] is None


# --------------------------------------------------------------------------- #
# 오프라인 동작
# --------------------------------------------------------------------------- #


def test_offline_mode_never_touches_network(monkeypatch):
    monkeypatch.setenv("SMARTMOB_OFFLINE", "1")
    dt = Dtumos()
    assert dt.mode == "fixture"
    assert dt.health()["status"] == "fixture"


def test_offline_missing_fixture_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("SMARTMOB_OFFLINE", "1")
    monkeypatch.setenv("SMARTMOB_DATA_DIR", str(tmp_path))
    dt = Dtumos()
    with pytest.raises(FixtureMissing) as exc:
        dt.run_simulation(city="nowhere", num_passengers=7)
    assert "녹화" in str(exc.value)
    assert "python -m smartmob.fixtures record" in str(exc.value)


def test_fixture_key_is_order_independent():
    assert key_for({"a": 1, "b": 2}) == key_for({"b": 2, "a": 1})
    assert key_for({"a": 1}) != key_for({"a": 2})
