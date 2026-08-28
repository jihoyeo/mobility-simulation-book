"""DTUMOS 엔진 클라이언트.

책의 모든 코드 셀은 `requests` 를 직접 쓰지 않고 이 모듈을 경유합니다.
그래야 서버가 없는 환경(CI, 집에서 복습)에서도 같은 코드가 돌아갑니다.

    from smartmob import Dtumos

    dt = Dtumos()
    sim = dt.run_simulation(city="hanam", fleet_size=80, num_passengers=1000)
    sim.record.head()

동작 모드
---------
``auto``(기본)
    ``GET /health`` 를 2초 안에 시도합니다. 붙으면 실서버, 안 붙으면 녹화본.
``live``
    반드시 실서버. 못 붙으면 :class:`DtumosUnavailable`.
``fixture``
    반드시 녹화본. 녹화가 없으면 :class:`~smartmob.fixtures.FixtureMissing`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from smartmob import fixtures
from smartmob.config import dtumos_url, offline

Mode = Literal["auto", "live", "fixture"]

# 서버가 강제하는 상한. 넘기면 요청 전에 막습니다.
MAX_PASSENGERS = 10_000
MAX_FLEET_SIZE = 1_000
MAX_TIME_RANGE_MIN = 1_440

# /api/transit-routing 은 한국 좌표만 받습니다.
LAT_RANGE = (33.0, 39.5)
LON_RANGE = (124.0, 132.0)

RESULT_FILES = (
    "config.json",
    "record.csv",
    "result.json",
    "trip.json",
    "passenger_marker.json",
    "vehicle_marker.json",
)


class DtumosUnavailable(RuntimeError):
    """DTUMOS 서버에 붙지 못했습니다."""


class DtumosError(RuntimeError):
    """서버가 오류를 돌려주었습니다."""


# --------------------------------------------------------------------------- #
# 시뮬레이션 결과
# --------------------------------------------------------------------------- #


@dataclass
class SimulationResult:
    """한 번의 시뮬레이션 산출물. 디렉터리 하나가 곧 결과입니다."""

    path: Path
    id: str
    from_fixture: bool = False
    _cache: dict[str, Any] = field(default_factory=dict, repr=False)

    # -- 원본 파일 ---------------------------------------------------------- #

    @property
    def config(self) -> dict[str, Any]:
        return self._json("config.json", default={})

    @property
    def record(self):
        """분 단위 시계열. 컬럼: time, waiting_passenger_cnt, fail_passenger_cnt,
        empty_vehicle_cnt, driving_vehicle_cnt"""
        import pandas as pd

        if "record" not in self._cache:
            p = self.path / "record.csv"
            # DTUMOS 가 BOM 을 붙여 쓰기도 해서 utf-8-sig 로 읽습니다.
            self._cache["record"] = (
                pd.read_csv(p, encoding="utf-8-sig") if p.exists() else pd.DataFrame()
            )
        return self._cache["record"]

    @property
    def result(self):
        """분 단위 상태. result.json 을 DataFrame 으로."""
        import pandas as pd

        if "result" not in self._cache:
            self._cache["result"] = pd.DataFrame(self._json("result.json", default=[]))
        return self._cache["result"]

    @property
    def trips(self) -> list[dict[str, Any]]:
        """구간(leg) 목록. 키가 런마다 달라서 여기서 정규화합니다."""
        if "trips" not in self._cache:
            self._cache["trips"] = [normalize_trip(t) for t in self._json("trip.json", default=[])]
        return self._cache["trips"]

    @property
    def passengers(self):
        """승객 마커. status 1=탑승 성공, 0=실패."""
        import pandas as pd

        if "passengers" not in self._cache:
            rows = []
            for p in self._json("passenger_marker.json", default=[]):
                ts = p.get("timestamp") or []
                loc = p.get("location") or [None, None]
                dst = p.get("destination") or [None, None]
                rows.append(
                    {
                        "passenger_id": p.get("passenger_id"),
                        "status": p.get("status"),
                        "origin_lon": loc[0],
                        "origin_lat": loc[1] if len(loc) > 1 else None,
                        "dest_lon": dst[0],
                        "dest_lat": dst[1] if len(dst) > 1 else None,
                        "request_time": ts[0] if ts else None,
                        "pickup_time": ts[1] if len(ts) > 1 else None,
                        "chosen_mode": p.get("chosen_mode", "taxi"),
                    }
                )
            df = pd.DataFrame(rows)
            if not df.empty:
                df["wait_min"] = df["pickup_time"] - df["request_time"]
            self._cache["passengers"] = df
        return self._cache["passengers"]

    @property
    def metrics(self) -> dict[str, Any]:
        """멀티모달 런이면 서버가 계산한 지표, 아니면 빈 dict."""
        return self._json("multimodal_metrics.json", default={})

    # -- 파생 ---------------------------------------------------------------- #

    def summary(self) -> dict[str, Any]:
        """채점과 비교에 쓰는 핵심 지표.

        정의는 ko/ch12_kpi.md 와 같습니다. 값이 없으면 None 을 넣습니다.
        """
        rec, res, pax = self.record, self.result, self.passengers
        out: dict[str, Any] = {"simulation_id": self.id}

        n_total = len(pax) if not pax.empty else None
        n_served = int((pax["status"] == 1).sum()) if not pax.empty else None
        out["total_passengers"] = n_total
        out["served_passengers"] = n_served
        out["service_rate"] = (n_served / n_total) if n_total else None

        if not res.empty and "average_waiting_time" in res:
            out["avg_waiting_time_min"] = float(res["average_waiting_time"].mean())
        elif not pax.empty and "wait_min" in pax:
            out["avg_waiting_time_min"] = float(pax["wait_min"].dropna().mean())
        else:
            out["avg_waiting_time_min"] = None

        if not res.empty and {"occupied_vehicle_num", "empty_vehicle_num"} <= set(res.columns):
            busy = res["occupied_vehicle_num"].astype(float)
            idle = res["empty_vehicle_num"].astype(float)
            denom = (busy + idle).replace(0, float("nan"))
            out["utilization"] = float((busy / denom).mean())
        else:
            out["utilization"] = None

        if not rec.empty and "fail_passenger_cnt" in rec:
            out["failed_passengers"] = int(rec["fail_passenger_cnt"].max())
        else:
            out["failed_passengers"] = None

        out["occupied_km"] = _leg_distance_km(self.trips, board=1)
        out["deadhead_km"] = _leg_distance_km(self.trips, board=0)
        return out

    # -- 저장 ---------------------------------------------------------------- #

    def save(self, dest: str | Path) -> Path:
        """결과 파일 일습을 다른 곳으로 복사합니다. 그대로 fixture 가 됩니다."""
        import shutil

        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for name in RESULT_FILES + ("multimodal_metrics.json",):
            src = self.path / name
            if src.exists():
                shutil.copy2(src, dest / name)
        return dest

    # -- 내부 ---------------------------------------------------------------- #

    def _json(self, name: str, default: Any) -> Any:
        if name not in self._cache:
            p = self.path / name
            self._cache[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
        return self._cache[name]

    def __repr__(self) -> str:  # pragma: no cover - 표시용
        src = "녹화본" if self.from_fixture else "실행"
        return f"<SimulationResult {self.id} ({src}) at {self.path}>"


def normalize_trip(trip: dict[str, Any]) -> dict[str, Any]:
    """구간 dict 의 키를 고르게 맞춥니다.

    택시 런과 멀티모달 런이 서로 다른 키를 씁니다. 빠진 키는 None 으로 채우고,
    좌표가 빈 구간(``trip: []``)도 그대로 통과시킵니다.
    """
    out = dict(trip)
    out.setdefault("trip", [])
    out.setdefault("timestamp", [])
    out.setdefault("board", None)
    out.setdefault("cartype", 0)
    out.setdefault("passenger_id", None)
    out.setdefault("vehicle_id", None)
    for optional in ("network_distance", "total_time_min", "total_fare", "route_name"):
        out.setdefault(optional, None)
    return out


def _leg_distance_km(trips: Iterable[dict[str, Any]], board: int) -> float | None:
    """board 값이 맞는 구간의 주행거리 합(km).

    ``network_distance`` 는 승객을 태운 구간에만 붙어 있을 수 있어서,
    없으면 좌표열로 대신 계산합니다.
    """
    total, seen = 0.0, False
    for t in trips:
        if t.get("board") != board:
            continue
        seen = True
        d = t.get("network_distance")
        total += float(d) if d is not None else polyline_km(t.get("trip") or [])
    return round(total, 3) if seen else None


def polyline_km(coords: list[list[float]]) -> float:
    """[[lon, lat], ...] 좌표열의 하버사인 거리 합(km)."""
    import math

    if not coords or len(coords) < 2:
        return 0.0
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = p2 - p1
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        total += 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(a)))
    return total


# --------------------------------------------------------------------------- #
# 클라이언트
# --------------------------------------------------------------------------- #


class Dtumos:
    """DTUMOS 서버로 가는 얇은 통로."""

    def __init__(
        self,
        base_url: str | None = None,
        mode: Mode = "auto",
        timeout: float = 30.0,
        api_key: str | None = None,
    ) -> None:
        self.base_url = (base_url or dtumos_url()).rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self._mode: Mode = "fixture" if offline() else mode
        self._resolved: Mode | None = "fixture" if self._mode == "fixture" else None

    # -- 접속 ---------------------------------------------------------------- #

    @property
    def mode(self) -> Mode:
        """실제로 쓰이는 모드. auto 였다면 여기서 판정합니다."""
        if self._resolved is None:
            self._resolved = "live" if self._probe() else "fixture"
            if self._resolved == "fixture":
                print(
                    f"[smartmob] {self.base_url} 에 연결하지 못해 녹화된 결과를 사용합니다.\n"
                    f"           실서버로 돌리려면 DTUMOS 를 띄우고 "
                    f"SMARTMOB_DTUMOS_URL 을 설정하세요."
                )
        return self._resolved

    def _probe(self) -> bool:
        try:
            import requests

            r = requests.get(f"{self.base_url}/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        if self.mode == "fixture":
            return {"status": "fixture", "base_url": self.base_url}
        return self._get("/health")

    # -- 시뮬레이션 ---------------------------------------------------------- #

    def run_simulation(
        self,
        city: str = "hanam",
        mode: str = "taxi",
        fleet_size: int = 80,
        num_passengers: int = 1000,
        time_start: int = 1080,
        time_end: int = 1440,
        dispatch_mode: str = "optimization",
        matrix_mode: str = "street_distance",
        vehicle_capacity: int = 1,
        random_seed: int = 42,
        wait: bool = True,
        poll_interval: float = 2.0,
        job_timeout: float = 900.0,
        progress: bool = True,
        **extra: Any,
    ) -> SimulationResult:
        """시뮬레이션 한 번. 끝나면 결과 파일이 담긴 :class:`SimulationResult`.

        ``time_start`` / ``time_end`` 는 자정부터의 분입니다. 1080 = 18:00.
        """
        payload = {
            "city": city,
            "mode": mode,
            "fleet_size": int(fleet_size),
            "num_passengers": int(num_passengers),
            "time_start": int(time_start),
            "time_end": int(time_end),
            "dispatch_mode": dispatch_mode,
            "matrix_mode": matrix_mode,
            "vehicle_capacity": int(vehicle_capacity),
            "random_seed": int(random_seed),
            **extra,
        }
        _check_simulation_limits(payload)

        if self.mode == "fixture":
            path = fixtures.replay("simulation", payload)
            return SimulationResult(path=path, id=path.name, from_fixture=True)

        job = self._post("/api/simulation/jobs", payload)
        job_id = job.get("job_id") or job.get("id")
        if job_id is None:
            raise DtumosError(f"서버가 job id 를 돌려주지 않았습니다: {job}")
        if not wait:
            return SimulationResult(path=Path("."), id=str(job_id))

        info = self._wait_for_job(job_id, poll_interval, job_timeout, progress)
        sim_id = info.get("simulation_id") or info.get("result", {}).get("simulation_id") or job_id
        local = self._download_result(str(sim_id))
        return SimulationResult(path=local, id=str(sim_id))

    def _wait_for_job(
        self, job_id: str, poll_interval: float, job_timeout: float, progress: bool
    ) -> dict[str, Any]:
        deadline = time.time() + job_timeout
        last = ""
        while time.time() < deadline:
            info = self._get(f"/api/simulation/jobs/{job_id}")
            status = str(info.get("status", "")).lower()
            if progress and status != last:
                print(f"[smartmob] job {job_id}: {status}")
                last = status
            if status in {"completed", "succeeded", "done"}:
                return info
            if status in {"failed", "error", "cancelled", "canceled"}:
                raise DtumosError(f"시뮬레이션이 실패했습니다: {info.get('error') or info}")
            time.sleep(poll_interval)
        raise DtumosError(f"job {job_id} 가 {job_timeout:.0f}초 안에 끝나지 않았습니다.")

    def _download_result(self, sim_id: str) -> Path:
        import requests

        from smartmob.config import repo_root

        dest = repo_root() / "simul_result" / sim_id
        dest.mkdir(parents=True, exist_ok=True)
        for name in RESULT_FILES + ("multimodal_metrics.json",):
            url = f"{self.base_url}/api/simulation/{sim_id}/files/{name}"
            try:
                r = requests.get(url, timeout=self.timeout, headers=self._headers())
            except Exception as exc:  # noqa: BLE001
                raise DtumosUnavailable(f"{url} 내려받기 실패: {exc}") from exc
            if r.status_code == 404:
                continue  # 런 종류에 따라 없는 파일이 있습니다
            r.raise_for_status()
            (dest / name).write_bytes(r.content)
        return dest

    # -- 라우팅 -------------------------------------------------------------- #

    def route(
        self,
        city: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any]:
        """도로망 최단경로 한 건. 학생 구현과 대조할 때 씁니다."""
        _check_korea(origin)
        _check_korea(destination)
        payload = {
            "city": city,
            "origin": {"lat": origin[0], "lon": origin[1]},
            "destination": {"lat": destination[0], "lon": destination[1]},
        }
        if self.mode == "fixture":
            path = fixtures.replay("route", payload)
            return json.loads((path / "response.json").read_text(encoding="utf-8"))
        return self._post("/api/routing/route", payload)

    def transit_route(
        self,
        city: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
        departure_time: str = "08:30",
        max_itineraries: int = 8,
        warmup_timeout: float = 90.0,
    ) -> list[dict[str, Any]]:
        """대중교통 경로안 목록.

        서버 엔드포인트가 킥보드 데모용이라 응답 키가 ``kickboard`` 입니다.
        여기서 ``itineraries`` 로 바꿔 돌려줍니다. 처음 호출하면 브리지를
        올리느라 30~60초가 걸리고 그동안 409 를 냅니다. 자동으로 기다립니다.
        """
        _check_korea(origin)
        _check_korea(destination)
        payload = {
            "city": city,
            "origin": {"lat": origin[0], "lon": origin[1]},
            "destination": {"lat": destination[0], "lon": destination[1]},
            "departure_time": departure_time,
            "compare": False,
            "max_itineraries": int(max_itineraries),
        }
        if self.mode == "fixture":
            path = fixtures.replay("transit_route", payload)
            body = json.loads((path / "response.json").read_text(encoding="utf-8"))
            return _unwrap_itineraries(body)

        deadline = time.time() + warmup_timeout
        delay = 2.0
        warmed = False
        while True:
            body, status = self._post_raw("/api/transit-routing/query", payload)
            if status == 200:
                return _unwrap_itineraries(body)
            if status != 409:
                raise DtumosError(f"대중교통 경로 질의 실패 (HTTP {status}): {body}")
            if not warmed:
                self._post_raw("/api/transit-routing/warmup", {"city": city, "profiles": ["walk"]})
                warmed = True
            if time.time() > deadline:
                raise DtumosError(
                    f"{city} 의 대중교통 엔진이 {warmup_timeout:.0f}초 안에 준비되지 않았습니다."
                )
            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)

    # -- 데이터 -------------------------------------------------------------- #

    def regions(self) -> list[dict[str, Any]]:
        if self.mode == "fixture":
            path = fixtures.directory_for(fixtures.key_for({"endpoint": "regions"}))
            if path is None:
                return []
            return json.loads((path / "response.json").read_text(encoding="utf-8"))
        return self._get("/api/data/regions")

    def upload_demand(self, city: str, df) -> dict[str, Any]:
        """수요 DataFrame 을 서버에 올립니다. 표준 5컬럼을 먼저 검사합니다."""
        from smartmob.data.demand import validate_demand

        validate_demand(df)
        if self.mode == "fixture":
            raise DtumosUnavailable(
                "수요 업로드는 실서버가 필요합니다. DTUMOS 를 띄우고 다시 실행하세요."
            )
        import io

        import requests

        buf = io.StringIO()
        df.to_csv(buf, index=False)
        files = {"file": ("demand.csv", buf.getvalue(), "text/csv")}
        r = requests.post(
            f"{self.base_url}/api/data/upload-demand",
            params={"city": city},
            files=files,
            timeout=self.timeout,
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    # -- HTTP 하부 ----------------------------------------------------------- #

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _get(self, path: str) -> Any:
        import requests

        try:
            r = requests.get(f"{self.base_url}{path}", timeout=self.timeout, headers=self._headers())
        except Exception as exc:  # noqa: BLE001
            raise DtumosUnavailable(f"{self.base_url}{path} 접속 실패: {exc}") from exc
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        body, status = self._post_raw(path, payload)
        if status >= 400:
            raise DtumosError(f"{path} 실패 (HTTP {status}): {body}")
        return body

    def _post_raw(self, path: str, payload: dict[str, Any]) -> tuple[Any, int]:
        import requests

        try:
            r = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                timeout=self.timeout,
                headers=self._headers(),
            )
        except Exception as exc:  # noqa: BLE001
            raise DtumosUnavailable(f"{self.base_url}{path} 접속 실패: {exc}") from exc
        try:
            return r.json(), r.status_code
        except ValueError:
            return r.text, r.status_code


# --------------------------------------------------------------------------- #
# 검사 도우미
# --------------------------------------------------------------------------- #


def _check_simulation_limits(payload: dict[str, Any]) -> None:
    if payload["num_passengers"] > MAX_PASSENGERS:
        raise ValueError(f"num_passengers 는 {MAX_PASSENGERS} 이하여야 합니다.")
    if payload["fleet_size"] > MAX_FLEET_SIZE:
        raise ValueError(f"fleet_size 는 {MAX_FLEET_SIZE} 이하여야 합니다.")
    span = payload["time_end"] - payload["time_start"]
    if span <= 0:
        raise ValueError("time_end 가 time_start 보다 커야 합니다.")
    if span > MAX_TIME_RANGE_MIN:
        raise ValueError(f"시간 범위는 {MAX_TIME_RANGE_MIN}분 이하여야 합니다.")


def _check_korea(point: tuple[float, float]) -> None:
    lat, lon = point
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
        raise ValueError(
            f"좌표 ({lat}, {lon}) 가 서비스 범위를 벗어납니다. "
            f"위도 {LAT_RANGE}, 경도 {LON_RANGE} 안이어야 합니다. "
            f"(lat, lon) 순서로 넣었는지 확인하세요."
        )


def _unwrap_itineraries(body: Any) -> list[dict[str, Any]]:
    """서버 응답에서 경로안 목록만 꺼냅니다."""
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    for key in ("itineraries", "kickboard", "walk"):
        value = body.get(key)
        if value:
            return value
    return []
