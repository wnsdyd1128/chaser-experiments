"""Specification tests for the period-spread x memory-mix design (run from the c3 copy, PYTHONPATH set)."""
from pathlib import Path
import statistics
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import boundary_set as bs

LOAD = bs.LOADS[0]
SAMPLE = range(0, bs.SETS, 3)


def roles(cell, set_id):
    return [t['role'] for t in bs.configuration(LOAD, cell, set_id, 'wfd')['tasks']]


def realized_cv(periods):
    return statistics.pstdev(periods) / statistics.mean(periods)


def test_cells_cross_every_period_cv_low_and_big_level():
    cells = [bs.cell(h) for h in bs.HEAVINESS]
    assert len(cells) == len(bs.PERIOD_CVS) * len(bs.LOWS) * len(bs.BIGS) == len(set(map(str, cells)))


def test_zero_period_cv_gives_every_task_the_mean_period():
    assert all(set(bs.periods(0.0, k)) == {bs.MU} for k in range(bs.SETS))


def test_period_spread_grows_with_the_nominal_cv():
    medians = [statistics.median(realized_cv(bs.periods(cv, k)) for k in range(bs.SETS)) for cv in bs.PERIOD_CVS]
    assert medians == sorted(medians) and len(set(medians)) == len(medians)


@pytest.mark.parametrize('set_id', SAMPLE)
def test_low_tasks_nest_and_big_tasks_are_the_same_in_every_cell(set_id):
    positions = lambda cell, role: {i for i, r in enumerate(roles(cell, set_id)) if r == role}
    for cv in bs.PERIOD_CVS:
        tag = f'cv{round(cv * 100):02d}'
        assert positions(f'{tag}-low4-big0', 'low') <= positions(f'{tag}-low8-big0', 'low')
        assert positions(f'{tag}-low8-big2', 'low') == positions(f'{tag}-low8-big0', 'low')
        assert positions(f'{tag}-low0-big2', 'big') == positions('cv00-low0-big2', 'big')


@pytest.mark.parametrize('set_id', SAMPLE)
@pytest.mark.parametrize('cell', ('cv00-low0-big0', 'cv10-low4-big2', 'cv30-low8-big2'))
def test_planned_utilization_meets_the_nominal_load(set_id, cell):
    tasks = bs.configuration(LOAD, cell, set_id, 'wfd')['tasks']
    assert sum(t['u_planned'] for t in tasks) == pytest.approx(LOAD * bs.CORES, rel=0.02)


@pytest.mark.parametrize('set_id', SAMPLE)
def test_big_tasks_hold_one_768_kib_sweep_in_every_cell(set_id):
    for cv in bs.PERIOD_CVS:
        tasks = bs.configuration(LOAD, f'cv{round(cv * 100):02d}-low0-big2', set_id, 'wfd')['tasks']
        big = [t for t in tasks if t['role'] == 'big']
        assert len(big) == 2 and all(t['sweeps'] >= 1 and abs(t['u_planned'] / t['u_target'] - 1) <= 0.005
                                     for t in big)


def test_placements_differ_only_in_cores():
    configs = [bs.configuration(LOAD, 'cv20-low8-big2', 4, p) for p in bs.PLACEMENTS]
    strip = lambda tasks: [{k: v for k, v in t.items() if k != 'core'} for t in tasks]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)


def test_balanced_cls_grouping_is_wfd_without_low_cls_tasks():
    cores = {p: [t['core'] for t in bs.configuration(LOAD, 'cv20-low0-big0', 2, p)['tasks']] for p in ('wfd', 'cgb')}
    assert cores['wfd'] == cores['cgb']
