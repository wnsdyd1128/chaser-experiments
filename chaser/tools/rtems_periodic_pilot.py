"""Bounded periodic pilot: explicit placements, ten runs, no training/test tuning."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
from pathlib import Path
import time

from chaser.features import build_features
from chaser.labeling import label_measurements
from chaser.periodic_analysis import analyze
from chaser.periodic_build import prepare
from chaser.periodic_dataset import characterize, load_batch, to_measurement
from tools.rtems_periodic import run
from tools.rtems_smoke import check_inputs, file_hash, write_json


def configurations() -> list[dict]:
    """Ten parameter variants in one family, each with about 9600 loads/job.

    The exploratory CPU target is 1--3 ms; it is assessed, not enforced by
    architecture-dependent tuning. These are controlled kernels, not ten
    independent application families. No theta has been calibrated yet.
    """
    result = []
    for n in range(10):
        tasks = []
        for i in range(4 + n % 3):
            distinct = (4, 8, 16, 64)[(n + i) % 4]
            tasks.append(dict(task_id=f't{i}', distinct=distinct,
                              stride=(1, 32, 4096)[(n + i) % 3],
                              sweeps=9600 // distinct, core=i % 4,
                              period_ticks=(10, 20)[(n + i) % 2]))
        result.append(dict(workload_id=f'pilot-{n:02d}', family_id='periodic-layout-pilot',
                           policy_id='pilot-explicit-core-order-v1', horizon_ticks=40,
                           tasks=tasks))
    return result


def prepare_pilot(output: Path) -> None:
    """Build and analyze a fixed ten-taskset suite; failed snapshots stay intact."""
    output.mkdir(parents=True, exist_ok=False)
    configs = configurations()
    write_json(output / 'pilot.json', dict(configurations=configs, expected_runs=10,
        cpu_target_ms=[1, 3], purpose='measurement feasibility and budget only',
        split_frozen=False, theta_calibrated=False, eligible_for_training=False))
    for config in configs:
        snapshot = output / config['workload_id']
        started = time.monotonic()
        prepare(config, snapshot)
        analyze(snapshot)
        print(f'{config["workload_id"]}: built/analyzed in {time.monotonic() - started:.1f}s', flush=True)


def execute_pilot(prepared: Path, output: Path, *, workers: int, timeout: float) -> dict:
    """Run independent batches concurrently; never replace failed attempts."""
    if not 1 <= workers <= 8:
        raise ValueError('Use 1--8 independent simulator workers')
    output.mkdir(parents=True, exist_ok=False)
    pilot = json.loads((prepared / 'pilot.json').read_text())
    write_json(output / 'protocol.json', dict(workers=workers, timeout_seconds=timeout,
        pilot_hash=file_hash(prepared / 'pilot.json'), expected_runs=10))
    jobs = []
    for config in pilot['configurations']:
        name = config['workload_id']
        for architecture in range(3):
            jobs.append((name, ('g', 'c', 'p')[architecture], architecture, 0))
        for i in range(len(config['tasks'])):
            jobs.append((name, f'u{i}', 2, i + 1))
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run, prepared / name, output / name / batch,
                    architecture=architecture, mode=mode, runs=10, timeout=timeout): (name, batch)
                   for name, batch, architecture, mode in jobs}
        for future in as_completed(futures):
            name, batch = futures[future]
            records = future.result()
            ok = sum(r['execution_status'] == 'ok' for r in records)
            print(f'{name}/{batch}: {ok}/10 ok', flush=True)
    report = summarize(prepared, output)
    report['collection_wall_seconds'] = time.monotonic() - started
    write_json(output / 'summary.json', report)
    return report


def summarize(prepared: Path, output: Path) -> dict:
    """Produce provisional labels/features and keep failures in the denominator."""
    pilot = json.loads((prepared / 'pilot.json').read_text())
    reports, samples, attempted, successful, seconds, characterization_seconds = [], [], 0, 0, 0.0, 0.0
    job_cpu_ms = []
    for config in pilot['configurations']:
        name = config['workload_id']
        snapshot = prepared / name
        plan = json.loads((snapshot / 'p/plan.json').read_text())
        u_batches = [load_batch(snapshot, output / name / f'u{i}') for i in range(len(plan['tasks']))]
        timing = [load_batch(snapshot, output / name / a) for a in ('g', 'c', 'p')]
        all_rows = [r for batch in u_batches + timing for r in batch]
        attempted += len(all_rows)
        successful += sum(r['execution_status'] == 'ok' for r in all_rows)
        seconds += sum(r['wall_seconds'] for r in all_rows)
        characterization_seconds += sum(r['wall_seconds'] for b in u_batches for r in b)
        report = dict(workload_id=name, attempted=len(all_rows),
                      successful=sum(r['execution_status'] == 'ok' for r in all_rows))
        for batch in u_batches:
            for row in batch:
                if row['execution_status'] == 'ok':
                    job_cpu_ms.extend((j['cpu_after_ns'] - j['cpu_before_ns']) / 1e6 for j in row['jobs'])
        try:
            u = characterize(plan, u_batches)
            write_json(output / name / 'utilization.json', u)
            measurements = []
            for a, rows in zip(('g', 'c', 'p'), timing):
                a_plan = json.loads((snapshot / a / 'plan.json').read_text())
                measurements.extend(to_measurement(a_plan, r) for r in rows)
            label = label_measurements(measurements, expected_runs=10)
            analysis_manifest = json.loads((snapshot / 'analysis/manifest.json').read_text())
            check_inputs(snapshot / 'analysis', analysis_manifest)
            locality = json.loads((snapshot / 'analysis/locality.json').read_text())
            if locality['manifest_hash'] != file_hash(snapshot / 'manifest.json'):
                raise ValueError('Analysis/execution snapshot mismatch')
            tasks = [dict(locality['cases'][t], utilization=value) for t, value in u['utilization'].items()]
            for kind, alpha in (('caas-ca', None), ('ca-line', None), ('ca-csrd', None), ('cls', 0.5)):
                samples.append(dict(workload_id=name, family_id=config['family_id'],
                    representation_id=kind, alpha=alpha, features=build_features(tasks, kind, alpha=alpha),
                    label=label.label, label_evidence=asdict(label),
                    characterization_id=u['characterization_id'],
                    analysis_manifest_hash=file_hash(snapshot / 'analysis/manifest.json'),
                    eligible_for_training=False, split_group='pilot'))
            report.update(label=asdict(label), utilization=u['utilization'])
        except ValueError as error:
            report['excluded_reason'] = str(error)
        reports.append(report)
    with (output / 'provisional_samples.jsonl').open('w') as stream:
        for row in samples:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
    size = sum(p.stat().st_size for root in (prepared, output) for p in root.rglob('*') if p.is_file())
    return dict(scope='pilot-only; explicit mapping, no calibrated theta or frozen split',
        workloads=reports, attempted_runs=attempted, successful_runs=successful,
        failed_runs=attempted - successful, provisional_sample_rows=len(samples),
        total_simulator_wall_seconds=seconds, characterization_wall_seconds=characterization_seconds,
        mean_run_wall_seconds=seconds / attempted, storage_bytes=size,
        independent_job_cpu_ms=dict(min=min(job_cpu_ms), max=max(job_cpu_ms)) if job_cpu_ms else None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare')
    build.add_argument('--output', required=True, type=Path)
    execute = commands.add_parser('run')
    execute.add_argument('prepared', type=Path)
    execute.add_argument('--output', required=True, type=Path)
    execute.add_argument('--workers', type=int, default=4)
    execute.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare_pilot(args.output.resolve())
    else:
        report = execute_pilot(args.prepared.resolve(), args.output.resolve(),
                               workers=args.workers, timeout=args.timeout)
        print(json.dumps({k: v for k, v in report.items() if k != 'workloads'}, indent=2))
        if report['failed_runs'] or any('excluded_reason' in r for r in report['workloads']):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
