"""Specification of the CLS x footprint task sets."""

from functools import cache

import pytest

from chaser.periodic.measurement import make_plan
from chaser.periodic.patterns import job_access_count
import bimodal
import footprint as fp

# Coefficients of the fitted O2 model (cls-bimodal-v2 calibration), rounded.
MODEL = dict(base=5405.8, sweeps=78.6, region_loops=17.94, l1_hits=20.13, l2_hits=68.22,
             pad_loops=20.07, pad_rounds=16.07, tail_loops=29.39, tail_rounds=20.14)


@cache
def levels():
    return fp.special_levels(MODEL)


@cache
def tables():
    return bimodal.solve_tables(MODEL, fp.BUDGET_NS)


def config(kind='BH', set_id=3, placement='mixed'):
    return fp.configuration(kind, set_id, tables(), levels(), placement)


def test_special_kinds_fill_the_budget_and_keep_their_footprint_and_cls_level():
    for kind, shape in levels().items():
        assert abs(shape['u_error']) < 1e-3
        assert shape['cold'] == (fp.BIG_LINES if fp.FOOTPRINT_KIB[kind] == 768 else fp.SMALL_LINES)
    assert levels()['SL']['cls'] < 0.1 and levels()['BL']['cls'] < 0.1
    assert 0.6 < levels()['SH']['cls'] < 0.75 and 0.6 < levels()['BH']['cls'] < 0.75


def test_small_and_big_kinds_of_a_cls_level_make_the_same_loads_and_close_l1_misses():
    for small, big in (('SL', 'BL'), ('SH', 'BH')):
        s, b = levels()[small], levels()[big]
        loads = [x['sweeps'] * (x['repeats'] * x['hot'] + x['cold']) for x in (s, b)]
        misses = [x['sweeps'] * (x['hot'] + x['cold']) for x in (s, b)]
        assert abs(loads[0] / loads[1] - 1) < 0.002
        assert abs(misses[0] / misses[1] - 1) < 0.07


def test_special_positions_and_background_targets_are_shared_by_all_kinds():
    configs = [config(kind) for kind in fp.KINDS]
    for task_set in zip(*(c['tasks'] for c in configs)):
        assert len({t['role'] for t in task_set}) == 1
        if task_set[0]['role'] == 'background':
            assert len({(t['hot_distinct'], t['hot_repeats'], t['sweeps']) for t in task_set}) == 1
    assert sum(t['role'] == 'special' for t in configs[0]['tasks']) == fp.SPECIAL


def test_mixed_puts_one_special_task_per_core_and_grouped_puts_all_on_core_zero():
    mixed = [t['core'] for t in config(placement='mixed')['tasks'] if t['role'] == 'special']
    grouped = [t['core'] for t in config(placement='grouped')['tasks'] if t['role'] == 'special']
    assert sorted(mixed) == [0, 1, 2, 3] and grouped == [0, 0, 0, 0]
    strip = lambda c: [{k: v for k, v in t.items() if k != 'core'} for t in c['tasks']]
    assert strip(config(placement='mixed')) == strip(config(placement='grouped'))


def test_footprint_sets_are_valid_plans_with_a_load_count_checksum():
    for kind in fp.KINDS:
        c = config(kind)
        assert c['horizon_ticks'] == (fp.WARMUP_JOBS + fp.MEASURED_JOBS) * fp.PERIOD
        plan = make_plan(c, 2)
        for task, planned in zip(c['tasks'], plan['tasks']):
            assert planned['expected_checksum'] == job_access_count(task) % (1 << 32)
        for architecture in (0, 1, 3):
            make_plan(c, architecture)
