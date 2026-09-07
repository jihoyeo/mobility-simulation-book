"""12장 웹 뷰어 — 내보내기(파이썬)와 화면(자바스크립트).

내보낸 파일의 키 이름은 DTUMOS 가 내는 것과 같아야 합니다.
그래야 서버에서 받은 결과 디렉터리를 뷰어에 그대로 넣을 수 있습니다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from smartmob.viz import export_viewer, viewer_payload

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "labs" / "ch12_viewer"
SAMPLE_DATA = PROJECT / "public" / "data"
MAIN_JS = PROJECT / "src" / "main.js"
CHECKER = ROOT / "tools" / "check_viewer.mjs"

FILES = ("trip.json", "vehicle_marker.json", "passenger_marker.json", "meta.json")
BLANKS = ("tripPath", "tripTimestamps", "tripColor", "waitingPassengers", "nextTime")


@pytest.fixture(scope="module")
def engine_run():
    from smartmob import Dtumos

    return Dtumos().run_simulation(
        city="hanam", mode="taxi", fleet_size=80, num_passengers=1000,
        time_start=1080, time_end=1440, dispatch_mode="optimization",
        matrix_mode="street_distance", vehicle_capacity=1, random_seed=42,
    )


@pytest.fixture(scope="module")
def loop_run():
    from smartmob.data import load_demand, load_vehicles
    from smartmob.teaching.simloop import simulate

    return simulate(load_demand("hanam"), load_vehicles("hanam"), 1080, 1440)


# --------------------------------------------------------------------------- #
# 내보내기
# --------------------------------------------------------------------------- #


def test_engine_payload_keeps_dtumos_keys(engine_run):
    """TripsLayer 가 읽는 두 키가 그대로 살아 있어야 합니다."""
    payload = viewer_payload(engine_run, sample=50)
    trip = payload["trip.json"][0]
    assert "trip" in trip and "timestamp" in trip
    assert len(trip["trip"]) == len(trip["timestamp"]) >= 2


def test_engine_payload_drops_empty_geometry(engine_run):
    """좌표가 비었거나 좌표와 시각의 길이가 다른 구간은 빠져야 합니다."""
    payload = viewer_payload(engine_run)
    assert all(len(t["trip"]) == len(t["timestamp"]) >= 2 for t in payload["trip.json"])
    assert len(payload["trip.json"]) < len(engine_run.trips)


def test_loop_payload_has_two_point_trips(loop_run):
    """직접 짠 루프는 경로를 남기지 않으므로 직선 두 점이 나옵니다."""
    payload = viewer_payload(loop_run)
    assert payload["meta.json"]["source"] == "직접 짠 루프"
    assert all(len(t["trip"]) == 2 for t in payload["trip.json"])


def test_payload_coordinates_are_lon_lat(loop_run):
    """deck.gl 은 [경도, 위도] 순입니다. 뒤집으면 좌표가 남태평양으로 갑니다."""
    for point in viewer_payload(loop_run)["trip.json"][0]["trip"]:
        lon, lat = point
        assert 124.0 <= lon <= 132.0, f"경도 자리에 {lon}"
        assert 33.0 <= lat <= 39.5, f"위도 자리에 {lat}"


def test_meta_covers_every_trip(engine_run):
    payload = viewer_payload(engine_run, sample=50)
    meta = payload["meta.json"]
    starts = [t["timestamp"][0] for t in payload["trip.json"]]
    ends = [t["timestamp"][-1] for t in payload["trip.json"]]
    assert meta["time_start"] == min(starts)
    assert meta["time_end"] == max(ends)
    assert meta["n_trips"] == len(payload["trip.json"])


def test_sample_thins_without_truncating(engine_run):
    """앞에서 자르면 초저녁만 남습니다. 고르게 건너뛰어야 합니다."""
    full = viewer_payload(engine_run)
    thin = viewer_payload(engine_run, sample=40)
    assert len(thin["trip.json"]) <= 40
    assert thin["meta.json"]["time_end"] > full["meta.json"]["time_start"] + 60


def test_export_writes_four_files(engine_run, tmp_path):
    out = export_viewer(engine_run, tmp_path / "viewer", sample=20)
    for name in FILES:
        assert (out / name).exists(), name
        json.loads((out / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 커밋된 표본
# --------------------------------------------------------------------------- #


def test_sample_data_is_committed():
    """`npm run dev` 만 해도 화면이 나와야 합니다."""
    for name in FILES:
        assert (SAMPLE_DATA / name).exists(), f"public/data/{name} 이 없습니다"


def test_sample_data_stays_small():
    total_mb = sum((SAMPLE_DATA / name).stat().st_size for name in FILES) / 1e6
    assert total_mb < 1.5, f"표본이 {total_mb:.1f}MB 입니다. sample 을 줄이세요"


# --------------------------------------------------------------------------- #
# 프로젝트 구성
# --------------------------------------------------------------------------- #


def _package_json() -> dict:
    return json.loads((PROJECT / "package.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("script", ["dev", "start", "build", "preview"])
def test_package_has_the_expected_scripts(script):
    """`npm run dev` 와 `npm start` 가 둘 다 돌아야 합니다."""
    assert script in _package_json()["scripts"]


def test_dependencies_are_pinned():
    """버전을 고정하지 않으면 어느 날 갑자기 빌드가 깨집니다."""
    pkg = _package_json()
    for name, version in {**pkg["dependencies"], **pkg["devDependencies"]}.items():
        assert version[0].isdigit(), f"{name} 이 {version} 로 고정되어 있지 않습니다"


def test_dependency_list_stays_short():
    """가볍게 유지합니다. deck.gl 셋과 Vite 하나면 충분합니다."""
    pkg = _package_json()
    assert len(pkg["dependencies"]) <= 4
    assert len(pkg["devDependencies"]) <= 2


def test_lockfile_is_committed():
    """CI 와 학생 노트북이 같은 것을 받아야 합니다."""
    assert (PROJECT / "package-lock.json").exists()


def test_node_modules_is_ignored():
    ignored = (PROJECT / ".gitignore").read_text(encoding="utf-8")
    assert "node_modules" in ignored
    assert "dist" in ignored


@pytest.mark.parametrize("name", BLANKS)
def test_main_js_has_its_blanks(name):
    source = MAIN_JS.read_text(encoding="utf-8")
    assert f"export function {name}(" in source
    assert "// TODO" in source


def test_viewer_wiring_is_separate_from_the_blanks():
    """학생이 고치는 파일과 배선을 나눠 둡니다."""
    wiring = (PROJECT / "src" / "viewer.js").read_text(encoding="utf-8")
    assert "TripsLayer" in wiring
    assert "TODO" not in MAIN_JS.read_text(encoding="utf-8").replace("// TODO", "")


# --------------------------------------------------------------------------- #
# 채점기
# --------------------------------------------------------------------------- #


def test_checker_reports_the_blank_state():
    """빈칸판은 하나도 통과하지 않아야 합니다. 실수로 정답이 남으면 안 됩니다.

    node 가 없는 환경에서는 건너뜁니다.
    """
    if shutil.which("node") is None:
        pytest.skip("node 가 없습니다")

    proc = subprocess.run(
        ["node", str(CHECKER)], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0/7 통과" in proc.stdout, proc.stdout
    assert "7/7 통과" in proc.stdout, "정답 구현이 채점 기준을 통과하지 못합니다"
