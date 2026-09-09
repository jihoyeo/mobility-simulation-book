"""내장 파이썬 엔진(smartmob.local) — 서버 없이 돌리는 모드."""

from __future__ import annotations

import json

import pytest

from smartmob import Dtumos
from smartmob.client import RESULT_FILES

REFERENCE = {
    "city": "hanam", "mode": "taxi", "fleet_size": 80, "num_passengers": 1000,
    "time_start": 1080, "time_end": 1440, "random_seed": 42,
}


@pytest.fixture
def dt(monkeypatch):
    monkeypatch.setenv("SMARTMOB_OFFLINE", "1")
    return Dtumos()


@pytest.fixture(scope="module")
def sim_40():
    import os

    os.environ["SMARTMOB_OFFLINE"] = "1"
    return Dtumos().run_simulation(**{**REFERENCE, "fleet_size": 40}, progress=False)


def test_reference_payload_still_replays_recording(dt):
    sim = dt.run_simulation(**REFERENCE)
    assert sim.from_fixture and not sim.from_local


def test_other_payload_runs_locally(sim_40):
    assert sim_40.from_local and not sim_40.from_fixture
    assert "내장 엔진" in repr(sim_40)


def test_local_run_writes_every_result_file(sim_40):
    for name in RESULT_FILES:
        assert (sim_40.path / name).exists(), name
    config = json.loads((sim_40.path / "config.json").read_text(encoding="utf-8"))
    assert config["engine"] == "smartmob.local"
    assert config["fleet_size"] == 40


def test_local_tables_have_engine_shape(sim_40):
    rec = sim_40.record
    assert list(rec.columns) == [
        "time", "waiting_passenger_cnt", "fail_passenger_cnt",
        "empty_vehicle_cnt", "driving_vehicle_cnt",
    ]
    assert len(rec) == 360
    res = sim_40.result
    for col in ("occupied_vehicle_num", "empty_vehicle_num", "dispatched_vehicle_num"):
        assert col in res.columns
    assert ((res["occupied_vehicle_num"] + res["empty_vehicle_num"]) == 40).all()
    pax = sim_40.passengers
    assert len(pax) == 1000
    assert pax.loc[pax["status"] == 0, "wait_min"].isna().all()
    assert pax.loc[pax["status"] == 1, "wait_min"].notna().all()


def test_fewer_vehicles_means_worse_service(dt, sim_40):
    big = dt.run_simulation(**REFERENCE).summary()
    small = sim_40.summary()
    assert small["service_rate"] < big["service_rate"]
    assert small["avg_waiting_time_min"] > big["avg_waiting_time_min"]
    assert small["failed_passengers"] > 0
    assert small["deadhead_km"] > 0 and small["occupied_km"] > 0


def test_summary_matches_teaching_loop(sim_40):
    """같은 조건을 11장 루프로 직접 돌린 것과 같은 답이어야 합니다."""
    import pandas as pd

    from smartmob.config import data_dir
    from smartmob.teaching.simloop import simulate

    demand = pd.read_csv(data_dir() / "hanam" / "demand.csv", encoding="utf-8-sig")
    vehicles = pd.read_csv(data_dir() / "hanam" / "vehicles.csv", encoding="utf-8-sig")
    mine = simulate(demand, vehicles.head(40), 1080, 1440).summary()
    theirs = sim_40.summary()
    assert theirs["service_rate"] == pytest.approx(mine["service_rate"])
    assert theirs["avg_waiting_time_min"] == pytest.approx(mine["avg_waiting_time_min"])
    assert theirs["deadhead_km"] == pytest.approx(mine["empty_km"], abs=0.1)
    assert theirs["occupied_km"] == pytest.approx(mine["loaded_km"], abs=0.1)


def test_generated_demand_is_deterministic(dt):
    payload = {**REFERENCE, "fleet_size": 30, "num_passengers": 300, "random_seed": 7}
    a = dt.run_simulation(**payload, progress=False)
    b = dt.run_simulation(**payload, progress=False)
    assert len(a.passengers) == 300
    assert json.loads((a.path / "config.json").read_text(encoding="utf-8"))["demand_source"] == "generated"
    assert a.summary() == b.summary()
    c = dt.run_simulation(**{**payload, "random_seed": 8}, progress=False)
    assert c.summary()["avg_waiting_time_min"] != a.summary()["avg_waiting_time_min"]


def test_local_route_uses_dijkstra(dt):
    r = dt.route("hanam", origin=(37.5393, 127.2148), destination=(37.5606, 127.1930))
    assert r["engine"] == "smartmob.local"
    assert 0 < r["duration"] / 60 < 30
    assert 1000 < r["distance"] < 10000
    assert len(r["route"]) > 2 and len(r["route"][0]) == 2


def test_viewer_export_accepts_local_result(sim_40, tmp_path):
    from smartmob.viz import export_viewer

    export_viewer(sim_40, tmp_path, sample=50)
    for name in ("trip.json", "vehicle_marker.json", "passenger_marker.json", "meta.json"):
        assert (tmp_path / name).exists()
