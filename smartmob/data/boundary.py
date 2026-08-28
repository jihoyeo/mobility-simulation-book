"""시군구 경계.

기말 프로젝트에서 대상지를 정할 때 씁니다. 전국 시군구 경계가 저장소에 들어 있어
서버 없이도 자기 동네를 잘라 낼 수 있습니다.

    from smartmob.data import list_sigungu, load_sigungu

    load_sigungu("하남시")          # shapely Polygon
    list_sigungu("성남")            # 이름으로 찾기

특별시·광역시·특별자치시는 통짜 폴리곤 하나이고, 도는 시·군 단위입니다.
일반구(예: 성남시 수정구)는 시로 합쳐져 있으므로 더 좁게 자르려면 직접 폴리곤을 그려야 합니다.
"""

from __future__ import annotations

import json
from functools import lru_cache

CATALOG = "kr_sigungu.geojson"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    from smartmob.data.paths import data_path

    return json.loads(data_path(CATALOG).read_text(encoding="utf-8"))


def list_sigungu(contains: str | None = None) -> list[str]:
    """시군구 이름 목록. ``contains`` 를 주면 그 글자가 든 것만 냅니다."""
    names = [f["properties"]["name"] for f in _catalog()["features"]]
    if contains:
        names = [n for n in names if contains in n]
    return sorted(names)


def load_sigungu(name: str):
    """이름으로 경계 폴리곤을 찾습니다.

    정확히 일치하는 이름이 없으면 부분 일치를 시도하고, 후보가 여럿이면 알려 줍니다.
    """
    from shapely.geometry import shape

    features = _catalog()["features"]
    exact = [f for f in features if f["properties"]["name"] == name]
    if exact:
        return shape(exact[0]["geometry"])

    partial = [f for f in features if name in f["properties"]["name"]]
    if len(partial) == 1:
        return shape(partial[0]["geometry"])
    if len(partial) > 1:
        found = ", ".join(f["properties"]["name"] for f in partial)
        raise ValueError(f"'{name}' 에 해당하는 시군구가 여럿입니다: {found}")

    hint = ", ".join(list_sigungu()[:5])
    raise KeyError(f"'{name}' 을 찾지 못했습니다. list_sigungu() 로 목록을 보세요. 예: {hint} …")


def sigungu_info(name: str) -> dict:
    """경계의 면적과 외접 사각형. 대상지가 적당한 크기인지 가늠할 때 씁니다."""
    import geopandas as gpd

    poly = load_sigungu(name)
    area_km2 = gpd.GeoSeries([poly], crs=4326).to_crs(5179).area.iloc[0] / 1e6
    min_lon, min_lat, max_lon, max_lat = poly.bounds
    return {
        "name": name,
        "area_km2": round(float(area_km2), 1),
        "bounds": {
            "min_lat": round(min_lat, 4), "max_lat": round(max_lat, 4),
            "min_lon": round(min_lon, 4), "max_lon": round(max_lon, 4),
        },
    }
