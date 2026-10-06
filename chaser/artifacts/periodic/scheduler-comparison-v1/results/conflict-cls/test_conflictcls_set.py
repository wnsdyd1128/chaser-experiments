"""Specification tests for the conflict-miss low-CLS design (run from the c3 copy, PYTHONPATH set)."""
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

import bimodal
import conflictcls_set as cc
from placement_lib import CLS_LOW, TRAFFIC_HIGH
import smallmem_set as sm

SAMPLE = range(0, cc.SETS, 4)
LOAD = cc.LOADS[0]
L1_SETS = 16 * 1024 // (32 * 4)  # rtems/baseline/cache.yaml: 16 KiB, 4-way, 32 B lines
L2_SETS = 2 * 1024 * 1024 // (32 * 4)


def tasks(cell, set_id, placement='wfd'):
    return cc.configuration(LOAD, cell, set_id, placement)['tasks']


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('cell', cc.HEAVINESS)
def test_sets_are_experiment_21s_with_only_the_low_task_shape_changed(set_id, cell):
    mine, theirs = tasks(cell, set_id), sm.configuration(LOAD, cell, set_id, 'wfd')['tasks']
    assert [(t['role'], t['period_ticks'], t['u_target']) for t in mine] == \
           [(t['role'], t['period_ticks'], t['u_target']) for t in theirs]
    high = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts if t['role'] == 'high']
    assert high(mine) == high(theirs)  # cores follow every task's U, so they may differ


def test_the_stride_puts_every_line_of_a_task_in_one_l1_set_and_distinct_l2_sets():
    lines = cc.CONFLICT_STRIDE // 32
    assert lines % L1_SETS == 0
    assert lines * max(cc.HOT_LINES) + lines * max(cc.COLD_LINES) <= L2_SETS


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_tasks_touch_little_data_yet_miss_l1_on_almost_every_access(set_id):
    low = [t for t in tasks('cv20-low50', set_id) if t['role'] == 'low']
    assert low
    for t in low:
        assert t['stride'] == cc.CONFLICT_STRIDE and t['distinct'] * 32 <= 2048
        assert t['hot_distinct'] <= 4 and t['distinct'] - t['hot_distinct'] >= 4  # associativity 4
        assert t['cls_planned'] <= CLS_LOW and t['traffic_planned'] > TRAFFIC_HIGH
        assert abs(t['cls_planned'] - t['cls_target']) < 0.03


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('cell', ('cv00-low50', 'cv20-low50'))
def test_planned_utilization_meets_the_nominal_load(set_id, cell):
    assert sum(t['u_planned'] for t in tasks(cell, set_id)) == pytest.approx(LOAD * cc.CORES, rel=0.02)


def test_placements_differ_only_in_cores():
    configs = [cc.configuration(LOAD, 'cv20-low25', 7, p) for p in cc.PLACEMENTS]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_task_budgets_follow_the_calibrated_conflict_model(set_id):
    model = cc.conflict_model()
    for t in tasks('cv00-low25', set_id):
        if t['role'] == 'low':
            job = float(bimodal.job_ns(model, t['hot_distinct'], t['hot_repeats'], t['sweeps'], 0,
                                       t.get('pad_tail', 0), t['distinct'] - t['hot_distinct']))
            assert job == pytest.approx(t['u_target'] * t['period_ticks'] * 1e6, rel=bimodal.U_PLAN_TOLERANCE)
