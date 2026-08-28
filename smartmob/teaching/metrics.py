"""시뮬레이션 지표.

12장에서 유도한 코드의 정돈본입니다.

시뮬레이션은 숫자를 많이 쏟아냅니다. 그중 무엇을 볼 것인가가 이 모듈의 주제입니다.
지표를 세 무리로 나눕니다.

- **승객이 보는 것** — 배차를 받았는가, 얼마나 기다렸는가
- **운영자가 보는 것** — 차가 얼마나 일했는가, 빈 차로 얼마나 달렸는가
- **도시가 보는 것** — 총 주행거리, 그중 승객을 태우지 않은 비율

    from smartmob.teaching.metrics import kpi_table
    kpi_table(sim)
"""

from __future__ import annotations

from typing import Iterable

# 이보다 오래 기다리면 서비스 실패로 봅니다. 업계 관행에 가까운 값입니다.
SERVICE_FAILURE_MIN = 30


# --------------------------------------------------------------------------- #
# 승객 관점
# --------------------------------------------------------------------------- #


def passenger_metrics(waits, n_total: int | None = None) -> dict:
    """대기시간 목록에서 승객 관점 지표를 냅니다.

    ``waits`` 는 배차받은 승객의 대기시간(분) 목록입니다.
    ``n_total`` 을 주면 서비스율을 함께 계산합니다.
    """
    import numpy as np

    waits = np.asarray([w for w in waits if w is not None], dtype=float)
    if waits.size == 0:
        return {"served": 0, "service_rate": 0.0 if n_total else None}

    total = n_total if n_total is not None else waits.size
    return {
        "served": int(waits.size),
        "service_rate": round(waits.size / total, 4) if total else None,
        "wait_mean": round(float(waits.mean()), 2),
        "wait_p50": round(float(np.percentile(waits, 50)), 2),
        "wait_p90": round(float(np.percentile(waits, 90)), 2),
        "wait_max": round(float(waits.max()), 2),
        "long_wait_share": round(float((waits > SERVICE_FAILURE_MIN).mean()), 4),
    }


# --------------------------------------------------------------------------- #
# 운영자 관점
# --------------------------------------------------------------------------- #


def fleet_metrics(record) -> dict:
    """분 단위 기록에서 차량 관점 지표를 냅니다.

    ``record`` 는 `empty_vehicle_cnt`, `driving_vehicle_cnt` 컬럼을 가진 DataFrame 입니다.
    """
    if record is None or len(record) == 0:
        return {}

    driving = record["driving_vehicle_cnt"].astype(float)
    empty = record["empty_vehicle_cnt"].astype(float)
    on_duty = driving + empty

    active = on_duty > 0
    utilization = float((driving[active] / on_duty[active]).mean()) if active.any() else None

    return {
        "fleet_peak": int(on_duty.max()),
        "driving_mean": round(float(driving.mean()), 1),
        "idle_mean": round(float(empty.mean()), 1),
        "utilization": round(utilization, 4) if utilization is not None else None,
        "busiest_minute": int(record.loc[driving.idxmax(), "time"]),
    }


# --------------------------------------------------------------------------- #
# 도시 관점
# --------------------------------------------------------------------------- #


def distance_metrics(loaded_km: float | None, empty_km: float | None) -> dict:
    """주행거리에서 도시 관점 지표를 냅니다.

    공차 비율은 도로를 차지하면서 아무도 태우지 않은 주행의 비중입니다.
    """
    if loaded_km is None or empty_km is None:
        return {}
    total = loaded_km + empty_km
    return {
        "loaded_km": round(loaded_km, 1),
        "empty_km": round(empty_km, 1),
        "total_km": round(total, 1),
        "empty_share": round(empty_km / total, 4) if total else None,
    }


def trips_distance(trips: Iterable[dict]) -> dict:
    """DTUMOS 의 `trip.json` 에서 실차·공차 거리를 뽑습니다.

    `network_distance` 가 승객을 태운 구간에만 있을 수 있어, 없으면 좌표로 계산합니다.
    """
    from smartmob.client import polyline_km

    loaded = empty = 0.0
    for leg in trips:
        km = leg.get("network_distance")
        if km is None:
            km = polyline_km(leg.get("trip") or [])
        if leg.get("board") == 1:
            loaded += float(km)
        elif leg.get("board") == 0:
            empty += float(km)
    return distance_metrics(loaded, empty)


# --------------------------------------------------------------------------- #
# 한 장으로 모으기
# --------------------------------------------------------------------------- #


def kpi_table(sim) -> dict:
    """엔진 결과(`SimulationResult`)와 직접 짠 결과(`SimResult`)를 같은 표로 냅니다."""
    record = getattr(sim, "record", None)

    if hasattr(sim, "requests"):                      # 11장의 SimResult
        served = [r for r in sim.requests if r.pickup_time is not None]
        waits = [r.wait_min for r in served]
        out = passenger_metrics(waits, n_total=len(sim.requests))
        out |= fleet_metrics(record)
        out |= distance_metrics(
            sum(v.loaded_km for v in sim.vehicles),
            sum(v.empty_km for v in sim.vehicles),
        )
        return out

    passengers = getattr(sim, "passengers", None)     # 엔진의 SimulationResult
    if passengers is not None and len(passengers):
        waits = passengers.loc[passengers["status"] == 1, "wait_min"].tolist()
        out = passenger_metrics(waits, n_total=len(passengers))
    else:
        out = {}
    out |= fleet_metrics(record)
    out |= trips_distance(getattr(sim, "trips", []) or [])
    return out


def compare(runs: dict) -> "object":
    """여러 시나리오의 지표를 한 표로 늘어놓습니다.

    ``runs`` 는 ``{"라벨": 결과}`` 입니다.
    """
    import pandas as pd

    return pd.DataFrame({label: kpi_table(sim) for label, sim in runs.items()}).T
