#!/usr/bin/env python3
"""커밋된 녹화본과 실제 DTUMOS 결과를 비교합니다.

`data/fixtures/index.json` 에 등록된 시뮬레이션 녹화본마다 같은 요청을 실서버에
보내고, 핵심 지표를 대조합니다. 하나라도 허용 오차를 벗어나면 종료코드 1 입니다.

    SMARTMOB_DTUMOS_URL=https://... python tools/check_fixture_drift.py

주 1회 .github/workflows/fixture-drift.yml 이 돌립니다.
"""

from __future__ import annotations

import os
import sys

# 지표별 허용 오차. 시뮬레이터에 난수가 섞여 있어 완전 일치를 요구하지 않습니다.
TOLERANCE = {
    "total_passengers": 0.0,
    "served_passengers": 0.02,
    "service_rate": 0.02,
    "avg_waiting_time_min": 0.10,
    "utilization": 0.10,
}


def main() -> int:
    os.environ.pop("SMARTMOB_OFFLINE", None)

    from smartmob import Dtumos, SimulationResult
    from smartmob.config import fixtures_dir
    from smartmob.fixtures import load_index

    index = load_index()
    sims = {k: v for k, v in index.items() if v.get("kind") == "simulation"}
    if not sims:
        print("비교할 시뮬레이션 녹화본이 없습니다.")
        return 0

    client = Dtumos(mode="live", api_key=os.environ.get("DTUMOS_API_KEY"))
    print(f"서버: {client.base_url}")

    failures: list[str] = []
    for key, entry in sorted(sims.items()):
        name = entry["dir"]
        recorded = SimulationResult(
            path=fixtures_dir() / name, id=name, from_fixture=True
        ).summary()
        print(f"\n[{key}] {name}")

        try:
            live = client.run_simulation(**entry["payload"], progress=False).summary()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: 실행 실패 — {exc}")
            print(f"  실행 실패: {exc}")
            continue

        for metric, tol in TOLERANCE.items():
            old, new = recorded.get(metric), live.get(metric)
            if old is None or new is None:
                continue
            drift = abs(new - old) / abs(old) if old else abs(new - old)
            mark = "ok " if drift <= tol else "DIFF"
            print(f"  {mark} {metric:<22} 녹화 {old:<12.4f} 실행 {new:<12.4f} 차이 {drift:.1%}")
            if drift > tol:
                failures.append(
                    f"{name}.{metric}: 녹화 {old:.4f} vs 실행 {new:.4f} (허용 {tol:.0%})"
                )

    print()
    if failures:
        print("어긋난 항목:")
        for f in failures:
            print(f"  - {f}")
        print(
            "\n조치: 엔진 변경이 의도된 것이면 녹화본을 다시 만들고, "
            "본문에 인용한 숫자와 tests/test_fixtures.py 의 고정값도 같이 고칩니다."
        )
        return 1

    print(f"녹화본 {len(sims)}건, 모두 허용 범위 안입니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
