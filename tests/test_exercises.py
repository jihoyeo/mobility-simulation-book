"""실습 스켈레톤과 자가 채점기.

두 방향을 다 확인합니다.

- 빈칸판은 **전부 실패**해야 합니다. 실수로 정답이 남아 있으면 안 됩니다
- 정답 구현은 **전부 통과**해야 합니다. 채점 기준이 실제로 달성 가능해야 합니다
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from smartmob.testing import (
    Report,
    check_dijkstra,
    check_raptor,
    check_simloop,
    toy_feed,
)

EXERCISES = Path(__file__).resolve().parent.parent / "exercises"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, EXERCISES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 스켈레톤 — 아직 아무것도 통과하면 안 됩니다
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ["w03_dijkstra", "w06_raptor", "w11_simloop"])
def test_skeleton_imports(name):
    """빈칸판도 불러와지기는 해야 합니다. 문법 오류가 있으면 학생이 시작을 못 합니다."""
    assert _load(name) is not None


def test_w03_skeleton_fails_everything():
    sol = _load("w03_dijkstra")
    report = check_dijkstra(sol.dijkstra)
    assert not report.ok
    assert all("아직 구현하지 않았습니다" in r.detail for r in report.results)


def test_w06_skeleton_fails_everything():
    sol = _load("w06_raptor")
    report = check_raptor(sol.TransitData.from_gtfs, sol.raptor)
    assert not report.ok


def test_w11_skeleton_raises():
    sol = _load("w11_simloop")
    from smartmob.data import load_demand, load_vehicles

    with pytest.raises(NotImplementedError):
        sol.simulate(load_demand("hanam"), load_vehicles("hanam"), 1080, 1100)


# --------------------------------------------------------------------------- #
# 정답 — 전부 통과해야 합니다
# --------------------------------------------------------------------------- #


def test_reference_dijkstra_passes():
    from smartmob.teaching.dijkstra import dijkstra as ref

    def shortest(graph, source, target):
        path = ref(graph, source, target)
        return path.duration_s, path.nodes, path.settled

    report = check_dijkstra(shortest)
    assert report.ok, [r.render() for r in report.results if not r.passed]


def test_reference_raptor_passes():
    from smartmob.teaching.raptor import TransitData, raptor as ref

    report = check_raptor(
        TransitData.from_gtfs,
        lambda data, origins, dep, **kw: ref(data, origins, dep, **kw).best,
    )
    assert report.ok, [r.render() for r in report.results if not r.passed]


def test_reference_simloop_passes():
    from smartmob.teaching.simloop import simulate

    report = check_simloop(simulate)
    assert report.ok, [r.render() for r in report.results if not r.passed]


# --------------------------------------------------------------------------- #
# 채점기 자체
# --------------------------------------------------------------------------- #


def test_toy_feed_is_hand_checkable():
    """작은 시간표는 정류장 5개, 노선 2개, 운행 3개여야 손으로 따라갈 수 있습니다."""
    feed = toy_feed()
    assert len(feed["stops"]) == 5
    assert len(feed["routes"]) == 2
    assert len(feed["trips"]) == 3
    assert len(feed["stop_times"]) == 8


def test_report_counts_and_renders():
    report = Report("테스트")
    report.add("통과하는 것", True)
    report.add("실패하는 것", False, "이유")
    assert not report.ok
    assert "PASS" in report.results[0].render()
    assert "이유" in report.results[1].render()


def test_report_catches_student_exceptions():
    """학생 코드가 어떤 예외를 던져도 채점기가 죽으면 안 됩니다."""
    report = Report("테스트")
    report.check("터지는 것", lambda: 1 / 0)
    assert not report.ok
    assert "ZeroDivisionError" in report.results[0].detail


def test_check_dijkstra_catches_wrong_answer():
    """일부러 틀린 구현을 주면 잡아내야 합니다."""
    from smartmob.teaching.dijkstra import dijkstra as ref

    def sloppy(graph, source, target):
        path = ref(graph, source, target)
        return path.duration_s * 1.05, path.nodes, path.settled     # 5% 부풀림

    report = check_dijkstra(sloppy, n_pairs=5)
    assert not report.ok
    failed = [r for r in report.results if not r.passed]
    assert any("NetworkX" in r.name for r in failed)


def test_check_simloop_catches_wrong_output_shape():
    """record 컬럼이 다르면 잡아내야 합니다."""
    from smartmob.teaching.simloop import simulate

    def renamed(*args, **kwargs):
        run = simulate(*args, **kwargs)
        run.record = run.record.rename(columns={"time": "minute"})
        return run

    report = check_simloop(renamed)
    assert not report.ok
    assert any("record 형식" in r.name and not r.passed for r in report.results)
