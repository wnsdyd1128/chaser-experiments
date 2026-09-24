"""PolyBench-derived Cachegrind comparison must count the same data accesses."""

import pytest

from chaser.s1_polybench import read_cachegrind_counts, selected_array_accesses


def test_versioned_polybench_sources_match_frozen_hashes():
    from pathlib import Path

    from chaser.s1_execution import file_hash
    from tools.run_s1_polybench import SOURCE_HASHES

    sources = Path(__file__).resolve().parents[1] / 'artifacts/s1/polybench-cold-v1/sources'
    assert all(file_hash(sources / name) == digest
               for name, digest in SOURCE_HASHES.items())


def test_cachegrind_keeps_unattributed_array_accesses_and_excludes_return_stack():
    raw = (
        'events: Ir I1mr ILmr Dr D1mr DLmr Dw D1mw DLmw\n'
        'fl=/tmp/kernel.c\nfn=kernel\n'
        '0 10 1 1 3 1 1 2 0 0\n'
        '12 8 0 0 1 0 0 1 1 0\n'
        '25 1 0 0 1 1 1 0 0 0\n'
        'summary: 19 1 1 5 2 2 3 1 0\n'
    )
    result = read_cachegrind_counts(raw, '/tmp/kernel.c', 'kernel', {25}, 7)
    assert result['counts'] == [5, 1, 1]
    assert result['selected_events']['Dr'] == 4
    assert result['selected_events']['Dw'] == 3
    assert result['excluded_events']['Dr'] == 1
    full = read_cachegrind_counts(raw, '/tmp/kernel.c', 'kernel', set(), None)
    assert full['counts'] == [5, 1, 2]
    assert full['selected_events']['Dr'] + full['selected_events']['Dw'] == 8


def test_cachegrind_rejects_wrong_population_or_missing_exclusion():
    raw = (
        'events: Ir I1mr ILmr Dr D1mr DLmr Dw D1mw DLmw\n'
        'fl=/tmp/kernel.c\nfn=kernel\n'
        '0 10 1 1 3 1 1 2 0 0\n'
        '25 1 0 0 1 1 1 0 0 0\n'
        'summary: 11 1 1 4 2 2 2 0 0\n'
    )
    with pytest.raises(ValueError, match='population'):
        read_cachegrind_counts(raw, '/tmp/kernel.c', 'kernel', {25}, 7)
    with pytest.raises(ValueError, match='excluded'):
        read_cachegrind_counts(raw, '/tmp/kernel.c', 'kernel', {26}, 5)


def test_lackey_array_filter_rejects_access_in_gap():
    trace = [
        'I  00000100,1\n',
        ' L 00001000,8\n',
        ' S 00001010,8\n',
        'I  00000200,1\n',
    ]
    assert selected_array_accesses(trace, function=(0x100, 0x10),
                                   arrays=[(0x1000, 8), (0x1010, 8)],
                                   max_references=10)[0] == [
                                       ('load', 0x1000, 8), ('store', 0x1010, 8)]
    trace[2] = ' S 00001008,8\n'
    with pytest.raises(ValueError, match='outside named arrays'):
        selected_array_accesses(trace, function=(0x100, 0x10),
                                arrays=[(0x1000, 8), (0x1010, 8)], max_references=10)


def test_frozen_external_comparison_reaggregates_raw_trace_and_cachegrind():
    import gzip
    from hashlib import sha256
    import json
    from pathlib import Path

    from chaser.s1_trace import compare_accesses

    evidence = Path(__file__).resolve().parents[1] / 'artifacts/s1/polybench-cold-v1'
    if not (evidence / 'manifest.json').is_file():
        pytest.skip('Local PolyBench raw capture is not present')
    manifest = json.loads((evidence / 'manifest.json').read_text())['sha256']
    assert len(manifest) >= 80
    for name, digest in manifest.items():
        assert sha256((evidence / name).read_bytes()).hexdigest() == digest
    report = json.loads((evidence / 'suite.json').read_text())
    assert report['status'] == 'ok' and len(report['rows']) == 4
    for row in report['rows']:
        case = evidence / row['id']
        with gzip.open(case / 'comparison/actual.events.json.gz', 'rt') as stream:
            events = json.load(stream)['events']
        expected = [(event['operation'], event['linked_address'], event['access_size'])
                    for event in events if event['line_span_ordinal'] == 0]
        with gzip.open(case / 'trace.log.gz', 'rt') as stream:
            actual, _ = selected_array_accesses(
                stream, function=tuple(row['symbols'][row['function']]),
                arrays=[tuple(row['symbols'][name]) for name in row['arrays']],
                max_references=500000)
        assert compare_accesses(expected, actual)['equal']
        with gzip.open(case / 'cachegrind.out.gz', 'rt') as stream:
            raw = stream.read()
        source = next(line[3:] for line in raw.splitlines()
                      if line.startswith('fl=') and line.endswith('/workload.c'))
        counted = read_cachegrind_counts(raw, source, row['function'],
                                         set(row['excluded_lines']), len(actual))
        assert counted['counts'] == row['cachegrind']['counts'] == row['csrd']
