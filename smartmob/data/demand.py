"""수요 데이터.

DTUMOS 가 받는 수요 CSV 는 컬럼 다섯 개가 계약입니다.

    request_time, origin_lat, origin_lon, dest_lat, dest_lon

``request_time`` 은 **자정부터의 분**입니다. 1080 = 18:00, 1440 = 24:00.
``id`` 와 ``mode`` 는 있으면 쓰고 없으면 채워 넣습니다.
"""

from __future__ import annotations

REQUIRED_COLUMNS = ("request_time", "origin_lat", "origin_lon", "dest_lat", "dest_lon")

# 한국 안이면 통과. 위경도를 뒤바꿔 넣는 실수를 여기서 잡습니다.
LAT_RANGE = (33.0, 39.5)
LON_RANGE = (124.0, 132.0)


class DemandFormatError(ValueError):
    pass


def validate_demand(df) -> None:
    """수요 DataFrame 이 계약을 지키는지 검사합니다. 어기면 예외를 던집니다."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DemandFormatError(
            f"필수 컬럼이 없습니다: {missing}\n  있는 컬럼: {list(df.columns)}"
        )
    if len(df) == 0:
        raise DemandFormatError("수요가 한 건도 없습니다.")

    t = df["request_time"]
    if t.isna().any():
        raise DemandFormatError("request_time 에 결측치가 있습니다.")
    if not ((t >= 0) & (t <= 1440)).all():
        bad = t[(t < 0) | (t > 1440)].head(3).tolist()
        raise DemandFormatError(
            f"request_time 은 자정부터의 분(0~1440)입니다. 범위를 벗어난 값: {bad}\n"
            f"  초나 타임스탬프를 넣지 않았는지 확인하세요."
        )

    for lat_col, lon_col in (("origin_lat", "origin_lon"), ("dest_lat", "dest_lon")):
        lat, lon = df[lat_col], df[lon_col]
        if lat.isna().any() or lon.isna().any():
            raise DemandFormatError(f"{lat_col}/{lon_col} 에 결측치가 있습니다.")
        if not ((lat >= LAT_RANGE[0]) & (lat <= LAT_RANGE[1])).all():
            raise DemandFormatError(
                f"{lat_col} 가 한국 범위 {LAT_RANGE} 를 벗어납니다. "
                f"위도와 경도를 바꿔 넣지 않았는지 확인하세요."
            )
        if not ((lon >= LON_RANGE[0]) & (lon <= LON_RANGE[1])).all():
            raise DemandFormatError(f"{lon_col} 가 한국 범위 {LON_RANGE} 를 벗어납니다.")


def normalize_demand(df):
    """계약을 지키는 형태로 다듬습니다. `id`, `mode` 를 채우고 시간순으로 정렬합니다."""
    validate_demand(df)
    out = df.copy()
    if "id" not in out.columns:
        out.insert(0, "id", range(len(out)))
    if "mode" not in out.columns:
        out["mode"] = "taxi"
    cols = ["id", *REQUIRED_COLUMNS, "mode"]
    out = out[cols + [c for c in out.columns if c not in cols]]
    return out.sort_values("request_time").reset_index(drop=True)


def load_demand(city: str = "hanam"):
    """`data/<city>/demand.csv` 를 읽습니다."""
    import pandas as pd

    from smartmob.data.paths import data_path

    return pd.read_csv(data_path(f"{city}/demand.csv"))


def load_vehicles(city: str = "hanam"):
    """`data/<city>/vehicles.csv` 를 읽습니다."""
    import pandas as pd

    from smartmob.data.paths import data_path

    return pd.read_csv(data_path(f"{city}/vehicles.csv"))


def minutes_to_hhmm(minutes: float) -> str:
    """1080 -> '18:00'."""
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def hhmm_to_minutes(text: str) -> int:
    """'18:00' -> 1080. '25:30' 처럼 24시를 넘는 표기도 받습니다."""
    parts = text.strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"'HH:MM' 형식이어야 합니다: {text!r}")
    return int(parts[0]) * 60 + int(parts[1])
