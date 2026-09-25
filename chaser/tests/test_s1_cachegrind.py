"""Cachegrind selection must preserve raw totals and reject population mismatches."""
import pytest
from chaser.s1.cachegrind import read_counts

HEADER = 'events: Ir I1mr ILmr Dr D1mr DLmr Dw D1mw DLmw\n'
TRACE = HEADER + 'fl=/tmp/workload.c\nfn=chaser_s1\n26 10 1 1 15 15 0 0 0 0\n27 1 0 0 1 0 0 0 0 0\nfn=s1_prepare\n14 20 0 0 0 0 0 10 10 10\nsummary: 31 1 1 16 15 0 10 10 10\n'


def test_select_load_lines_without_discarding_function_counts():
    result = read_counts(TRACE, '/tmp/workload.c', [26], 15)
    assert result['counts'] == [0, 15, 0]
    assert result['function_events']['Dr'] == 16
    assert result['selected_events']['Dr'] == 15
    assert result['summary_events']['Dw'] == 10


@pytest.mark.parametrize('text', [TRACE.replace('15 15 0', '15 16 0'),
    TRACE.replace('15 15 0', '15 10 11'), TRACE.replace('15 15 0', '14 14 0'),
    TRACE.replace('fn=chaser_s1', 'fn=other'), TRACE.split('summary:')[0],
    TRACE.replace('26 10 1 1 15 15 0 0 0 0', '26 10 1')])
def test_incomplete_or_incompatible_report_rejected(text):
    with pytest.raises(ValueError):
        read_counts(text, '/tmp/workload.c', [26], 15)


def test_same_function_name_in_another_file_not_selected():
    text = TRACE.replace('summary:', 'fl=/tmp/other.c\nfn=chaser_s1\n26 1 0 0 7 7 7 0 0 0\nsummary:')
    assert read_counts(text, '/tmp/workload.c', [26], 15)['counts'] == [0, 15, 0]


def test_real_cachegrind_uses_execution_counts_and_reports_warm_difference(tmp_path):
    from chaser.s1.execution import run_execution_suite
    from chaser.s1.cachegrind import run_cachegrind
    source = tmp_path / 'host'
    output = tmp_path / 'cg'
    assert run_execution_suite(output_dir=source, case_ids=['packed_8', 'conflict_5'])['status'] == 'ok'
    result = run_cachegrind(input_dir=source, output_dir=output)
    assert result['status'] == 'ok'
    packed, conflict = result['rows']
    assert packed['cachegrind']['counts'] == [24, 0, 0]
    assert conflict['cachegrind']['counts'] == [0, 15, 0]
    assert conflict['cold_reference_counts'] == [0, 10, 5]
    assert conflict['cachegrind']['function_events']['Dr'] == 16
    assert result['summary']['csrd_count_equal'] == 0
    with pytest.raises(FileExistsError):
        run_cachegrind(input_dir=source, output_dir=output)
    # An ELF changed since YARDA analyzed it must never be compared successfully.
    (source / 'packed_8/workload.exe').write_bytes(b'changed')
    failed = run_cachegrind(input_dir=source, output_dir=tmp_path / 'bad')
    assert failed['status'] == 'failed'
    assert failed['rows'][0]['status'] == 'failed'
    assert failed['rows'][1]['status'] == 'ok'


def test_frozen_cachegrind_results_reproduce_from_external_tool_output():
    import gzip
    import json
    from pathlib import Path
    from chaser.s1.execution import ROOT, file_hash
    evidence = ROOT / 'artifacts/s1/cachegrind-v1'
    manifest = json.loads((evidence / 'manifest.json').read_text())
    for name, digest in manifest['sha256'].items():
        assert file_hash(evidence / name) == digest
    suite = json.loads((evidence / 'suite.json').read_text())
    assert suite['status'] == 'ok' and suite['summary']['evaluated'] == 25
    for row in suite['rows']:
        source = next(p for p in row['input_sha256'] if Path(p).suffix == '.c')
        with gzip.open(evidence / row['id'] / 'cachegrind.out.gz', 'rt') as stream:
            actual = read_counts(stream.read(), source, row['cachegrind']['load_lines'],
                                 sum(row['csrd_counts']))
        assert actual['counts'] == row['cachegrind']['counts']
        assert list(actual['ratios']) == row['reference']
