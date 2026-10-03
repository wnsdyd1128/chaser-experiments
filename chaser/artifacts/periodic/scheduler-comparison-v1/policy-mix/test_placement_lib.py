"""Specification tests for the shared Partitioned placement policies.

Run from the c3 code copy with PYTHONPATH set to it (the regression test imports hl_set).
"""
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))

from placement_lib import (BALANCE_SLACK, CLS_LOW, CORE_CAP, TRAFFIC_HIGH, Item, cls_grouped, cls_grouped_balanced,
                           cohort_cost, is_high_traffic, is_low_cls, place, release_aware, release_aware_grouped,
                           traffic_grouped, wfd)


def items(us, periods=None, traffic=None, cls=None):
    periods = periods or [40] * len(us)
    traffic = traffic or [1.0] * len(us)
    cls = cls or [0.9] * len(us)
    return [Item(u=u, period=p, traffic=r, cls=c) for u, p, r, c in zip(us, periods, traffic, cls)]


def core_loads(assign, tasks, cores=4):
    return [sum(t.u for t, c in zip(tasks, assign) if c == core) for core in range(cores)]


def test_wfd_places_the_largest_task_first_on_the_least_loaded_core():
    assert wfd(items([0.1, 0.4, 0.3, 0.2, 0.05])) == [3, 0, 1, 2, 3]


def test_traffic_above_the_per_core_share_of_l2_bandwidth_is_high():
    assert not is_high_traffic(Item(u=0.1, period=40, traffic=TRAFFIC_HIGH))
    assert is_high_traffic(Item(u=0.1, period=40, traffic=TRAFFIC_HIGH * 1.01))


def test_traffic_grouping_packs_high_traffic_tasks_onto_the_fewest_cores_under_the_cap():
    tasks = items([0.3, 0.3, 0.3, 0.2, 0.2, 0.2, 0.2, 0.2], traffic=[14, 14, 14, 1, 1, 1, 1, 1])
    assign = traffic_grouped(tasks)
    assert {assign[i] for i in range(3)} == {0}  # 0.9 fits one core under the 0.95 cap
    assert max(core_loads(assign, tasks)) <= CORE_CAP


def test_traffic_grouping_opens_another_core_when_one_would_exceed_the_cap():
    tasks = items([0.4, 0.4, 0.4, 0.1, 0.1], traffic=[14, 14, 14, 1, 1])
    assign = traffic_grouped(tasks)
    assert len({assign[i] for i in range(3)}) == 2


def test_traffic_grouping_without_high_traffic_tasks_is_wfd():
    tasks = items([0.1, 0.4, 0.3, 0.2, 0.05])
    assert traffic_grouped(tasks) == wfd(tasks)


def test_cohort_cost_sums_the_busiest_core_released_work_over_one_hyperperiod():
    tasks = items([0.5, 0.25, 0.5], periods=[20, 40, 40])
    # releases at 0 (all) and 20 (the 20 ms task); work = U x period
    assert cohort_cost([0, 1, 1], tasks, cores=2) == pytest.approx(max(10, 10 + 20) + 10)


def test_cohort_cost_penalizes_a_core_above_the_cap():
    tasks = items([0.6, 0.6])
    assert cohort_cost([0, 0], tasks, cores=2) > 1e5


def test_release_aware_reproduces_the_informed_placement_of_experiment_9():
    import hl_set
    for set_id in range(3):
        for load, heaviness in ((0.5, 'light'), (0.85, 'heavy')):
            periods = hl_set.periods(set_id)
            targets = hl_set.utilizations(load, heaviness, set_id)
            sweeps = [hl_set.sweeps(u, p) for u, p in zip(targets, periods)]
            us = [hl_set.planned_u(s, p) for s, p in zip(sweeps, periods)]
            expected = hl_set.informed(us, periods, hl_set.SEED_BASE + set_id)
            assert release_aware(items(us, periods), seed=hl_set.SEED_BASE + set_id) == expected


