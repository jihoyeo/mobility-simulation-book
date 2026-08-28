"""시뮬레이션 결과 시각화.

`trip.json` 을 pydeck 의 ``TripsLayer`` 로 재생합니다. DTUMOS 의 React 화면과
같은 그림을 노트북 안에서 봅니다.

    from smartmob.viz import trips_deck
    deck = trips_deck(sim.trips, boundary=None)
    deck.to_html("trips.html")

주의: pydeck 출력을 노트북에 저장하면 파일이 수십 MB 가 됩니다.
:func:`deck_size_guard` 가 이를 막습니다.
"""

from __future__ import annotations

from typing import Any, Iterable

# trip.json 의 cartype 코드
CARTYPE_LABEL = {
    0: "호출형 택시",
    10: "도보",
    11: "버스",
    12: "도시철도",
    13: "GTX",
    14: "일반철도",
    15: "해운",
    16: "항공",
}

# 밝은 배경에서 읽히는 팔레트 (R, G, B)
CARTYPE_COLOR = {
    0: [214, 96, 40],
    10: [130, 130, 130],
    11: [40, 120, 190],
    12: [70, 150, 90],
    13: [150, 80, 170],
    14: [180, 140, 40],
    15: [60, 150, 160],
    16: [200, 70, 120],
}
DEADHEAD_COLOR = [190, 190, 190]


class DeckTooLarge(RuntimeError):
    pass


def deck_size_guard(html: str, max_mb: float = 2.0) -> str:
    """렌더 결과가 너무 크면 막습니다. 노트북이 부풀지 않게 합니다."""
    size_mb = len(html.encode("utf-8")) / 1e6
    if size_mb > max_mb:
        raise DeckTooLarge(
            f"렌더 결과가 {size_mb:.1f}MB 로 상한 {max_mb}MB 를 넘습니다.\n"
            f"  sample= 인자로 구간 수를 줄이거나, 시간 범위를 좁히세요."
        )
    return html


def prepare_trips(
    trips: Iterable[dict[str, Any]],
    sample: int | None = None,
    include_deadhead: bool = True,
) -> list[dict[str, Any]]:
    """pydeck 이 받는 형태로 다듬습니다.

    좌표가 빈 구간(``trip: []``)과 좌표·시각 길이가 안 맞는 구간을 걸러 냅니다.
    """
    out: list[dict[str, Any]] = []
    for t in trips:
        path = t.get("trip") or []
        stamps = t.get("timestamp") or []
        if len(path) < 2 or len(path) != len(stamps):
            continue
        board = t.get("board")
        if not include_deadhead and board == 0:
            continue
        cartype = int(t.get("cartype") or 0)
        color = DEADHEAD_COLOR if board == 0 else CARTYPE_COLOR.get(cartype, [120, 120, 120])
        out.append(
            {
                "path": [[float(x), float(y)] for x, y in path],
                "timestamps": [float(s) for s in stamps],
                "color": color,
                "cartype": cartype,
                "label": CARTYPE_LABEL.get(cartype, f"기타({cartype})"),
                "board": board,
            }
        )
    if sample is not None and len(out) > sample:
        step = max(1, len(out) // sample)
        out = out[::step][:sample]
    return out


def time_bounds(prepared: list[dict[str, Any]]) -> tuple[float, float]:
    """재생 시간 범위(분)."""
    if not prepared:
        return (0.0, 1440.0)
    starts = [p["timestamps"][0] for p in prepared]
    ends = [p["timestamps"][-1] for p in prepared]
    return (min(starts), max(ends))


def view_center(prepared: list[dict[str, Any]]) -> tuple[float, float]:
    """구간 좌표의 중앙값. 지도 초기 위치로 씁니다."""
    lons = [pt[0] for p in prepared for pt in p["path"]]
    lats = [pt[1] for p in prepared for pt in p["path"]]
    if not lons:
        return (127.2, 37.54)  # 하남시
    lons.sort()
    lats.sort()
    return (lons[len(lons) // 2], lats[len(lats) // 2])


def trips_deck(
    trips: Iterable[dict[str, Any]],
    current_time: float | None = None,
    trail_length: float = 30.0,
    sample: int | None = 2000,
    include_deadhead: bool = True,
    zoom: float = 11.0,
    map_style: str = "light",
):
    """``pydeck.Deck`` 을 만들어 돌려줍니다.

    ``current_time`` 은 자정부터의 분입니다. 비워 두면 마지막 시각을 씁니다.
    """
    import pydeck as pdk

    prepared = prepare_trips(trips, sample=sample, include_deadhead=include_deadhead)
    if not prepared:
        raise ValueError("그릴 구간이 없습니다. trip.json 이 비어 있는지 확인하세요.")

    t0, t1 = time_bounds(prepared)
    now = t1 if current_time is None else current_time
    lon, lat = view_center(prepared)

    layer = pdk.Layer(
        "TripsLayer",
        data=prepared,
        get_path="path",
        get_timestamps="timestamps",
        get_color="color",
        width_min_pixels=2,
        trail_length=trail_length,
        current_time=now,
        rounded=True,
    )
    view = pdk.ViewState(longitude=lon, latitude=lat, zoom=zoom, pitch=0)
    return pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        map_style=map_style,
        tooltip={"text": "{label}"},
    )


def save_deck(deck, path: str, max_mb: float = 2.0) -> str:
    """HTML 로 저장합니다. 크기 상한을 넘으면 저장하지 않고 막습니다."""
    html = deck.to_html(as_string=True)
    deck_size_guard(html, max_mb=max_mb)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
