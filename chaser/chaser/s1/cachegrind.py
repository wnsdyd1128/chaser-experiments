"""Compare existing S1 host predictions with stock Cachegrind source-line counts."""

import csv
import gzip
import json
import re
from math import isfinite
from pathlib import Path
import shutil
import subprocess

from chaser.locality.cache_reference import FirstHits
from chaser.locality.estimators import compare
from chaser.s1.capture import capture
from chaser.s1.execution import file_hash

EVENTS = 'Ir I1mr ILmr Dr D1mr DLmr Dw D1mw DLmw'.split()


def read_counts(text, source, load_lines, expected):
    """Read uncompressed Cachegrind line positions, requiring load-only population.

    Selection is attribution after full-program cache simulation, not an address
    filter before simulation. Other traffic and preparation remain influential.
    Unsupported position compression fails closed rather than silently miscounts.
    """
    columns = None
    filename = function = None
    selected = dict.fromkeys(EVENTS, 0)
    total = dict.fromkeys(EVENTS, 0)
    summary = None
    seen = set()
    for line in text.splitlines():
        if line.startswith('events:'):
            if columns is not None:
                raise ValueError('Duplicate events declaration')
            columns = line.split()[1:]
            if columns != EVENTS:
                raise ValueError('Unsupported Cachegrind events')
        elif line.startswith('fl='):
            filename = line[3:]
        elif line.startswith('fn='):
            function = line[3:]
        elif line.startswith('summary:'):
            values = line.split()[1:]
            if columns is None or summary is not None or len(values) != len(EVENTS):
                raise ValueError('Invalid Cachegrind summary')
            summary = dict(zip(EVENTS, map(int, values)))
        elif not line or line.startswith(('desc:', 'cmd:')):
            continue
        else:
            fields = line.split()
            if columns is None or len(fields) != len(EVENTS) + 1 or not all(v.isdecimal() for v in fields):
                raise ValueError('Unsupported or truncated Cachegrind record')
            if filename == source and function == 'chaser_s1':
                values = dict(zip(EVENTS, map(int, fields[1:])))
                for key in EVENTS:
                    total[key] += values[key]
                position = int(fields[0])
                if position in load_lines:
                    seen.add(position)
                    for key in EVENTS:
                        selected[key] += values[key]
    if summary is None or any(v < 0 for v in summary.values()) or seen != set(load_lines):
        raise ValueError('Missing selected source lines or complete summary')
    if selected['Dr'] != expected or any(selected[k] for k in ('Dw', 'D1mw', 'DLmw')):
        raise ValueError('Selected lines are not the expected load-only population')
    if not 0 <= selected['DLmr'] <= selected['D1mr'] <= selected['Dr']:
        raise ValueError('Cachegrind misses do not conserve accesses')
    counts = [selected['Dr'] - selected['D1mr'], selected['D1mr'] - selected['DLmr'], selected['DLmr']]
    return dict(counts=counts, ratios=FirstHits(*counts).ratios, selected_events=selected,
                function_events=total, summary_events=summary, load_lines=sorted(seen))


