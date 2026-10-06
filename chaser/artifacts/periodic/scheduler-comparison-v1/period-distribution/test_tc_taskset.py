"""Specification of the 12-20 task variant of the normal-period generator."""

from collections import Counter
import math

import pytest

from chaser.periodic.measurement import make_plan
import taskset
import tc_taskset as tc

COUNTS = range(tc.TASK_RANGE[0], tc.TASK_RANGE[1] + 1)


def test_every_task_count_appears_equally_often_and_sets_0_to_8_hold_one_each():
    counts = Counter(tc.task_count(k) for k in range(tc.SETS))
    assert set(counts) == set(COUNTS) and len(set(counts.values())) == 1
    assert [tc.task_count(k) for k in tc.set_ids(0.0)] == list(COUNTS)


def test_per_task_u_keeps_the_per_core_nominal_u_of_experiment_1():
    for k in range(tc.SETS):
        assert tc.task_u(k) * tc.task_count(k) == pytest.approx(taskset.TASK_U * taskset.TASKS)
    assert tc.TASK_U == tc.task_u(0) == max(tc.task_u(k) for k in range(tc.SETS))


def test_draws_are_shared_by_every_mean_and_cv_and_sized_by_the_task_count():
    for k in (0, 5, 13):
        configs = [tc.configuration(mean, cv, k) for mean in tc.MEANS for cv in tc.CVS if cv > 0]
        draws = {tuple(c['period_distribution']['draws']) for c in configs}
        assert len(draws) == 1 and len(next(iter(draws))) == tc.task_count(k)


def test_zero_cv_gives_the_mean_period_to_every_task():
    for k in tc.set_ids(0.0):
        assert {t['period_ticks'] for t in tc.configuration(50, 0.0, k)['tasks']} == {50}


@pytest.mark.parametrize('mean', tc.MEANS)
@pytest.mark.parametrize('cv', tc.CVS)
def test_every_design_configuration_is_a_valid_plan(mean, cv):
    for set_id in tc.set_ids(cv):
        config = tc.configuration(mean, cv, set_id)
        plans = [make_plan(config, architecture) for architecture in range(3)]
        tasks = plans[0]['tasks']
        n = tc.task_count(set_id)
        assert len(tasks) == n
        per_core = [sum(t['core'] == c for t in tasks) for c in range(tc.CORES)]
        assert sum(per_core) == n and max(per_core) - min(per_core) <= 1
        assert config['warmup_ticks'] * 2 == config['horizon_ticks']
        assert plans[0]['warmup_jobs'] + plans[0]['measurement_jobs'] <= 4096
        for task in tasks:
            predicted = tc.JOB_BASE_NS + tc.SWEEP_NS * task['sweeps']
            assert math.isclose(predicted / (task['period_ticks'] * 1e6), tc.task_u(set_id), rel_tol=0.02)
