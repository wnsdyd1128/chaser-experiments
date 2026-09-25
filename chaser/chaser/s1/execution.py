"""Validate S1 against host execution-derived, function/array-filtered memory traces."""

import gzip
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import shutil
import subprocess
from time import perf_counter
import zlib

from chaser.locality.cache_reference import CacheLevel, FirstHits, simulate
from chaser.locality.estimators import compare
from chaser.s1.evaluation import evaluate_task
from chaser.s1.capture import capture
from chaser.s1.trace import cache_lines, compare_accesses, parse_lackey
from chaser.s1.workloads import access_count, cases, source_text

ROOT = Path(__file__).resolve().parents[2]
HARNESS = '''#include <stdint.h>
#include <stdio.h>
void s1_prepare(void);
uint32_t chaser_s1(void);
uint32_t s1_expected(void);
int main(void) {
    s1_prepare();
    uint32_t got = chaser_s1(), expected = s1_expected();
    printf("checksum=%u expected=%u\\n", got, expected);
    return got != expected;
}
'''


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def file_hash(path):
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _symbols(text):
    found = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[3] in ('data', 'chaser_s1'):
            address, size, kind, name = fields
            if name in found or kind.lower() != ('b' if name == 'data' else 't'):
                raise ValueError('Expected unique BSS array and text function symbols')
            found[name] = (int(address, 16), int(size, 16))
    if set(found) != {'data', 'chaser_s1'} or any(size <= 0 for _, size in found.values()):
        raise ValueError('Missing nonempty data/function symbol')
    return found


