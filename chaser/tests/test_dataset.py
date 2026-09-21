from dataclasses import asdict, replace
import json

import pytest

from chaser.dataset import Workload, build_dataset, freeze_split, write_dataset
from chaser.labeling import Measurement
from chaser.rf import fit_rf


def inputs():
    from pathlib import Path

    cases = json.loads(Path('exports/locality.json').read_text())['cases']
    workloads = [Workload(f'w{i}', f'f{i}', {'spread': 0.1 + i / 100},
                          'measured-mean') for i in range(10)]
    rows = [Measurement(w.workload_id, a, 'topology', 'allocator', f'map{a}', '0',
                        10, 20 + a, 'ok', measurement_source='synthetic')
            for w in workloads for a in range(3)]
    provenance = {t: dict(source_hash='source', elf_hash='elf', analyzer_commit='commit',
                         cache_model_id='model', cache_config_hash='config', model_hash=None)
                  for t in cases}
    return cases, workloads, rows, provenance


def test_split_is_frozen_and_variants_share_family(tmp_path):
    _, workloads, _, _ = inputs()
    workloads.append(replace(workloads[0], workload_id='period-variant'))
    path = tmp_path / 'split.json'
    first = freeze_split(path, workloads, seed=42, policy='family-70-20-10-v1')
    before = path.read_bytes()
    assert freeze_split(path, reversed(workloads), seed=99, policy='family-70-20-10-v1') == first
    assert path.read_bytes() == before
    assert [list(first['families'].values()).count(s) for s in
            ('train', 'validation', 'test')] == [7, 2, 1]
    with pytest.raises(ValueError):
        freeze_split(path, workloads[:-1], seed=42, policy='family-70-20-10-v1')


def test_bridge_common_population_no_label_leakage_and_rf_connection(tmp_path):
    cases, workloads, rows, provenance = inputs()
    split = freeze_split(tmp_path / 'split.json', workloads, seed=42, policy='family-70-20-10-v1')
    data = build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)
    assert len(data['rf_samples']) == 80  # CA three controls + five CLS alphas
    train = [s for s in data['rf_samples'] if s['representation_id'] == 'caas-ca'
             and s['split_group'] == 'train']
    by_id = {w.workload_id: w for w in workloads}
    model = fit_rf(cases, [by_id[s['workload_id']].utilization for s in train],
                   [s['label'] for s in train], 'caas-ca', seed=42)
    assert model.pipeline['scale'].n_features_in_ == 11
    assert all(len(s['features']) == 11 for s in data['rf_samples'])
    write_dataset(tmp_path / 'data', data)
    assert len((tmp_path / 'data/raw_measurements.jsonl').read_text().splitlines()) == 30
    assert json.loads((tmp_path / 'data/task_characterization.jsonl').read_text().splitlines()[0])['utilization_source'] == 'measured-mean'
    with pytest.raises(FileExistsError):
        write_dataset(tmp_path / 'data', data)


def test_incomplete_locality_or_measurement_excludes_every_representation(tmp_path):
    cases, workloads, rows, provenance = inputs()
    cases['spread']['clp'] = None
    split = freeze_split(tmp_path / 'split.json', workloads, seed=1, policy='family-70-20-10-v1')
    data = build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)
    assert not data['rf_samples']
    assert len(data['metadata']['excluded']) == 10
    cases, workloads, rows, provenance = inputs()
    data = build_dataset(cases, workloads, rows[:-1], provenance, split, expected_runs=1)
    assert {s['workload_id'] for s in data['rf_samples']} == {f'w{i}' for i in range(9)}
    assert len(data['raw_measurements']) == 29


def test_missing_u_and_provenance_are_errors(tmp_path):
    cases, workloads, rows, provenance = inputs()
    split = freeze_split(tmp_path / 'split.json', workloads, seed=1, policy='family-70-20-10-v1')
    workloads[0] = replace(workloads[0], utilization={'spread': None})
    with pytest.raises(ValueError, match='Utilization'):
        build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)
    workloads[0] = replace(workloads[0], utilization={'spread': 0.2})
    del provenance['spread']['elf_hash']
    with pytest.raises(ValueError, match='provenance'):
        build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)


def test_topology_fixed_across_workloads_but_mapping_may_vary(tmp_path):
    cases, workloads, rows, provenance = inputs()
    split = freeze_split(tmp_path / 'split.json', workloads, seed=1, policy='family-70-20-10-v1')
    rows[-1] = replace(rows[-1], mapping_hash='other-workload-mapping')
    assert build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)['rf_samples']
    rows[-1] = replace(rows[-1], topology_id='other-core-grouping')
    with pytest.raises(ValueError, match='topology'):
        build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)


def test_label_changes_do_not_change_features_and_task_join_is_order_independent(tmp_path):
    cases, workloads, rows, provenance = inputs()
    workloads = [replace(w, utilization={'spread': 0.1, 'conflict': 0.7}) for w in workloads]
    split = freeze_split(tmp_path / 'split.json', workloads, seed=1, policy='family-70-20-10-v1')
    first = build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)
    workloads = [replace(w, utilization={'conflict': 0.7, 'spread': 0.1}) for w in workloads]
    rows = [replace(r, tat=1 if r.architecture == 2 else 50, tet=100) for r in rows]
    second = build_dataset(cases, reversed(workloads), reversed(rows), provenance, split, expected_runs=1)
    assert {s['label'] for s in first['rf_samples']} == {0}
    assert {s['label'] for s in second['rf_samples']} == {2}
    assert [s['features'] for s in first['rf_samples']] == [s['features'] for s in second['rf_samples']]
    assert first['rf_samples'][0]['features'][5:] == pytest.approx([0.4, 0.3, 0.1, 0.7, 0.4, 0.8])


def test_missing_one_alpha_excludes_common_population(tmp_path):
    cases, workloads, rows, provenance = inputs()
    split = freeze_split(tmp_path / 'split.json', workloads, seed=1, policy='family-70-20-10-v1')
    del cases['spread']['cls']['0.7']
    data = build_dataset(cases, workloads, rows, provenance, split, expected_runs=1)
    assert not data['rf_samples']
    assert all('alpha=0.7' in r['reason'] for r in data['metadata']['excluded'])


def test_cli_exports_deterministic_tables_and_preserves_existing_dataset(tmp_path):
    import subprocess
    import sys

    cases, workloads, rows, provenance = inputs()
    payload = {'cases': cases, 'workloads': [asdict(w) for w in workloads],
               'measurements': [asdict(r) for r in rows], 'provenance': provenance}
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(payload))
    command = [sys.executable, '-m', 'tools.build_dataset', str(source),
               '--split', str(tmp_path / 'split.json'), '--seed', '42', '--expected-runs', '1', '--split-policy', 'family-70-20-10-v1']
    for name in ('first', 'second'):
        subprocess.run(command + ['--output', str(tmp_path / name)], check=True)
    for file in (tmp_path / 'first').iterdir():
        assert file.read_bytes() == (tmp_path / 'second' / file.name).read_bytes()
    result = subprocess.run(command + ['--output', str(tmp_path / 'first')], capture_output=True)
    assert result.returncode == 2
