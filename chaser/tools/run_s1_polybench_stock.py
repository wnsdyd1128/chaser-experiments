"""Capture stock Cachegrind counts for the frozen S1 PolyBench kernels."""

import argparse
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from chaser.s1.polybench import read_cachegrind_counts


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def hit_rate(counts):
    return 100 * (1 - counts[2] / sum(counts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--valgrind', type=Path, default=Path('/usr/bin/valgrind'))
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text())
    if (suite['status'] != 'ok' or len(suite['rows']) != 4 or
            not all(row['sequence']['equal'] for row in suite['rows'])):
        parser.error('Require four successful, trace-validated kernels')
    manifest = args.suite.parent / 'manifest.json'
    frozen = json.loads(manifest.read_text())['sha256'] if manifest.exists() else {}
    version = subprocess.check_output([args.valgrind, '--version'], text=True).strip()
    if version != 'valgrind-3.18.1':
        parser.error(f'Expected stock Valgrind 3.18.1, got {version}')
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'mode': 'unmodified Cachegrind function statistics',
              'cache_geometry': suite['cache_geometry'], 'valgrind_version': version,
              'valgrind_sha256': digest(args.valgrind),
              'yarda_suite_sha256': digest(args.suite), 'rows': []}
    for row in suite['rows']:
        name = row['id']
        source_case = args.suite.parent / name
        executable = source_case / 'workload.exe'
        expected_executable = row.get('executable_sha256',
                                      frozen.get(f'{name}/workload.exe'))
        if expected_executable is None or digest(executable) != expected_executable:
            raise ValueError(f'Frozen executable changed: {name}')
        case = args.output / name
        case.mkdir(exist_ok=True)
        if any(case.iterdir()):
            raise FileExistsError(f'Output case is not empty: {case}')
        raw_path = case / 'cachegrind.out'
        with tempfile.TemporaryDirectory(prefix=f'chaser-stock-{name}-') as temporary:
            runnable = Path(temporary) / 'workload.exe'
            shutil.copyfile(executable, runnable)
            runnable.chmod(0o755)
            command = [str(args.valgrind), '--command-line-only=yes',
                       '--tool=cachegrind', '--cache-sim=yes', '--branch-sim=no',
                       '--I1=16384,4,32', '--D1=16384,4,32', '--LL=2097152,4,32',
                       '--error-exitcode=97', '--log-fd=2',
                       f'--cachegrind-out-file={raw_path}', str(runnable)]
            run = subprocess.run(command, capture_output=True, text=True, timeout=120,
                                 check=True)
        if run.stdout != (source_case / 'cachegrind.stdout').read_text():
            raise ValueError(f'Stock Cachegrind checksum changed: {name}')
        raw_bytes = raw_path.read_bytes()
        raw = raw_bytes.decode('utf-8')
        source = next(line[3:] for line in raw.splitlines()
                      if line.startswith('fl=') and line.endswith('/workload.c'))
        counted = read_cachegrind_counts(raw, source, row['function'], set(), None)
        function_accesses = (counted['selected_events']['Dr'] +
                             counted['selected_events']['Dw'])
        compressed = case / 'cachegrind.out.gz'
        compressed.write_bytes(gzip.compress(raw_bytes, mtime=0))
        raw_path.unlink()
        (case / 'cachegrind.stderr.txt').write_text(run.stderr)
        (case / 'stdout.txt').write_text(run.stdout)
        report['rows'].append({
            'kernel': name, 'csrd_array_accesses': row['sequence']['expected_count'],
            'cachegrind_function_accesses': function_accesses,
            'cachegrind_counts': counted['counts'], 'csrd_counts': row['csrd'],
            'cachegrind_hit_pct': hit_rate(counted['counts']),
            'csrd_hit_pct': hit_rate(row['csrd']),
            'executable_sha256': digest(executable),
            'stock_raw_sha256': sha256(raw_bytes).hexdigest(),
            'stock_raw_gzip_sha256': digest(compressed), 'command': command})
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    with (args.output / 'results.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('kernel', 'csrd_array_accesses', 'cachegrind_function_accesses',
                         'csrd_hit_pct', 'cachegrind_hit_pct',
                         'csrd_llc_misses', 'cachegrind_llc_misses'))
        for row in report['rows']:
            writer.writerow((row['kernel'], row['csrd_array_accesses'],
                             row['cachegrind_function_accesses'],
                             f'{row["csrd_hit_pct"]:.6f}',
                             f'{row["cachegrind_hit_pct"]:.6f}',
                             row['csrd_counts'][2], row['cachegrind_counts'][2]))


if __name__ == '__main__':
    main()
