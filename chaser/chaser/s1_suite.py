"""Build source-derived S1 cases and aggregate independent cache-model comparisons."""

import csv
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path
import shutil
import subprocess
from time import perf_counter

from chaser.ca import ca_from_histogram, ca_csrd
from chaser.s1 import evaluate_task
from chaser.s1_workloads import access_count, cases, source_text

ROOT = Path(__file__).resolve().parents[1]


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def summarize(rows: list[dict]) -> dict:
    """Weight each evaluated workload equally; preserve failures in the denominator report."""
    evaluated = [row for row in rows if row['status'] in ('ok', 'mismatch')]
    result = {'requested': len(rows), 'evaluated': len(evaluated),
              'failed': [row['id'] for row in rows if row['status'] == 'failed'],
              'mismatched': [row['id'] for row in rows if row['status'] == 'mismatch'],
              'weighting': 'equal-workload', 'level_order': ['L1', 'LLC', 'memory']}
    for model in ('global_rd', 'csrd'):
        errors = [[abs(p - r) for p, r in zip(row[model], row['reference'])]
                  for row in evaluated]
        result[model] = None if not errors else {
            'mae': [sum(e[i] for e in errors) / len(errors) for i in range(3)],
            'rmse': [sqrt(sum(e[i] ** 2 for e in errors) / len(errors)) for i in range(3)],
            'max_absolute_error': [max(e[i] for e in errors) for i in range(3)]}
    return result


def _offsets(case, sweeps):
    if case['id'] == 'mean_mixed':
        for _ in range(1023 * (sweeps - 1) + 1):
            yield 0
        for _ in range(sweeps):
            yield from range(32, 32768, 32)
    elif case['id'] == 'mean_uniform':
        for i in range(512 + 2046 * (sweeps - 1)):
            yield (i % 512) * 32
        yield from range(16384, 32768, 32)
    else:
        for _ in range(sweeps):
            yield from range(0, case['distinct'] * case['stride'], case['stride'])


def _check_stream(path, case, sweeps):
    events = json.loads(path.read_text())['events']
    if len(events) != access_count(case, sweeps):
        raise ValueError('Generated source access count disagrees with APE stream')
    base = events[0]['linked_address']
    if base % 4096:
        raise ValueError('S1 object is not aligned to the L1 set period')
    for event, offset in zip(events, _offsets(case, sweeps)):
        if (event['operation'] != 'load' or event['access_size'] != 1 or
                event['object_id'] != 'global::data' or event['linked_address'] != base + offset):
            raise ValueError('Generated load-only logical order disagrees with linked APE stream')
    return base


def _csv(path, rows):
    fields = ['id', 'status', 'source_accesses', 'modeled_accesses', 'element_ca', 'line_ca',
              'csrd_ca', 'line_mean_rd', 'cold_fraction', 'wall_seconds', 'artifact_bytes']
    fields += [f'{model}_{level}' for model in ('reference', 'global_rd', 'csrd')
               for level in ('l1', 'llc', 'memory')]
    fields += [f'{model}_ae_{level}' for model in ('global_rd', 'csrd')
               for level in ('l1', 'llc', 'memory')]
    fields += ['error']
    with path.open('w') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = {key: row[key] for key in fields if key in row}
            if row['status'] in ('ok', 'mismatch'):
                for model in ('reference', 'global_rd', 'csrd'):
                    for i, level in enumerate(('l1', 'llc', 'memory')):
                        flat[f'{model}_{level}'] = row[model][i]
                        if model != 'reference':
                            flat[f'{model}_ae_{level}'] = abs(row[model][i] - row['reference'][i])
            writer.writerow(flat)


