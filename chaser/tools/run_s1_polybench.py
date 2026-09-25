"""Compare four fixed PolyBench-derived kernels with cold-entry Cachegrind."""

import argparse
import gzip
import json
from math import isclose
from pathlib import Path
import re
import subprocess

from chaser.s1.evaluation import evaluate_task
from chaser.s1.cachegrind import check_cold_reset
from chaser.s1.capture import capture
from chaser.s1.execution import file_hash
from chaser.s1.polybench import read_cachegrind_counts, selected_array_accesses
from chaser.s1.trace import compare_accesses


ROOT = Path(__file__).resolve().parents[1]
CASES = {
    '2mm': ('kernel_2mm', ('A', 'B', 'C', 'D', 'tmp'), (50,),
            'for (int ci=0;ci<NI;ci++) for (int cj=0;cj<NL;cj++) checksum += D[ci][cj];'),
    'atax': ('atax_kernel', ('A', 'x', 'y', 'tmp'), (43,),
             'for (int ci=0;ci<N;ci++) checksum += y[ci];'),
    'gemm': ('gemm_kernel', ('A', 'B', 'C'), (41,),
             'for (int ci=0;ci<N;ci++) for (int cj=0;cj<N;cj++) checksum += C[ci][cj];'),
    'jacobi': ('jacobi_2d_kernel', ('A', 'B'), (21, 50),
               'for (int ci=0;ci<N;ci++) for (int cj=0;cj<N;cj++) checksum += A[ci][cj]+B[ci][cj];'),
}
SOURCE_HASHES = {
    'polybench_2mm.c': '50d1367dd10d08a22ef4ce53a3b6d56970aa5e24145ec6efefe20219aeb79608',
    'polybench_atax.c': 'b0e7f7a81e48b6c314ae23b86a34ac9a90feba4cd375e926453a2917de4dfed8',
    'polybench_correlation.c': '87110088af6b10f39df73ce931fcb16399e98f5979b236b3bbdb095c14485925',
    'polybench_gemm.c': 'a7be01c8e4101ab395e13e5cb970351c92068cbb171df9e15dbb44288ad695dc',
    'polybench_jacobi.c': '662afa159d5eb086edc20eaa966800693998486256a64cacec6e12d4416c9318',
}
SOURCE_TYPE = ('local CAAS PolyBench-derived adapted C examples, not the '
               'unmodified PolyBench/C 4.2.1 distribution')


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def _checksum_source(source, loop):
    replacement = ('double checksum = 0;\n    ' + loop +
                   '\n    printf("checksum=%.17g\\n", checksum);\n    return 0;')
    changed, count = re.subn(r'\breturn 0;', lambda _: replacement, source)
    if count != 1:
        raise ValueError('Expected one main return for checksum')
    return changed


def _adapt(source, function, arrays):
    for array in arrays:
        source, count = re.subn(r'(?m)^double ' + array + r'\[',
                                'volatile double ' + array + '[', source, count=1)
        if count != 1:
            raise ValueError(f'Missing global array {array}')
    source, count = re.subn(r'(?m)^void ' + function + r'\(',
                            '__attribute__((noinline,annotate("ape.analyze"))) void ' +
                            function + '(', source, count=1)
    if count != 1:
        raise ValueError('Missing kernel function')
    return source


def _run(argv, cwd, log, timeout):
    with log.open('w') as stream:
        process = subprocess.run([str(v) for v in argv], cwd=cwd, stdout=stream,
                                 stderr=subprocess.STDOUT, timeout=timeout)
    process.check_returncode()
    return [str(v) for v in argv]


def _symbols(text, names):
    selected = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[3] in names:
            base, size, kind, name = parts
            if name in selected or kind.lower() != ('t' if name == names[0] else 'b'):
                raise ValueError('Duplicate or non-static kernel/array symbol')
            selected[name] = (int(base, 16), int(size, 16))
    if set(selected) != set(names) or any(size <= 0 for _, size in selected.values()):
        raise ValueError('Missing nonempty kernel/array symbols')
    return selected


