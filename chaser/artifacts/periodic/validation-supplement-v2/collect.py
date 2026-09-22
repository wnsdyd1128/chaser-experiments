"""Run the fixed V2 input through ELF, independent U, then normal G/C/P gates."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

from rebuild import HERE, ROOT, artifacts
from chaser.periodic import parse_log
from chaser.periodic_build import prepare
from chaser.periodic_analysis import analyze
from chaser.event_compression import EventCompressionQueue
from chaser.periodic_dataset import load_batch, characterize
from tools.rtems_periodic import run
from tools.rtems_periodic_gcp import collect as collect_gcp
from tools.rtems_periodic_characterize import checked_locality, feature_record
from tools.rtems_smoke import check_inputs, file_hash, write_json


def execute(output):
    expected = artifacts()
    for name, data in expected.items():
        if json.loads((HERE / name).read_text()) != data:
            raise ValueError(f'Frozen input drift: {name}')
    config = expected['configuration.json']
    member = next(r for r in expected['active-population.json']['workloads']
                  if r['workload_id'] == config['workload_id'])
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in
              [*HERE.glob('*.py'), *[HERE / n for n in expected],
               * (ROOT / 'chaser').glob('*.py'),
               ROOT / 'tools/rtems_periodic.py', ROOT / 'tools/rtems_periodic_gcp.py',
               ROOT / 'tools/rtems_periodic_characterize.py', ROOT / 'tools/rtems_smoke.py',
               ROOT / 'rtems/periodic/init.c', ROOT / 'rtems/periodic/probe.c']}
    write_json(output / 'source-hashes.json', dict(files=hashes))
    def stage(name, **fields):
        check_inputs(ROOT, dict(files=hashes))
        write_json(output / 'progress.json', dict(phase=name, updated_utc=datetime.now(timezone.utc).isoformat(), **fields))
        print(name, fields, flush=True)
    stage('prepare')
    snapshot = output / 'prepared' / config['workload_id']
    prepare(config, snapshot)
    with EventCompressionQueue() as queue:
        analyze(snapshot, compress_events=True, compression_queue=queue)
    locality = checked_locality(snapshot)
    plan = json.loads((snapshot / 'p/plan.json').read_text())
    stage('independent_u', elfs_verified=3, planned_runs=100)
    def batch(i):
        directory = output / 'u' / f'u{i}'
        run(snapshot, directory, architecture=2, mode=i+1, runs=10, timeout=600)
        rows = load_batch(snapshot, directory)
        print(f'U task {i}: {sum(r["execution_status"]=="ok" for r in rows)}/10', flush=True)
        return rows
    with ThreadPoolExecutor(max_workers=16) as executor:
        batches = list(executor.map(batch, range(10)))
    utilization = characterize(plan, batches)
    write_json(output / 'utilization.json', utilization)
    features = feature_record(member, locality, utilization)
    write_json(output / 'features.json', features)
    if not features['within_u_bounds'] or features['undefined_features']:
        raise ValueError('U bounds or feature gate failed; G/C/P not admitted')
    stage('gcp', independent_u_successful_runs=100, planned_gcp_runs=30)
    code = 0
    try:
        collect_gcp([snapshot], output / 'gcp', workers=16, timeout=1800)
    except SystemExit as error:
        code = int(error.code or 0)
    results = []
    for a in ('g','c','p'):
        directory = output / 'gcp/runs' / config['workload_id'] / a
        rows = load_batch(snapshot, directory)
        arch_plan = json.loads((snapshot / a / 'plan.json').read_text())
        parsed = [parse_log((directory / r['log']).read_text(errors='replace'), arch_plan) for r in rows]
        results.append(dict(architecture=a, runs=len(rows), successful_runs=sum(r['execution_status']=='ok' for r in rows),
                            raw_errors=[r['errors'] for r in parsed if r['errors']]))
    # Recompute independent U after G/C/P; the original ELF and raw hashes must still agree.
    reloaded = [load_batch(snapshot, output / 'u' / f'u{i}') for i in range(10)]
    if characterize(plan, reloaded) != utilization:
        raise ValueError('U evidence changed during G/C/P')
    checked_locality(snapshot)
    passed = code == 0 and all(r['runs']==r['successful_runs']==10 and not r['raw_errors'] for r in results)
    stage('complete' if passed else 'gcp_failed')
    write_json(output / 'summary.json', dict(status='pass' if passed else 'failed',
        independent_u_successful_runs=100, by_architecture=results, raw_revalidated=True,
        u_evidence_unchanged=True, within_u_bounds=True, undefined_features={},
        theta_policy_frozen=False, completed_utc=datetime.now(timezone.utc).isoformat()))
    return 0 if passed else 1


if __name__ == '__main__':
    output = Path(sys.argv[1]).resolve()
    # Launcher owns directory creation; this marker rejects duplicate collector starts.
    with (output / 'started').open('x') as stream:
        stream.write(datetime.now(timezone.utc).isoformat())
    code = 1
    try:
        code = execute(output)
    except Exception:
        traceback.print_exc()
        write_json(output / 'failure.json', dict(status='failed', detail=traceback.format_exc()))
    finally:
        with (output / 'exit.json').open('x') as stream:
            json.dump(dict(exit_code=code, completed_utc=datetime.now(timezone.utc).isoformat()), stream)
    raise SystemExit(code)