def run_execution_suite(*, output_dir: Path, case_ids=None, sweeps=3,
                        max_references=250000, timeout=120, max_trace_bytes=512 * 1024 * 1024):
    """Build the same C into host ELF and APE, then compare ordered runtime accesses.

    Cold cache replay intentionally excludes initialization, instructions, stack,
    and all other objects. This validates host array streams, not target traffic,
    hardware timing/counters, or a full-program Cachegrind cache model.
    """
    catalog = {case['id']: case for case in cases()}
    selected = list(catalog) if case_ids is None else case_ids
    if not selected or len(set(selected)) != len(selected) or any(c not in catalog for c in selected):
        raise ValueError('Select nonempty, unique known S1 case IDs')
    access_count(catalog[selected[0]], sweeps)
    if any(type(n) is not int or n <= 0 for n in (max_references, max_trace_bytes)):
        raise ValueError('Positive reference and decoded trace limits required')
    if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
        raise ValueError('Positive finite timeout required')
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True)
    executable = ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp'
    plugin = ROOT / 'rtems/baseline/build/yarda/libMemoryAccessPatterns.so'
    cache = output_dir / 'cache.yaml'
    shutil.copyfile(ROOT / 'rtems/baseline/cache.yaml', cache)
    harness = output_dir / 'main.c'
    harness.write_text(HARNESS)
    toolchain = {}
    for name in ('clang-14', 'opt-14', 'valgrind', 'nm'):
        tool = Path(shutil.which(name) or name).resolve()
        version = subprocess.run([str(tool), '--version'], capture_output=True, text=True,
                                 check=True, timeout=timeout)
        toolchain[name] = dict(path=str(tool), sha256=file_hash(tool), version=version.stdout)
    inputs = dict(sweeps=sweeps, max_references=max_references, timeout_seconds=timeout,
                  max_decoded_trace_bytes=max_trace_bytes, cases=[catalog[c] for c in selected],
                  toolchain=toolchain, sha256={str(p): file_hash(p) for p in
                      (executable, plugin, cache, harness, Path(__file__),
                       ROOT / 'chaser/s1/trace.py', ROOT / 'chaser/s1/capture.py',
                       ROOT / 'chaser/s1/workloads.py')})
    _write(output_dir / 'inputs.json', inputs)
    report = dict(schema_version=1, status='running', rows=[],
                  validation_scope='host-x86_64-execution-function-and-array-filtered',
                  execution_validation='valgrind-lackey-ordered-accesses',
                  cache_validation='independent-cold-LRU-replay-of-filtered-execution-trace',
                  target_execution_validation='not-performed',
                  selection='full' if set(selected) == set(catalog) else 'partial')
    _write(output_dir / 'suite.json', report)
    for case_id in selected:
        start = perf_counter()
        directory = output_dir / case_id
        directory.mkdir()
        row = dict(id=case_id, status='failed', family=catalog[case_id]['family'])
        commands = []

        def run(name, argv):
            record = dict(name=name, argv=[str(a) for a in argv])
            commands.append(record)
            try:
                with (directory / f'{name}.log').open('w') as log:
                    result = subprocess.run(record['argv'], cwd=directory, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=timeout)
                record['returncode'] = result.returncode
                result.check_returncode()
            finally:
                _write(directory / 'commands.json', commands)

        phase = 'build'
        try:
            case = catalog[case_id]
            count = access_count(case, sweeps)
            if count > max_references:
                raise ValueError('Source reference limit exceeded')
            source = directory / 'workload.c'
            source.write_text(source_text(case, sweeps))
            elf, llvm = (directory / f'workload.{suffix}' for suffix in ('exe', 'll'))
            ape = directory / 'workload_ape.json'
            run('host-build', [toolchain['clang-14']['path'], '-O1', '-gdwarf-4', '-fno-pie',
                              '-no-pie', source, harness, '-o', elf])
            if elf.read_bytes()[:20] != bytes.fromhex('7f454c4602010100000000000000000002003e00'):
                raise ValueError('Expected ELF64 little-endian x86-64 ET_EXEC')
            run('llvm', [toolchain['clang-14']['path'], '-O0', '-Xclang', '-disable-O0-optnone',
                         '-g', '-emit-llvm', '-S', source, '-o', llvm])
            run('ape', [toolchain['opt-14']['path'], f'-load-pass-plugin={plugin}',
                        '-passes=function(mem2reg),loop-simplify,loop-annotated-trace',
                        llvm, '-o', '/dev/null'])
            run('symbols', [toolchain['nm']['path'], '-S', '--defined-only', elf])
            symbols = _symbols((directory / 'symbols.log').read_text())
            if symbols['data'][1] != case['distinct'] * case['stride'] or symbols['data'][0] % 4096:
                raise ValueError('Array size/alignment differs from generated source')
            snapshot = {str(p): file_hash(p) for p in (source, elf, ape, llvm)}
            phase = 'execution'
            run('native', [elf])
            capture([toolchain['valgrind']['path'], '--command-line-only=yes', '--tool=lackey',
                     '--basic-counts=no', '--detailed-counts=no', '--trace-mem=yes',
                     '--trace-superblocks=no', '--log-fd=2', '--error-exitcode=97', elf],
                    directory, timeout=timeout, max_bytes=max_trace_bytes)
            checksum = f'checksum={count} expected={count}\n'
            if any((directory / name).read_text() != checksum for name in ('native.log', 'stdout.txt')):
                raise ValueError('Native/traced checksum differs from source access count')
            phase = 'filter'
            with gzip.open(directory / 'trace.log.gz', 'rt', encoding='ascii') as stream:
                accesses, stats = parse_lackey(stream, function=symbols['chaser_s1'],
                                              array=symbols['data'], max_references=max_references)
            with gzip.open(directory / 'accesses.jsonl.gz', 'wt', encoding='ascii') as stream:
                for access in accesses:
                    stream.write(json.dumps(access, separators=(',', ':')) + '\n')
            phase = 'yarda'
            comparison = evaluate_task('chaser_s1', ape=ape, elf=elf, source=source, cache=cache,
                                       executable=executable, output_dir=directory / 'comparison',
                                       max_source_accesses=max_references,
                                       max_line_references=max_references,
                                       max_cumulative_loop_iterations=max_references * 2, timeout=timeout)
            events = json.loads((directory / 'comparison/actual.events.json').read_text())['events']
            expected = [(e['operation'], e['linked_address'], e['access_size']) for e in events
                        if e['line_span_ordinal'] == 0]
            sequence = compare_accesses(expected, accesses)
            levels = {level['role']: CacheLevel(level['size_bytes'], level['line_size_bytes'],
                                                level['associativity'])
                      for level in comparison['cache_hierarchy']['levels']}
            reference = simulate(cache_lines(accesses, levels['L1'].line_bytes),
                                 levels['L1'], levels['LLC'])
            counts = [reference.l1, reference.llc, reference.miss]
            cache_equal = counts == comparison['csrd']['counts']
            predictions = {}
            for model in ('csrd', 'global_rd'):
                predicted = FirstHits(*comparison[model]['counts'])
                predictions[model] = dict(counts=comparison[model]['counts'],
                    ratios=predicted.ratios, error=compare(predicted, reference)
                    if predicted.total == reference.total else None)
            passed = (sequence['equal'] and len(accesses) == count and cache_equal
                      and comparison['status'] == 'ok')
            for paths in (snapshot, inputs['sha256']):
                if any(file_hash(Path(p)) != h for p, h in paths.items()):
                    raise ValueError('Input changed during execution')
            row.update(status='ok' if passed else 'mismatch', checksum=count, symbols=symbols,
                       trace=stats, sequence=sequence, trace_reference_counts=counts,
                       trace_reference_ratios=reference.ratios, csrd=predictions['csrd'],
                       global_rd=predictions['global_rd'], cache_counts_equal=cache_equal,
                       cache_hierarchy=comparison['cache_hierarchy'], input_sha256=snapshot)
        except (ValueError, KeyError, TypeError, OSError, EOFError, zlib.error, subprocess.SubprocessError) as error:
            row.update(status='failed', phase=phase, error=f'{type(error).__name__}: {error}')
        row['wall_seconds'] = perf_counter() - start
        row['artifact_bytes'] = sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())
        row['artifact_sha256'] = {str(p.relative_to(directory)): file_hash(p)
                                  for p in sorted(directory.rglob('*')) if p.is_file()}
        _write(directory / 'execution.json', row)
        report['rows'].append(row)
        _write(output_dir / 'suite.json', report)
        print(f"{case_id}: {row['status']} ({row['wall_seconds']:.2f}s)", flush=True)
    report['status'] = 'ok' if all(r['status'] == 'ok' for r in report['rows']) else 'failed'
    report['summary'] = dict(requested=len(selected), passed=sum(r['status'] == 'ok' for r in report['rows']),
                             failed=[r['id'] for r in report['rows'] if r['status'] == 'failed'],
                             mismatched=[r['id'] for r in report['rows'] if r['status'] == 'mismatch'])
    _write(output_dir / 'suite.json', report)
    return report
