"""Source-informed mixed candidates retain lineage and unmeasured status."""

from collections import Counter
from copy import deepcopy
import json

import pytest

from chaser.periodic import make_plan
from chaser.periodic_recipes import RECIPES
from chaser.periodic_registry import build_registry
from tools.rtems_periodic_pool import initialize


def test_v2_has_role_mixtures_and_bounded_memory_period_coverage():
    from tools.rtems_periodic_pool_v2 import candidate_pool

    pool = candidate_pool()
    assert len(pool['candidates']) == 180
    assert pool['dataset_ready'] is pool['split_frozen'] is False
    assert pool['design']['excluded_pattern_sources'] == ['PolyBench']
    assert set(r['target_total_u'] for r in pool['candidates']) == {0.5, 1.0, 1.5}
    task_ids = []
    for row in pool['candidates']:
        config = row['configuration']
        assert len({t['pattern'] for t in config['tasks']}) == 2
        assert len({RECIPES[t['pattern']] for t in config['tasks']}) == 1
        assert row['measured_utilization'] is None
        assert row['eligibility_status'] == 'pending_measurement'
        assert config['eligible_for_training'] is config['test_eligible'] is False
        assert max(row['estimated_utilization'].values()) <= 0.25
        assert sum(row['estimated_utilization'].values()) <= row['target_total_u']
        for architecture in range(3):
            plan = make_plan(config, architecture)
            assert sum(t['job_count'] for t in plan['tasks']) <= 64
            assert len(plan['tasks']) * max(t['job_count'] for t in plan['tasks']) <= 64
        if row['profile'].startswith('llc'):
            assert sum(t['distinct'] > 65536 for t in config['tasks']) == (
                1 if row['profile'] == 'llc-one' else 2)
        if row['profile'] == 'l1-skew':
            assert sorted(Counter(t['pattern'] for t in config['tasks']).values()) == [
                len(config['tasks'])//4, 3*len(config['tasks'])//4]
            assert len({t['period_ticks'] for t in config['tasks']}) == 3
        task_ids.extend(t['task_id'] for t in config['tasks'])
    assert len(task_ids) == len(set(task_ids))


def test_v2_roles_and_numeric_variants_merge_and_cross_mix_connects_families():
    from tools.rtems_periodic_pool_v2 import candidate_pool

    rows = candidate_pool()['candidates']
    assert build_registry(rows)['primary_family_count'] == 3
    first, other = deepcopy(rows[0]), deepcopy(rows[60])
    other['configuration']['workload_id'] = 'cross-mix'
    other['configuration']['tasks'][0]['pattern'] = first['configuration']['tasks'][0]['pattern']
    # Use an already valid task shape from the first record.
    task = other['configuration']['tasks'][0]
    for key in ('pattern', 'width', 'distinct'):
        task[key] = first['configuration']['tasks'][0][key]
    registry = build_registry([*rows, other])
    assert registry['primary_family_count'] == 2


def test_v2_artifact_exposes_small_split_and_preserves_every_candidate(tmp_path):
    from tools.rtems_smoke import check_inputs

    output = tmp_path / 'v2'
    report = initialize(output, version=2)
    assert report['candidate_workloads'] == 180
    assert report['primary_families'] == 3
    assert report['family_counts'] == {'train': 1, 'validation': 1, 'test': 1}
    assert report['measured_workloads'] == 0
    assert report['sufficiency_status'] == 'not_assessed'
    assert len(list((output / 'configs').glob('*.json'))) == 180
    pool = json.loads((output / 'pool.json').read_text())
    assert all(r['source_basis'] for r in pool['candidates'])
    check_inputs(output, json.loads((output / 'manifest.json').read_text()))
    assert (output / 'implementation/periodic_recipes.py').is_file()
    assert (output / 'implementation/RECIPES.md').is_file()
    with pytest.raises(FileExistsError):
        initialize(output, version=2)
