"""Candidate count cannot conceal family leakage or unmeasured utilization."""

from copy import deepcopy
import json

import pytest

from chaser.periodic import digest, make_plan
from chaser.periodic_registry import build_registry
from tools.rtems_periodic_pool import candidate_pool, initialize


def record(name, patterns, *, development=False, recipe=None):
    return dict(recipe_id=recipe or name, development_exposed=development,
                role='development' if development else 'candidate',
                configuration=dict(workload_id=name, family_id='untrusted-name',
                    policy_id='provisional', horizon_ticks=40,
                    tasks=[dict(task_id=f't{i}', pattern=p, distinct=24, stride=32,
                                sweeps=2, period_ticks=20, core=i % 4)
                           for i, p in enumerate(patterns)]))


def test_shared_base_tasks_merge_transitively_despite_renaming():
    rows = [record('a', ['overlap']), record('b', ['overlap', 'mirrored']),
            record('c', ['mirrored'])]
    result = build_registry(rows)
    assert len(result['families']) == 1
    assert len({r['family_id'] for r in result['workloads']}) == 1


def test_development_exposure_propagates_across_whole_family():
    rows = [record('pilot', ['overlap'], development=True),
            record('mix', ['overlap', 'mirrored']), record('other', ['mirrored'])]
    result = build_registry(rows)
    assert all(not r['primary_candidate'] for r in result['workloads'])
    assert result['primary_family_count'] == 0
    assert all(r['family_development_exposed'] for r in result['workloads'])


def test_known_development_structure_cannot_be_relabelled_as_new():
    result = build_registry([record('renamed', ['cyclic'])])
    assert result['workloads'][0]['exclusion_reasons'] == ['development_lineage']


def test_numeric_variants_and_directional_scans_remain_one_family():
    rows = [record('a', ['forward-reverse']), record('b', ['tile-reverse'])]
    rows[1]['configuration']['tasks'][0].update(distinct=48, stride=1, sweeps=3)
    result = build_registry(rows)
    assert len(result['families']) == 1


def test_recipe_link_merges_even_when_base_task_structures_differ():
    result = build_registry([record('a', ['overlap'], recipe='shared'),
                             record('b', ['mirrored'], recipe='shared')])
    assert len(result['families']) == 1


def test_registry_is_order_independent_and_preserves_input():
    rows = [record('a', ['overlap']), record('b', ['mirrored'])]
    original = deepcopy(rows)
    assert build_registry(rows) == build_registry(list(reversed(rows)))
    assert rows == original


def test_reused_local_task_ids_have_distinct_global_lookup_keys():
    result = build_registry([record('a', ['overlap']), record('b', ['mirrored'])])
    keys = [t['global_task_id'] for r in result['workloads'] for t in r['tasks']]
    assert len(set(keys)) == 2
    assert all(t['snapshot_hash'] is None for r in result['workloads'] for t in r['tasks'])


def test_duplicate_workload_identity_is_rejected():
    row = record('a', ['overlap'])
    with pytest.raises(ValueError, match='Duplicate workload'):
        build_registry([row, row])


def test_registry_access_count_is_not_truncated_to_checksum_width():
    row = record('large', ['tile-reuse'])
    row['configuration']['tasks'][0].update(distinct=2400, sweeps=1_000_000)
    result = build_registry([row])
    assert result['workloads'][0]['tasks'][0]['loads_per_job'] == 4_800_000_000


def test_pool_has_heterogeneous_periods_bounded_jobs_and_no_measured_u():
    pool = candidate_pool()
    assert len(pool['candidates']) == 240
    ids = set()
    for row in pool['candidates']:
        config = row['configuration']
        for architecture in range(3):
            plan = make_plan(config, architecture)
            assert sum(t['job_count'] for t in plan['tasks']) <= 64
            assert len({t['period_ticks'] for t in plan['tasks']}) > 1
        assert row['measured_utilization'] is None
        assert row['eligibility_status'] == 'pending_measurement'
        assert max(row['estimated_utilization'].values()) <= pool['design']['u_max']
        assert sum(row['estimated_utilization'].values()) <= pool['design']['U_max']
        assert sum(row['estimated_utilization'].values()) <= row['target_total_u']
        for t in config['tasks']:
            assert t['task_id'] not in ids
            ids.add(t['task_id'])
    assert pool['design']['status'] == 'provisional'
    assert pool['dataset_ready'] is False


def test_pool_artifact_retains_membership_and_refuses_overwrite(tmp_path):
    root = tmp_path / 'pool'
    initialize(root)
    pool = json.loads((root / 'pool.json').read_text())
    registry = json.loads((root / 'registry.json').read_text())
    split = json.loads((root / 'split-proposal.json').read_text())
    assert len(split['families']) == registry['primary_family_count'] == 9
    assert len(split['workloads']) == 240
    assert set(split['families'].values()) == {'train', 'validation', 'test'}
    assert pool['split_frozen'] is False
    for row in registry['workloads']:
        if row['primary_candidate']:
            assert split['workloads'][row['workload_id']] == row['family_id']
            path = root / 'configs' / (row['workload_id'] + '.json')
            assert json.loads(path.read_text()) == row['configuration']
            assert digest(row['configuration']) == row['configuration_hash']
        else:
            assert row['workload_id'] not in split['workloads']
    manifest = json.loads((root / 'manifest.json').read_text())
    assert manifest['registry_hash'] == digest(registry)
    from tools.rtems_smoke import check_inputs
    check_inputs(root, manifest)
    with pytest.raises(FileExistsError):
        initialize(root)


def test_changed_candidate_input_invalidates_saved_manifest(tmp_path):
    root = tmp_path / 'pool'
    initialize(root)
    path = root / 'configs/candidate-0000.json'
    config = json.loads(path.read_text())
    config['tasks'][0]['period_ticks'] *= 2
    path.write_text(json.dumps(config))
    from tools.rtems_smoke import check_inputs
    with pytest.raises(ValueError, match='changed'):
        check_inputs(root, json.loads((root / 'manifest.json').read_text()))