def check_cold_reset(text, entry):
    resets = re.findall(r'S1 cold reset: entry=0x([0-9a-f]+) count=(\d+) I1,D1,LL', text)
    totals = re.findall(r'S1 cold reset total: (\d+)', text)
    if resets != [(f'{entry:x}', '1')] or totals != ['1']:
        raise ValueError('Require exactly one runtime cold reset at the ELF function entry')
    return dict(entry=entry, count=1, caches=['I1', 'D1', 'LL'])


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def run_cachegrind(*, input_dir: Path, output_dir: Path, timeout=120, cold_prefix: Path | None = None):
    """Use exact prior ELF/source/analysis; retain disagreements as results, not failures."""
    if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
        raise ValueError('Positive finite timeout required')
    input_dir, output_dir = input_dir.resolve(), output_dir.resolve()
    suite_path = input_dir / 'suite.json'
    original_hash = file_hash(suite_path)
    prior = json.loads(suite_path.read_text())
    if prior['status'] != 'ok' or prior['execution_validation'] != 'valgrind-lackey-ordered-accesses':
        raise ValueError('Require a successful host execution suite')
    output_dir.mkdir(parents=True)
    tool = Path(shutil.which('valgrind') or 'valgrind').resolve()
    tool_command = [str(tool)]
    cold_files = {}
    if cold_prefix is not None:
        cold_prefix = cold_prefix.resolve()
        tool = cold_prefix / 'bin/valgrind'
        library = cold_prefix / 'libexec/valgrind'
        tool_command = ['env', f'VALGRIND_LIB={library}', str(tool)]
        cold_files = {str(p): file_hash(p) for p in (tool, library / 'cachegrind-amd64-linux',
                      library / 'vgpreload_core-amd64-linux.so', cold_prefix / 's1-build.json')}
    version = subprocess.check_output([*tool_command, '--version'], text=True, timeout=timeout).strip()
    report = dict(schema_version=1, status='running', rows=[], selection=prior['selection'],
                  execution_validation='cachegrind-source-line-attribution',
                  validation_scope='stock-cachegrind-full-process-state-array-load-source-lines',
                  initial_state='inherited-from-startup-and-s1_prepare',
                  cache_geometry=dict(I1=[16384, 4, 32], D1=[16384, 4, 32], LL=[2097152, 4, 32]),
                  target_execution_validation='not-performed',
                  input_suite=str(suite_path), input_suite_sha256=original_hash,
                  tool=dict(path=str(tool), version=version, sha256=file_hash(tool)),
                  implementation_sha256=file_hash(Path(__file__)))
    if cold_prefix is not None:
        report.update(initial_state='I1-D1-LL-reset-before-chaser_s1-entry',
                      validation_scope='patched-cachegrind-cold-entry-full-traffic-array-load-source-lines',
                      cold_tool_sha256=cold_files,
                      cold_build=json.loads((cold_prefix / 's1-build.json').read_text()))
    _write(output_dir / 'suite.json', report)
    for previous in prior['rows']:
        case_id = previous['id']
        directory = output_dir / case_id
        directory.mkdir()
        row = dict(id=case_id, status='failed')
        try:
            source, elf = (input_dir / case_id / f'workload.{ext}' for ext in ('c', 'exe'))
            snapshot = {str(p): file_hash(p) for p in (source, elf)}
            if any(previous['input_sha256'][p] != h for p, h in snapshot.items()):
                raise ValueError('Source/ELF differs from prior analysis')
            for name, digest in previous['artifact_sha256'].items():
                if name.startswith('comparison/') and file_hash(input_dir / case_id / name) != digest:
                    raise ValueError('Prior analysis artifact changed')
            levels = {l['role']: (l['size_bytes'], l['associativity'], l['line_size_bytes'])
                      for l in previous['cache_hierarchy']['levels']}
            if levels != {'L1': (16384, 4, 32), 'LLC': (2097152, 4, 32)}:
                raise ValueError('Cache geometry differs from comparison settings')
            lines = [i for i, line in enumerate(source.read_text().splitlines(), 1) if 'sum += data[' in line]
            raw = directory / 'cachegrind.out'
            cold_options = []
            if cold_prefix is not None:
                from chaser.s1.execution import _symbols
                nm = subprocess.check_output(['nm', '-S', '--defined-only', str(elf)], text=True, timeout=timeout)
                (directory / 'symbols.txt').write_text(nm)
                entry = _symbols(nm)['chaser_s1'][0]
                cold_options = [f'--s1-cold-entry=0x{entry:x}']
            argv = [*tool_command, *cold_options, '--command-line-only=yes', '--tool=cachegrind', '--cache-sim=yes',
                    '--branch-sim=no', '--I1=16384,4,32', '--D1=16384,4,32', '--LL=2097152,4,32',
                    '--error-exitcode=97', '--log-fd=2', f'--cachegrind-out-file={raw}', str(elf)]
            capture(argv, directory, timeout=timeout, max_bytes=1024 * 1024)
            if cold_prefix is not None:
                with gzip.open(directory / 'trace.log.gz', 'rt') as log:
                    row['cold_reset'] = check_cold_reset(log.read(), entry)
            count = previous['sequence']['observed_count']
            if (directory / 'stdout.txt').read_text() != f'checksum={count} expected={count}\n':
                raise ValueError('Cachegrind execution checksum mismatch')
            result = read_counts(raw.read_text(), str(source), lines, count)
            with gzip.open(directory / 'cachegrind.out.gz', 'wb') as stream:
                stream.write(raw.read_bytes())
            reference = FirstHits(*result['counts'])
            row.update(status='ok', cachegrind=result, reference=result['ratios'],
                       cold_reference_counts=previous['trace_reference_counts'], input_sha256=snapshot,
                       csrd_count_equal=result['counts'] == previous['csrd']['counts'])
            for model in ('global_rd', 'csrd'):
                prediction = FirstHits(*previous[model]['counts'])
                row[model] = prediction.ratios
                row[model + '_counts'] = previous[model]['counts']
                row[model + '_error'] = compare(prediction, reference)
            if any(file_hash(Path(p)) != h for p, h in snapshot.items()) or file_hash(suite_path) != original_hash:
                raise ValueError('Input changed during collection')
            if any(file_hash(Path(p)) != h for p, h in cold_files.items()):
                raise ValueError('Cold Cachegrind tool changed during collection')
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            row.update(status='failed', error=f'{type(error).__name__}: {error}')
        row['artifact_sha256'] = {p.name: file_hash(p) for p in sorted(directory.iterdir()) if p.is_file()}
        _write(directory / 'comparison.json', row)
        report['rows'].append(row)
        _write(output_dir / 'suite.json', report)
        print(f"{case_id}: {row['status']}", flush=True)
    good = [r for r in report['rows'] if r['status'] == 'ok']
    report['status'] = 'ok' if len(good) == len(prior['rows']) else 'failed'
    report['summary'] = dict(requested=len(prior['rows']), evaluated=len(good),
        failed=[r['id'] for r in report['rows'] if r['status'] == 'failed'],
        csrd_count_equal=sum(r['csrd_count_equal'] for r in good),
        mae={m: [sum(r[m + '_error']['absolute_error'][i] for r in good) / len(good)
                  for i in range(3)] if good else None for m in ('global_rd', 'csrd')})
    _write(output_dir / 'suite.json', report)
    with (output_dir / 'results.csv').open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'status', 'cachegrind_l1', 'cachegrind_ll', 'cachegrind_memory',
                         'csrd_l1', 'csrd_ll', 'csrd_memory', 'global_rd_l1', 'global_rd_ll', 'global_rd_memory'])
        for r in report['rows']:
            writer.writerow([r['id'], r['status']] + (r['cachegrind']['counts'] + r['csrd_counts'] +
                             r['global_rd_counts'] if r['status'] == 'ok' else []))
    return report
