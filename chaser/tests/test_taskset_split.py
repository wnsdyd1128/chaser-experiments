"""Within-family splits bind input identities before any measurement exists."""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from chaser.dataset.builder import Workload, build_dataset, freeze_split
from chaser.periodic.measurement import digest


def population(counts=(41, 41, 41, 43, 41)):
    return [Workload(f'f{f}-w{i}', f'f{f}', {}, 'pending',
                     input_signature=digest([f, i]))
            for f, count in enumerate(counts) for i in range(count)]


def test_every_family_is_stratified_and_rounding_is_explicit(tmp_path):
    split = freeze_split(tmp_path / 'split.json', population(), seed=20260921)
    assert Counter(split['assignments'].values()) == dict(train=126, validation=41, test=40)
    assert split['family_counts']['f0'] == dict(train=25, validation=8, test=8)
    assert split['family_counts']['f3'] == dict(train=26, validation=9, test=8)
    assert split['schema_version'] == 2
    assert split['ratios'] == dict(train=0.6, validation=0.2, test=0.2)


def test_order_independence_frozen_reuse_and_seed_variation(tmp_path):
    rows = population()
    path = tmp_path / 'split.json'
    first = freeze_split(path, rows, seed=42)
    before = path.read_bytes()
    assert freeze_split(path, reversed(rows), seed=99) == first
    assert path.read_bytes() == before
    assert freeze_split(tmp_path / 'repeat.json', reversed(rows), seed=42) == first
    other = freeze_split(tmp_path / 'other.json', rows, seed=99)
    assert other['assignments'] != first['assignments']


def test_duplicate_aliases_share_split_without_changing_unique_counts(tmp_path):
    rows = population((10,))
    first = freeze_split(tmp_path / 'first.json', rows, seed=7)
    rows.append(replace(rows[0], workload_id='renamed-policy-variant'))
    split = freeze_split(tmp_path / 'aliases.json', rows, seed=7)
    assert split['assignments']['renamed-policy-variant'] == split['assignments'][rows[0].workload_id]
    assert split['family_counts'] == first['family_counts']
    assert all(split['assignments'][w] == group for w, group in first['assignments'].items())


@pytest.mark.parametrize('count,expected', [(3, (1, 1, 1)), (4, (2, 1, 1)),
                                          (5, (3, 1, 1)), (6, (4, 1, 1))])
def test_small_families_keep_all_splits_nonempty(tmp_path, count, expected):
    split = freeze_split(tmp_path / 'split.json', population((count,)), seed=7)
    assert tuple(split['family_counts']['f0'][g] for g in ('train', 'validation', 'test')) == expected


@pytest.mark.parametrize('count', [1, 2])
def test_fewer_than_three_unique_inputs_is_rejected_without_a_file(tmp_path, count):
    path = tmp_path / 'split.json'
    with pytest.raises(ValueError, match='three unique'):
        freeze_split(path, population((count,)), seed=7)
    assert not path.exists()


def test_missing_identity_and_conflicting_family_are_rejected(tmp_path):
    rows = population((5,))
    with pytest.raises(ValueError, match='input signature'):
        freeze_split(tmp_path / 'missing.json', [replace(rows[0], input_signature=None)], seed=7)
    rows.append(replace(rows[0], workload_id='cross-family-copy', family_id='other'))
    with pytest.raises(ValueError, match='multiple families'):
        freeze_split(tmp_path / 'conflict.json', rows, seed=7)


@pytest.mark.parametrize('mutation', ['assignment', 'seed', 'hash', 'count', 'identity', 'ratio'])
def test_frozen_manifest_tampering_is_rejected(tmp_path, mutation):
    rows = population((10,))
    path = tmp_path / 'split.json'
    split = freeze_split(path, rows, seed=7)
    if mutation == 'assignment':
        name = next(iter(split['assignments']))
        split['assignments'][name] = 'test' if split['assignments'][name] == 'train' else 'train'
    elif mutation == 'seed':
        split['seed'] += 1
    elif mutation == 'hash':
        split['membership_hash'] = 'bad'
    elif mutation == 'count':
        split['family_counts']['f0']['train'] += 1
    elif mutation == 'identity':
        split['input_signatures'][rows[0].workload_id] = digest('different')
    else:
        split['ratios']['train'] = 0.7
    path.write_text(json.dumps(split))
    with pytest.raises(ValueError, match='Frozen split'):
        freeze_split(path, rows, seed=7)


