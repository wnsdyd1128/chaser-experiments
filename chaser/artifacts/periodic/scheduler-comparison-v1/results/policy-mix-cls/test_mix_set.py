"""Specification tests for the multi-factor task-set design (run from the c3 copy, PYTHONPATH set)."""
from collections import Counter
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mix_set


def test_every_factor_level_appears_equally_often_across_sets():
    for name, levels in mix_set.FACTORS.items():
        counts = Counter(mix_set.factors(k)[name] for k in range(mix_set.SETS))
        assert set(counts) == set(levels)
        assert max(counts.values()) - min(counts.values()) <= 1


def test_factor_levels_are_drawn_independently_of_each_other():
    pairs = Counter((mix_set.factors(k)['low'], mix_set.factors(k)['big']) for k in range(mix_set.SETS))
    assert len(pairs) == len(mix_set.FACTORS['low']) * len(mix_set.FACTORS['big'])


@pytest.mark.parametrize('set_id', range(0, mix_set.SETS, 7))
def test_roles_match_the_set_factors(set_id):
    f, roles = mix_set.factors(set_id), mix_set.roles(set_id)
    counts = Counter(roles)
    assert (counts['low'], counts['big'], counts['heavy']) == (f['low'], f['big'], f['heavy'])
    assert len(roles) == mix_set.TASKS


@pytest.mark.parametrize('set_id', range(0, mix_set.SETS, 7))
def test_both_loads_share_roles_periods_and_the_heavy_task(set_id):
    low, high = (mix_set.configuration(load, 'mix', set_id, 'wfd')['tasks'] for load in mix_set.LOADS)
    for a, b in zip(low, high):
        assert (a['role'], a['period_ticks']) == (b['role'], b['period_ticks'])
        if a['role'] == 'heavy':
            assert a['u_target'] == pytest.approx(b['u_target'], abs=2e-4)


@pytest.mark.parametrize('set_id', range(0, mix_set.SETS, 7))
@pytest.mark.parametrize('load', mix_set.LOADS)
def test_planned_utilization_meets_the_nominal_load(set_id, load):
    tasks = mix_set.configuration(load, 'mix', set_id, 'wfd')['tasks']
    assert sum(t['u_planned'] for t in tasks) == pytest.approx(load * mix_set.CORES, rel=0.02)


@pytest.mark.parametrize('budget', (1_800_000, 3_000_000, 9_000_000, 30_000_000))
def test_big_level_fits_its_budget_with_one_768_kib_sweep_or_more(budget):
    level = mix_set.big_level(budget)
    assert level['cold'] == mix_set.BIG_LINES and level['sweeps'] >= 1
    assert abs(level['u_error']) <= 0.005


@pytest.mark.parametrize('set_id', range(0, mix_set.SETS, 3))
def test_cls_and_traffic_grouping_differ_only_when_low_cls_tasks_have_matched_traffic(set_id):
    f = mix_set.factors(set_id)
    cores = {p: [t['core'] for t in mix_set.configuration(0.3, 'mix', set_id, p)['tasks']] for p in ('tg', 'cg')}
    assert (cores['tg'] != cores['cg']) == (f['low'] > 0 and f['traffic'] == 'matched')


def test_placements_differ_only_in_cores():
    configs = [mix_set.configuration(0.45, 'mix', 3, p) for p in mix_set.PLACEMENTS]
    strip = lambda tasks: [{k: v for k, v in t.items() if k != 'core'} for t in tasks]
    assert all(strip(c['tasks']) == strip(configs[0]['tasks']) for c in configs)
