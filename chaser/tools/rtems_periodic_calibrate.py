"""Plan, prepare and measure validation mappings, then freeze measured policies."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
from dataclasses import asdict
from itertools import islice
import json
from pathlib import Path
from statistics import median
import shutil
import time

from chaser.event_compression import EventCompressionQueue
from chaser.periodic import digest
from chaser.periodic_analysis import analyze
from chaser.periodic_build import prepare
from chaser.periodic_calibration import (CORES, KINDS, ROOT, check_mapping_snapshot,
    make_calibration_plan, mapping_id, read_json)
from chaser.periodic_dataset import load_batch
from chaser.threshold import calibrate
from tools.rtems_periodic import run
from tools.rtems_smoke import check_inputs, file_hash, write_json


def measured_tat(snapshot: Path, directory: Path, timeout: float, simulator_hash: str) -> float:
    """Accept exactly ten normal successful P runs, revalidated from raw logs."""
    protocol = read_json(directory / 'protocol.json')
    expected = dict(runs=10, timeout_seconds=timeout, mode=0, trace=False, empty=False,
                    simulator_hash=simulator_hash)
    if any(protocol.get(k) != v for k, v in expected.items()):
        raise ValueError('Calibration batch protocol differs')
    rows = load_batch(snapshot, directory)
    if (len(rows) != 10 or {r['run_id'] for r in rows} != {str(i) for i in range(10)}
            or any(r['execution_status'] != 'ok' or r['architecture'] != 2
                   or r['mode'] or r['trace'] or r['empty'] for r in rows)):
        raise ValueError('Calibration requires ten successful normal P runs')
    return median(r['tat_ns'] for r in rows)


def collect(frozen: Path, characterized: Path, output: Path, *, phase: str,
            workers: int = 16, prepare_workers: int = 8, timeout: float = 1800) -> dict:
    """Preserve failed/partial evidence; freeze only after every planned batch passes.

    A single SIGINT drains admitted work. Any failed batch prevents new admissions
    after it is observed; already admitted work drains. Resume revalidates complete
    evidence and never overwrites partial snapshots or failed measurements.
    """
    if phase not in ('plan', 'prepare', 'run', 'freeze'):
        raise ValueError('Unknown calibration phase')
    plan, cases, rows = make_calibration_plan(frozen, characterized, workers=workers,
                                            prepare_workers=prepare_workers, timeout=timeout)
    plan = json.loads(json.dumps(plan))
    output = output.resolve()
    if output.exists():
        if read_json(output / 'plan.json') != plan:
            raise ValueError('Calibration plan or implementation changed')
        check_inputs(output / 'implementation', dict(files=plan['implementation_hashes']))
    else:
        if phase != 'plan':
            raise ValueError('Create the calibration plan first')
        output.mkdir(parents=True)
        write_json(output / 'plan.json', plan)
        for relative in plan['implementation_hashes']:
            destination = output / 'implementation' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
    if phase == 'plan':
        summary = dict(validation_workloads=len(rows), planned_batches=plan['planned_batches'],
                       planned_runs=plan['planned_runs'], representations={kind: dict(
                           candidates=len(p['candidates']), mappings=len(p['mappings']),
                           common_workloads=len(p['common_workloads']))
                           for kind, p in plan['representations'].items()})
        print(json.dumps(summary, indent=2), flush=True)
        return summary

    def snapshot_for(identity):
        return output / 'prepared' / identity

    def check_snapshot(identity):
        entry = plan['mappings'][identity]
        check_mapping_snapshot(snapshot_for(identity), entry, plan['inputs'][entry['workload_id']])

    if phase == 'freeze':
        # Recheck every batch before publishing any representation's policy.
        tats, evidence = {}, {}
        for identity in plan['mappings']:
            check_snapshot(identity)
            directory = output / 'runs' / identity
            tats[identity] = measured_tat(snapshot_for(identity), directory, timeout,
                                          plan['tool_identity']['simulator_hash'])
            evidence[identity] = dict(
                snapshot_manifest_hash=file_hash(snapshot_for(identity) / 'manifest.json'),
                analysis_manifest_hash=file_hash(snapshot_for(identity) / 'analysis/manifest.json'),
                batch_protocol_hash=file_hash(directory / 'protocol.json'),
                measurements_hash=file_hash(directory / 'measurements.jsonl'))
        results, policies = {}, {}
        for kind in KINDS:
            result = calibrate(cases, rows, CORES, kind=kind,
                alpha=0.5 if kind == 'cls' else None,
                tat=lambda name, mapping: tats[mapping_id(name, mapping)],
                seed=plan['seed'], analyzer_version=digest({name: row['analysis_manifest_hash']
                    for name, row in plan['inputs'].items()}),
                feature_version=plan['implementation_hashes']['chaser/features.py'],
                measurement_source='measured')
            results[kind] = asdict(result)
            policy = dict(kind=kind, alpha=result.alpha, threshold=result.threshold,
                          cores=asdict(CORES), core_capacity=1,
                          allocator_hash=plan['implementation_hashes']['chaser/allocator.py'],
                          c_transform='core-0-to-C0;cores-1-2-3-to-C1',
                          calibration_plan_hash=file_hash(output / 'plan.json'),
                          calibration_result_hash=digest(asdict(result)),
                          measurement_evidence_hash=digest(evidence),
                          frozen_split_hash=plan['frozen_split_hash'])
            policies[kind] = dict(policy, policy_id='calibrated-' + digest(policy))
        frozen_result = dict(dataset_stage='theta_policy_frozen', results=results,
                             policies=policies, evidence=evidence,
                             scope='validation calibration; final G/C/P labels pending')
        path = output / 'frozen-policies.json'
        normalized = json.loads(json.dumps(frozen_result))
        if path.exists():
            if read_json(path) != normalized:
                raise ValueError('Frozen calibration result changed')
        else:
            write_json(path, frozen_result)
        return frozen_result

    reports = []
    total = len(plan['mappings'])

    def progress():
        successful = sum(r['status'] == 'ok' for r in reports)
        stage = ('failed' if any(r['status'] == 'failed' for r in reports) else
                 'complete' if len(reports) == total else 'in_progress')
        write_json(output / (phase + '-progress.json'), dict(
            phase=phase, status=stage, planned_batches=total, processed_batches=len(reports),
            successful_batches=successful, batches=reports))

    def process(identity, queue):
        entry = plan['mappings'][identity]
        snapshot = snapshot_for(identity)
        report = dict(mapping_id=identity, workload_id=entry['workload_id'], status='failed')
        started = time.monotonic()
        try:
            if phase == 'prepare':
                if not snapshot.exists():
                    prepare(entry['configuration'], snapshot)
                if not (snapshot / 'analysis').exists():
                    analyze(snapshot, compress_events=True, compression_queue=queue)
                check_snapshot(identity)
            else:
                check_snapshot(identity)
                directory = output / 'runs' / identity
                if not directory.exists():
                    run(snapshot, directory, architecture=2, runs=10, timeout=timeout)
                report['median_tat_ns'] = measured_tat(snapshot, directory, timeout,
                                                       plan['tool_identity']['simulator_hash'])
            report['status'] = 'ok'
        except Exception as error:
            report['error'] = f'{type(error).__name__}: {error}'
        report['wall_seconds'] = time.monotonic() - started
        return report

    # Compression has its own bounded raw-file reservation and worker pool.
    context = EventCompressionQueue() if phase == 'prepare' else nullcontext(None)
    limit = prepare_workers if phase == 'prepare' else workers
    jobs = iter(plan['mappings'])
    progress()
    with context as queue, ThreadPoolExecutor(max_workers=limit) as executor:
        pending = {executor.submit(process, identity, queue) for identity in islice(jobs, limit)}
        failed = False
        while pending:
            completed, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                report = future.result()
                reports.append(report)
                failed |= report['status'] != 'ok'
                progress()
                print(f'{phase} {report["workload_id"]}/{report["mapping_id"][:12]}: '
                      f'{report["status"]} ({report["wall_seconds"]:.1f}s)'
                      + (f' {report["error"]}' if 'error' in report else ''), flush=True)
            if not failed:
                pending.update(executor.submit(process, identity, queue)
                               for identity in islice(jobs, len(completed)))
    if failed:
        raise SystemExit(1)
    return read_json(output / (phase + '-progress.json'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('plan', 'prepare', 'run', 'freeze'))
    parser.add_argument('frozen', type=Path)
    parser.add_argument('--characterized', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--prepare-workers', type=int, default=8)
    parser.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args()
    collect(args.frozen, args.characterized, args.output, phase=args.phase,
            workers=args.workers, prepare_workers=args.prepare_workers, timeout=args.timeout)


if __name__ == '__main__':
    main()
