"""smartmob — 『스마트 교통물류』 교재의 실습 헬퍼 패키지.

    from smartmob import Dtumos, load_road_graph

    dt = Dtumos()
    sim = dt.run_simulation(city="hanam", fleet_size=80)
    sim.summary()
"""

__version__ = "0.1.0"

from smartmob.client import (
    Dtumos,
    DtumosError,
    DtumosUnavailable,
    SimulationResult,
)
from smartmob.config import data_dir, dtumos_url, offline

__all__ = [
    "Dtumos",
    "DtumosError",
    "DtumosUnavailable",
    "SimulationResult",
    "data_dir",
    "dtumos_url",
    "load_gtfs",
    "load_road_graph",
    "offline",
]


def __getattr__(name):
    """무거운 것들은 실제로 쓸 때 불러옵니다(pandas import 지연)."""
    if name == "load_road_graph":
        from smartmob.data import load_road_graph

        return load_road_graph
    if name == "load_gtfs":
        from smartmob.data import load_gtfs

        return load_gtfs
    raise AttributeError(name)
