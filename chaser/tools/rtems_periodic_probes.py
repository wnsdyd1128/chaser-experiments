"""Fixed development probes and resource boundaries, never RF training samples."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from chaser.periodic import make_plan
from chaser.periodic_build import read_symbols
from chaser.periodic_dataset import load_batch
from tools.rtems_smoke import check_inputs, file_hash, write_json


def _configuration(name: str, tasks: list[dict], horizon: int) -> dict:
    return dict(workload_id=name, family_id='development-periodic-feasibility-v1',
                policy_id='development-explicit-core-order-v1', horizon_ticks=horizon,
                eligible_for_training=False, test_eligible=False, tasks=tasks)


def _task(i: int, *, distinct: int = 64, stride: int = 32,
          sweeps: int = 160, period: int = 20, **pattern) -> dict:
    return dict(task_id=f't{i}', distinct=distinct, stride=stride, sweeps=sweeps,
                period_ticks=period, core=i % 4, **pattern)


def configurations() -> list[dict]:
    """Eleven two-task probes; q>=2 and at least 10240 loads/job.

    Initial development periods are 20 ms, or 100 ms for LLC boundary targets;
    both tasks execute two jobs. These are feasibility inputs, not U targets.
    No G/C/P outcome or label selects these constants.
    """
    result = []
    for name, distinct, stride in (
            ('layout-packed', 64, 1), ('layout-spread', 64, 32),
            ('layout-conflict', 64, 4096),
            *[(f'l1-{d}', d, 32) for d in (511, 512, 513)],
            *[(f'llc-{d}', d, 32) for d in (65535, 65536, 65537)]):
        period = 100 if distinct > 65534 else 20
        target = _task(0, distinct=distinct, stride=stride,
                       sweeps=max(2, (10240 + distinct - 1) // distinct), period=period)
        result.append(_configuration(name, [target, _task(1, period=period)], 2 * period))
    for pattern, cold in (('hot-cold', 1), ('phase', 4)):
        count = 64 * 4 + 1024 * cold
        target = _task(0, distinct=1088, pattern=pattern, hot_distinct=64,
                       hot_repeats=4, cold_repeats=cold,
                       sweeps=max(2, (10240 + count - 1) // count))
        result.append(_configuration(pattern, [target, _task(1)], 40))
    return result


def boundary_configurations() -> list[dict]:
    """Build/runtime boundaries; these are not utilization or full-load claims."""
    result = [_configuration(f'tasks-{n:02d}', [_task(i, sweeps=2) for i in range(n)], 40)
              for n in (4, 8, 12, 16)]
    result.extend([
        _configuration('jobs-balanced', [_task(i, sweeps=1, period=1)
                                         for i in range(16)], 256),
        _configuration('jobs-skewed', [_task(i, sweeps=1, period=1 if i == 0 else 4081)
                                       for i in range(16)], 4081),
        _configuration('data-limit', [_task(i, distinct=32768, sweeps=2, period=100)
                                      for i in range(16)], 200),
        _configuration('capacity-mixed-16', [
            _task(i, distinct=65537 if i == 0 else 64, sweeps=2, period=100)
            for i in range(16)], 200),
    ])
    return result


def initialize(output: Path) -> None:
    """Freeze development inputs in a fresh directory before any measurements."""
    output.mkdir(parents=True, exist_ok=False)
    (output / 'configs').mkdir()
    suite = dict(probes=configurations(), boundaries=boundary_configurations(),
                 eligible_for_training=False, test_eligible=False, split_frozen=False,
                 theta_calibrated=False, expected_probe_timing_u_runs=550,
                 period_rule='20 ms; LLC probes 100 ms; two jobs/task',
                 sweep_rule='max(2, ceil(10240 / accesses_per_sweep)); companion q=160',
                 boundary_analysis='build/runtime only; full linked streams checked on 11 probes',
                 rss_scope='Linux wait4 ru_maxrss: largest process high-water mark, not concurrent RSS sum')
    for group in ('probes', 'boundaries'):
        for config in suite[group]:
            for architecture in range(3):
                make_plan(config, architecture)
            write_json(output / 'configs' / (config['workload_id'] + '.json'), config)
    write_json(output / 'suite.json', suite)


def _profile(command: list[str], destination: Path) -> dict:
    """Record separate child resource usage and preserve command failures."""
    destination.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    with (destination / 'command.log').open('x') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        _, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    result = dict(command=command, returncode=process.returncode,
                  wall_seconds=time.monotonic() - started, peak_rss_kib=usage.ru_maxrss,
                  user_seconds=usage.ru_utime, system_seconds=usage.ru_stime)
    write_json(destination / 'resources.json', result)
    return result


def build_suite(root: Path, configs: list[dict], *, analysis: bool) -> list[dict]:
    """Profile builds separately from analyses; leave failed snapshots intact."""
    results = []
    for config in configs:
        name = config['workload_id']
        if json.loads((root / 'configs' / (name + '.json')).read_text()) != config:
            raise ValueError('Prepared input differs from suite configuration')
        snapshot = root / 'snapshots' / name
        cost = root / 'costs' / name
        row = _profile([sys.executable, '-m', 'tools.rtems_periodic', 'prepare',
                        str(root / 'configs' / (name + '.json')), '--output', str(snapshot)],
                       cost / 'prepare')
        results.append(row)
        if row['returncode'] == 0:
            symbols = read_symbols(snapshot / 'build/p.exe')
            plan = json.loads((snapshot / 'p/plan.json').read_text())
            write_json(cost / 'static-memory.json', dict(
                logical_jobs=sum(t['job_count'] for t in plan['tasks']),
                record_slots=len(plan['tasks']) * max(t['job_count'] for t in plan['tasks']),
                jobs_bytes=symbols['jobs'][1], dispatches_bytes=symbols['dispatches'][1],
                aligned_data_bytes=sum((t['data_size'] + 4095) // 4096 * 4096 for t in plan['tasks'])))
            if analysis:
                row = _profile([sys.executable, '-m', 'tools.rtems_periodic', 'analyze',
                                str(snapshot)], cost / 'analyze')
                results.append(row)
        print(f'{name}: {"ok" if row["returncode"] == 0 else "FAILED"}', flush=True)
    return results


def execute_suite(root: Path, configs: list[dict], *, stage: str,
                  workers: int, timeout: float) -> list[dict]:
    """Keep every attempt; repetition requires successful smoke and analysis."""
    if not 1 <= workers <= 8:
        raise ValueError('Use 1--8 independent simulator workers')
    # Validate the entire requested population before creating the stage.
    for config in configs:
        snapshot = root / 'snapshots' / config['workload_id']
        check_inputs(snapshot, json.loads((snapshot / 'manifest.json').read_text()))
        if json.loads((snapshot / 'configuration.json').read_text()) != config:
            raise ValueError('Snapshot differs from suite configuration')
        if stage == 'repeat':
            check_inputs(snapshot / 'analysis', json.loads((snapshot / 'analysis/manifest.json').read_text()))
            locality = json.loads((snapshot / 'analysis/locality.json').read_text())
            if locality['manifest_hash'] != file_hash(snapshot / 'manifest.json'):
                raise ValueError('Analysis/execution snapshot mismatch')
            for batch in ('g', 'c', 'p', 'u0', 'u1'):
                rows = load_batch(snapshot, root / 'runs/smoke' / config['workload_id'] / batch)
                if len(rows) != 1 or any(r['execution_status'] != 'ok' for r in rows):
                    raise ValueError('Repeat requires successful smoke for every selected probe')
    output = root / 'runs' / stage
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'protocol.json', dict(stage=stage, workers=workers, timeout_seconds=timeout,
        suite_hash=file_hash(root / 'suite.json'), workloads=[c['workload_id'] for c in configs]))
    jobs = []
    for config in configs:
        name = config['workload_id']
        batches = [('g', 'g', 0), ('c', 'c', 0), ('p', 'p', 0)]
        if stage in ('smoke', 'repeat'):
            batches = [(f'u{i}', 'p', i + 1) for i in range(len(config['tasks']))] + batches
        if stage == 'empty':
            batches = [('empty', 'p', 1)]
        for batch, architecture, mode in batches:
            command = [sys.executable, '-m', 'tools.rtems_periodic', 'run',
                       str(root / 'snapshots' / name), '--output', str(output / name / batch),
                       '--architecture', architecture, '--mode', str(mode),
                       '--runs', '10' if stage in ('repeat', 'empty') else '1',
                       '--timeout', str(timeout)]
            if stage == 'diagnostic':
                command.append('--trace')
            elif stage == 'empty':
                command.append('--empty')
            jobs.append((name, batch, command))
    results, started = [], time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_profile, cmd, root / 'costs' / name / stage / batch):
                   (name, batch) for name, batch, cmd in jobs}
        for future in as_completed(futures):
            name, batch = futures[future]
            row = dict(future.result(), workload_id=name, batch=batch)
            results.append(row)
            print(f'{name}/{batch}: {"ok" if row["returncode"] == 0 else "FAILED"}', flush=True)
    write_json(output / 'collection.json', dict(wall_seconds=time.monotonic() - started,
                                              batches=results))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'build', 'run'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--group', choices=('probes', 'boundaries'), default='probes')
    parser.add_argument('--only', nargs='+')
    parser.add_argument('--stage', choices=('smoke', 'repeat', 'boundary', 'diagnostic', 'empty'),
                        default='smoke')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == 'init':
        initialize(root)
        return
    suite = json.loads((root / 'suite.json').read_text())
    configs = suite[args.group]
    if args.only:
        if set(args.only) - {c['workload_id'] for c in configs}:
            parser.error('Unknown workload in --only')
        configs = [c for c in configs if c['workload_id'] in args.only]
    if args.command == 'build':
        results = build_suite(root, configs, analysis=args.group == 'probes')
    else:
        results = execute_suite(root, configs, stage=args.stage,
                                workers=args.workers, timeout=args.timeout)
    if any(r['returncode'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
