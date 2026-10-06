"""Specification tests for the small-memory design (run from the c3 copy, PYTHONPATH set)."""
from collections import Counter
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import smallmem_set as sm
from placement_lib import CLS_LOW, TRAFFIC_HIGH

SAMPLE = range(0, sm.SETS, 4)
LOAD = sm.LOADS[0]


def tasks(cell, set_id, placement='wfd'):
    return sm.configuration(LOAD, cell, set_id, placement)['tasks']


def test_every_task_count_in_range_appears_equally_often():
    counts = Counter(sm.task_count(k) for k in range(sm.SETS))
    assert set(counts) == set(range(sm.TASK_RANGE[0], sm.TASK_RANGE[1] + 1))
    assert max(counts.values()) == min(counts.values())


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_shares_share_periods_and_period_cvs_share_low_tasks(set_id):
    for cv in sm.PERIOD_CVS:
        same_cv = [tasks(h, set_id) for h in sm.HEAVINESS if sm.cell(h)['period_cv'] == cv]
        assert all([t['period_ticks'] for t in ts] == [t['period_ticks'] for t in same_cv[0]] for ts in same_cv)
    for share in sm.LOW_SHARES:
        same_low = [tasks(h, set_id) for h in sm.HEAVINESS if sm.cell(h)['low_share'] == share]
        assert all([t['role'] for t in ts] == [t['role'] for t in same_low[0]] for ts in same_low)
        assert all(len(ts) == sm.task_count(set_id) for ts in same_low)


def test_zero_period_cv_gives_every_task_the_mean_period():
    assert {t['period_ticks'] for t in tasks('cv00-low25', 3)} == {sm.MU}


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_tasks_nest_and_hold_about_their_share_of_u(set_id):
    low = {share: {i for i, t in enumerate(tasks(f'cv10-low{round(share * 100):02d}', set_id)) if t['role'] == 'low'}
           for share in sm.LOW_SHARES}
    assert low[0.0] == set() and low[0.25] <= low[0.5]
    for share in (0.25, 0.5):
        ts = tasks(f'cv10-low{round(share * 100):02d}', set_id)
        realized = sum(t['u_planned'] for t in ts if t['role'] == 'low') / sum(t['u_planned'] for t in ts)
        largest = max(t['u_planned'] for t in ts) / sum(t['u_planned'] for t in ts)
        assert abs(realized - share) <= largest  # within one task's share of the target


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_tasks_are_small_memory_bound_and_the_only_cls_group(set_id):
    for t in tasks('cv20-low50', set_id):
        if t['role'] == 'low':
            assert t['cls_planned'] <= CLS_LOW and t['traffic_planned'] > TRAFFIC_HIGH
            assert t['footprint_kib'] <= 64  # a 32 KiB cold region, no 768 KiB arrays
        else:
            assert t['role'] == 'high' and t['cls_planned'] > CLS_LOW


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('cell', ('cv00-low50', 'cv30-low50'))
def test_planned_utilization_meets_the_nominal_load(set_id, cell):
    assert sum(t['u_planned'] for t in tasks(cell, set_id)) == pytest.approx(LOAD * sm.CORES, rel=0.02)


def test_job_budgets_stay_inside_the_copied_model_check_range_of_their_family():
    for k in range(sm.SETS):
        for h in sm.HEAVINESS:
            roles = sm.roles(h, k)
            for role, budget in zip(roles, sm.budgets(LOAD, sm.cell(h)['period_cv'], k)):
                low, high = sm.MODEL_CHECK_NS[role]
                assert low <= budget <= high, (h, k, role, budget)


def test_placements_differ_only_in_cores():
    configs = [sm.configuration(LOAD, 'cv20-low25', 7, p) for p in sm.PLACEMENTS]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)
