import json
from hashlib import sha256
from pathlib import Path
import subprocess

import pytest

from chaser.s1_workloads import cases, source_text
from chaser.s1_suite import run_suite, summarize

def test_catalog_pairs_and_capacity_boundaries():
    catalog = {case['id']: case for case in cases()}
    for d in (3, 4, 5, 8):
        spread, conflict = catalog[f'spread_{d}'], catalog[f'conflict_{d}']
        assert spread['distinct'] == conflict['distinct'] == d
        assert spread['stride'] == 32 and conflict['stride'] == 4096
    for d in (511, 512, 513, 65535, 65536, 65537, 73728):
        assert catalog[f'capacity_{d}']['distinct'] == d
    assert catalog['packed_8']['stride'] == 1
    with pytest.raises(ValueError):
        source_text(catalog['packed_8'], 1)


def test_summary_weights_workloads_equally_and_reports_failures():
    rows = [dict(id='small', status='ok', modeled_accesses=3,
                 global_rd=[1, 0, 0], csrd=[0, 1, 0], reference=[0, 1, 0]),
            dict(id='large', status='ok', modeled_accesses=300,
                 global_rd=[0, 1, 0], csrd=[0, 1, 0], reference=[0, 1, 0]),
            dict(id='broken', status='failed', error='timeout')]
    summary = summarize(rows)
    assert summary['evaluated'] == 2
    assert summary['failed'] == ['broken']
    assert summary['global_rd']['mae'] == [0.5, 0.5, 0]
    assert summary['global_rd']['rmse'] == pytest.approx([2 ** -0.5, 2 ** -0.5, 0])
    assert summary['global_rd']['max_absolute_error'] == [1, 1, 0]
    assert summary['csrd']['mae'] == [0, 0, 0]
    assert summarize(rows[-1:])['global_rd'] is None


def test_source_derived_suite_closed_forms_and_same_mean(tmp_path):
    ids = ['packed_8', 'spread_8', 'conflict_3', 'conflict_4', 'conflict_5',
           'conflict_8', 'capacity_512', 'capacity_513', 'mean_uniform', 'mean_mixed']
    report = run_suite(output_dir=tmp_path / 'suite', case_ids=ids, sweeps=3,
                       max_references=6000, timeout=30)
    assert report['status'] == 'ok', report
    rows = {row['id']: row for row in report['rows']}
    for name, counts in [('packed_8', [23, 0, 1]), ('spread_8', [16, 0, 8]),
                         ('conflict_3', [6, 0, 3]), ('conflict_4', [8, 0, 4]),
                         ('conflict_5', [0, 10, 5]), ('conflict_8', [0, 16, 8]),
                         ('capacity_512', [1024, 0, 512]),
                         ('capacity_513', [1016, 10, 513]),
                         ('mean_uniform', [4092, 0, 1024]),
                         ('mean_mixed', [2046, 2046, 1024])]:
        row = rows[name]
        assert row['reference_counts'] == counts
        assert row['csrd'] == row['reference']
        assert row['source_accesses'] == row['modeled_accesses'] == sum(counts)
        assert row['element_ca'] == pytest.approx(1 / (8 if name == 'packed_8' else
                                                       512 if name.startswith('mean_') else
                                                       int(name.rsplit('_', 1)[1])))
    assert rows['packed_8']['line_ca'] == 1
    assert rows['spread_8']['line_ca'] == rows['conflict_8']['line_ca'] == 1 / 8
    assert rows['mean_mixed']['line_mean_rd'] == rows['capacity_512']['line_mean_rd'] == 511
    assert rows['mean_mixed']['line_histogram'] == {'0': 2046, '1022': 2046}
    assert rows['capacity_512']['line_histogram'] == {'511': 1024}
    assert rows['mean_mixed']['reference'] != rows['capacity_512']['reference']
    uniform, mixed = rows['mean_uniform'], rows['mean_mixed']
    assert uniform['line_mean_rd'] == mixed['line_mean_rd'] == 511
    assert uniform['cold_fraction'] == mixed['cold_fraction']
    assert uniform['modeled_accesses'] == mixed['modeled_accesses'] == 5116
    assert uniform['line_histogram'] == {'511': 4092}
    assert (tmp_path / 'suite/results.csv').exists()
    assert report['execution_validation'] == 'not-performed'
    # Refuse reuse before building or replacing any previous artifact.
    with pytest.raises(FileExistsError):
        run_suite(output_dir=tmp_path / 'suite', case_ids=ids, sweeps=3,
                  max_references=6000, timeout=30)


def test_suite_preserves_limit_failure_and_continues(tmp_path):
    report = run_suite(output_dir=tmp_path / 'suite',
                       case_ids=['capacity_73728', 'packed_8'], sweeps=3,
                       max_references=100, timeout=30)
    assert report['status'] == 'failed'
    assert report['summary']['failed'] == ['capacity_73728']
    assert report['rows'][1]['status'] == 'ok'
    assert json.loads((tmp_path / 'suite/capacity_73728/failure.json').read_text())['phase'] == 'budget'


def test_real_llc_boundary_has_partial_set_overflow(tmp_path):
    report = run_suite(output_dir=tmp_path / 'suite', case_ids=['capacity_65537'])
    assert report['status'] == 'ok'
    row = report['rows'][0]
    assert row['reference_counts'] == [0, 131064, 65547]
    assert row['global_rd'] == [0, 0, 1]
    assert row['csrd'] == row['reference']


def test_cli_failed_case_returns_nonzero_with_report(tmp_path):
    result = subprocess.run(['python3', '-m', 'tools.run_s1_suite', '--output', str(tmp_path / 'suite'),
                             '--cases', 'capacity_73728', '--max-references', '100'],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads((tmp_path / 'suite/suite.json').read_text())['summary']['evaluated'] == 0


def test_frozen_model_evidence_is_complete_and_matches_comparisons():
    directory = Path(__file__).resolve().parents[1] / 'artifacts/s1/model-v1'
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, digest in manifest['sha256'].items():
        assert sha256((directory / name).read_bytes()).hexdigest() == digest
    suite = json.loads((directory / 'suite.json').read_text())
    comparisons = json.loads((directory / 'comparisons.json').read_text())
    assert suite['selection'] == 'full'
    assert len(suite['rows']) == len(comparisons) == 25
    assert suite['summary'] == summarize(suite['rows'])
    for row in suite['rows']:
        comparison = comparisons[row['id']]
        assert row['status'] == comparison['status'] == 'ok'
        assert row['source_coverage'] == 1
        assert comparison['csrd']['counts'] == row['reference_counts']
        assert comparison['reference']['counts'] == row['reference_counts']
