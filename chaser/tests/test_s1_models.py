import pytest

from chaser.locality.cache_reference import CacheLevel, FirstHits, simulate
from chaser.locality.estimators import global_rd, csrd_counts, compare


def test_cold_empty_and_lru_refresh():
    l1 = CacheLevel(2, 1, 2)
    llc = CacheLevel(4, 1, 4)
    assert simulate([], l1, llc) == FirstHits(0, 0, 0)
    assert simulate([], l1, llc).ratios is None
    # Touch 0 before inserting 2: L1 evicts 1, not 0.
    assert simulate([0, 1, 0, 2, 0, 1], l1, llc) == FirstHits(2, 1, 3)


@pytest.mark.parametrize('distinct', [3, 4, 5, 8])
def test_associativity_boundary_and_distributed_pair(distinct):
    l1, llc = CacheLevel(16, 1, 4), CacheLevel(128, 1, 4)
    conflict = [i * 4 for i in range(distinct)] * 3
    spread = list(range(distinct)) * 3
    expected = FirstHits(2 * distinct, 0, distinct) if distinct <= 4 else FirstHits(0, 2 * distinct, distinct)
    assert simulate(conflict, l1, llc) == expected
    assert simulate(spread, l1, llc) == FirstHits(2 * distinct, 0, distinct)


def test_llc_sees_only_l1_misses_and_no_back_invalidation():
    assert simulate([0, 4, 0], CacheLevel(2, 1, 2), CacheLevel(4, 1, 1)) == FirstHits(1, 0, 2)
    l1, llc = CacheLevel(2, 1, 1), CacheLevel(4, 1, 4)
    # An L1 hit must not refresh LLC recency; the final 0 was evicted from LLC.
    assert simulate([0, 1, 0, 2, 3, 4, 0], l1, llc) == FirstHits(1, 0, 6)
    assert global_rd({'cold_misses': 5, 'histogram': {'1': 1, '3': 1}}, l1, llc) == FirstHits(1, 1, 5)


def test_global_rd_thresholds_include_cold_in_denominator():
    result = global_rd({'cold_misses': 2, 'histogram': {'0': 1, '1': 2, '2': 3, '3': 4, '4': 5}},
                       CacheLevel(2, 1, 1), CacheLevel(4, 1, 1))
    assert result == FirstHits(3, 7, 7)
    assert result.ratios == pytest.approx((3 / 17, 7 / 17, 7 / 17))
    assert global_rd({'cold_misses': 0, 'histogram': {}}, CacheLevel(1, 1, 1),
                     CacheLevel(2, 1, 1)).ratios is None


def test_csrd_threshold_and_llc_population():
    l1, llc = CacheLevel(4, 1, 2), CacheLevel(8, 1, 2)
    task = {'modeled_accesses': 7,
            'l1': {'lookups': 7, 'cold_misses': 3, 'csrd_histogram': {'1': 2, '2': 2}},
            'llc': {'lookups': 5, 'cold_misses': 3, 'csrd_histogram': {'1': 1, '2': 1}}}
    assert csrd_counts(task, l1, llc) == FirstHits(2, 1, 4)
    task['llc']['lookups'] = 4
    with pytest.raises(ValueError, match='population'):
        csrd_counts(task, l1, llc)


def test_error_metrics_and_incomparable_populations():
    error = compare(FirstHits(3, 0, 1), FirstHits(1, 2, 1))
    assert error['absolute_error'] == [0.5, 0.5, 0.0]
    assert error['mae'] == pytest.approx(1 / 3)
    assert error['rmse'] == pytest.approx((0.5 / 3) ** 0.5)
    assert error['max_absolute_error'] == 0.5
    assert compare(FirstHits(0, 0, 0), FirstHits(0, 0, 0)) is None
    with pytest.raises(ValueError, match='population'):
        compare(FirstHits(1, 0, 0), FirstHits(0, 0, 2))


@pytest.mark.parametrize('args', [(0, 1, 1), (4, 0, 1), (4, 1, 0), (5, 2, 1), (4, 1, 3), (True, 1, 1)])
def test_invalid_geometry(args):
    with pytest.raises(ValueError):
        CacheLevel(*args)


@pytest.mark.parametrize('profile', [
    {'cold_misses': -1, 'histogram': {}},
    {'cold_misses': True, 'histogram': {}},
    {'cold_misses': 1, 'histogram': {'-1': 2}},
    {'cold_misses': 1, 'histogram': {'0': -1}},
    {'cold_misses': 1, 'histogram': {'0': 1.5}},
])
def test_invalid_histogram(profile):
    with pytest.raises(ValueError):
        global_rd(profile, CacheLevel(2, 1, 1), CacheLevel(4, 1, 1))


def test_incompatible_hierarchy_and_invalid_lines():
    with pytest.raises(ValueError):
        simulate([0], CacheLevel(4, 1, 1), CacheLevel(8, 2, 1))
    with pytest.raises(ValueError):
        simulate([-1], CacheLevel(4, 1, 1), CacheLevel(8, 1, 1))
