#!/usr/bin/env python3
"""실습 자가 채점.

    python labs/check.py ch03      # 3장 최단경로
    python labs/check.py ch06      # 6장 RAPTOR
    python labs/check.py ch11      # 11장 시뮬레이션 루프
    python labs/check.py all       # 전부

노트북 안에서는 이렇게 부릅니다.

    from check import check
    check("ch03")

`tests/` 가 쓰는 기준과 같은 것을 봅니다. 여기를 통과하면 과제 채점도 통과합니다.
아직 구현하지 않은 함수는 `아직 구현하지 않았습니다` 로 표시됩니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

LABS = Path(__file__).resolve().parent
ROOT = LABS.parent
for path in (str(ROOT), str(LABS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _check_ch03():
    import ch03_dijkstra as sol
    from smartmob.testing import check_dijkstra

    return check_dijkstra(sol.dijkstra)


def _check_ch06():
    import ch06_raptor as sol
    from smartmob.testing import check_raptor

    return check_raptor(sol.TransitData.from_gtfs, sol.raptor)


def _check_ch11():
    import ch11_simloop as sol
    from smartmob.testing import check_simloop

    return check_simloop(sol.simulate)


CHECKS = {"ch03": _check_ch03, "ch06": _check_ch06, "ch11": _check_ch11}

# 예전 이름으로도 부를 수 있게 남겨 둡니다.
ALIASES = {"w03": "ch03", "w06": "ch06", "w11": "ch11"}


def check(name: str):
    """채점 보고서를 화면에 찍고 `Report` 를 돌려줍니다."""
    name = ALIASES.get(name, name)
    if name not in CHECKS:
        raise ValueError(f"{name} 은 없는 실습입니다. {', '.join(CHECKS)} 중에 고르세요.")
    report = CHECKS[name]()
    report.show()
    return report


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    target = ALIASES.get(argv[0], argv[0]) if argv else None
    if target not in {*CHECKS, "all"}:
        print(__doc__)
        return 2

    names = list(CHECKS) if target == "all" else [target]
    ok = True
    for name in names:
        try:
            ok = check(name).ok and ok
        except Exception as exc:  # noqa: BLE001 - 학생 파일이 아예 못 불러와질 수도 있습니다
            print(f"\n{name}: 파일을 불러오지 못했습니다 — {type(exc).__name__}: {exc}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