def run_suite(source_dir: Path, output_dir: Path, cold_prefix: Path, timeout=120):
    """Keep exact source, binary, trace and tool evidence for an isolated comparison."""
    source_dir, output_dir, cold_prefix = (p.resolve() for p in
                                            (source_dir, output_dir, cold_prefix))
    for name, expected in SOURCE_HASHES.items():
        if file_hash(source_dir / name) != expected:
            raise ValueError(f'Versioned PolyBench source differs from frozen hash: {name}')
    plugin = ROOT / 'rtems/baseline/build/yarda/libMemoryAccessPatterns.so'
    yarda = ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp'
    cache = ROOT / 'rtems/baseline/cache.yaml'
    tool = cold_prefix / 'bin/valgrind'
    library = cold_prefix / 'libexec/valgrind'
    tool_files = [tool, library / 'cachegrind-amd64-linux',
                  library / 'vgpreload_core-amd64-linux.so', cold_prefix / 's1-build.json']
    provenance = {str(p): file_hash(p) for p in
                  [plugin, yarda, cache, *tool_files]}
    output_dir.mkdir(parents=True)
    report = {'schema_version': 1, 'status': 'running', 'rows': [],
              'source_type': SOURCE_TYPE,
              'initial_state': 'I1-D1-LL-reset-before-kernel-entry',
              'cache_geometry': {'I1': [16384, 4, 32], 'D1': [16384, 4, 32],
                                 'LL': [2097152, 4, 32]},
              'provenance_sha256': provenance,
              'compiler_contract': 'host Clang-14 O1; YARDA Clang-14 O0 mem2reg; same ELF',
              'limitation': 'PolyBench-derived fixed-size volatile global-array adaptations; host cache simulator, not target hardware'}
    _write(output_dir / 'suite.json', report)
    for key, (function, arrays, excluded, checksum_loop) in CASES.items():
        case = output_dir / key
        case.mkdir()
        row = {'id': key, 'status': 'failed', 'function': function,
               'arrays': list(arrays), 'excluded_lines': list(excluded), 'commands': []}
        phase = 'source'
        try:
            original_path = source_dir / f'polybench_{key}.c'
            original = original_path.read_text()
            baseline = case / 'baseline.c'
            source = case / 'workload.c'
            baseline.write_text(_checksum_source(original, checksum_loop))
            source.write_text(_checksum_source(_adapt(original, function, arrays), checksum_loop))
            row['input_sha256'] = {str(p.name): file_hash(p) for p in (original_path, baseline, source)}
            phase = 'build'
            row['commands'].append(_run(['clang-14', '-O1', '-g', '-fno-pie', '-no-pie',
                                         baseline, '-lm', '-o', case / 'baseline.exe'],
                                        case, case / 'baseline-build.log', timeout))
            row['commands'].append(_run(['clang-14', '-O1', '-g', '-fno-pie', '-no-pie',
                                         source, '-lm', '-o', case / 'workload.exe'],
                                        case, case / 'build.log', timeout))
            row['executable_sha256'] = file_hash(case / 'workload.exe')
            row['commands'].append(_run(['clang-14', '-O0', '-Xclang', '-disable-O0-optnone',
                                         '-g', '-emit-llvm', '-S', source, '-o', case / 'workload.ll'],
                                        case, case / 'llvm.log', timeout))
            row['commands'].append(_run(['opt-14', f'-load-pass-plugin={plugin}',
                                         '-passes=function(mem2reg),loop-simplify,loop-annotated-trace',
                                         case / 'workload.ll', '-o', '/dev/null'],
                                        case, case / 'ape.log', timeout))
            baseline_output = subprocess.check_output([case / 'baseline.exe'], text=True, timeout=timeout)
            adapted_output = subprocess.check_output([case / 'workload.exe'], text=True, timeout=timeout)
            if not (baseline_output.startswith('checksum=') and adapted_output.startswith('checksum=')):
                raise ValueError('Missing numerical checksum')
            baseline_value = float(baseline_output.split('=', 1)[1])
            adapted_value = float(adapted_output.split('=', 1)[1])
            if not isclose(baseline_value, adapted_value, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('Adaptation changed numerical output')
            row['checksum'] = {'baseline': baseline_value, 'adapted': adapted_value}
            nm = subprocess.check_output(['nm', '-S', '--defined-only', case / 'workload.exe'], text=True,
                                         timeout=timeout)
            (case / 'symbols.txt').write_text(nm)
            symbols = _symbols(nm, (function, *arrays))
            row['symbols'] = {name: list(pair) for name, pair in symbols.items()}
            phase = 'yarda'
            comparison = evaluate_task(function, ape=case / 'workload_ape.json',
                                       elf=case / 'workload.exe', source=source, cache=cache,
                                       executable=yarda, output_dir=case / 'comparison',
                                       max_source_accesses=500000, max_line_references=500000,
                                       max_cumulative_loop_iterations=1000000, timeout=timeout)
            phase = 'lackey'
            capture(['valgrind', '--command-line-only=yes', '--tool=lackey',
                     '--basic-counts=no', '--detailed-counts=no', '--trace-mem=yes',
                     '--trace-superblocks=no', '--log-fd=2', '--error-exitcode=97',
                     case / 'workload.exe'], case, timeout=timeout,
                    max_bytes=512 * 1024 * 1024)
            if (case / 'stdout.txt').read_text() != adapted_output:
                raise ValueError('Lackey execution checksum differs')
            with gzip.open(case / 'trace.log.gz', 'rt', encoding='ascii') as stream:
                accesses, stats = selected_array_accesses(stream, function=symbols[function],
                    arrays=[symbols[name] for name in arrays], max_references=500000)
            events = json.loads((case / 'comparison/actual.events.json').read_text())['events']
            expected = [(event['operation'], event['linked_address'], event['access_size'])
                        for event in events if event['line_span_ordinal'] == 0]
            sequence = compare_accesses(expected, accesses)
            if not sequence['equal'] or len(accesses) != comparison['source_accesses']:
                raise ValueError('YARDA and host array access order differ')
            row.update(sequence=sequence, lackey_stats=stats)
            phase = 'cachegrind'
            entry = symbols[function][0]
            argv = ['env', f'VALGRIND_LIB={library}', tool, f'--s1-cold-entry=0x{entry:x}',
                    '--command-line-only=yes', '--tool=cachegrind', '--cache-sim=yes',
                    '--branch-sim=no', '--I1=16384,4,32', '--D1=16384,4,32',
                    '--LL=2097152,4,32', '--error-exitcode=97', '--log-fd=2',
                    f'--cachegrind-out-file={case / "cachegrind.out"}', case / 'workload.exe']
            result = subprocess.run([str(v) for v in argv], capture_output=True, text=True,
                                    timeout=timeout)
            (case / 'cachegrind.log').write_text(result.stderr)
            (case / 'cachegrind.stdout').write_text(result.stdout)
            row['commands'].append([str(v) for v in argv])
            result.check_returncode()
            row['reset'] = check_cold_reset(result.stderr, entry)
            if result.stdout != adapted_output:
                raise ValueError('Cachegrind execution checksum differs')
            counts = read_cachegrind_counts((case / 'cachegrind.out').read_text(),
                                            str(source), function, set(excluded),
                                            len(accesses))
            row.update(status='ok', source_accesses=len(accesses),
                       cachegrind=counts, csrd=comparison['csrd']['counts'],
                       global_rd=comparison['global_rd']['counts'],
                       csrd_equal=counts['counts'] == comparison['csrd']['counts'])
            if any(file_hash(p) != digest for p, digest in
                   ((Path(name), value) for name, value in provenance.items())):
                raise ValueError('Tool changed during experiment')
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            row.update(status='failed', phase=phase, error=f'{type(error).__name__}: {error}')
        _write(case / 'result.json', row)
        report['rows'].append(row)
        _write(output_dir / 'suite.json', report)
        print(f'{key}: {row["status"]}', flush=True)
    report['status'] = 'ok' if all(row['status'] == 'ok' for row in report['rows']) else 'failed'
    _write(output_dir / 'suite.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'artifacts/s1/polybench-cold-v1/sources')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cold-prefix', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_suite(args.source_dir, args.output, args.cold_prefix)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(2, f'{error}\n')
    if report['status'] != 'ok':
        parser.exit(1)


if __name__ == '__main__':
    main()
