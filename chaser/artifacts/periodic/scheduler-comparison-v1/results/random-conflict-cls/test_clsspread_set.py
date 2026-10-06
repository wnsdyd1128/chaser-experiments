"""Specification tests for the CLS spread design (run from the c3 copy, PYTHONPATH set)."""
from collections import Counter
from pathlib import Path
import statistics
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import clsspread_set as cs
from placement_lib import CLS_LOW

SAMPLE = range(0, cs.SETS, 4)
LOAD = cs.LOADS[0]


def tasks(cell, set_id, placement='wfd'):
    return cs.configuration(LOAD, cell, set_id, placement)['tasks']


def name(mean, sd, cv):
    return f'cls{round(mean * 100):02d}-sd{round(sd * 100):02d}-cv{round(cv * 100):02d}'


def test_every_task_count_in_range_appears_equally_often():
    counts = Counter(cs.task_count(k) for k in range(cs.SETS))
    assert set(counts) == set(range(cs.TASK_RANGE[0], cs.TASK_RANGE[1] + 1))
    assert max(counts.values()) == min(counts.values())


def test_no_cls_mean_sits_on_the_absolute_grouping_cut():
    assert CLS_LOW not in cs.CLS_MEANS


@pytest.mark.parametrize('set_id', SAMPLE)
def test_cls_cells_share_periods_and_budgets_and_period_cvs_share_cls(set_id):
    for cv in cs.PERIOD_CVS:
        same = [tasks(name(m, s, cv), set_id) for m in cs.CLS_MEANS for s in cs.CLS_SDS]
        key = lambda ts: [(t['period_ticks'], t['u_target']) for t in ts]
        assert all(key(ts) == key(same[0]) for ts in same)
    for m in cs.CLS_MEANS:
        for s in cs.CLS_SDS:
            a, b = (tasks(name(m, s, cv), set_id) for cv in cs.PERIOD_CVS)
            assert [t['cls_target'] for t in a] == [t['cls_target'] for t in b]
            assert len(a) == cs.task_count(set_id)


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('mean', cs.CLS_MEANS)
def test_zero_spread_gives_every_task_the_mean_cls_to_a_hundredth(set_id, mean):
    assert {round(t['cls_planned'], 2) for t in tasks(name(mean, 0.0, 0.2), set_id)} == {mean}


@pytest.mark.parametrize('set_id', SAMPLE)
def test_wider_spread_widens_the_planned_cls_and_lower_cls_means_more_traffic(set_id):
    sds = [statistics.pstdev([t['cls_planned'] for t in tasks(name(0.6, s, 0.2), set_id)]) for s in cs.CLS_SDS]
    assert sds[0] < 0.01 < sds[1] < sds[2]
    ts = sorted(tasks(name(0.6, 0.2, 0.2), set_id), key=lambda t: t['cls_planned'])
    assert ts[0]['traffic_planned'] > ts[-1]['traffic_planned']


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('cell', ('cls30-sd20-cv00', 'cls90-sd20-cv20'))
def test_planned_utilization_meets_the_nominal_load(set_id, cell):
    assert sum(t['u_planned'] for t in tasks(cell, set_id)) == pytest.approx(LOAD * cs.CORES, rel=0.02)


def test_long_jobs_reach_mid_range_cls():
    budget = max(b for k in range(cs.SETS) for cv in cs.PERIOD_CVS for b in cs.budgets(LOAD, cv, k))
    assert abs(cs.level(budget, 0.3)['cls'] - 0.3) < 0.01


def test_placements_differ_only_in_cores():
    configs = [cs.configuration(LOAD, 'cls60-sd20-cv20', 7, p) for p in cs.PLACEMENTS]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)
