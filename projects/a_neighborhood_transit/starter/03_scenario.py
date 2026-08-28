"""프로젝트 A 3단계 — 개선 시나리오 (12주차)

    python 03_scenario.py

`gtfs/` 를 고쳐 `gtfs_scenario/` 로 저장하고, 같은 O-D 로 before-after 를 비교합니다.

고치는 부분은 여러분이 채웁니다. 아래 `shorten_headway` 가 예시입니다.
노선 신설이나 정류장 이설을 고른다면 그에 맞게 바꾸세요.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from smartmob.data.gtfs import (
    load_gtfs_feed,
    parse_gtfs_time,
    save_gtfs,
    seconds_to_gtfs_time,
)
from smartmob.teaching.fare import calc_fare
from smartmob.teaching.raptor import TransitData, journey, raptor, summarize

BEFORE = Path("gtfs")
AFTER = Path("gtfs_scenario")
DEPARTURE = 8 * 3600


def shorten_headway(feed: dict, route_short_name: str, factor: int = 2) -> dict:
    """특정 노선의 운행을 `factor` 배로 늘립니다 — 배차간격 단축 시나리오.

    기존 운행 사이에 새 운행을 끼워 넣습니다. 가장 단순한 방식은
    각 운행을 복제하면서 시각을 (다음 운행과의 간격 / factor) 만큼 밀어 주는 것입니다.

    주의
    ----
    - `trip_id` 가 겹치면 안 됩니다. 접미사를 붙이세요
    - 막차 이후로 넘어가는 운행은 만들지 않습니다
    - **차량이 몇 대 더 필요한지 계산해 보고서에 적으세요.** 공짜가 아닙니다
    """
    routes = feed["routes"]
    target = routes[routes["route_short_name"].astype(str) == str(route_short_name)]
    if target.empty:
        names = routes["route_short_name"].astype(str).head(15).tolist()
        raise ValueError(f"'{route_short_name}' 노선이 없습니다. 예: {names}")

    route_ids = set(target["route_id"])
    trips = feed["trips"]
    mine = trips[trips["route_id"].isin(route_ids)]
    st = feed["stop_times"]

    new_trips, new_times = [], []
    for trip_id in mine["trip_id"]:
        rows = st[st["trip_id"] == trip_id].copy()
        if rows.empty:
            continue
        for k in range(1, factor):
            shifted = rows.copy()
            shifted["trip_id"] = f"{trip_id}_x{k}"
            # 여기를 여러분의 방식으로 바꾸세요. 지금은 다음 운행까지의 간격을
            # 모르므로 임시로 고정 오프셋을 씁니다.
            offset = 0
            raise NotImplementedError(
                "배차간격을 어떻게 줄일지 정하고 offset 을 계산하세요.\n"
                "  힌트: 같은 노선의 연속한 두 운행의 첫 정류장 출발 시각 차이가 배차간격입니다."
            )

    out = dict(feed)
    out["trips"] = pd.concat([trips, pd.DataFrame(new_trips)], ignore_index=True)
    out["stop_times"] = pd.concat([st, pd.concat(new_times)], ignore_index=True)
    return out


def evaluate(data: TransitData, pairs, departure: int) -> pd.DataFrame:
    """O-D 목록의 지표를 냅니다. 02_baseline.py 와 같은 계산입니다."""
    rows = []
    for origin, dest in pairs:
        result = raptor(data, [(origin, 0)], departure)
        legs = journey(data, result, dest)
        s = summarize(data, legs, departure)
        if s.get("reachable"):
            s["fare"] = calc_fare(legs)
            s.pop("modes", None)
            s.pop("routes", None)
            rows.append(s)
    return pd.DataFrame(rows)


def main() -> int:
    before_feed = load_gtfs_feed(BEFORE)
    before_data = TransitData.from_gtfs(before_feed)

    # 02_baseline.py 와 같은 O-D 를 써야 비교가 됩니다.
    # baseline.csv 를 만들 때 쓴 쌍을 저장해 두고 여기서 읽는 것이 안전합니다.
    raise NotImplementedError(
        "02_baseline.py 에서 쓴 O-D 쌍을 파일로 저장하고 여기서 읽으세요.\n"
        "  다른 쌍으로 비교하면 before-after 차이가 시나리오 때문인지 알 수 없습니다."
    )

    after_feed = shorten_headway(before_feed, route_short_name="30", factor=2)
    save_gtfs(after_feed, AFTER)
    after_data = TransitData.from_gtfs(after_feed)

    before = evaluate(before_data, pairs, DEPARTURE)
    after = evaluate(after_data, pairs, DEPARTURE)

    cols = ["total_min", "wait_min", "transfers", "fare"]
    table = pd.DataFrame({
        "개선 전": before[cols].median(),
        "개선 후": after[cols].median(),
    })
    table["차이"] = (table["개선 후"] - table["개선 전"]).round(2)
    print(table.round(2).to_string())

    print("\n보고서에 반드시 적을 것")
    print("  - 개선 효과와 함께 **대가**. 차량이 몇 대 더 필요한가")
    print("  - 도달 가능한 O-D 수가 늘었는가 (서비스 범위 변화)")
    print("  - 중앙값뿐 아니라 90분위도. 누가 이득을 봤는지가 거기서 보입니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
