import json
from copy import deepcopy
from hashlib import sha256

import pytest

from chaser.features import build_features
from chaser.final_clp import build_clp_samples, export_final_clp


POLICIES = ('caas-ca', 'ca-csrd', 'cls')


def fixture_data():
    split = {'assignments': {'w1': 'train', 'w2': 'test', 'failed': 'train'},
             'workloads': {'w1': 'family-a', 'w2': 'family-b', 'failed': 'family-a'}}
    profiles = {'w1': ([1, 0, 0], [0, 1, 0]), 'w2': ([0.25, 0.5, 0.25],)}
    characterizations = []
    samples = {}
    eligibility = {'common_workloads': ['w1', 'w2'], 'required_policies': {},
                   'policy_workloads': []}
    for w, values in profiles.items():
        for i, profile in enumerate(values):
            characterizations.append({
                'workload_id': w, 'task_id': f'{w}-t{i}', 'clp': profile,
                'utilization': 0.1 * (i + 1), 'utilization_source': 'measured-mean',
                'modeled_accesses': 1, 'u_characterization_id': 'u-id', 'u_elf_hash': 'elf',
                'ca_caas_element': 0.5, 'ca_csrd_l1': 0.6,
                'cls': {'0.5': 0.7},
            })
    tasks = {w: [r for r in characterizations if r['workload_id'] == w] for w in profiles}
    for index, policy in enumerate(POLICIES):
        eligibility['required_policies'][policy] = {}
        samples[policy] = []
        for w in split['assignments']:
            eligible = w in profiles
            evidence = {'label': index}
            eligibility['policy_workloads'].append({
                'kind': policy, 'workload_id': w, 'eligible': eligible,
                'common_eligible': eligible, 'label_evidence': evidence})
            if not eligible:
                continue
            for rep in POLICIES:
                features = build_features(tasks[w], rep, alpha=0.5 if rep == 'cls' else None)
                samples[policy].append({
                    'workload_id': w, 'representation_id': rep,
                    'alpha': 0.5 if rep == 'cls' else None,
                    'features': features, 'label': index, 'label_evidence': evidence,
                    'split_group': split['assignments'][w],
                    'family_id': split['workloads'][w], 'allocator_id': policy,
                    'eligible_for_common_analysis': True,
                })
    return eligibility, split, characterizations, samples


def test_clp_export_preserves_policy_labels_split_and_common_analysis_set():
    eligibility, split, tasks, samples = fixture_data()
    result = build_clp_samples(eligibility, split, tasks, samples)
    assert set(result) == set(POLICIES)
    assert all(len(result[p]) == 2 for p in POLICIES)
    assert {r['workload_id'] for rows in result.values() for r in rows} == {'w1', 'w2'}
    for index, policy in enumerate(POLICIES):
        for row in result[policy]:
            assert row['representation_id'] == 'clp'
            assert row['alpha'] is None
            assert row['label'] == index
            assert row['split_group'] == split['assignments'][row['workload_id']]
            source = [t for t in tasks if t['workload_id'] == row['workload_id']]
            assert row['features'] == build_features(source, 'clp')
            assert len(row['features']) == 21
    assert result['caas-ca'][0]['features'] == result['cls'][0]['features']


def test_clp_export_rejects_label_mismatch_and_invalid_profile():
    eligibility, split, tasks, samples = fixture_data()
    changed = deepcopy(samples)
    changed['cls'][0]['label'] = 1
    with pytest.raises(ValueError):
        build_clp_samples(eligibility, split, tasks, changed)
    tasks[0]['clp'] = [1, 0, 0.1]
    with pytest.raises(ValueError):
        build_clp_samples(eligibility, split, tasks, samples)


def test_clp_export_writes_new_version_without_touching_source(tmp_path):
    eligibility, split, tasks, samples = fixture_data()
    source = tmp_path / 'source'
    source.mkdir()
    files = {'eligibility.json': json.dumps(eligibility), 'split.json': json.dumps(split)}
    for policy, rows in samples.items():
        files[f'{policy}/rf_samples.jsonl'] = ''.join(json.dumps(x) + '\n' for x in rows)
        files[f'{policy}/task_characterization.jsonl'] = ''.join(
            json.dumps(x) + '\n' for x in tasks)
    for path, content in files.items():
        target = source / path
        target.parent.mkdir(exist_ok=True)
        target.write_text(content)
    lock = {'analysis_set_id': 'fixture-common-2', 'common_count': 2,
            'split_counts': {'train': 1, 'test': 1},
            'source_hashes': {name: sha256(content.encode()).hexdigest()
                              for name, content in files.items()}}
    (source / 'analysis-set-lock.json').write_text(json.dumps(lock))
    output = tmp_path / 'clp-v1'
    export_final_clp(source, output)
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['analysis_set_id'] == lock['analysis_set_id']
    assert 'cohort_id' not in summary
    assert summary['feature_dimension'] == 21
    assert summary['sample_rows'] == dict.fromkeys(POLICIES, 2)
    assert summary['source_hashes'] == lock['source_hashes']
    assert len((output / 'cls/rf_samples.jsonl').read_text().splitlines()) == 2
    assert all((source / name).read_text() == content for name, content in files.items())
    repeat = tmp_path / 'clp-v1-repeat'
    export_final_clp(source, repeat)
    assert {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()} == {
        p.relative_to(repeat): p.read_bytes() for p in repeat.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        export_final_clp(source, output)
    (source / 'split.json').write_text(files['split.json'] + ' ')
    with pytest.raises(ValueError, match='hash mismatch'):
        export_final_clp(source, tmp_path / 'clp-v1-tampered')
