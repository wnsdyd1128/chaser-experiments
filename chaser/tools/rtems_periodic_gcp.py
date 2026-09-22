"""Collect G/C/P timing only from prepared snapshots; no U runs or final labels."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from itertools import islice
import json
from pathlib import Path
import time

from chaser.periodic_dataset import load_batch
from tools.rtems_periodic import run
from tools.rtems_smoke import check_inputs, file_hash, write_json


def collect(prepared: list[Path], output: Path, *, workers: int = 16,
            timeout: float = 1800) -> None:
    """Share a bounded simulator pool across tasksets and G/C/P batches.

    Each batch uses ten fresh simulator processes sequentially, normal mode and
    no diagnostic probes. Complete existing batches are revalidated; partial or
    failed evidence is preserved and reported, never replaced. A single SIGINT
    to the collector drains admitted batches without admitting the whole queue.
    Callers must supply the intended policy snapshots; collection success does
    not establish policy freezing, eligibility, or final architecture labels.
    """
    if type(workers) is not int or not 1 <= workers <= 32 or not 0 < timeout < float('inf'):
        raise ValueError('Use 1--32 workers and a positive finite timeout')
    if not prepared:
        raise ValueError('At least one prepared snapshot is required')
    snapshots, identities = {}, {}
    policy_ids = set()
    for path in prepared:
        path = path.resolve()
        manifest = json.loads((path / 'manifest.json').read_text())
        check_inputs(path, manifest)
        plans = [json.loads((path / a / 'plan.json').read_text()) for a in ('g', 'c', 'p')]
        name = plans[0]['workload_id']
        if not name or name in ('.', '..') or Path(name).name != name:
            raise ValueError('Workload ID must be a single directory name')
        if name in snapshots:
            raise ValueError(f'Duplicate workload: {name}')
        if any(plan['workload_id'] != name or plan['architecture'] != i
               for i, plan in enumerate(plans)):
            raise ValueError('G/C/P plan identity mismatch')
        policy_ids.update(plan['policy_id'] for plan in plans)
        snapshots[name] = path
        identities[name] = dict(path=str(path), manifest_hash=file_hash(path / 'manifest.json'))
    if len(policy_ids) != 1:
        raise ValueError('Use a separate output for each allocation policy')
    output = output.resolve()
    protocol = dict(scope='gcp-timing-only', workers=workers, timeout_seconds=timeout,
                    expected_runs=10, mode=0, trace=False, empty=False,
                    policy_id=next(iter(policy_ids)), snapshots=identities,
                    collector_hash=file_hash(Path(__file__)))
    protocol_path = output / 'protocol.json'
    if output.exists():
        if json.loads(protocol_path.read_text()) != protocol:
            raise ValueError('Collection protocol changed')
    else:
        output.mkdir(parents=True)
        write_json(protocol_path, protocol)

    def batch(name: str, architecture: int) -> dict:
        letter = ('g', 'c', 'p')[architecture]
        directory = output / 'runs' / name / letter
        report = dict(workload_id=name, architecture=architecture, status='failed')
        started = time.monotonic()
        try:
            snapshot = snapshots[name]
            if file_hash(snapshot / 'manifest.json') != identities[name]['manifest_hash']:
                raise ValueError('Prepared manifest changed')
            if not directory.exists():
                run(snapshot, directory, architecture=architecture, mode=0,
                    runs=10, timeout=timeout, trace=False, empty=False)
            actual = json.loads((directory / 'protocol.json').read_text())
            expected = dict(runs=10, timeout_seconds=timeout, mode=0, trace=False, empty=False)
            if any(actual.get(key) != value for key, value in expected.items()):
                raise ValueError('G/C/P batch protocol differs')
            rows = load_batch(snapshot, directory)
            if len(rows) != 10 or {r['run_id'] for r in rows} != {str(i) for i in range(10)}:
                raise ValueError('Expected ten distinct G/C/P runs')
            if any(r['architecture'] != architecture or r['mode'] != 0
                   or r['trace'] or r['empty'] for r in rows):
                raise ValueError('G/C/P run identity mismatch')
            report.update(attempted_runs=len(rows),
                          successful_runs=sum(r['execution_status'] == 'ok' for r in rows))
            if report['successful_runs'] != 10:
                raise ValueError('Failed G/C/P measurements')
            if file_hash(snapshot / 'manifest.json') != identities[name]['manifest_hash']:
                raise ValueError('Prepared manifest changed')
            report['status'] = 'ok'
        except (ValueError, KeyError, TypeError, OSError) as error:
            report['error'] = f'{type(error).__name__}: {error}'
        report['wall_seconds'] = time.monotonic() - started
        return report

    reports = []
    total = 3 * len(snapshots)

    def progress() -> None:
        successful = sum(r['status'] == 'ok' for r in reports)
        stage = ('gcp_collecting' if len(reports) < total else
                 'gcp_collected' if successful == total else 'gcp_collection_failed')
        write_json(output / 'run-progress.json', dict(dataset_stage=stage,
            planned_batches=total, processed_batches=len(reports),
            successful_batches=successful, batches=reports))

    progress()
    jobs = iter((name, architecture) for name in snapshots for architecture in range(3))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(batch, *job) for job in islice(jobs, workers)}
        while pending:
            completed, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                report = future.result()
                reports.append(report)
                progress()
                print(f'{report["workload_id"]}/{("g", "c", "p")[report["architecture"]]}: '
                      f'{report["status"]} ({report["wall_seconds"]:.1f}s)'
                      + (f' {report["error"]}' if 'error' in report else ''), flush=True)
            pending.update(executor.submit(batch, *job) for job in islice(jobs, len(completed)))
    if any(r['status'] != 'ok' for r in reports):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prepared', nargs='+', type=Path, help='Prepared policy snapshot directories')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=16, help='Global simulator limit (1--32)')
    parser.add_argument('--timeout', type=float, default=1800, help='Seconds per fresh simulator run')
    args = parser.parse_args()
    collect(args.prepared, args.output, workers=args.workers, timeout=args.timeout)


if __name__ == '__main__':
    main()
