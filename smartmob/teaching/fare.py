"""수도권 통합환승요금.

7장에서 유도한 코드의 정돈본입니다. 성인 카드 기준이고, 시내버스·도시철도·GTX 만
다룹니다. 광역버스 할증, 심야 할증, 청소년·어린이 할인은 넣지 않았습니다.

규칙은 세 줄입니다.

1. 기본요금은 **탄 수단 중 기본요금이 가장 비싼 것** 하나만 냅니다
2. 총 이동거리 10km 까지는 기본요금만 냅니다
3. 10km 를 넘으면 5km 마다 100원씩 붙습니다 (GTX 를 탔으면 250원)

환승 할인이 아니라 **거리 비례 통합요금**이라는 점이 중요합니다. 버스에서 지하철로
갈아타도 요금을 다시 내지 않고, 두 구간의 거리를 합쳐 한 번 계산합니다.

    from smartmob.teaching.fare import calc_fare
    calc_fare([{"mode": "BUS", "km": 3.2}, {"mode": "SUBWAY", "km": 8.5}])
"""

from __future__ import annotations

import math
from typing import Iterable

# 성인 카드 기준 기본요금(원)
BASE_FARE = {"BUS": 1500, "SUBWAY": 1550, "GTX": 3200}

FREE_KM = 10.0          # 여기까지는 기본요금만
BLOCK_KM = 5.0          # 초과분은 이 거리마다
BLOCK_WON = 100         # 이만큼씩 붙습니다
BLOCK_WON_GTX = 250     # GTX 를 탔으면 가산액이 큽니다

FARE_MODES = frozenset(BASE_FARE)
FREE_MODES = frozenset({"WALK", "TAXI", "SCOOTER"})


def count_transfers(legs: Iterable[dict]) -> int:
    """환승 횟수 = 대중교통 승차 횟수 - 1.

    도보는 세지 않습니다. 버스에서 다른 버스로 갈아타는 것도 승차 두 번입니다.
    """
    boardings = sum(1 for leg in legs if _mode(leg) not in FREE_MODES)
    return max(boardings - 1, 0)


def calc_fare(legs: Iterable[dict], round_to: int = 10) -> int:
    """구간 목록에서 요금(원)을 계산합니다.

    각 구간은 ``{"mode": "BUS", "km": 3.2}`` 형태입니다. `mode` 가
    BUS/SUBWAY/GTX 가 아니면 요금 계산에서 빠집니다.
    """
    legs = list(legs)
    fare_legs = [leg for leg in legs if _mode(leg) in FARE_MODES]
    if not fare_legs:
        return 0

    modes = {_mode(leg) for leg in fare_legs}
    total_km = sum(float(leg.get("km", 0.0)) for leg in fare_legs)

    base = max(BASE_FARE[m] for m in modes)          # 규칙 1
    if total_km <= FREE_KM:                          # 규칙 2
        return base

    over = total_km - FREE_KM                        # 규칙 3
    blocks = math.ceil(over / BLOCK_KM)
    per_block = BLOCK_WON_GTX if "GTX" in modes else BLOCK_WON
    total = base + blocks * per_block
    return int(round(total / round_to) * round_to)


def fare_detail(legs: Iterable[dict]) -> dict:
    """요금이 어떻게 나왔는지 풀어 보여 줍니다. 계산을 검산할 때 씁니다."""
    legs = list(legs)
    fare_legs = [leg for leg in legs if _mode(leg) in FARE_MODES]
    if not fare_legs:
        return {"fare": 0, "reason": "요금이 붙는 구간이 없습니다"}

    modes = sorted({_mode(leg) for leg in fare_legs})
    total_km = sum(float(leg.get("km", 0.0)) for leg in fare_legs)
    base_mode = max(modes, key=lambda m: BASE_FARE[m])
    over = max(total_km - FREE_KM, 0.0)
    blocks = math.ceil(over / BLOCK_KM) if over > 0 else 0
    per_block = BLOCK_WON_GTX if "GTX" in modes else BLOCK_WON

    return {
        "fare": calc_fare(legs),
        "modes": modes,
        "base_mode": base_mode,
        "base_fare": BASE_FARE[base_mode],
        "total_km": round(total_km, 2),
        "over_km": round(over, 2),
        "blocks": blocks,
        "won_per_block": per_block,
        "surcharge": blocks * per_block,
        "transfers": count_transfers(legs),
    }


def _mode(leg: dict) -> str:
    return str(leg.get("mode", "")).upper()
