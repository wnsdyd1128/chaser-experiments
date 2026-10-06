"""Specification tests for the small-memory load design (run from the c3 copy, PYTHONPATH set)."""
from collections import Counter
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loadmem_set as lm
from placement_lib import CLS_LOW, TRAFFIC_HIGH

SAMPLE = range(0, lm.SETS, 4)


def tasks(load, cell, set_id, placement='wfd'):
    return lm.configuration(load, cell, set_id, placement)['tasks']


def test_every_task_count_in_range_appears_equally_often():
    counts = Counter(lm.task_count(k) for k in range(lm.SETS))
    assert set(counts) == set(range(lm.TASK_RANGE[0], lm.TASK_RANGE[1] + 1))
    assert max(counts.values()) == min(counts.values())


@pytest.mark.parametrize('set_id', SAMPLE)
def test_loads_share_periods_and_low_tasks_and_scale_only_the_budgets(set_id):
    for cell in lm.HEAVINESS:
        same = [tasks(load, cell, set_id) for load in lm.LOADS]
        assert all([t['period_ticks'] for t in ts] == [t['period_ticks'] for t in same[0]] for ts in same)
        assert all([t['role'] for t in ts] == [t['role'] for t in same[0]] for ts in same)
        assert all(len(ts) == lm.task_count(set_id) for ts in same)


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_tasks_nest_across_shares_and_hold_about_their_share_of_u(set_id):
    load = lm.LOADS[0]
    low = {s: {i for i, t in enumerate(tasks(load, f'cv20-low{round(s * 100):02d}', set_id)) if t['role'] == 'low'}
           for s in lm.LOW_SHARES}
    assert low[0.25] <= low[0.5]
    for s in lm.LOW_SHARES:
        ts = tasks(load, f'cv20-low{round(s * 100):02d}', set_id)
        realized = sum(t['u_planned'] for t in ts if t['role'] == 'low') / sum(t['u_planned'] for t in ts)
        largest = max(t['u_planned'] for t in ts) / sum(t['u_planned'] for t in ts)
        assert abs(realized - s) <= largest


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_tasks_are_small_memory_bound_and_the_only_cls_group(set_id):
    for t in tasks(max(lm.LOADS), 'cv20-low50', set_id):
        if t['role'] == 'low':
            assert t['cls_planned'] <= CLS_LOW and t['traffic_planned'] > TRAFFIC_HIGH and t['footprint_kib'] <= 64
        else:
            assert t['cls_planned'] > CLS_LOW


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('load', lm.LOADS)
def test_planned_utilization_meets_each_nominal_load(set_id, load):
    assert sum(t['u_planned'] for t in tasks(load, 'cv00-low50', set_id)) == pytest.approx(load * lm.CORES, rel=0.02)


def test_job_budgets_stay_inside_the_copied_model_check_range_of_their_family():
    for k in range(lm.SETS):
        for h in lm.HEAVINESS:
            for load in lm.LOADS:
                for role, budget in zip(lm.roles(h, k), lm.budgets(load, lm.cell(h)['period_cv'], k)):
                    low, high = lm.MODEL_CHECK_NS[role]
                    assert low <= budget <= high, (h, k, load, role, budget)


def test_placements_differ_only_in_cores():
    configs = [lm.configuration(0.55, 'cv20-low25', 7, p) for p in lm.PLACEMENTS]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)
