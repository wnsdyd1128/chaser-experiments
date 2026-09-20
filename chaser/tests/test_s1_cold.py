"""Cold comparisons require runtime proof of exactly one reset at the ELF entry."""
import pytest
from chaser.s1_cachegrind import check_cold_reset


def test_reset_evidence_requires_matching_entry_and_single_runtime_reset():
    text = '==3== S1 cold reset: entry=0x401160 count=1 I1,D1,LL\n==3== S1 cold reset total: 1\n'
    assert check_cold_reset(text, 0x401160) == {'entry': 0x401160, 'count': 1, 'caches': ['I1', 'D1', 'LL']}
    for bad in ('', text.replace('401160', '401161'), text.replace('total: 1', 'total: 0'),
                text + text, text.replace('count=1', 'count=2')):
        with pytest.raises(ValueError):
            check_cold_reset(bad, 0x401160)


def test_patched_cachegrind_resets_instruction_and_data_state_on_each_entry(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    from chaser.s1_cachegrind import read_counts
    prefix = os.environ.get('CHASER_COLD_PREFIX')
    if not prefix:
        pytest.skip('Build the optional patched Cachegrind and set CHASER_COLD_PREFIX for live reset test')
    prefix = Path(prefix)
    source = tmp_path / 'probe.c'
    source.write_text('volatile unsigned char data __attribute__((aligned(4096)));\n'
        '__attribute__((noinline,aligned(64))) int chaser_s1(void) { return data; }\n'
        'int main(void) { data=1; int a=chaser_s1(); int b=chaser_s1(); return a+b!=2; }\n')
    elf = tmp_path / 'probe.exe'
    subprocess.run(['clang-14', '-O1', '-gdwarf-4', '-fno-pie', '-no-pie', str(source), '-o', str(elf)], check=True)
    symbols = subprocess.check_output(['nm', '-S', str(elf)], text=True)
    entry = int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' chaser_s1')), 16)
    results = {}
    for name, extra in [('warm', []), ('cold', [f'--s1-cold-entry=0x{entry:x}'])]:
        raw, log = tmp_path / f'{name}.out', tmp_path / f'{name}.log'
        subprocess.run(['env', f'VALGRIND_LIB={prefix}/libexec/valgrind', str(prefix / 'bin/valgrind'),
            '--command-line-only=yes', '--tool=cachegrind', '--cache-sim=yes', *extra,
            '--I1=16384,4,32', '--D1=16384,4,32', '--LL=2097152,4,32',
            f'--cachegrind-out-file={raw}', f'--log-file={log}', str(elf)], check=True, timeout=30)
        # Both the byte load and return's stack read belong to this one-line function.
        results[name] = read_counts(raw.read_text(), str(source), [2], 4)['function_events']
    assert results['warm']['I1mr'] <= 1  # Startup may already have fetched this code line.
    assert results['cold']['Ir'] == results['warm']['Ir'] == 4
    assert results['cold']['I1mr'] == results['cold']['ILmr'] == 2
    assert results['cold']['D1mr'] == results['cold']['DLmr'] == 4
    assert results['warm']['D1mr'] < results['cold']['D1mr']
    with pytest.raises(ValueError):
        check_cold_reset((tmp_path / 'cold.log').read_text(), entry)  # Two entries cannot pass single-call suite.


def test_frozen_cold_cachegrind_counts_reset_proof_and_disabled_control():
    import gzip
    import json
    from pathlib import Path
    from chaser.s1_cachegrind import read_counts
    from chaser.s1_execution import ROOT, file_hash
    evidence = ROOT / 'artifacts/s1/cachegrind-cold-v1'
    manifest = json.loads((evidence / 'manifest.json').read_text())
    for name, digest in manifest['sha256'].items():
        assert file_hash(evidence / name) == digest
    suite = json.loads((evidence / 'suite.json').read_text())
    assert suite['initial_state'] == 'I1-D1-LL-reset-before-chaser_s1-entry'
    assert suite['summary']['evaluated'] == suite['summary']['csrd_count_equal'] == 25
    assert suite['cold_build']['patch_sha256'] == file_hash(ROOT / 'tools/cachegrind/s1-cold-entry.patch')
    for row in suite['rows']:
        source = next(p for p in row['input_sha256'] if Path(p).suffix == '.c')
        directory = evidence / row['id']
        with gzip.open(directory / 'cachegrind.out.gz', 'rt') as stream:
            counts = read_counts(stream.read(), source, row['cachegrind']['load_lines'], sum(row['csrd_counts']))
        assert counts['counts'] == row['cachegrind']['counts'] == row['csrd_counts']
        nm_entry = int(next(l.split()[0] for l in (directory / 'symbols.txt').read_text().splitlines()
                            if l.endswith(' chaser_s1')), 16)
        with gzip.open(directory / 'trace.log.gz', 'rt') as stream:
            assert check_cold_reset(stream.read(), nm_entry) == row['cold_reset']
    control = json.loads((evidence / 'no-reset-control/suite.json').read_text())
    assert len(control['rows']) == 25 and control['all_equal']
    assert all(row['counts'] == row['stock_counts'] for row in control['rows'])
    for row in control['rows']:
        assert file_hash(evidence / 'no-reset-control' / (row['id'] + '.out.gz')) == row['output_sha256']
