"""Run the cache-affinity design: prepare, isolated baselines, pilot, empty control, full.

Cells are (working-set level, sweeps); each has SETS jittered task sets run under
G, C (1+3), C2 (1+1+2), and P once each. Isolated runs of set 0 per cell give
per-task baselines; empty-job runs per distinct period measure scheduling and
instrumentation overhead without workload. Run with PYTHONPATH set to the
4d03b93 + C2 code copy.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.build import prepare
from chaser.periodic.dataset import load_batch
from tools.rtems_periodic import run
from tools.rtems_smoke import file_hash, write_json

import affinity
import run as design
import stats

SNAPSHOT = ('affinity.py', 'aff_run.py', 'test_affinity.py')
ARCHS = ('g', 'c', 'c2', 'p')


def cases():
    return [(level, sweeps, k) for level in affinity.WS_LEVELS for sweeps in affinity.SWEEPS
            for k in range(affinity.SETS)]


def label(case):
    level, sweeps, k = case
    return f'ws{level:03d}/s{sweeps:02d}/set{k:02d}'


def case_dir(output, case):
    return output / label(case)


def prepare_one(output, case, optimization):
    target = case_dir(output, case)
    target.mkdir(parents=True)
    config = affinity.configuration(*case, optimization)
    write_json(target / 'configuration.json', config)
    prepare(config, target / 'prepared')
    commands = json.loads((target / 'prepared/build/compile_commands.json').read_text())
    for row in commands:
        expected = optimization if Path(row['file']).name == 'workload.c' else 'O0'
        if f'-{expected}' not in row['arguments']:
            raise ValueError(f'{label(case)}: {row["file"]} not compiled with -{expected}')
    return file_hash(target / 'prepared/manifest.json')


def prepare_all(output, workers, optimization):
    output.mkdir(parents=True, exist_ok=False)
    for name in SNAPSHOT:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    manifests = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case, optimization): case for case in cases()}
        for future in as_completed(futures):
            manifests[label(futures[future])] = future.result()
    write_json(output / 'protocol.json', dict(
        workload_optimization=optimization,
        ws_levels=affinity.WS_LEVELS, sweeps=affinity.SWEEPS, sets=affinity.SETS, tasks=affinity.TASKS,
        jitter=affinity.JITTER, u_cap=affinity.U_CAP, warmup_jobs=affinity.WARMUP_JOBS,
        measured_jobs=affinity.MEASURED_JOBS,
        periods={f'{l}/{s}': affinity.period_ticks(l, s) for l in affinity.WS_LEVELS for s in affinity.SWEEPS},
        prepared_manifest_hashes=dict(sorted(manifests.items())),
        snapshot_hashes={name: file_hash(output / name) for name in SNAPSHOT}))
    design.announce(f'prepared {len(manifests)} task sets')


def check_protocol(output):
    protocol = json.loads((output / 'protocol.json').read_text())
    for name, expected in protocol['snapshot_hashes'].items():
        if file_hash(output / name) != expected:
            raise ValueError(f'Snapshot changed: {name}')
    for case in cases():
        if file_hash(case_dir(output, case) / 'prepared/manifest.json') != protocol['prepared_manifest_hashes'][label(case)]:
            raise ValueError(f'Prepared manifest changed: {label(case)}')


def task_cpu(record, config):
    """Mean measured-job CPU (ns) per task, in configuration order."""
    warm = config['warmup_ticks']
    cpu = {i: [] for i in range(len(config['tasks']))}
    for job in record['jobs']:
        if job['job'] >= warm // config['tasks'][job['task']]['period_ticks']:
            cpu[job['task']].append(job['cpu_after_ns'] - job['cpu_before_ns'])
    return [sum(v) / len(v) for v in cpu.values()]


def isolated(output, workers):
    selected = [c for c in cases() if c[2] == 0]
    specs = [(f'{label(c)}/isolated/t{i:02d}', case_dir(output, c) / 'prepared',
              case_dir(output, c) / 'isolated' / f't{i:02d}', 'p', i + 1)
             for c in selected for i in range(affinity.TASKS)]
    failed, infra = design.run_specs(specs, workers)
    if failed or infra:
        raise RuntimeError(f'Isolated runs failed: {failed}, infrastructure={infra}')
    report = {}
    for c in selected:
        config = json.loads((case_dir(output, c) / 'configuration.json').read_text())
        cpu = []
        for i in range(affinity.TASKS):
            record = load_batch(case_dir(output, c) / 'prepared', case_dir(output, c) / 'isolated' / f't{i:02d}')[0]
            cpu.append(_one_task_cpu(record, config, i))
        period_ns = config['tasks'][0]['period_ticks'] * 1e6
        report[label(c)] = dict(task_cpu_ns=cpu, task_u=[v / period_ns for v in cpu])
        design.announce(f'{label(c)} isolated task U {min(cpu) / period_ns:.4f}-{max(cpu) / period_ns:.4f}')
    write_json(output / 'isolated.json', report)


def _one_task_cpu(record, config, index):
    warm = config['warmup_ticks'] // config['tasks'][index]['period_ticks']
    values = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
              if j['task'] == index and j['job'] >= warm]
    return sum(values) / len(values)


def empty_control(output, workers):
    """One empty-job run per architecture for each distinct period."""
    chosen = {}
    for c in cases():
        chosen.setdefault(affinity.period_ticks(c[0], c[1]), c)
    specs = [(period, c, arch) for period, c in sorted(chosen.items()) for arch in ARCHS]

    def one(spec):
        period, c, arch = spec
        destination = output / 'empty' / f'p{period:02d}' / arch
        if design.completed(destination):
            return json.loads((destination / 'measurements.jsonl').read_text().splitlines()[0])
        destination.parent.mkdir(parents=True, exist_ok=True)
        design.launch_gate()
        return run(case_dir(output, c) / 'prepared', destination, architecture=design.ARCHITECTURES.index(arch),
                   runs=1, empty=True, timeout=design.TIMEOUT_SECONDS)[0]

    report = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for (period, c, arch), row in zip(specs, pool.map(one, specs)):
            if row['execution_status'] != 'ok':
                raise RuntimeError(f'Empty run failed: p{period}/{arch}: {row.get("errors")}')
            report.setdefault(f'p{period:02d}', dict(source=label(c)))[arch] = dict(
                tet_ns=row['tet_ns'], tat_ns=row['tat_ns'], response_sum_ns=row['response_sum_ns'])
    write_json(output / 'empty.json', report)
    design.announce(f'empty control done for periods {sorted(chosen)}')


def specs_for(output, selected):
    return [(f'{label(c)}/{a}', case_dir(output, c) / 'prepared', case_dir(output, c) / a, a, 0)
            for c in selected for a in ARCHS]


def summarize(output):
    rows = []
    for case in cases():
        target = case_dir(output, case)
        if not all((target / a / 'measurements.jsonl').exists() for a in ARCHS):
            continue
        config = json.loads((target / 'configuration.json').read_text())
        row = dict(mean=case[0], cv=case[1], set_id=case[2], ws_level_pct=case[0], sweeps=case[1],
                   period_ticks=config['tasks'][0]['period_ticks'],
                   per_core_bytes=config['cache_affinity']['per_core_bytes'])
        for arch in ARCHS:
            result = load_batch(target / 'prepared', target / arch)[0]
            ok = result['execution_status'] == 'ok'
            row[arch] = dict(status=result['execution_status'], errors=result.get('errors', []),
                tet_ns=result['tet_ns'] if ok else None, tat_ns=result['tat_ns'] if ok else None,
                response_sum_ns=result.get('response_sum_ns') if ok else None,
                measured_jobs=result.get('measured_jobs'), cohorts=len(result.get('cohorts', [])),
                start_core_changes=design._start_core_changes(result, config) if ok else None,
                task_cpu_ns=task_cpu(result, config) if ok else None)
        write_json(target / 'summary.json', row)
        rows.append(row)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    design.announce(f'summarized {len(rows)} task sets')


def report(output):
    rows = stats.load(output / 'results.jsonl')
    cells = stats.cell_tests(rows)
    result = dict(alpha=stats.ALPHA, task_sets=len(rows), pairs=stats.PAIRS,
                  cell_keys=dict(mean='ws_level_pct', cv='sweeps'), cells=cells,
                  factors=stats.factor_tests(rows))
    (output / 'stats.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (output / 'stats.md').write_text(stats.markdown(cells))
    design.announce('wrote statistics')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'isolated', 'pilot', 'empty', 'full', 'summarize', 'stats'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    parser.add_argument('--optimization', choices=('O0', 'O2'), default='O0',
                        help='workload.c optimization, used by the prepare stage')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == 'prepare':
        prepare_all(output, min(args.workers, 32), args.optimization)
        return
    if args.stage == 'stats':
        report(output)
        return
    check_protocol(output)
    if args.stage == 'isolated':
        isolated(output, args.workers)
    elif args.stage == 'pilot':
        failed, _ = design.run_specs(specs_for(output, [c for c in cases() if c[2] == 0]), args.workers)
        summarize(output)
        if failed:
            raise RuntimeError(f'Pilot runs failed: {failed}')
    elif args.stage == 'empty':
        empty_control(output, args.workers)
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[2] != 0), key=lambda c: (c[2], c[0], c[1]))
        failed, _ = design.run_specs(specs_for(output, remaining), args.workers)
        summarize(output)
        if failed:
            design.announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(output)


if __name__ == '__main__':
    main()