def run_suite(*, output_dir: Path, case_ids: list[str] | None = None, sweeps: int = 3,
              max_references: int = 250000, timeout: float = 60) -> dict:
    """Build and evaluate selected cases, preserving raw inputs and per-case failures.

    Uses the repository verifier's installed toolchain and cache geometry. The
    budget caps each case before compilation; timeout applies to each external
    command. Matching source/ELF and logical APE order do not validate CPU traces.
    """
    catalog = {case['id']: case for case in cases()}
    selected = list(catalog) if case_ids is None else case_ids
    if not selected or len(set(selected)) != len(selected) or any(c not in catalog for c in selected):
        raise ValueError('Select nonempty, unique known S1 case IDs')
    access_count(catalog[selected[0]], sweeps)
    if type(max_references) is not int or max_references < 1:
        raise ValueError('Positive reference limit required')
    if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
        raise ValueError('Positive finite timeout required')
    executable = ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp'
    plugin = ROOT / 'rtems/baseline/build/yarda/libMemoryAccessPatterns.so'
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True)
    support = output_dir / 'build-support'
    support.mkdir()
    for origin, name in ((ROOT / 'rtems/s1/Makefile', 'Makefile'),
                         (ROOT / 'rtems/s1/init.c', 'init.c'),
                         (ROOT / 'rtems/baseline/cache.yaml', 'cache.yaml')):
        shutil.copyfile(origin, support / name)
    provenance = {'schema_version': 1, 'sweeps': sweeps, 'max_references': max_references,
                  'command_timeout_seconds': timeout, 'cases': [catalog[c] for c in selected],
                  'sha256': {str(p): _hash(p) for p in
                             [executable, plugin, *support.iterdir(), Path(__file__),
                              Path(__file__).with_name('s1_workloads.py')]}}
    provenance['toolchain'] = {}
    for name in ('/opt/rtems/6/bin/sparc-rtems6-gcc', 'clang-14', 'opt-14', 'make'):
        version = subprocess.run([name, '--version'], capture_output=True, text=True,
                                 check=True, timeout=timeout)
        provenance['toolchain'][name] = version.stdout
    _write(output_dir / 'inputs.json', provenance)
    rows = []
    report = {'schema_version': 1, 'status': 'running', 'rows': rows,
              'selection': 'full' if set(selected) == set(catalog) else 'partial',
              'validation_scope': 'cache-decisions-on-source-derived-yarda-linked-stream',
              'execution_validation': 'not-performed',
              'global_rd_rule': 'full-linked-stream-capacity-bins-v1',
              'limitations': ['LLC recency differs between Global RD and demand reference.',
                              'Instruction/stack accesses and preparation are outside the model.',
                              'Source and logical-order checks do not independently validate CPU traces.',
                              'RMW evidence remains in artifacts/baseline/rtems-v1.']}
    _write(output_dir / 'suite.json', report)
    for case_id in selected:
        case = catalog[case_id]
        directory = output_dir / case_id
        directory.mkdir()
        row = {'id': case_id, 'family': case['family'], 'status': 'failed'}
        start, phase, commands = perf_counter(), 'budget', []
        try:
            expected_count = access_count(case, sweeps)
            if expected_count > max_references:
                raise ValueError(f'{expected_count} references exceed budget {max_references}')
            source = directory / 'workload.c'
            source.write_text(source_text(case, sweeps))
            source_hash = _hash(source)
            build = directory / 'build'

            def run(name, argv):
                record = {'name': name, 'argv': [str(a) for a in argv]}
                commands.append(record)
                began = perf_counter()
                try:
                    with (directory / f'{name}.log').open('w') as log:
                        process = subprocess.run(record['argv'], stdout=log, stderr=subprocess.STDOUT,
                                                 timeout=timeout)
                    record['returncode'] = process.returncode
                    process.check_returncode()
                except subprocess.TimeoutExpired:
                    record['timed_out'] = True
                    raise
                finally:
                    record['wall_seconds'] = perf_counter() - began
                    _write(directory / 'commands.json', commands)

            phase = 'build'
            run('build', ['make', '-f', support / 'Makefile', f'SOURCE={source}',
                          f'INIT={support / "init.c"}', f'BUILD={build}', f'PLUGIN={plugin}', 'all'])
            ape, elf = build / 'workload_ape.json', build / 'workload.exe'
            if elf.read_bytes()[:20] != bytes.fromhex('7f454c4601020100000000000000000000020002'):
                raise ValueError('Expected ELF32 big-endian SPARC executable')
            phase = 'compare'
            comparison = evaluate_task('chaser_s1', ape=ape, elf=elf, source=source,
                                       cache=support / 'cache.yaml', executable=executable,
                                       output_dir=directory / 'comparison',
                                       max_source_accesses=max_references,
                                       max_line_references=max_references,
                                       max_cumulative_loop_iterations=max_references * 2,
                                       timeout=timeout)
            phase = 'source-contract'
            geometry = [(level['role'], level['size_bytes'], level['line_size_bytes'],
                         level['associativity']) for level in comparison['cache_hierarchy']['levels']]
            if sorted(geometry) != [('L1', 16384, 32, 4), ('LLC', 2097152, 32, 4)]:
                raise ValueError('S1 catalog requires the baseline 16-KiB/2-MiB four-way geometry')
            base = _check_stream(directory / 'comparison/actual.events.json', case, sweeps)
            if comparison['source_accesses'] != expected_count:
                raise ValueError('Source access coverage mismatch')
            phase = 'element'
            run('element', [executable, ape, '--mode', 'unroll', '--granularity', 'element',
                            '--max-cumulative-loop-iterations', str(max_references * 2),
                            '--export', directory / 'element.json'])
            element = json.loads((directory / 'element.json').read_text())['program']
            if element['cold_misses'] + sum(element['histogram'].values()) != expected_count:
                raise ValueError('Element profile population mismatch')
            actual = json.loads((directory / 'comparison/actual.json').read_text())['tasks'][0]
            line = json.loads((directory / 'comparison/global.json').read_text())['tasks'][0]['l1']
            histogram = line['csrd_histogram']
            reuses = sum(histogram.values())
            current_inputs = {'source': source, 'ape': ape, 'elf': elf,
                              'cache': support / 'cache.yaml', 'executable': executable}
            if (_hash(source) != source_hash or
                    any(_hash(p) != comparison['input_sha256'][name] for name, p in current_inputs.items()) or
                    any(_hash(Path(p)) != h for p, h in provenance['sha256'].items())):
                raise ValueError('Suite input changed during execution')
            row.update(status=comparison['status'], source_accesses=expected_count,
                       modeled_accesses=comparison['modeled_accesses'], linked_base=base,
                       source_coverage=1.0,
                       element_ca=ca_from_histogram(element['histogram']),
                       line_ca=ca_from_histogram(histogram), csrd_ca=ca_csrd(actual),
                       line_mean_rd=sum(int(d) * n for d, n in histogram.items()) / reuses,
                       line_histogram=histogram, cold_fraction=line['cold_misses'] / expected_count,
                       element_profile=element, reference_counts=comparison['reference']['counts'],
                       input_sha256=comparison['input_sha256'],
                       compiler_artifact_sha256={p.name: _hash(p) for p in build.iterdir() if p.is_file()},
                       element_sha256=_hash(directory / 'element.json'))
            for model in ('reference', 'csrd', 'global_rd'):
                row[model] = comparison[model]['ratios']
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
            row.update(status='failed', error=f'{type(error).__name__}: {error}')
            _write(directory / 'failure.json', {**row, 'phase': phase, 'commands': commands})
        row['wall_seconds'] = perf_counter() - start
        row['artifact_bytes'] = sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())
        rows.append(row)
        report['summary'] = summarize(rows)
        _write(output_dir / 'suite.json', report)
        print(f"{case_id}: {row['status']} ({row['wall_seconds']:.2f}s)", flush=True)
    report['status'] = 'ok' if all(row['status'] == 'ok' for row in rows) else 'failed'
    _write(output_dir / 'suite.json', report)
    _csv(output_dir / 'results.csv', rows)
    return report
