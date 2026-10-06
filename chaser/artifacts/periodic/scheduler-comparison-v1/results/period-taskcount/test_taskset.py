"""Specification of the normal-period task-set generator."""

import math

import pytest

from chaser.periodic.measurement import make_plan
import taskset


def test_standard_draws_are_seeded_and_truncated_at_three_sigma():
    first = taskset.standard_draws(7)
    assert first == taskset.standard_draws(7)
    assert first != taskset.standard_draws(8)
    assert len(first) == taskset.TASKS
    assert all(-3 <= z <= 3 for z in first)


def test_quantize_picks_log_nearest_grid_divisor_scaled_by_unit():
    assert taskset.quantize(17, 20) == 18
    assert taskset.quantize(13, 20) == 12
    assert taskset.quantize(68, 80) == 72
    assert taskset.quantize(2.1, 20) == 2
    assert taskset.quantize(52, 50) == 50


def test_zero_cv_gives_the_mean_for_every_task():
    assert taskset.periods(20, 0.0, taskset.standard_draws(0)) == [20] * taskset.TASKS


def test_relative_periods_are_identical_across_means():
    draws = taskset.standard_draws(3)
    base = [p // taskset.unit(20) for p in taskset.periods(20, 0.3, draws)]
    for mean in taskset.MEANS:
        assert taskset.periods(mean, 0.3, draws) == [taskset.unit(mean) * p for p in base]


def test_means_are_20_50_80_100_500_on_integer_units():
    assert taskset.MEANS == (20, 50, 80, 100, 500)
    assert [taskset.unit(mean) for mean in taskset.MEANS] == [2, 5, 8, 10, 50]


def test_mean_must_be_a_multiple_of_the_reference_mean():
    with pytest.raises(ValueError):
        taskset.periods(25, 0.1, taskset.standard_draws(0))


def test_snake_assignment_puts_one_task_of_each_rank_group_on_every_core():
    periods = [40, 2, 30, 5, 20, 8, 12, 18, 24, 3, 9, 15, 36, 6, 10, 4]
    cores = taskset.assign_cores(periods)
    assert sorted(cores) == sorted(list(range(4)) * 4)
    order = sorted(range(16), key=lambda i: (periods[i], i))
    for group in range(4):
        assert sorted(cores[i] for i in order[4 * group:4 * group + 4]) == [0, 1, 2, 3]


def test_sweeps_follow_the_isolated_cpu_calibration():
    assert taskset.sweeps(20) == round((2_500_000 - taskset.JOB_BASE_NS) / taskset.SWEEP_NS)
    assert taskset.sweeps(2) < taskset.sweeps(20) < taskset.sweeps(608)


@pytest.mark.parametrize('mean', taskset.MEANS)
@pytest.mark.parametrize('cv', taskset.CVS)
def test_every_design_configuration_is_a_valid_plan(mean, cv):
    for set_id in taskset.set_ids(cv):
        config = taskset.configuration(mean, cv, set_id)
        plans = [make_plan(config, architecture) for architecture in range(3)]
        tasks = plans[0]['tasks']
        assert len(tasks) == taskset.TASKS
        assert [sum(t['core'] == c for t in tasks) for c in range(4)] == [4] * 4
        assert config['warmup_ticks'] * 2 == config['horizon_ticks']
        assert plans[0]['warmup_jobs'] + plans[0]['measurement_jobs'] <= 4096
        for task in tasks:
            predicted = taskset.JOB_BASE_NS + taskset.SWEEP_NS * task['sweeps']
            assert math.isclose(predicted / (task['period_ticks'] * 1e6),
                                taskset.TASK_U, rel_tol=0.02)


def test_zero_cv_has_one_set_and_other_cvs_share_draws():
    assert taskset.set_ids(0.0) == [0]
    assert taskset.set_ids(0.2) == list(range(taskset.SETS))
    low = taskset.configuration(20, 0.1, 5)['period_distribution']['draws']
    high = taskset.configuration(20, 0.3, 5)['period_distribution']['draws']
    assert low == high
