"""Specification of the bimodal CLS task-set generator."""

from functools import cache

import numpy as np
import pytest

from chaser.periodic.measurement import make_plan
import bimodal

# Close to the isolated O2 pad-check runs; calibrate.py fits the real model.
MODEL = dict(base=6000.0, sweeps=200.0, region_loops=50.0, l1_hits=20.7, l2_hits=67.0,
             pad_loops=20.3, pad_rounds=16.1, tail_loops=30.0, tail_rounds=16.1)


@cache
def tables():
    return bimodal.solve_tables(MODEL)


def test_closed_form_cls_matches_yarda_for_padded_and_low_kernels():
    # yarda_cpp 374b2c9 on the O2 pad-check workload.
    assert bimodal.cls_model(64, 100, 4) == pytest.approx(0.863163, abs=1e-6)
    assert bimodal.cls_model(40, 2, 20) == pytest.approx(0.117158, abs=1e-6)


def test_no_dispersion_puts_every_task_at_its_mode_center():
    wanted = bimodal.targets(0.25, 0.0, 3)
    assert sorted(t for _, t in wanted) == [bimodal.LOW_CENTER] * 4 + [bimodal.HIGH_CENTER] * 12


def test_cv_scales_the_distance_to_the_nearest_bound_within_three_sigma():
    for set_id in range(bimodal.SETS):
        for mode, value in bimodal.targets(0.5, 0.3, set_id):
            if mode == 'high':
                assert 0.81 - 1e-12 <= value <= 0.99 + 1e-12
            else:
                assert 0.085 - 1e-12 <= value <= 0.175 + 1e-12


def test_common_random_numbers_nest_low_slots_and_share_draws_across_cv():
    for set_id in range(3):
        lows = [{i for i, (mode, _) in enumerate(bimodal.targets(p, 0.2, set_id)) if mode == 'low'}
                for p in (0.25, 0.5, 0.75)]
        assert lows[0] < lows[1] < lows[2] and [len(s) for s in lows] == [4, 8, 12]
        centers = {'high': bimodal.HIGH_CENTER, 'low': bimodal.LOW_CENTER}
        small, large = bimodal.targets(0.5, 0.1, set_id), bimodal.targets(0.5, 0.3, set_id)
        for (mode, a), (_, b) in zip(small, large):
            assert b - centers[mode] == pytest.approx(3 * (a - centers[mode]))


@pytest.mark.parametrize('mode,traffic,span,tolerance', [
    ('high', 'as-is', (0.81, 0.96), 0.002), ('low', 'as-is', (0.087, 0.175), 0.001),
    ('low', 'matched', (0.085, 0.175), 0.002)])
def test_levels_hit_the_cls_target_and_the_planned_u(mode, traffic, span, tolerance):
    for target in np.linspace(*span, 50):
        lv = bimodal.level(tables(), mode, traffic, target)
        assert abs(lv['cls'] - target) <= tolerance
        assert abs(lv['u_error']) <= bimodal.U_PLAN_TOLERANCE
        assert lv['cls'] == pytest.approx(bimodal.cls_model(lv['hot'], lv['repeats'], lv['sweeps']))


def test_tail_fills_at_most_the_allowed_share_of_the_job():
    budget = bimodal.TASK_U * bimodal.PERIOD * 1e6
    for mode, traffic in (('high', 'as-is'), ('low', 'as-is'), ('low', 'matched')):
        for target in ((0.83, 0.9, 0.95) if mode == 'high' else (0.09, 0.13, 0.17)):
            lv = bimodal.level(tables(), mode, traffic, target)
            assert lv['tail'] == 0 or lv['tail'] >= bimodal.MIN_LOOP_ROUNDS
            shape = dict(hot=lv['hot'], repeats=lv['repeats'], sweeps=lv['sweeps'], pad=lv['pad'])
            share = (bimodal.job_ns(MODEL, **shape, tail=lv['tail']) - bimodal.job_ns(MODEL, **shape)) / budget
            assert 0 <= share <= bimodal.TAIL_SHARE


def test_low_mode_reads_hot_lines_twice_under_both_traffic_levels():
    for traffic in ('as-is', 'matched'):
        assert {bimodal.level(tables(), 'low', traffic, t)['repeats'] for t in (0.09, 0.13, 0.17)} == {2}


def test_matched_low_tasks_request_the_high_center_l1_misses_with_padding():
    misses = tables()['center_l1_misses']
    for target in np.linspace(0.09, 0.17, 9):
        lv = bimodal.level(tables(), 'low', 'matched', target)
        assert lv['pad'] >= bimodal.MIN_LOOP_ROUNDS
        assert abs(lv['sweeps'] * (lv['hot'] + bimodal.COLD_LINES) / misses - 1) <= bimodal.TRAFFIC_TOLERANCE
    unmatched = bimodal.level(tables(), 'low', 'as-is', bimodal.LOW_CENTER)
    assert unmatched['pad'] == 0
    assert unmatched['sweeps'] * (unmatched['hot'] + bimodal.COLD_LINES) > 2 * misses


def test_placements_differ_only_in_cores_and_group_low_tasks_on_the_first_cores():
    mixed = bimodal.configuration(0.25, 0.2, 'as-is', 4, tables(), 'mixed')
    grouped = bimodal.configuration(0.25, 0.2, 'as-is', 4, tables(), 'grouped')
    strip = lambda config: [{k: v for k, v in t.items() if k != 'core'} for t in config['tasks']]
    assert strip(mixed) == strip(grouped)
    low_cores = lambda config: sorted(t['core'] for t in config['tasks'] if t['mode'] == 'low')
    assert low_cores(grouped) == [0, 0, 0, 0]
    assert low_cores(mixed) == [0, 1, 2, 3]


def test_every_architecture_accepts_the_generated_o2_workload():
    config = bimodal.configuration(0.5, 0.3, 'matched', 7, tables(), 'mixed')
    assert config['workload_optimization'] == 'O2'
    assert any('pad_rounds' in t for t in config['tasks'])
    for architecture in range(4):
        make_plan(config, architecture)


def test_run_count_skips_identical_single_mode_sets_and_grouped_single_mode_runs():
    runs = sum(len(bimodal.set_ids(p, cv)) * (3 + len(bimodal.placements(p)))
               for p, cv, _ in bimodal.cells())
    assert len(bimodal.cells()) == 24
    assert runs == 2088
