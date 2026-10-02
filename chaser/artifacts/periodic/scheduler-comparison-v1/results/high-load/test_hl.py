"""Specification of the high-load task sets."""

import pytest

from chaser.periodic.measurement import make_plan
import hl_set as hl


def test_utilizations_sum_to_the_load_and_respect_the_bounds():
    for heaviness in hl.HEAVINESS:
        for load in hl.LOADS:
            for k in (0, 7):
                us = hl.utilizations(load, heaviness, k)
                assert sum(us) == pytest.approx(load * hl.CORES)
                assert min(us) >= hl.U_MIN - 1e-12
                light = [u for u in us if u < hl.HEAVY_RANGE[0]]
                assert max(light) <= hl.LIGHT_CAP + 1e-12
                assert len(us) - len(light) == (hl.HEAVY if heaviness == 'heavy' else 0)


def test_load_levels_scale_the_same_shares_and_keep_the_heavy_tasks():
    low, high = (hl.utilizations(load, 'heavy', 4) for load in (hl.LOADS[0], hl.LOADS[-1]))
    heavy = [i for i, u in enumerate(high) if u >= hl.HEAVY_RANGE[0]]
    assert [low[i] for i in heavy] == pytest.approx([high[i] for i in heavy])
    light = [i for i in range(hl.TASKS) if i not in heavy]
    ratio = [high[i] / low[i] for i in light]
    assert max(ratio) == pytest.approx(min(ratio))
    assert hl.periods(4) == hl.periods(4) and len(set(hl.periods(4))) > 1


def test_wfd_and_informed_keep_cores_under_the_caps_and_c_informed_fills_core_zero_lightly():
    for heaviness in hl.HEAVINESS:
        config = {p: hl.configuration(0.85, heaviness, 2, p) for p in hl.PLACEMENTS}
        assert max(config['informed']['high_load']['core_u']) <= hl.CORE_CAP + 1e-9
        assert max(config['wfd']['high_load']['core_u']) <= 1.0
        core0 = config['c-informed']['high_load']['core_u'][0]
        assert core0 <= config['c-informed']['high_load']['total_u'] / hl.CORES + 1e-9
        assert not any(t['heavy'] for t in config['c-informed']['tasks'] if t['core'] == 0)


def test_placements_differ_only_in_cores_and_build_valid_plans():
    configs = {p: hl.configuration(0.7, 'heavy', 5, p) for p in hl.PLACEMENTS}
    strip = lambda c: [{k: v for k, v in t.items() if k != 'core'} for t in c['tasks']]
    assert all(strip(c) == strip(configs['wfd']) for c in configs.values())
    for architecture in range(4):
        make_plan(configs['wfd'], architecture)
    assert configs['wfd']['horizon_ticks'] % hl.HYPERPERIOD == 0


def test_planned_u_follows_the_experiment_one_job_model():
    s = hl.sweeps(0.2, 40)
    assert abs(hl.planned_u(s, 40) - 0.2) * 40e6 <= hl.taskset.SWEEP_NS / 2 + 1
