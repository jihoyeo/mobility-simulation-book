"""프로젝트 A 1단계 — 대상지 GTFS 자르기 (6~8주차)

    python 01_clip_gtfs.py 하남시

전국 GTFS 를 내려받아 대상지만 남기고 `gtfs/` 에 저장합니다.
처음 한 번은 내려받느라 몇 분 걸립니다. 그다음부터는 캐시를 씁니다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import mapping

from smartmob.data import ensure, list_sigungu, load_sigungu, sigungu_info
from smartmob.data.gtfs import (
    clip_to_boundary,
    describe_feed,
    load_gtfs_feed,
    save_gtfs,
)

OUT = Path("gtfs")
BUFFER_M = 500.0        # 경계 바깥 이 거리까지의 정류장도 남깁니다


def main(name: str) -> int:
    try:
        boundary = load_sigungu(name)
    except (KeyError, ValueError) as exc:
        print(exc)
        print("\n쓸 수 있는 이름 일부:", ", ".join(list_sigungu()[:10]), "…")
        return 1

    info = sigungu_info(name)
    print(f"{name}  면적 {info['area_km2']} km²")
    print(f"  위도 {info['bounds']['min_lat']} ~ {info['bounds']['max_lat']}")
    print(f"  경도 {info['bounds']['min_lon']} ~ {info['bounds']['max_lon']}")

    Path("boundary.geojson").write_text(
        json.dumps(mapping(boundary), ensure_ascii=False), encoding="utf-8"
    )
    print("  경계 저장: boundary.geojson")

    print("\n전국 GTFS 를 준비합니다 (처음 한 번만 내려받습니다)")
    zip_path = ensure("GTFS_Korea_2024.zip")

    print("읽는 중…")
    feed = load_gtfs_feed(zip_path)
    before = describe_feed(feed)

    print(f"자르는 중… (버퍼 {BUFFER_M:.0f}m)")
    mine = clip_to_boundary(feed, boundary, buffer_m=BUFFER_M)
    after = describe_feed(mine)

    print("\n자르기 전후")
    for key in ("stops", "routes", "trips", "stop_times"):
        print(f"  {key:12s} {before[key]:>10,} → {after[key]:>10,}")

    print("\nroute_type 분포 (5장의 TAGO 코드)")
    for label, count in sorted(after.get("route_type", {}).items(), key=lambda x: -x[1]):
        print(f"  {label:20s} {count:>5,}")

    save_gtfs(mine, OUT)
    print(f"\n저장 완료: {OUT}/")

    print("\n다음에 할 일 — 02_gtfs.md 에 적을 것")
    print("  - 위 표를 옮겨 적습니다")
    print("  - 첫차와 막차 시각 (연습 5.1 참고)")
    print("  - 이상해 보이는 것 하나. 이름 중복, 하루 한 번뿐인 노선, 엉뚱한 좌표 등")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        print("예: python 01_clip_gtfs.py 하남시")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
