#!/usr/bin/env python3
"""실습 자가 채점.

    python exercises/check.py w03      # 3주차 최단경로
    python exercises/check.py w06      # 6주차 RAPTOR
    python exercises/check.py w11      # 11주차 시뮬레이션 루프
    python exercises/check.py all      # 전부

`tests/` 가 쓰는 기준과 같은 것을 봅니다. 여기를 통과하면 과제 채점도 통과합니다.

아직 구현하지 않은 함수는 `아직 구현하지 않았습니다` 로 표시됩니다.
하나씩 채우면서 통과 개수가 늘어나는 것을 확인하세요.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_w03():
    import w03_dijkstra as sol
    from smartmob.testing import check_dijkstra

    return check_dijkstra(sol.dijkstra).show()


def run_w06():
    import w06_raptor as sol
    from smartmob.testing import check_raptor

    return check_raptor(sol.TransitData.from_gtfs, sol.raptor).show()


def run_w11():
    import w11_simloop as sol
    from smartmob.testing import check_simloop

    return check_simloop(sol.simulate).show()


RUNNERS = {"w03": run_w03, "w06": run_w06, "w11": run_w11}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] not in {*RUNNERS, "all"}:
        print(__doc__)
        return 2

    targets = list(RUNNERS) if argv[0] == "all" else [argv[0]]
    ok = True
    for name in targets:
        try:
            ok = RUNNERS[name]() and ok
        except Exception as exc:  # noqa: BLE001 - 학생 파일이 아예 못 불러와질 수도 있습니다
            print(f"\n{name}: 파일을 불러오지 못했습니다 — {type(exc).__name__}: {exc}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
