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


def test_matched_extension_adds_only_matched_cells_at_the_other_mixed_fractions():
    cells = bimodal.cells('matched-extension')
    assert {(p, t) for p, _, t in cells} == {(0.25, 'matched'), (0.75, 'matched')}
    assert sum(len(bimodal.set_ids(p, cv)) * (3 + len(bimodal.placements(p))) for p, cv, _ in cells) == 800


def test_run_count_skips_identical_single_mode_sets_and_grouped_single_mode_runs():
    runs = sum(len(bimodal.set_ids(p, cv)) * (3 + len(bimodal.placements(p)))
               for p, cv, _ in bimodal.cells())
    assert len(bimodal.cells()) == 24
    assert runs == 2088


def test_default_period_reproduces_the_v2_configuration_and_other_periods_change_only_timing():
    v2 = bimodal.configuration(0.5, 0.1, 'as-is', 3, tables(), 'grouped')
    assert bimodal.configuration(0.5, 0.1, 'as-is', 3, tables(), 'grouped', period=40) == v2
    slow = bimodal.configuration(0.5, 0.1, 'as-is', 3, tables(), 'grouped', period=80)
    assert slow['horizon_ticks'] == 1600 and slow['warmup_ticks'] == 800
    assert slow['workload_id'].endswith('-as-is-t080-s03-grouped-v2')
    timing = ('period_ticks', 'u_planned')
    for fast, task in zip(v2['tasks'], slow['tasks']):
        assert {k: v for k, v in task.items() if k not in timing} == {k: v for k, v in fast.items() if k not in timing}
        assert task['period_ticks'] == 80 and task['u_planned'] == pytest.approx(fast['u_planned'] / 2)


def test_load_level_varies_only_the_period_of_one_cls_condition():
    assert bimodal.cells('load-level') == [(0.5, 0.1, 'as-is')]
    assert bimodal.periods('load-level') == (80, 40, 30, 20)
    runs = sum(len(bimodal.set_ids(p, cv)) * (3 + len(bimodal.placements(p)))
               for p, cv, _ in bimodal.cells('load-level')) * len(bimodal.periods('load-level'))
    assert runs == 400


def test_level_designs_carry_their_level_in_the_path_and_the_main_paths_stay_unchanged():
    import bi_run
    try:
        bi_run.select_design('load-level')
        assert bi_run.label((0.5, 0.1, 'as-is', 30, 0.0, 7)) == 'as-is/t030/p050/cv10/s07'
        assert len(bi_run.cases()) == 80
        bi_run.select_design('u-imbalance')
        assert bi_run.label((0.5, 0.1, 'as-is', 40, 0.25, 7)) == 'as-is/u025/p050/cv10/s07'
        assert len(bi_run.cases()) == 80
        assert sum(len(bi_run.runs_for(c)) for c in bi_run.cases()) == 560
        bi_run.select_design('main')
        assert bi_run.label((0.5, 0.1, 'as-is', 40, 0.0, 7)) == 'as-is/p050/cv10/s07'
    finally:
        bi_run.DESIGN, bi_run.RUNS, bi_run.PAIRS = 'main', bi_run.RUNS_MAIN, bi_run.PAIRS_MAIN


@cache
def budget_tables(budget):
    return bimodal.solve_tables(MODEL, budget)


def test_task_utilizations_keep_the_total_and_share_draws_across_cv():
    assert bimodal.task_utilizations(0.0, 5) == pytest.approx([bimodal.U_TOTAL / bimodal.TASKS] * bimodal.TASKS)
    small, large = (np.log(bimodal.task_utilizations(cv, 5)) for cv in (0.25, 0.75))
    for cv in (0.25, 0.5, 0.75):
        assert sum(bimodal.task_utilizations(cv, 5)) == pytest.approx(bimodal.U_TOTAL)
    # Same standard draws: log U deviations scale with sigma = sqrt(ln(1 + CV^2)).
    ratio = np.sqrt(np.log(1 + 0.75 ** 2) / np.log(1 + 0.25 ** 2))
    assert large - large.mean() == pytest.approx(ratio * (small - small.mean()))


def test_budgets_are_rounded_job_lengths_of_the_task_utilizations():
    budgets = bimodal.imbalance_budgets(0.5, 2)
    assert all(b % bimodal.BUDGET_STEP_NS == 0 for b in budgets)
    for b, u in zip(budgets, bimodal.task_utilizations(0.5, 2)):
        assert abs(b - u * bimodal.PERIOD * 1e6) <= bimodal.BUDGET_STEP_NS / 2


def test_balanced_cores_put_four_tasks_per_core_and_even_out_the_load():
    us = bimodal.task_utilizations(0.75, 9)
    cores = bimodal.balanced_cores(us, range(16), range(4))
    loads = [sum(u for i, u in enumerate(us) if cores[i] == c) for c in range(4)]
    assert sorted(cores.values()) == [0] * 4 + [1] * 4 + [2] * 4 + [3] * 4
    naive = [sum(us[c * 4:(c + 1) * 4]) for c in range(4)]
    assert max(loads) - min(loads) < max(naive) - min(naive)


def test_imbalance_placements_differ_only_in_cores_and_group_balanced_keeps_modes_apart():
    configs = {p: bimodal.imbalance_configuration(0.5, 4, budget_tables, p) for p in bimodal.IMBALANCE_PLACEMENTS}
    strip = lambda c: [{k: v for k, v in t.items() if k != 'core'} for t in c['tasks']]
    assert all(strip(c) == strip(configs['mixed']) for c in configs.values())
    gb = configs['grouped-balanced']['tasks']
    assert {t['core'] for t in gb if t['mode'] == 'low'} == {0, 1}
    assert {t['core'] for t in gb if t['mode'] == 'high'} == {2, 3}
    for task, budget in zip(configs['balanced']['tasks'], bimodal.imbalance_budgets(0.5, 4)):
        assert task['u_target'] == pytest.approx(budget / (bimodal.PERIOD * 1e6))
        assert task['period_ticks'] == bimodal.PERIOD
    for architecture in range(4):
        make_plan(configs['balanced'], architecture)
