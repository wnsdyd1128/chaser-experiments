"""Collect frozen-input ELF locality and independent U before policy calibration."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from math import fsum
from pathlib import Path
import shutil
import time

from chaser.features import build_features
from chaser.event_compression import EventCompressionQueue
from chaser.periodic import digest
from chaser.periodic_analysis import analyze
from chaser.periodic_build import prepare
from chaser.periodic_dataset import characterize, load_batch
from tools.rtems_periodic import run
from tools.rtems_periodic_freeze import verify
from tools.rtems_smoke import check_inputs, file_hash, write_json


def feature_record(member: dict, locality: dict, utilization: dict) -> dict:
    """Join exact task IDs, retain bound failures, and never produce labels."""
    values = utilization['utilization']
    if set(values) != set(locality['cases']):
        raise ValueError('Locality and independent U task IDs differ')
    reasons = []
    if max(values.values()) > 0.25:
        reasons.append('task_u_exceeds_0.25')
    if fsum(values.values()) > 2.0:
        reasons.append('taskset_u_exceeds_2.0')
    tasks = [dict(locality['cases'][key], utilization=value) for key, value in values.items()]
    features = {}
    undefined = {}
    for kind in ('caas-ca', 'ca-line', 'ca-csrd', 'cls'):
        try:
            features[kind] = build_features(tasks, kind, alpha=0.5 if kind == 'cls' else None)
        except ValueError as error:
            undefined[kind] = str(error)
    return dict(member, characterization_id=utilization['characterization_id'],
                utilization=values, features=features, undefined_features=undefined,
                cls_alpha=0.5, within_u_bounds=not reasons, exclusion_reasons=reasons,
                dataset_stage='characterized')


def _dataset_stage(phase: str, reports: list[dict], total: int) -> str:
    ongoing, complete, failed = {
        'prepare': ('preparing', 'prepared', 'prepare_failed'),
        'run': ('characterizing', 'characterized', 'characterization_failed'),
    }[phase]
    if len(reports) < total:
        return ongoing
    return complete if all(r['status'] == 'ok' for r in reports) else failed


def checked_locality(snapshot: Path) -> dict:
    """Accept only a complete analysis tied to the unchanged execution snapshot."""
    check_inputs(snapshot, json.loads((snapshot / 'manifest.json').read_text()))
    directory = snapshot / 'analysis'
    check_inputs(directory, json.loads((directory / 'manifest.json').read_text()))
    locality = json.loads((directory / 'locality.json').read_text())
    if locality['manifest_hash'] != file_hash(snapshot / 'manifest.json'):
        raise ValueError('Analysis/execution snapshot mismatch')
    return locality


def collect(frozen: Path, output: Path, *, phase: str, workers: int, timeout: float,
            prepare_workers: int | None = None) -> None:
    """Resume verified complete batches; preserve interrupted or failed evidence.

    Preparation uses ``prepare_workers`` (defaults to ``workers``), each in its own
    snapshot; full-event JSON and compressor memory scale with that limit.
    U runs one taskset at a time with at most ``workers`` simulator processes,
    each executing one task on core zero.
    Existing incomplete batches are reported as failures and never overwritten.
    """
    if not 1 <= workers <= 8 or not 0 < timeout < float('inf'):
        raise ValueError('Use 1--8 workers and a positive finite timeout')
    preparation_limit = workers if prepare_workers is None else prepare_workers
    if not 1 <= preparation_limit <= 16:
        raise ValueError('Use 1--16 prepare workers')
    if phase != 'prepare' and prepare_workers is not None:
        raise ValueError('prepare_workers applies only to prepare')
    verify(frozen)
    population = json.loads((frozen / 'population.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    protocol = dict(population_hash=file_hash(frozen / 'population.json'),
                    split_hash=file_hash(frozen / 'split.json'), expected_runs=10,
                    workers=workers, timeout_seconds=timeout, u_max=0.25, U_max=2.0)
    protocol_path = output / 'protocol.json'
    if protocol_path.exists():
        previous = json.loads(protocol_path.read_text())
        # Readiness was an invariant false flag, not a measurement parameter.
        migrated = dict(previous)
        if migrated.get('dataset_ready') is False:
            del migrated['dataset_ready']
        if migrated != protocol:
            raise ValueError('Collection protocol changed')
        if previous != protocol:
            write_json(protocol_path, protocol)
    else:
        write_json(protocol_path, protocol)
    if phase == 'run':
        implementation = output / 'characterization-implementation'
        root = Path(__file__).resolve().parents[1]
        names = ('tools/rtems_periodic_characterize.py', 'chaser/features.py',
                 'chaser/periodic_dataset.py', 'chaser/periodic.py')
        hashes = {name: file_hash(root / name) for name in names}
        identity = output / 'characterization-implementation.json'
        if identity.exists():
            if json.loads(identity.read_text()) != hashes:
                raise ValueError('Characterization implementation changed')
            check_inputs(implementation, dict(files=hashes))
        else:
            implementation.mkdir(exist_ok=False)
            for name in names:
                destination = implementation / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / name, destination)
            write_json(identity, hashes)
    def collect_member(member: dict) -> dict:
        name = member['workload_id']
        snapshot = output / 'prepared' / name
        configuration = frozen / 'source/configs' / (name + '.json')
        report = dict(member, phase=phase, status='failed')
        started = time.monotonic()
        try:
            config = json.loads(configuration.read_text())
            if digest(config) != member['configuration_hash']:
                raise ValueError('Frozen configuration changed')
            if phase == 'prepare':
                if not snapshot.exists():
                    prepare(config, snapshot)
                if json.loads((snapshot / 'configuration.json').read_text()) != config:
                    raise ValueError('Prepared configuration differs from frozen input')
                check_inputs(snapshot, json.loads((snapshot / 'manifest.json').read_text()))
                if not (snapshot / 'analysis').exists():
                    analyze(snapshot, compress_events=True, compression_queue=compression_queue)
                checked_locality(snapshot)
            else:
                if json.loads((snapshot / 'configuration.json').read_text()) != config:
                    raise ValueError('Prepared configuration differs from frozen input')
                locality = checked_locality(snapshot)
                plan = json.loads((snapshot / 'p/plan.json').read_text())

                def batch(index: int) -> list[dict]:
                    directory = output / 'runs' / name / f'u{index}'
                    if not directory.exists():
                        run(snapshot, directory, architecture=2, mode=index + 1,
                            runs=10, timeout=timeout)
                    batch_protocol = json.loads((directory / 'protocol.json').read_text())
                    if (batch_protocol['runs'] != 10
                            or batch_protocol['timeout_seconds'] != timeout
                            or batch_protocol['mode'] != index + 1
                            or batch_protocol['trace'] or batch_protocol['empty']):
                        raise ValueError('Independent batch protocol differs')
                    rows = load_batch(snapshot, directory)
                    if len(rows) != 10:
                        raise ValueError('Expected ten independent runs')
                    return rows

                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = [executor.submit(batch, i) for i in range(len(plan['tasks']))]
                    # All submitted batches finish even if another task fails.
                    batches = [future.result() for future in futures]
                utilization = characterize(plan, batches)
                directory = output / 'runs' / name
                write_json(directory / 'utilization.json', utilization)
                record = feature_record(member, locality, utilization)
                record['analysis_manifest_hash'] = file_hash(snapshot / 'analysis/manifest.json')
                record['execution_manifest_hash'] = file_hash(snapshot / 'manifest.json')
                record['implementation_hashes'] = hashes
                write_json(directory / 'features.json', record)
                report.update(within_u_bounds=record['within_u_bounds'],
                              exclusion_reasons=record['exclusion_reasons'],
                              undefined_features=record['undefined_features'])
            report['status'] = 'ok'
        except Exception as error:
            report['error'] = f'{type(error).__name__}: {error}'
        report['wall_seconds'] = time.monotonic() - started
        report['dataset_stage'] = _dataset_stage(phase, [report], 1)
        return report

    reports = []

    def write_progress() -> None:
        write_json(output / (phase + '-progress.json'), dict(
            planned_workloads=len(population['workloads']), processed_workloads=len(reports),
            successful_workloads=sum(r['status'] == 'ok' for r in reports), workloads=reports,
            dataset_stage=_dataset_stage(phase, reports, len(population['workloads']))))

    def record(report: dict) -> None:
        reports.append(report)
        write_progress()
        print(f'{phase} {report["workload_id"]}: {report["status"]} ({report["wall_seconds"]:.1f}s)'
              + (f' {report["error"]}' if 'error' in report else ''), flush=True)

    write_progress()
    if phase == 'prepare':
        with EventCompressionQueue() as compression_queue, \
                ThreadPoolExecutor(max_workers=preparation_limit) as executor:
            write_json(output / 'prepare-compression.json', dict(
                workers=4, max_raw_files=compression_queue.max_files,
                max_file_bytes=compression_queue.max_file_bytes,
                max_raw_bytes=compression_queue.max_files * compression_queue.max_file_bytes,
                preset='6', includes=['generating', 'queued', 'compressing']))
            futures = [executor.submit(collect_member, m) for m in population['workloads']]
            for future in as_completed(futures):
                record(future.result())
    else:
        for member in population['workloads']:
            record(collect_member(member))
    if any(r['status'] != 'ok' for r in reports):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('frozen', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=8,
                        help='1--8 concurrent tasksets for prepare, simulators for run')
    parser.add_argument('--prepare-workers', type=int,
                        help='Override prepare concurrency only (1--16); keeps simulator protocol unchanged')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    collect(args.frozen.resolve(), args.output.resolve(), phase=args.phase,
            workers=args.workers, timeout=args.timeout, prepare_workers=args.prepare_workers)


if __name__ == '__main__':
    main()
