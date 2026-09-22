"""Prepare the preregistered supplement and collect 400 independent U runs once."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import traceback

from chaser.event_compression import EventCompressionQueue
from chaser.periodic_analysis import analyze
from chaser.periodic_build import prepare
from chaser.periodic_dataset import characterize, load_batch
from tools.rtems_periodic import run
from tools.rtems_periodic_characterize import checked_locality, feature_record
from tools.rtems_smoke import check_inputs, file_hash, write_json
from supplement_inputs import HERE, ROOT, materialize, verify_inputs


def prepare_member(inputs, output, member, queue):
    """Validate every final ELF and its complete linked stream before U starts."""
    name = member['workload_id']
    config = json.loads((inputs / 'configs' / (name + '.json')).read_text())
    snapshot = output / 'prepared' / name
    prepare(config, snapshot)
    analyze(snapshot, compress_events=True, compression_queue=queue)
    checked_locality(snapshot)
    return dict(workload_id=name, status='ok', execution_manifest_hash=file_hash(snapshot / 'manifest.json'),
                analysis_manifest_hash=file_hash(snapshot / 'analysis/manifest.json'))


def run_batch(output, name, index):
    """Retain ten attempts and reparse their raw logs, including failed attempts."""
    snapshot = output / 'prepared' / name
    directory = output / 'runs' / name / f'u{index}'
    run(snapshot, directory, architecture=2, mode=index + 1, runs=10, timeout=600)
    rows = load_batch(snapshot, directory)
    successful = sum(r['execution_status'] == 'ok' for r in rows)
    return dict(workload_id=name, task_index=index, runs=len(rows), successful_runs=successful,
                status='ok' if successful == 10 else 'failed', raw_revalidated=True)


def collect(inputs: Path, output: Path):
    """Run once; a preparation failure blocks U, and no failed batch is retried."""
    report = verify_inputs(inputs)
    output.mkdir(parents=True, exist_ok=True)
    protocol = dict(input_manifest_hash=file_hash(inputs / 'manifest.json'),
        extension_hash=file_hash(inputs / 'extension.json'), expected_runs=10,
        prepare_workers=4, simulator_workers=16, timeout_seconds=600,
        scope='independent-U-only; no normal G/C/P timing, calibration or labels')
    # Exclusive creation prevents a second invocation from replacing evidence.
    with (output / 'protocol.json').open('x') as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
    sources = [*sorted((ROOT / 'chaser').glob('*.py')),
               *[ROOT / 'tools' / name for name in ('rtems_periodic.py', 'rtems_smoke.py',
                                                  'rtems_periodic_characterize.py')],
               *[HERE / name for name in ('collect_supplement.py', 'supplement_inputs.py', 'revalidate.py')],
               *[ROOT / 'rtems/periodic' / name for name in ('init.c', 'probe.c', 'probe.h', 'wscript')]]
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in sources}
    for relative in hashes:
        destination = output / 'implementation' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    write_json(output / 'implementation.json', dict(files=hashes))
    progress = dict(phase='prepare', planned_workloads=4, planned_batches=40,
                    planned_runs=400, prepare=[], batches=[], features=[])

    def save():
        progress['updated_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(output / 'progress.tmp', progress)
        (output / 'progress.tmp').replace(output / 'progress.json')

    def record(future, identity, key):
        try:
            row = future.result()
        except Exception as error:
            row = dict(identity, status='failed', error=f'{type(error).__name__}: {error}')
        progress[key].append(row)
        save()
        print(json.dumps(row, sort_keys=True), flush=True)

    save()
    print('Preparing 4 tasksets / 12 ELFs; U admission requires all analyses to pass.', flush=True)
    with EventCompressionQueue() as queue, ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(prepare_member, inputs, output, m, queue):
                   dict(workload_id=m['workload_id']) for m in report['workloads']}
        for future in as_completed(futures):
            record(future, futures[future], 'prepare')
    if any(r['status'] != 'ok' for r in progress['prepare']):
        progress['phase'] = 'prepare_failed'
        save()
        write_json(output / 'summary.json', progress)
        return 1
    verify_inputs(inputs)
    check_inputs(ROOT, dict(files=hashes))
    progress['phase'] = 'independent_u'
    save()
    print('All 12 ELFs/analyses verified. Starting 400 U runs, 16 workers, timeout 600s.', flush=True)
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(run_batch, output, m['workload_id'], i):
                   dict(workload_id=m['workload_id'], task_index=i)
                   for m in report['workloads'] for i in range(10)}
        for future in as_completed(futures):
            record(future, futures[future], 'batches')
    check_inputs(ROOT, dict(files=hashes))
    check_inputs(output / 'implementation', dict(files=hashes))
    verify_inputs(inputs)
    for member in report['workloads']:
        name = member['workload_id']
        snapshot = output / 'prepared' / name
        try:
            batches = [load_batch(snapshot, output / 'runs' / name / f'u{i}') for i in range(10)]
            plan = json.loads((snapshot / 'p/plan.json').read_text())
            utilization = characterize(plan, batches)
            record_data = feature_record(member, checked_locality(snapshot), utilization)
            record_data.update(analysis_manifest_hash=file_hash(snapshot / 'analysis/manifest.json'),
                execution_manifest_hash=file_hash(snapshot / 'manifest.json'), implementation_hashes=hashes)
            write_json(output / 'runs' / name / 'utilization.json', utilization)
            write_json(output / 'runs' / name / 'features.json', record_data)
            progress['features'].append(dict(workload_id=name, status='ok',
                within_u_bounds=record_data['within_u_bounds'],
                exclusion_reasons=record_data['exclusion_reasons'],
                undefined_features=record_data['undefined_features']))
        except Exception as error:
            progress['features'].append(dict(workload_id=name, status='failed', error=str(error)))
    ok = all(r['status'] == 'ok' for r in [*progress['batches'], *progress['features']])
    progress.update(phase='complete' if ok else 'measurement_failed',
        successful_runs=sum(r.get('successful_runs', 0) for r in progress['batches']),
        recorded_runs=sum(r.get('runs', 0) for r in progress['batches']),
        theta_policy_frozen=False, dataset_ready=False)
    save()
    write_json(output / 'summary.json', progress)
    return 0 if ok else 1


if __name__ == '__main__':
    inputs, output = (Path(p).resolve() for p in sys.argv[1:])
    code = 1
    try:
        code = collect(inputs, output)
    except Exception:
        traceback.print_exc()
    finally:
        with (output / 'exit.json').open('x') as stream:
            json.dump(dict(exit_code=code, completed_utc=datetime.now(timezone.utc).isoformat()), stream)
    raise SystemExit(code)
