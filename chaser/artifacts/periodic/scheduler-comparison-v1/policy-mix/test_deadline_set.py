"""Specification tests for the confirmatory deadline designs (run from the c3 copy, PYTHONPATH set)."""
from collections import Counter
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import boundary_set
import clsspread_set
import deadline_big_set
import deadline_set
import loadmem_set
import mix_set
from placement_lib import BOUNDARY_POLICIES, CLS_LOW, RANDOM_POLICIES, TRAFFIC_HIGH
import smallmem_set
import taskcount_set

DESIGNS = (deadline_set, deadline_big_set)
EXPLORATORY = (mix_set, boundary_set, taskcount_set, smallmem_set, clsspread_set, loadmem_set)
SAMPLE = range(0, 18, 4)


def tasks(ds, load, cell, set_id, placement='wfd'):
    return ds.configuration(load, cell, set_id, placement)['tasks']


def seeds(module):
    return set(range(module.SEED_BASE, module.SEED_BASE + module.SETS))


def test_sets_are_fresh_draws_disjoint_from_every_exploratory_design_and_each_other():
    assert not seeds(deadline_set) & seeds(deadline_big_set)
    for ds in DESIGNS:
        for module in EXPLORATORY:
            assert not seeds(ds) & seeds(module), module.__name__


def test_small_design_grid_is_the_pre_registered_one():
    assert deadline_set.LOADS == (0.45, 0.475, 0.5, 0.525, 0.55, 0.575, 0.6)
    assert deadline_set.HEAVINESS == ('cv00-low50', 'cv20-low50')
    assert deadline_set.MEMORY_ROLE == 'low' and deadline_set.SETS == 18


def test_big_design_grid_is_the_pre_registered_one():
    assert deadline_big_set.LOADS == (0.3, 0.35, 0.4, 0.45)
    assert deadline_big_set.HEAVINESS == ('cv00-big25', 'cv20-big25')
    assert deadline_big_set.MEMORY_ROLE == 'big' and deadline_big_set.SETS == 18


@pytest.mark.parametrize('ds', DESIGNS)
def test_placements_are_the_boundary_policies_and_three_random_draws(ds):
    assert ds.PLACEMENTS == BOUNDARY_POLICIES + RANDOM_POLICIES


@pytest.mark.parametrize('ds', DESIGNS)
def test_measured_window_is_three_hyperperiods_after_one_of_warm_up(ds):
    config = ds.configuration(ds.LOADS[0], ds.HEAVINESS[0], 0, 'wfd')
    assert config['warmup_ticks'] == 240 and config['horizon_ticks'] == 4 * 240
    assert all(240 % t['period_ticks'] == 0 for t in config['tasks'])


@pytest.mark.parametrize('ds', DESIGNS)
def test_every_task_count_in_range_appears_equally_often(ds):
    counts = Counter(ds.task_count(k) for k in range(ds.SETS))
    assert set(counts) == set(range(ds.TASK_RANGE[0], ds.TASK_RANGE[1] + 1))
    assert max(counts.values()) == min(counts.values())


@pytest.mark.parametrize('ds', DESIGNS)
@pytest.mark.parametrize('set_id', SAMPLE)
def test_loads_share_periods_and_memory_tasks_and_scale_only_the_budgets(ds, set_id):
    for cell in ds.HEAVINESS:
        same = [tasks(ds, load, cell, set_id) for load in ds.LOADS]
        assert all([t['period_ticks'] for t in ts] == [t['period_ticks'] for t in same[0]] for ts in same)
        assert all([t['role'] for t in ts] == [t['role'] for t in same[0]] for ts in same)
        assert all(len(ts) == ds.task_count(set_id) for ts in same)


@pytest.mark.parametrize('ds', DESIGNS)
@pytest.mark.parametrize('set_id', SAMPLE)
def test_both_period_cells_keep_the_same_memory_tasks(ds, set_id):
    roles = [ds.roles(cell, set_id) for cell in ds.HEAVINESS]
    assert roles[0] == roles[1]


