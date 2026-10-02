"""Specification tests for the static task-set representations of the feature pre-check."""
import pytest

from taskset_features import (TRAFFIC_HIGH, Task, best_choice, bow, r0_cls, regret,
                              release_structure, task_type)


def task(u, cls=0.9, traffic=4.0, footprint_kib=36.0, period_ms=40.0):
    return Task(u=u, period_ms=period_ms, cls=cls, p_l1=cls, p_llc=1 - cls, p_miss=0.0,
                traffic=traffic, footprint_kib=footprint_kib)


def test_swapping_which_tasks_carry_the_large_u_keeps_r0_but_changes_the_bag_of_types():
    high, low = dict(cls=0.9, traffic=4.0), dict(cls=0.13, traffic=14.0)
    a = [task(0.1, **high) for _ in range(8)] + [task(0.025, **low) for _ in range(8)]
    b = [task(0.025, **high) for _ in range(8)] + [task(0.1, **low) for _ in range(8)]
    assert r0_cls(a) == pytest.approx(r0_cls(b))
    assert bow(a) != pytest.approx(bow(b))


@pytest.mark.parametrize('footprint_kib, expected', [(16.0, 0), (16.5, 1), (512.0, 1), (513.0, 2)])
def test_footprint_class_boundaries_are_l1_and_the_per_core_share_of_l2(footprint_kib, expected):
    assert task_type(task(0.1, footprint_kib=footprint_kib))[0] == expected


def test_traffic_at_the_per_core_share_of_l2_bandwidth_still_counts_as_low():
    assert task_type(task(0.1, traffic=TRAFFIC_HIGH))[1] == 0
    assert task_type(task(0.1, traffic=TRAFFIC_HIGH * 1.01))[1] == 1


def test_only_utilization_above_one_half_is_heavy():
    assert task_type(task(0.5))[2] == 0
    assert task_type(task(0.51))[2] == 1


def test_release_structure_of_synchronously_released_tasks():
    tasks = [task(0.25, period_ms=20), task(0.5, period_ms=40), task(0.25, period_ms=30)]
    peak, distinct, harmonic = release_structure(tasks, cores=4)
    assert peak == pytest.approx((5 + 20 + 7.5) / (4 * 20))  # all release at 0; next release at 20 ms
    assert distinct == 3
    assert harmonic == pytest.approx(1 / 3)  # only 20 divides 40


def test_best_choice_takes_lower_tat_then_lower_tet_then_first_option():
    assert best_choice(tat=(100, 95), tet=(50, 60)) == 1
    assert best_choice(tat=(100, 100), tet=(50, 49)) == 1
    assert best_choice(tat=(100, 100), tet=(50, 50)) == 0


def test_regret_is_the_relative_excess_over_the_best_option():
    assert regret((100.0, 95.0), 0) == pytest.approx(100 / 95 - 1)
    assert regret((100.0, 95.0), 1) == 0.0
