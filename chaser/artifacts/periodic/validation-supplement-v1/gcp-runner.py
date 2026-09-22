"""Validate the fixed supplement, collect normal G/C/P, and audit all raw runs."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

ROOT = Path('/workspace/experiments/chaser')
sys.path.insert(0, str(ROOT / 'artifacts/periodic/validation-supplement-v1'))
from supplement_inputs import verify_inputs
from chaser.periodic import digest, parse_log
from chaser.periodic_dataset import load_batch, characterize
from tools.rtems_periodic_characterize import checked_locality
from tools.rtems_periodic_gcp import collect
from tools.rtems_smoke import file_hash, write_json

OUT = ROOT / '.cache/validation-supplement-v1-gcp'
U = ROOT / '.cache/validation-supplement-v1-characterization'


def main():
    extension = verify_inputs(ROOT / '.cache/validation-supplement-v1-inputs')
    generation = json.loads((ROOT / 'artifacts/periodic/validation-supplement-v1/generation-manifest.json').read_text())
    expected = {r['workload_id']: r for r in generation['planned_inputs']}
    preparation = {r['workload_id']: r for r in json.loads((U / 'summary.json').read_text())['prepare']}
    snapshots = []
    preserved = {}
    for member in extension['workloads']:
        name = member['workload_id']
        snapshot = U / 'prepared' / name
        assert digest(json.loads((snapshot / 'configuration.json').read_text())) == member['configuration_hash']
        checked_locality(snapshot)
        for filename, key in [('manifest.json', 'execution_manifest_hash'), ('analysis/manifest.json', 'analysis_manifest_hash')]:
            assert file_hash(snapshot / filename) == preparation[name][key]
        for a, letter in enumerate(('g','c','p')):
            plan = json.loads((snapshot / letter / 'plan.json').read_text())
            assert plan['plan_hash'] == expected[name]['plan_hashes'][str(a)]
        batches = [load_batch(snapshot, U / 'runs' / name / f'u{i}') for i in range(10)]
        recalculated = characterize(json.loads((snapshot / 'p/plan.json').read_text()), batches)
        assert recalculated == json.loads((U / 'runs' / name / 'utilization.json').read_text())
        for path in (U / 'runs' / name).rglob('*'):
            if path.is_file():
                preserved[str(path)] = file_hash(path)
        snapshots.append(snapshot)
    preflight = dict(status='pass', workloads=4, verified_elf_plans=12,
                     independent_u_raw_runs_revalidated=400, policy_id=generation['initial_policy_id'],
                     scope='fixed initial mapping validation, not theta calibration or labels',
                     preserved_u_files=preserved)
    write_json(OUT / 'preflight.json', preflight)
    print('Preflight PASS: 12 exact ELF plans, linked analyses, 400 independent U raw runs.', flush=True)
    code = 0
    try:
        collect(snapshots, OUT / 'collection', workers=16, timeout=1800)
    except SystemExit as error:
        code = int(error.code or 0)
    results = []
    for snapshot in snapshots:
        for a, letter in enumerate(('g','c','p')):
            plan = json.loads((snapshot / letter / 'plan.json').read_text())
            directory = OUT / 'collection/runs' / snapshot.name / letter
            rows = load_batch(snapshot, directory)
            errors = Counter()
            for row in rows:
                parsed = parse_log((directory / row['log']).read_text(errors='replace'), plan)
                errors.update(parsed['errors'])
                if row['execution_status'] == 'ok':
                    assert parsed['execution_status'] == 'ok' and row['returncode'] == 0
            results.append(dict(workload_id=snapshot.name, architecture=letter, runs=len(rows),
                                successful_runs=sum(r['execution_status']=='ok' for r in rows),
                                raw_error_counts=dict(errors)))
    for path, expected_hash in preserved.items():
        assert file_hash(Path(path)) == expected_hash, path
    by_architecture = {a: dict(total_runs=sum(r['runs'] for r in results if r['architecture']==a),
        successful_runs=sum(r['successful_runs'] for r in results if r['architecture']==a)) for a in ('g','c','p')}
    success = sum(r['successful_runs'] for r in results)
    passed = code == 0 and success == 120 and sum(r['runs'] for r in results) == 120
    write_json(OUT / 'summary.json', dict(status='pass' if passed else 'failed',
        completed_utc=datetime.now(timezone.utc).isoformat(), total_runs=sum(r['runs'] for r in results),
        successful_runs=success, batches=results, by_architecture=by_architecture,
        raw_evidence_revalidated=True, historical_u_unchanged=True,
        theta_policy_frozen=False, scope=preflight['scope']))
    print(f'Raw audit complete: {success}/120 successful; historical U unchanged.', flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    code = 1
    try:
        code = main()
    except Exception:
        traceback.print_exc()
    finally:
        with (OUT / 'exit.json').open('x') as stream:
            json.dump(dict(exit_code=code, completed_utc=datetime.now(timezone.utc).isoformat()), stream)
    raise SystemExit(code)