@pytest.mark.parametrize('ds', DESIGNS)
@pytest.mark.parametrize('set_id', SAMPLE)
def test_period_cv_zero_cell_runs_every_task_at_the_center_period(ds, set_id):
    config = ds.configuration(ds.LOADS[0], ds.HEAVINESS[0], set_id, 'wfd')
    assert {t['period_ticks'] for t in config['tasks']} == {ds.MU}
    spread = ds.configuration(ds.LOADS[0], ds.HEAVINESS[1], set_id, 'wfd')['high_load']['realized_period_cv']
    assert spread > 0


@pytest.mark.parametrize('ds', DESIGNS)
@pytest.mark.parametrize('set_id', range(18))
def test_memory_tasks_hold_about_their_share_of_u(ds, set_id):
    for cell in ds.HEAVINESS:
        ts = tasks(ds, ds.LOADS[0], cell, set_id)
        total = sum(t['u_planned'] for t in ts)
        realized = sum(t['u_planned'] for t in ts if t['role'] == ds.MEMORY_ROLE) / total
        assert abs(realized - ds.MEMORY_SHARE) <= max(t['u_planned'] for t in ts) / total, (cell, realized)


@pytest.mark.parametrize('set_id', SAMPLE)
def test_small_design_memory_tasks_are_32_kib_low_cls_high_traffic_and_the_only_cls_group(set_id):
    for t in tasks(deadline_set, max(deadline_set.LOADS), 'cv20-low50', set_id):
        if t['role'] == 'low':
            assert t['cls_planned'] <= CLS_LOW and t['traffic_planned'] > TRAFFIC_HIGH and t['footprint_kib'] <= 64
        else:
            assert t['cls_planned'] > CLS_LOW


@pytest.mark.parametrize('set_id', SAMPLE)
def test_big_design_memory_tasks_sweep_768_kib_and_are_the_only_cls_group(set_id):
    for t in tasks(deadline_big_set, max(deadline_big_set.LOADS), 'cv20-big25', set_id):
        if t['role'] == 'big':
            assert t['footprint_kib'] >= 768 and t['cls_planned'] <= CLS_LOW
        else:
            assert t['cls_planned'] > CLS_LOW and t['footprint_kib'] <= 64


@pytest.mark.parametrize('ds', DESIGNS)
@pytest.mark.parametrize('set_id', SAMPLE)
def test_planned_utilization_meets_each_nominal_load(ds, set_id):
    for load in ds.LOADS:
        total = sum(t['u_planned'] for t in tasks(ds, load, ds.HEAVINESS[1], set_id))
        assert total == pytest.approx(load * ds.CORES, rel=0.02)


@pytest.mark.parametrize('ds', DESIGNS)
def test_job_budgets_stay_inside_the_copied_model_check_range_of_their_family(ds):
    for k in range(ds.SETS):
        for h in ds.HEAVINESS:
            for load in ds.LOADS:
                for role, budget in zip(ds.roles(h, k), ds.budgets(load, ds.cell(h)['period_cv'], k)):
                    low, high = ds.MODEL_CHECK_NS[role]
                    assert low <= budget <= high, (h, k, load, role, budget)


@pytest.mark.parametrize('ds', DESIGNS)
def test_placements_differ_only_in_cores(ds):
    configs = [ds.configuration(ds.LOADS[3], ds.HEAVINESS[1], 7, p) for p in ds.PLACEMENTS]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)


@pytest.mark.parametrize('ds', DESIGNS)
def test_every_placement_keeps_each_core_under_the_cap(ds):
    for p in ds.PLACEMENTS:
        hl = ds.configuration(max(ds.LOADS), ds.HEAVINESS[1], 5, p)['high_load']
        assert max(hl['core_u']) <= hl['core_cap'] + 1e-9, p


@pytest.mark.parametrize('ds', DESIGNS)
def test_workload_ids_are_unique_across_the_load_grid(ds):
    ids = {ds.configuration(load, ds.HEAVINESS[0], 0, 'wfd')['workload_id'] for load in ds.LOADS}
    assert len(ids) == len(ds.LOADS)
