"""Specification tests for the task-count x memory-pressure design (run from the c3 copy, PYTHONPATH set)."""
from collections import Counter
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import taskcount_set as tc

SAMPLE = range(0, tc.SETS, 5)


def tasks(load, cell, set_id, placement='wfd'):
    return tc.configuration(load, cell, set_id, placement)['tasks']


def test_every_task_count_in_range_appears_equally_often():
    counts = Counter(tc.task_count(k) for k in range(tc.SETS))
    assert set(counts) == set(range(tc.TASK_RANGE[0], tc.TASK_RANGE[1] + 1))
    assert max(counts.values()) == min(counts.values())


@pytest.mark.parametrize('set_id', SAMPLE)
def test_cells_share_the_task_count_periods_and_u_shares(set_id):
    reference = tasks(tc.LOADS[0], tc.HEAVINESS[0], set_id)
    for load in tc.LOADS:
        for cell in tc.HEAVINESS:
            other = tasks(load, cell, set_id)
            assert [t['period_ticks'] for t in other] == [t['period_ticks'] for t in reference]
            assert len(other) == tc.task_count(set_id)


@pytest.mark.parametrize('set_id', SAMPLE)
def test_memory_tasks_nest_and_hold_about_their_share_of_u(set_id):
    big = {cell: {i for i, t in enumerate(tasks(tc.LOADS[0], cell, set_id)) if t['role'] == 'big'}
           for cell in tc.HEAVINESS}
    assert big['mem00'] == set() and big['mem25'] <= big['mem50']
    for cell, share in (('mem25', 0.25), ('mem50', 0.5)):
        ts = tasks(tc.LOADS[0], cell, set_id)
        realized = sum(t['u_planned'] for t in ts if t['role'] == 'big') / sum(t['u_planned'] for t in ts)
        largest = max(t['u_planned'] for t in ts) / sum(t['u_planned'] for t in ts)
        assert abs(realized - share) <= largest  # within one task's share of the target


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('load', tc.LOADS)
def test_planned_utilization_meets_the_nominal_load(set_id, load):
    assert sum(t['u_planned'] for t in tasks(load, 'mem50', set_id)) == pytest.approx(load * tc.CORES, rel=0.02)


def test_placements_differ_only_in_cores():
    configs = [tc.configuration(0.45, 'mem25', 7, p) for p in tc.PLACEMENTS]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)
