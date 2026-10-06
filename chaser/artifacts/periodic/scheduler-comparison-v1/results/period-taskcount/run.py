"""Run the normal-period G/C/P design: isolated-U gate, pilot, then all sets.

Stages:
  prepare  build every task set's G/C/P ELFs and freeze their manifest hashes
  u-check  run each task of the widest set (CV 0.3, set 0) alone on P per mean
  pilot    set 0 of every (mean, CV) cell under G/C/P; all runs must pass
  full     remaining sets, ordered by set id so every cell fills evenly

A run directory that holds a parsed run header is kept, including deadline
misses; one whose simulator produced no header is moved aside and retried.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from threading import Lock
import time

from chaser.periodic.build import prepare
from chaser.periodic.dataset import characterize, load_batch
from tools.rtems_periodic import run
from tools.rtems_smoke import file_hash, write_json

import taskset

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / '.cache/period-distribution-v2'
SNAPSHOT = ('taskset.py', 'run.py', 'stats.py', 'test_taskset.py')
# C2 is the (0, 1, 2, 2) topology of the patched code copy.
ARCHITECTURES = ('g', 'c', 'p', 'c2')
U_TOLERANCE = 0.05
TIMEOUT_SECONDS = 14400
MAX_INFRA_FAILURES = 3
MAX_WORKERS = 84
# Simulators contact the remote X display at startup; space the launches.
LAUNCH_INTERVAL_SECONDS = 1.0
LOCK = Lock()
LAUNCH_LOCK = Lock()
_last_launch = [0.0]


def announce(message):
    with LOCK:
        print(f'{datetime.now(timezone.utc).isoformat()} {message}', flush=True)


def cases():
    return [(mean, cv, set_id) for mean in taskset.MEANS for cv in taskset.CVS
            for set_id in taskset.set_ids(cv)]


def label(case):
    mean, cv, set_id = case
    return f'm{mean:03d}/cv{round(cv * 100):02d}/s{set_id:02d}'


def case_dir(output, case):
    return output / label(case)


def prepare_one(output, case):
    target = case_dir(output, case)
    target.mkdir(parents=True)
    config = taskset.configuration(*case)
    write_json(target / 'configuration.json', config)
    prepare(config, target / 'prepared')
    for architecture in ARCHITECTURES:
        plan = json.loads((target / f'prepared/{architecture}/plan.json').read_text())
        planned = [(t['task_id'], t['period_ticks'], t['core'], t['sweeps'])
                   for t in config['tasks']]
        if ([(t['task_id'], t['period_ticks'], t['core'], t['sweeps'])
             for t in plan['tasks']] != planned
                or plan['warmup_ticks'] != config['warmup_ticks']
                or any(t['expected_checksum'] != 64 * t['sweeps'] for t in plan['tasks'])):
            raise ValueError(f'Unexpected prepared plan: {label(case)}/{architecture}')
    return file_hash(target / 'prepared/manifest.json')


def prepare_all(output, workers):
    output.mkdir(parents=True, exist_ok=False)
    for name in SNAPSHOT:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    manifests = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case): case for case in cases()}
        for future in as_completed(futures):
            manifests[label(futures[future])] = future.result()
            announce(f'prepared {label(futures[future])}')
    write_json(output / 'protocol.json', dict(
        means=taskset.MEANS, cvs=taskset.CVS, sets=taskset.SETS, tasks=taskset.TASKS,
        grid=taskset.GRID, reference_mean=taskset.REFERENCE_MEAN, task_u=taskset.TASK_U,
        truncation_sigma=taskset.TRUNCATION_SIGMA, seed_base=taskset.SEED_BASE,
        job_base_ns=taskset.JOB_BASE_NS, sweep_ns=taskset.SWEEP_NS,
        u_tolerance=U_TOLERANCE, architectures=ARCHITECTURES, runs_per_policy=1,
        prepared_manifest_hashes=dict(sorted(manifests.items())),
        snapshot_hashes={name: file_hash(output / name) for name in SNAPSHOT}))
    announce(f'prepared all {len(manifests)} task sets')


def check_protocol(output):
    protocol = json.loads((output / 'protocol.json').read_text())
    for name, expected in protocol['snapshot_hashes'].items():
        if file_hash(output / name) != expected:
            raise ValueError(f'Snapshot changed: {name}')
    for case in cases():
        path = case_dir(output, case) / 'prepared/manifest.json'
        if file_hash(path) != protocol['prepared_manifest_hashes'][label(case)]:
            raise ValueError(f'Prepared manifest changed: {label(case)}')


def completed(destination):
    """Return True for a finished run; move an infrastructure failure aside."""
    records = destination / 'measurements.jsonl'
    if not destination.exists():
        return False
    lines = records.read_text().splitlines() if records.exists() else []
    if lines and 'header' in json.loads(lines[0]):
        return True
    attempt = 0
    while destination.with_name(f'{destination.name}.aborted-{attempt}').exists():
        attempt += 1
    destination.rename(destination.with_name(f'{destination.name}.aborted-{attempt}'))
    return False


def launch_gate():
    with LAUNCH_LOCK:
        wait = _last_launch[0] + LAUNCH_INTERVAL_SECONDS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_launch[0] = time.monotonic()


def execute(prepared, destination, architecture, mode=0):
    """Run once; return the record, or None when no run header was produced."""
    if completed(destination):
        return json.loads((destination / 'measurements.jsonl').read_text().splitlines()[0])
    destination.parent.mkdir(parents=True, exist_ok=True)
    launch_gate()
    row = run(prepared, destination, architecture=ARCHITECTURES.index(architecture), runs=1,
              mode=mode, timeout=TIMEOUT_SECONDS)[0]
    return row if 'header' in row else None


def run_specs(specs, workers):
    """Run (name, prepared, destination, architecture, mode) specs in parallel."""
    infra, failed = 0, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(execute, *spec[1:]): spec[0] for spec in specs}
        for future in as_completed(futures):
            name = futures[future]
            row = future.result()
            if row is None:
                infra += 1
                announce(f'infrastructure failure {name} (no run header)')
                if infra >= MAX_INFRA_FAILURES:
                    for pending in futures:
                        pending.cancel()
                    raise RuntimeError(f'{infra} runs produced no run header')
                continue
            if row['execution_status'] != 'ok':
                failed.append(name)
            announce(f'finished {name} status={row["execution_status"]} '
                     f'errors={row.get("errors", [])} wall_s={row.get("wall_seconds", 0):.1f}')
    return failed, infra


def u_check(output, workers):
    selected = [(mean, max(taskset.CVS), 0) for mean in taskset.MEANS]
    specs = []
    for case in selected:
        prepared = case_dir(output, case) / 'prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        specs += [(f'{label(case)}/isolated/{t["task_id"]}', prepared,
                   case_dir(output, case) / 'isolated' / t['task_id'], 'p', i + 1)
                  for i, t in enumerate(plan['tasks'])]
    failed, infra = run_specs(specs, workers)
    if failed or infra:
        raise RuntimeError(f'Isolated U runs failed: {failed}, infrastructure={infra}')
    report = {}
    for case in selected:
        prepared = case_dir(output, case) / 'prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        isolated = case_dir(output, case) / 'isolated'
        batches = [load_batch(prepared, isolated / t['task_id']) for t in plan['tasks']]
        values = characterize(plan, batches)['utilization']
        errors = {k: v / taskset.TASK_U - 1 for k, v in values.items()}
        report[label(case)] = dict(utilization=values, relative_error=errors,
            periods={t['task_id']: t['period_ticks'] for t in plan['tasks']})
        for task in plan['tasks']:
            announce(f'{label(case)} {task["task_id"]} period={task["period_ticks"]} '
                     f'U={values[task["task_id"]]:.5f} error={errors[task["task_id"]]:+.2%}')
    write_json(output / 'isolated-u.json', report)
    worst = max(abs(e) for row in report.values() for e in row['relative_error'].values())
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    announce(f'isolated U gate passed: worst relative error {worst:.2%}')


def architecture_specs(output, selected):
    return [(f'{label(case)}/{architecture}', case_dir(output, case) / 'prepared',
             case_dir(output, case) / architecture, architecture, 0)
            for case in selected for architecture in ARCHITECTURES]


def summarize(output):
    rows = []
    for case in cases():
        target = case_dir(output, case)
        if not all((target / a / 'measurements.jsonl').exists() for a in ARCHITECTURES):
            continue
        config = json.loads((target / 'configuration.json').read_text())
        result = dict(mean=case[0], cv=case[1], set_id=case[2],
                      periods=[t['period_ticks'] for t in config['tasks']])
        for architecture in ARCHITECTURES:
            row = load_batch(target / 'prepared', target / architecture)[0]
            ok = row['execution_status'] == 'ok'
            result[architecture] = dict(status=row['execution_status'],
                errors=row.get('errors', []),
                tet_ns=row['tet_ns'] if ok else None, tat_ns=row['tat_ns'] if ok else None,
                response_sum_ns=row.get('response_sum_ns') if ok else None,
                measured_jobs=row.get('measured_jobs'),
                cohorts=len(row.get('cohorts', [])),
                start_core_changes=_start_core_changes(row, config) if ok else None)
        write_json(target / 'summary.json', result)
        rows.append(result)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    announce(f'summarized {len(rows)} task sets into results.jsonl')


def _start_core_changes(row, config):
    warmup = {i: config['warmup_ticks'] // t['period_ticks'] for i, t in enumerate(config['tasks'])}
    by_task = {}
    for job in sorted(row['jobs'], key=lambda job: (job['task'], job['job'])):
        if job['job'] >= warmup[job['task']]:
            by_task.setdefault(job['task'], []).append(job['start_core'])
    return sum(a != b for cores in by_task.values() for a, b in zip(cores, cores[1:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'u-check', 'pilot', 'full', 'summarize'))
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--workers', type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    if not 1 <= args.workers <= MAX_WORKERS:
        parser.error(f'workers must be between 1 and {MAX_WORKERS}')
    if args.stage == 'prepare':
        prepare_all(args.output, min(args.workers, 32))
        return
    check_protocol(args.output)
    if args.stage == 'u-check':
        u_check(args.output, args.workers)
    elif args.stage == 'pilot':
        failed, _ = run_specs(architecture_specs(
            args.output, [c for c in cases() if c[2] == 0]), args.workers)
        summarize(args.output)
        if failed:
            raise RuntimeError(f'Pilot runs failed: {failed}')
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[2] != 0), key=lambda c: (c[2], c[0], c[1]))
        failed, _ = run_specs(architecture_specs(args.output, remaining), args.workers)
        summarize(args.output)
        if failed:
            announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(args.output)


if __name__ == '__main__':
    main()
