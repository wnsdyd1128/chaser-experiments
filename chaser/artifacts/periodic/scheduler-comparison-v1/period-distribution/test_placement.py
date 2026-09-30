"""Specification of the cohort-aware P placement."""

from itertools import permutations

import placement
import taskset


def test_cohort_cost_sums_the_busiest_core_per_release_instant():
    # Window 4 has release instants t=0 (all tasks) and t=2 (period-2 tasks);
    # each released job weighs its period.
    periods = [2, 4, 2, 4]
    assert placement.cohort_cost(periods, [0, 0, 1, 1], 4) == 6 + 2
    assert placement.cohort_cost(periods, [0, 1, 0, 1], 4) == 8 + 4
    assert placement.cohort_cost(periods, [0, 1, 2, 3], 4) == 4 + 2


def test_local_search_matches_exhaustive_optimum_on_small_sets():
    for periods in ([2, 3, 4, 6, 6, 12, 12, 4], [3, 3, 3, 6, 6, 9, 18, 18]):
        window = 36
        best = min(placement.cohort_cost(periods, list(cores), window)
                   for cores in set(permutations([0, 0, 1, 1, 2, 2, 3, 3])))
        cores = placement.cohort_cores(periods, window)
        assert sorted(cores) == [0, 0, 1, 1, 2, 2, 3, 3]
        assert placement.cohort_cost(periods, cores, window) == best


def test_placement_is_deterministic_and_never_worse_than_snake():
    for cv in (0.1, 0.2, 0.3):
        for set_id in taskset.set_ids(cv):
            periods = taskset.periods(taskset.REFERENCE_MEAN, cv,
                                      taskset.standard_draws(taskset.SEED_BASE + set_id))
            cores = placement.cohort_cores(periods, taskset.GRID)
            assert cores == placement.cohort_cores(periods, taskset.GRID)
            assert [cores.count(c) for c in range(4)] == [4] * 4
            assert (placement.cohort_cost(periods, cores, taskset.GRID)
                    <= placement.cohort_cost(periods, taskset.assign_cores(periods),
                                             taskset.GRID))
