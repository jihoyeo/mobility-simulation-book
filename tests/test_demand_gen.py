"""수요 재표집의 결합 관계와 포아송 발생의 단위·변동을 확인합니다."""
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from smartmob.data import load_demand
from smartmob.teaching.demand_gen import (
    bootstrap_demand, generate_poisson_demand, sample_poisson_times,
)


def test_bootstrap_preserves_whole_rows_without_mutating_source():
    base = load_demand("hanam")
    before = base.copy(deep=True)
    out = bootstrap_demand(base, seed=42)
    assert len(out) == len(base)
    assert out.id.tolist() == list(range(len(base)))
    assert out.request_time.is_monotonic_increasing
    cols = [c for c in base.columns if c != "id"]
    originals = set(base[cols].itertuples(index=False, name=None))
    assert all(row in originals for row in out[cols].itertuples(index=False, name=None))
    assert out[cols].duplicated().any()
    pd.testing.assert_frame_equal(base, before)
    pd.testing.assert_frame_equal(out, bootstrap_demand(base, seed=42))


def test_poisson_partial_hours_and_zero_weights():
    weights = [0.0] * 24
    weights[18] = weights[19] = 1
    # 18:30~20:00의 기대 건수를 1:2로 나누어야 합니다.
    times = sample_poisson_times(30000, np.random.default_rng(14), weights, (1110, 1200))
    assert all(1110 <= t < 1200 for t in times)
    first = sum(t < 1140 for t in times)
    assert .31 < first / len(times) < .36
    assert times == sorted(times)
    assert sample_poisson_times(0, np.random.default_rng(14), weights) == []


def test_poisson_count_moments_match_expected_count():
    rng = np.random.default_rng(18)
    counts = np.array([len(sample_poisson_times(10, rng, None, (480, 540)))
                       for _ in range(5000)])
    assert abs(counts.mean() - 10) < .2
    assert abs(counts.var(ddof=1) - 10) < .7


@pytest.mark.parametrize("mean,weights,window", [
    (-1, None, (0, 60)), (float("nan"), None, (0, 60)),
    (10, [0]*24, (0, 60)), (10, [1]*23, (0, 60)),
    (10, [-1]*24, (0, 60)), (10, [float("inf")]*24, (0, 60)),
    (10, None, (60, 60)), (10, None, (0, 1441)),
])
def test_invalid_poisson_inputs(mean, weights, window):
    with pytest.raises(ValueError):
        sample_poisson_times(mean, np.random.default_rng(1), weights, window)


def test_generated_poisson_requests_and_empty_realization():
    boundary = box(127.1, 37.5, 127.2, 37.6)
    out = generate_poisson_demand(boundary=boundary, expected_n=50, seed=9)
    assert len(out) > 0
    assert out.request_time.between(1080, 1439).all()
    assert out.id.is_unique
    assert out.origin_lon.between(127.1, 127.2).all()
    pd.testing.assert_frame_equal(out, generate_poisson_demand(boundary=boundary, expected_n=50, seed=9))
    empty = generate_poisson_demand(boundary=boundary, expected_n=0)
    assert empty.empty and list(empty.columns) == list(out.columns)
