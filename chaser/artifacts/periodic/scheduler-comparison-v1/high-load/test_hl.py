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


def test_infeasible_heavy_tasks_cannot_share_a_core_and_five_or_more_exceed_any_partition():
    import inf_set
    for heaviness in inf_set.HEAVINESS:
        for load in inf_set.LOADS:
            us = inf_set.utilizations(load, heaviness, 3)
            heavy = sorted(u for u in us if u > 0.5)
            assert len(heavy) == inf_set.heavy_count(heaviness)
            assert heavy[0] + heavy[1] > 1.0
            assert sum(us) == pytest.approx(load * hl.CORES) and min(us) >= inf_set.U_MIN - 1e-12
    low, high = (inf_set.utilizations(load, 'h5', 3) for load in inf_set.LOADS)
    assert [u for u in low if u > 0.5] == pytest.approx([u for u in high if u > 0.5])


def test_cluster_capacity_placements_balance_per_core_load_across_clusters():
    import inf_set
    config = inf_set.configuration(0.95, 'h5', 2, 'c2-cap')
    us = [t['u_planned'] for t in config['tasks']]
    clusters = [sum(u for u, t in zip(us, config['tasks']) if t['core'] in members) / len(members)
                for members in inf_set.CLUSTERS['c2-cap']]
    assert max(clusters) - min(clusters) < 0.6
    for placement in inf_set.PLACEMENTS:
        make_plan(inf_set.configuration(0.85, 'h6', 1, placement), 1)
    strip = lambda c: [{k: v for k, v in t.items() if k != 'core'} for t in c['tasks']]
    configs = [inf_set.configuration(0.85, 'h4', 1, p) for p in inf_set.PLACEMENTS]
    assert all(strip(c) == strip(configs[0]) for c in configs)
