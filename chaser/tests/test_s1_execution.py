"""Real host compiler/Lackey/YARDA correspondence and failure propagation."""

import gzip
import json

import pytest

from chaser import s1_execution


@pytest.fixture(scope='module')
def pilot(tmp_path_factory):
    output = tmp_path_factory.mktemp('execution') / 'pilot'
    report = s1_execution.run_execution_suite(output_dir=output,
                        case_ids=['packed_8', 'conflict_5', 'capacity_513'])
    return output, report


def test_real_host_sequence_and_cold_replay(pilot):
    output, report = pilot
    assert report['status'] == 'ok'
    assert report['target_execution_validation'] == 'not-performed'
    assert report['summary']['passed'] == 3
    expected = [[23, 0, 1], [0, 10, 5], [1016, 10, 513]]
    for row, counts in zip(report['rows'], expected):
        assert row['sequence']['equal'] is True
        assert row['sequence']['expected_sha256'] == row['sequence']['observed_sha256']
        assert row['trace_reference_counts'] == counts
        assert row['trace']['excluded_outside_roi'] > 0
        assert row['trace']['excluded_outside_array'] > 0
        for name, digest in row['artifact_sha256'].items():
            assert s1_execution.file_hash(output / row['id'] / name) == digest


def test_existing_output_is_never_overwritten(pilot):
    output, _ = pilot
    before = (output / 'suite.json').read_bytes()
    with pytest.raises(FileExistsError):
        s1_execution.run_execution_suite(output_dir=output, case_ids=['packed_8'])
    assert (output / 'suite.json').read_bytes() == before


def test_same_counts_do_not_hide_execution_sequence_mismatch(tmp_path, monkeypatch):
    original = s1_execution.parse_lackey

    def reordered(*args, **kwargs):
        rows, stats = original(*args, **kwargs)
        rows[0], rows[1] = rows[1], rows[0]
        return rows, stats

    monkeypatch.setattr(s1_execution, 'parse_lackey', reordered)
    report = s1_execution.run_execution_suite(output_dir=tmp_path / 'mismatch', case_ids=['packed_8'])
    row = report['rows'][0]
    assert report['status'] == 'failed'
    assert row['status'] == 'mismatch'
    assert row['cache_counts_equal'] is True
    assert row['sequence']['equal'] is False


@pytest.mark.parametrize('fault', ['checksum', 'gzip', 'deflate'])
def test_bad_execution_evidence_is_preserved_as_failure(tmp_path, monkeypatch, fault):
    original = s1_execution.capture

    def corrupted(argv, directory, **kwargs):
        record = original(argv, directory, **kwargs)
        if directory.name != 'packed_8':
            return record
        if fault == 'checksum':
            (directory / 'stdout.txt').write_text('checksum=0 expected=24\n')
        elif fault == 'gzip':
            path = directory / 'trace.log.gz'
            path.write_bytes(path.read_bytes()[:-8])
        else:
            broken = bytearray(gzip.compress(b'I 100,1\n'))
            broken[10] = 6  # Reserved DEFLATE block type.
            (directory / 'trace.log.gz').write_bytes(broken)
        return record

    monkeypatch.setattr(s1_execution, 'capture', corrupted)
    output = tmp_path / fault
    selected = ['packed_8', 'spread_3'] if fault == 'deflate' else ['packed_8']
    report = s1_execution.run_execution_suite(output_dir=output, case_ids=selected)
    assert report['status'] == 'failed'
    assert report['rows'][0]['status'] == 'failed'
    assert (output / 'packed_8/trace.log.gz').is_file()
    assert 'error' in json.loads((output / 'packed_8/execution.json').read_text())
    if fault == 'deflate':
        assert report['rows'][1]['id'] == 'spread_3'
        assert report['rows'][1]['status'] == 'ok'


def test_frozen_execution_evidence_is_complete_and_hash_consistent():
    from chaser.s1_workloads import cases

    evidence = s1_execution.ROOT / 'artifacts/s1/host-trace-v1'
    manifest = json.loads((evidence / 'manifest.json').read_text())
    for name, digest in manifest['sha256'].items():
        assert s1_execution.file_hash(evidence / name) == digest
    report = json.loads((evidence / 'suite.json').read_text())
    assert report['status'] == 'ok'
    assert {r['id'] for r in report['rows']} == {c['id'] for c in cases()}
    model = json.loads((evidence.parent / 'model-v1/suite.json').read_text())
    model_counts = {r['id']: r['reference_counts'] for r in model['rows']}
    for row in report['rows']:
        assert row['sequence']['equal'] is True
        assert row['sequence']['expected_count'] == row['checksum']
        assert row['sequence']['expected_sha256'] == row['sequence']['observed_sha256']
        assert row['trace_reference_counts'] == row['csrd']['counts'] == model_counts[row['id']]
        assert 'trace.log.gz' in row['artifact_sha256']