def test_combined_policy_keeps_high_traffic_tasks_on_the_cores_traffic_grouping_chose():
    tasks = items([0.2, 0.2, 0.2, 0.15, 0.1, 0.1, 0.1, 0.1], periods=[20, 40, 80, 20, 40, 80, 20, 40],
                  traffic=[14, 14, 14, 1, 1, 1, 1, 1])
    grouped = traffic_grouped(tasks)
    combined = release_aware_grouped(tasks, seed=1)
    assert {combined[i] for i in range(3)} <= {grouped[i] for i in range(3)}
    assert cohort_cost(combined, tasks) <= cohort_cost(grouped, tasks)
    assert max(core_loads(combined, tasks)) <= CORE_CAP


def test_combined_policy_without_high_traffic_tasks_is_release_aware():
    tasks = items([0.2, 0.15, 0.1, 0.3, 0.25, 0.1], periods=[20, 40, 80, 20, 40, 80])
    assert release_aware_grouped(tasks, seed=7) == release_aware(tasks, seed=7)


def test_cls_at_the_threshold_counts_as_low():
    assert is_low_cls(Item(u=0.1, period=40, traffic=1.0, cls=CLS_LOW))
    assert not is_low_cls(Item(u=0.1, period=40, traffic=1.0, cls=CLS_LOW + 0.01))


def test_cls_grouping_packs_low_cls_tasks_even_when_their_traffic_is_low():
    tasks = items([0.3, 0.3, 0.3, 0.2, 0.2, 0.2, 0.2, 0.2], traffic=[4, 4, 4, 14, 1, 1, 1, 1],
                  cls=[0.13, 0.13, 0.13, 0.9, 0.9, 0.9, 0.9, 0.9])
    assign = cls_grouped(tasks)
    assert {assign[i] for i in range(3)} == {0}
    assert traffic_grouped(tasks) != assign  # traffic grouping would pack task 3 instead


def test_cls_grouping_matches_traffic_grouping_when_low_cls_and_high_traffic_coincide():
    tasks = items([0.3, 0.3, 0.3, 0.2, 0.2, 0.2], traffic=[14, 14, 14, 4, 4, 4], cls=[0.13, 0.13, 0.13, 0.9, 0.9, 0.9])
    assert cls_grouped(tasks) == traffic_grouped(tasks)


def test_balanced_cls_grouping_spreads_the_group_so_no_core_exceeds_the_mean_load():
    tasks = items([0.075] * 16, cls=[0.13] * 8 + [0.9] * 8)
    assign = cls_grouped_balanced(tasks)
    assert {assign[i] for i in range(8)} == {0, 1}  # 0.6 of low-CLS U over two cores at the 0.3 mean
    assert {assign[i] for i in range(8, 16)} == {2, 3}
    assert max(core_loads(assign, tasks)) <= 0.3 * (1 + BALANCE_SLACK)
    assert max(core_loads(cls_grouped(tasks), tasks)) == pytest.approx(0.6)  # packing puts all eight on core 0


def test_balanced_cls_grouping_lets_one_large_low_cls_task_exceed_the_mean():
    tasks = items([0.5, 0.1, 0.1, 0.1, 0.1, 0.1], cls=[0.1, 0.1, 0.9, 0.9, 0.9, 0.9])
    assign = cls_grouped_balanced(tasks)
    assert assign[0] != assign[1]  # 0.5 alone already exceeds the 0.25 mean; the other member needs a core
    assert max(core_loads(assign, tasks)) == pytest.approx(0.5)


def test_release_aware_within_balanced_cls_grouping_keeps_the_group_on_its_cores():
    tasks = items([0.075] * 16, periods=[20, 40, 80, 40] * 4, cls=[0.13] * 8 + [0.9] * 8)
    grouped, combined = cls_grouped_balanced(tasks), place('ra-cgb', tasks, seed=3)
    assert {combined[i] for i in range(8)} <= {grouped[i] for i in range(8)}
    assert cohort_cost(combined, tasks) <= cohort_cost(grouped, tasks)


def test_release_aware_within_cls_grouping_keeps_low_cls_tasks_on_the_grouped_cores():
    tasks = items([0.2, 0.2, 0.2, 0.15, 0.1, 0.1, 0.1, 0.1], periods=[20, 40, 80, 20, 40, 80, 20, 40],
                  cls=[0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.9])
    grouped, combined = cls_grouped(tasks), place('ra-cg', tasks, seed=1)
    assert {combined[i] for i in range(3)} <= {grouped[i] for i in range(3)}
    assert cohort_cost(combined, tasks) <= cohort_cost(grouped, tasks)
