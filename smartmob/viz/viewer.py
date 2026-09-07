"""시뮬레이션 결과를 웹 뷰어가 읽는 형태로 내보냅니다.

`labs/ch12_viewer.html` 이 여기서 나온 파일을 읽습니다. 파일 이름과 키 이름은
DTUMOS 가 내는 것을 그대로 씁니다. 그래서 서버에서 받은 결과 디렉터리를
그대로 넣어도 뷰어가 읽습니다.

    from smartmob.viz import export_viewer

    export_viewer(engine_result, "labs/ch12_viewer_data", sample=200)
    export_viewer(my_loop_result, "labs/ch12_viewer_data")   # 11장에서 짠 것도 됩니다

내보내는 것은 넷입니다.

``trip.json``
    구간마다 ``trip``(좌표열)과 ``timestamp``(분). deck.gl 의 ``TripsLayer`` 가
    이 두 키를 그대로 읽습니다. DTUMOS 프론트엔드도 같은 두 키를 씁니다.
``vehicle_marker.json``
    차량의 위치와 그 위치에 머문 시간 구간.
``passenger_marker.json``
    승객의 호출 위치와 배차 여부.
``meta.json``
    지도 초기 위치와 재생 시간 범위. 뷰어가 처음 열릴 때 씁니다.

엔진 결과와 11장에서 직접 짠 결과를 둘 다 받습니다.
직접 짠 루프는 도로망 위를 달리지 않으므로 구간이 직선 두 점으로 나옵니다.
그 직선이 곧 그 모형의 근사 수준입니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

__all__ = ["export_viewer", "viewer_payload"]

# 뷰어가 쓰는 키만 남깁니다. 나머지는 파일만 키웁니다.
TRIP_KEYS = ("trip", "timestamp", "board", "cartype", "vehicle_id", "passenger_id")

HANAM_CENTER = (127.2, 37.54)


# --------------------------------------------------------------------------- #
# 엔진 결과
# --------------------------------------------------------------------------- #


def _engine_trips(trips: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """좌표가 없거나 좌표와 시각의 길이가 다른 구간을 걸러 냅니다.

    엔진은 차가 이미 승객 위치에 있어 이동이 없었던 경우에도 구간을 하나 냅니다.
    그때 ``trip`` 은 비어 있고 ``timestamp`` 만 하나 있습니다. 그대로 그리면 터집니다.
    """
    out = []
    for t in trips:
        path = t.get("trip") or []
        stamps = t.get("timestamp") or []
        if len(path) < 2 or len(path) != len(stamps):
            continue
        out.append({key: t.get(key) for key in TRIP_KEYS})
    return out


def _read_json(sim, name: str) -> list:
    path = Path(getattr(sim, "path", "")) / name if getattr(sim, "path", None) else None
    if path is None or not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 직접 짠 루프의 결과 (11장)
# --------------------------------------------------------------------------- #


def _loop_trips(result) -> list[dict[str, Any]]:
    """`SimResult.requests` 에서 구간을 만듭니다.

    직접 짠 루프는 경로를 남기지 않습니다. 출발지와 목적지를 잇는 직선 하나가
    그 통행의 전부입니다. 좌표는 (위도, 경도) 순으로 들어 있어 뒤집어 넣습니다.
    """
    out = []
    for req in result.requests:
        if req.pickup_time is None or req.dropoff_time is None:
            continue
        out.append({
            "trip": [
                [req.origin[1], req.origin[0]],
                [req.dest[1], req.dest[0]],
            ],
            "timestamp": [float(req.pickup_time), float(req.dropoff_time)],
            "board": 1,
            "cartype": 0,
            "vehicle_id": req.vehicle_id,
            "passenger_id": req.id,
        })
    return out


def _loop_passengers(result) -> list[dict[str, Any]]:
    out = []
    for req in result.requests:
        end = req.pickup_time if req.pickup_time is not None else req.request_time + 10
        out.append({
            "passenger_id": req.id,
            "status": 0 if req.failed else 1,
            "location": [req.origin[1], req.origin[0]],
            "destination": [req.dest[1], req.dest[0]],
            "timestamp": [float(req.request_time), float(end)],
            "chosen_mode": "taxi",
        })
    return out


def _loop_vehicles(result) -> list[dict[str, Any]]:
    return [
        {
            "vehicle_id": v.id,
            "cartype": 0,
            "location": [v.location[1], v.location[0]],
            "timestamp": [float(v.work_start), float(v.work_end)],
        }
        for v in result.vehicles
    ]


# --------------------------------------------------------------------------- #
# 공통
# --------------------------------------------------------------------------- #


def _thin(rows: list, limit: int | None) -> list:
    """개수를 줄입니다. 앞에서 자르지 않고 고르게 건너뜁니다."""
    if limit is None or len(rows) <= limit:
        return rows
    step = max(1, len(rows) // limit)
    return rows[::step][:limit]


def _center(trips: list[dict[str, Any]]) -> tuple[float, float]:
    lons = sorted(pt[0] for t in trips for pt in t["trip"])
    lats = sorted(pt[1] for t in trips for pt in t["trip"])
    if not lons:
        return HANAM_CENTER
    return (lons[len(lons) // 2], lats[len(lats) // 2])


def _time_bounds(trips: list[dict[str, Any]]) -> tuple[float, float]:
    if not trips:
        return (1080.0, 1440.0)
    return (
        float(min(t["timestamp"][0] for t in trips)),
        float(max(t["timestamp"][-1] for t in trips)),
    )


def viewer_payload(sim, sample: int | None = None) -> dict[str, Any]:
    """뷰어가 읽는 네 덩어리를 만듭니다. 파일로 쓰지 않고 dict 로 돌려줍니다."""
    if hasattr(sim, "requests"):                       # 11장의 SimResult
        trips = _loop_trips(sim)
        vehicles = _loop_vehicles(sim)
        passengers = _loop_passengers(sim)
        source = "직접 짠 루프"
    else:                                              # 엔진의 SimulationResult
        trips = _engine_trips(sim.trips)
        vehicles = _read_json(sim, "vehicle_marker.json")
        passengers = _read_json(sim, "passenger_marker.json")
        source = "DTUMOS 엔진"

    trips = _thin(trips, sample)
    if not trips:
        raise ValueError(
            "그릴 구간이 없습니다. 엔진 결과라면 trip.json 이 비었는지, "
            "직접 짠 결과라면 배차된 승객이 있는지 확인하세요."
        )

    lon, lat = _center(trips)
    t0, t1 = _time_bounds(trips)
    return {
        "trip.json": trips,
        "vehicle_marker.json": _thin(vehicles, sample),
        "passenger_marker.json": _thin(passengers, sample),
        "meta.json": {
            "source": source,
            "simulation_id": getattr(sim, "id", None),
            "center": [lon, lat],
            "zoom": 11,
            "time_start": t0,
            "time_end": t1,
            "n_trips": len(trips),
        },
    }


def export_viewer(sim, out_dir: str | Path, sample: int | None = None) -> Path:
    """뷰어가 읽는 파일 넷을 ``out_dir`` 에 씁니다.

    ``sample`` 로 구간 수를 줄일 수 있습니다. 브라우저가 버거우면 200쯤으로 낮춥니다.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    payload = viewer_payload(sim, sample=sample)
    for name, data in payload.items():
        (out / name).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    meta = payload["meta.json"]
    total_mb = sum(p.stat().st_size for p in out.glob("*.json")) / 1e6
    print(f"{out} 에 파일 4개, 합계 {total_mb:.1f}MB ({meta['source']})")
    print(f"구간 {meta['n_trips']}개, 재생 범위 "
          f"{meta['time_start']:.0f}~{meta['time_end']:.0f}분")
    return out
