"""Specification of the cache-affinity task-set generator."""

import pytest

from chaser.periodic.measurement import make_plan
import affinity


def test_mean_lines_split_the_per_core_l1_share_over_four_tasks():
    assert [affinity.mean_lines(level) for level in affinity.WS_LEVELS] == [32, 64, 128, 192]


def test_period_is_the_shortest_whole_tick_keeping_task_u_at_most_the_cap():
    assert affinity.period_ticks(25, 2) == 1
    assert affinity.period_ticks(50, 8) == 1
    assert affinity.period_ticks(50, 32) == 2
    assert affinity.period_ticks(100, 32) == 4
    assert affinity.period_ticks(150, 8) == 2
    assert affinity.period_ticks(150, 32) == 5
    for level in affinity.WS_LEVELS:
        for sweeps in affinity.SWEEPS:
            job = affinity.planned_job_ns(affinity.mean_lines(level), sweeps)
            assert job / (affinity.period_ticks(level, sweeps) * 1e6) <= affinity.U_CAP


def test_one_tick_periods_keep_task_u_at_most_the_one_tick_cap():
    # One-tick G/C runs missed deadlines at a planned per-core U of 0.40.
    assert affinity.period_ticks(25, 32) == 2
    assert affinity.period_ticks(100, 8) == 2
    for level in affinity.WS_LEVELS:
        for sweeps in affinity.SWEEPS:
            if affinity.period_ticks(level, sweeps) == 1:
                job = affinity.planned_job_ns(affinity.mean_lines(level), sweeps)
                assert job / 1e6 <= affinity.U_CAP_ONE_TICK


def test_task_lines_are_seeded_within_jitter_and_shared_across_conditions():
    first = affinity.task_lines(100, 3)
    assert first == affinity.task_lines(100, 3)
    assert first != affinity.task_lines(100, 4)
    assert all(96 <= lines <= 160 for lines in first)
    scale = [a / b for a, b in zip(affinity.task_lines(50, 3), affinity.task_lines(150, 3))]
    assert max(scale) - min(scale) < 0.05


@pytest.mark.parametrize('level', affinity.WS_LEVELS)
@pytest.mark.parametrize('sweeps', affinity.SWEEPS)
def test_configurations_are_valid_contiguous_per_core_plans(level, sweeps):
    config = affinity.configuration(level, sweeps, 0)
    plans = [make_plan(config, a) for a in range(3)]
    tasks = plans[2]['tasks']
    assert [t['core'] for t in tasks] == [i // 4 for i in range(16)]
    assert plans[0]['warmup_jobs'] == plans[0]['measurement_jobs'] == 160
    assert all(t['pattern'] == 'cyclic' and t['stride'] == 32 and t['sweeps'] == sweeps for t in tasks)
    assert len({t['period_ticks'] for t in tasks}) == 1
