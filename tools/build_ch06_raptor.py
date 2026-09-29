"""하남 GTFS와 제공 RAPTOR로 실제 노선의 라운드 탐색 화면을 만듭니다.

    .venv/bin/python tools/build_ch06_raptor.py

계산값·경로 복원 기록·도로·지도 라이브러리는 HTML에 포함합니다.
온라인 배경지도가 없어도 저장된 도로와 정류장을 볼 수 있습니다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely.geometry import Point, mapping, shape
from shapely.ops import transform, unary_union
from smartmob.data import load_gtfs, load_road_graph
from smartmob.data.paths import data_path
from smartmob.teaching.raptor import Pattern, TransitData, journey, raptor, toy_feed
from smartmob.viz.transit import _boundary, _builder_roads, _finite


def build_isochrones(data, rounds, departure, origin):
    """정류장 도착 + 마지막 도보로 만든 근사 도달 영역.

    마지막 도보는 우회 보정 거리로 최대 500m, 직접 도보는 최대 800m.
    도로망·수역·횡단 가능 여부를 반영한 보행 등시선과 구분합니다.
    """
    east = 111_195.08 * math.cos(math.radians(origin[1]))
    north = 111_195.08
    points = [Point((lon - origin[0]) * east, (lat - origin[1]) * north)
              for lon, lat in zip(data.stop_lons, data.stop_lats)]
    result = {}
    for minutes in (15, 30, 45, 60, 90):
        series = []
        for row in rounds:
            disks = [Point(0, 0).buffer(min(800, minutes * 60 * 1.2) / 1.35, quad_segs=8)]
            for point, arrival in zip(points, row):
                remaining = departure + minutes * 60 - arrival
                if remaining > 0:
                    radius = min(500, remaining * 1.2) / 1.35
                    disks.append(point.buffer(radius, quad_segs=8))
            area = unary_union(disks)
            simplified = area.simplify(15, preserve_topology=True)
            geographic = transform(lambda x, y: (x / east + origin[0], y / north + origin[1]), simplified)
            series.append(dict(geometry=mapping(geographic), area=round(area.area / 1e6, 3)))
        result[str(minutes)] = series
    return result


def build_intro():
    """본문·노트북과 같은 A–E 시간표를 종료 라운드까지 기록합니다.

    설명에 필요한 계산만 골라 보여 주되, 시각과 상태는 실제 RAPTOR에서 가져옵니다.
    """
    data = TransitData.from_gtfs(toy_feed(), max_transfer_m=300)
    a, b, c, d = [data.index_of[s] for s in "ABCD"]
    runs = []
    for departure in (28800, 29100):
        result = raptor(data, [(a, 0)], departure, record_steps=True)

        def event(kind, round_number, stop=None):
            return next(s for s in result.steps
                        if s['kind'] == kind and s['round'] == round_number
                        and (stop is None or s.get('stop') == stop))

        scenes = [event('access', 0), event('board', 1, a), event('ride', 1, c),
                  event('walk', 1, d), event('end', 1), event('round', 2),
                  event('end', 2)]
        if result.n_rounds >= 3:
            scenes.extend([event('round', 3), event('end', 3)])
        runs.append(dict(departure=departure, rounds=result.rounds, scenes=scenes))
    return _finite(dict(
        stops=data.stop_ids,
        patterns=[dict(name=p.name, stops=p.stops, arrivals=p.arrivals,
                       departures=p.departures) for p in data.patterns],
        walk=next(seconds for stop, seconds in data.transfers[b] if stop == d),
        runs=runs,
    ))


def build_lesson(data, origins, target):
    """두 실제 경로의 구간만 추려, 작은 네트워크의 전체 계산을 기록합니다.

    시각과 방문 순서는 원본 그대로이며 도보 연결도 원본에서 가져옵니다.
    전체 하남망의 결과와 구분해 '선택 구간 학습 예제'로 표시합니다.
    """
    paths = [journey(data, raptor(data, origins, 28800, max_rounds=k), target)
             for k in (1, 2)]
    direct = next(l for l in paths[0] if l['kind'] == 'transit')
    bus, rail = [l for l in paths[1] if l['kind'] == 'transit']
    key_stops = [bus['from'], bus['to'], rail['from'], rail['stop_path'][1],
                 rail['to'], target, direct['from'], direct['to']]
    old_ids = list(dict.fromkeys(key_stops + direct['stop_path']))
    index = {s: i for i, s in enumerate(old_ids)}
    patterns = []
    for leg in (bus, direct, rail):
        for p in data.patterns:
            if p.name != leg['route']:
                continue
            candidates = [b for b in range(len(p.stops))
                          if p.stops[b:b + len(leg['stop_path'])] == leg['stop_path']]
            match = next((b for b in candidates if any(
                dep[b] == leg['board_time'] and arr[b + len(leg['stop_path']) - 1] == leg['alight_time']
                for dep, arr in zip(p.departures, p.arrivals))), None)
            if match is None:
                continue
            end = match + len(leg['stop_path'])
            cropped = Pattern(p.route_id, p.name, p.route_type,
                              [index[s] for s in leg['stop_path']],
                              [a[match:end] for a in p.arrivals],
                              [d[match:end] for d in p.departures])
            cropped.build_index()
            patterns.append(cropped)
            break
        else:
            raise ValueError(f"원본 시간표에서 {leg['route']} 구간을 찾지 못했습니다.")
    routes_by_stop = [[] for _ in old_ids]
    for pi, p in enumerate(patterns):
        for pos, s in enumerate(p.stops):
            routes_by_stop[s].append((pi, pos))
    transfers = [[] for _ in old_ids]
    for path in paths:
        for leg in path:
            if leg['kind'] == 'transfer':
                edge = (index[leg['to']], leg['seconds'])
                assert (leg['to'], leg['seconds']) in data.transfers[leg['from']]
                if edge not in transfers[index[leg['from']]]:
                    transfers[index[leg['from']]].append(edge)
    subset = TransitData(
        [data.stop_ids[s] for s in old_ids], [data.stop_names[s] for s in old_ids],
        [data.stop_lats[s] for s in old_ids], [data.stop_lons[s] for s in old_ids],
        patterns, routes_by_stop, transfers,
    )
    access = [(index[s], seconds) for s, seconds in origins
              if s in (bus['from'], direct['from'])]
    runs = []
    visible = set(range(len(key_stops)))
    for departure in (28800, 29100):
        result = raptor(subset, access, departure, record_steps=True)
        steps = []
        for i, event in enumerate(result.steps):
            event = dict(event, before=result.steps[max(0, i - 1)]['times'])
            if event['kind'] == 'round':
                steps.extend([dict(event, kind='copy'), dict(event, kind='queue')])
            elif event['kind'] in ('access', 'pattern', 'end') or event.get('stop') in visible:
                steps.append(event)
            if event['kind'] == 'end' and event['round'] == 1:
                steps.append(dict(event, kind='gate', stop=index[rail['from']]))
        runs.append(dict(departure=departure, rounds=result.rounds, steps=steps))
    return _finite(dict(
        stops=list(zip(subset.stop_ids, subset.stop_names)), visible=list(range(8)),
        patterns=[dict(name=p.name, type=p.route_type, stops=p.stops,
                       arrivals=p.arrivals, departures=p.departures) for p in patterns],
        walks=[(s, t, seconds) for s, rows in enumerate(transfers) for t, seconds in rows],
        access=access, target=index[target], runs=runs,
    ))


def build_payload():
    feed = load_gtfs("hanam")
    data = TransitData.from_gtfs(feed)
    origin = [127.2148, 37.5393]
    origins = data.access_stops(origin[1], origin[0])
    runs = []
    for departure in (7 * 3600, 8 * 3600, 8 * 3600 + 300, 8 * 3600 + 1800, 23 * 3600):
        result = raptor(data, origins, departure)
        parents = []
        for (k, stop), entry in sorted(result.parent.items()):
            if entry[0] == "ride":
                _, pi, trip, board, alight = entry
                p = data.patterns[pi]
                # Use the chosen trip's actual times from the feed.
                parents.append([k, stop, "ride", pi, board, alight,
                                p.departures[trip][board], p.arrivals[trip][alight]])
            else:
                parents.append([k, stop, *entry])
        runs.append(dict(departure=departure, parents=parents, rounds=[
            [None if math.isinf(t) else int(t) for t in row] for row in result.rounds
        ], isochrones=build_isochrones(data, result.rounds, departure, origin)))
    target = data.nearest_stop(37.5606, 127.1930)
    destinations = [
        (target, "미사역 부근"),
        (data.index_of["BS_1100_123000017"], "천호역·풍납시장"),
        (data.index_of["BS_1100_123000002"], "잠실역·잠실대교남단"),
        (data.index_of["BS_1100_124000077"], "강동경희대병원"),
        (data.index_of["BS_TAGO_GGB227000209"], "하남풍산역"),
    ]
    geo = json.loads(data_path("hanam/boundary.geojson").read_text())
    roads = _builder_roads(load_road_graph("hanam"))
    return dict(
        origin=origin, target=target, destinations=destinations,
        intro=build_intro(), lesson=build_lesson(data, origins, target),
        stops=list(zip(data.stop_ids, data.stop_names, data.stop_lons, data.stop_lats)),
        patterns=[dict(name=p.name, type=p.route_type, stops=p.stops)
                  for p in data.patterns],
        runs=runs, counts=data.describe(), routes=len(feed["routes"]),
        boundary=_boundary(shape(geo["features"][0]["geometry"])),
        roads=[[r[1], r[3]] for r in roads],
    )


def main():
    base = ROOT / "smartmob/viz"
    page = (base / "raptor_rounds.html").read_text(encoding="utf-8")
    page = page.replace("__LESSON__", (base / "raptor_lesson.html").read_text(encoding="utf-8"))
    page = page.replace("__INTRO__", (base / "raptor_intro.html").read_text(encoding="utf-8"))
    page = page.replace("__LESSON_SCRIPT__", (base / "raptor_lesson_script.html").read_text(encoding="utf-8"))
    page = page.replace("__INTRO_SCRIPT__", (base / "raptor_intro_script.html").read_text(encoding="utf-8"))
    page = page.replace("__ACCESSIBILITY__", (base / "raptor_accessibility.html").read_text(encoding="utf-8"))
    payload = json.dumps(build_payload(), ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).replace("<", "\\u003c")
    vendor = base / "vendor/maplibre-gl"
    library = (vendor / "maplibre-gl.js").read_text(encoding="utf-8")
    library = library.split("//# sourceMappingURL=")[0].replace("</script", "<\\/script")
    license_text = (vendor / "LICENSE.txt").read_text(encoding="utf-8").replace("--", "—")
    page = page.replace("__MAPLIBRE__", "<!-- MapLibre GL JS 5.6.0\n" + license_text
                        + "\n--><style>" + (vendor / "maplibre-gl.css").read_text()
                        + "</style><script>" + library + "</script>")
    page = page.replace("__DATA__", payload)
    target = ROOT / "_static/ch06_raptor.html"
    target.write_text(page, encoding="utf-8")
    print(f"{target} · {target.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