def test_changed_input_and_membership_cannot_reuse_freeze(tmp_path):
    rows = population((10,))
    path = tmp_path / 'split.json'
    freeze_split(path, rows, seed=7)
    for changed in (rows[:-1], [replace(rows[0], input_signature=digest('changed')), *rows[1:]]):
        with pytest.raises(ValueError, match='Frozen split'):
            freeze_split(path, changed, seed=7)


def test_dataset_variants_and_policies_use_workload_assignment(tmp_path):
    from test_dataset import inputs

    cases, old, measurements, provenance = inputs()
    rows = [replace(w, family_id='shared', input_signature=digest(w.workload_id)) for w in old]
    split = freeze_split(tmp_path / 'split.json', rows, seed=7)
    for policy in ('first-policy', 'second-policy'):
        data = build_dataset(cases, rows, [replace(m, allocator_id=policy) for m in measurements],
                             provenance, split, expected_runs=1)
        assert len(data['rf_samples']) == 80
        assert all(s['split_group'] == split['assignments'][s['workload_id']]
                   for s in data['rf_samples'])
    failed = build_dataset(cases, rows, measurements[:-1], provenance, split, expected_runs=1)
    assert failed['metadata']['split'] == split
    assert len(failed['metadata']['excluded']) == 1


def test_cli_reuses_new_split_for_repeated_measurements(tmp_path):
    from dataclasses import asdict
    import subprocess
    import sys
    from test_dataset import inputs

    cases, rows, measurements, provenance = inputs()
    rows = [replace(w, family_id='shared', input_signature=digest(w.workload_id)) for w in rows]
    split_path = tmp_path / 'split.json'
    split = freeze_split(split_path, rows, seed=7)
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(dict(cases=cases, workloads=[asdict(w) for w in rows],
        measurements=[asdict(replace(m, run_id=str(i))) for m in measurements for i in range(2)],
        provenance=provenance)))
    subprocess.run([sys.executable, '-m', 'tools.build_dataset', str(source),
                    '--split', str(split_path), '--seed', '999', '--expected-runs', '2',
                    '--output', str(tmp_path / 'dataset')], check=True)
    metadata = json.loads((tmp_path / 'dataset/metadata.json').read_text())
    assert metadata['split'] == split
    assert not metadata['excluded']


def test_legacy_split_cannot_be_silently_reused_as_new_policy(tmp_path):
    from test_dataset import inputs

    _, rows, _, _ = inputs()
    path = tmp_path / 'split.json'
    freeze_split(path, rows, seed=7, policy='family-70-20-10-v1')
    with pytest.raises(ValueError, match='policy mismatch'):
        freeze_split(path, rows, seed=7)


def test_taskset_identity_ignores_names_and_policy_but_preserves_work(tmp_path):
    from chaser.dataset.splits import taskset_signature

    config = dict(workload_id='original', family_id='family', policy_id='policy',
                  horizon_ticks=40, eligible_for_training=False, test_eligible=False,
                  tasks=[dict(task_id='t0', core=0, pattern='cyclic', distinct=64,
                              stride=32, sweeps=2, period_ticks=20)])
    changed = deepcopy(config)
    changed.update(workload_id='copy', family_id='copy', policy_id='other-policy',
                   eligible_for_training=True, test_eligible=True)
    for task in changed['tasks']:
        task.update(task_id='renamed-' + task['task_id'], core=(task['core'] + 1) % 4)
    assert taskset_signature(changed) == taskset_signature(config)
    changed['tasks'][0]['sweeps'] += 1
    assert taskset_signature(changed) != taskset_signature(config)
