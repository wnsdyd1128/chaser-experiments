"""Replay extracted feasibility evidence with the matching implementation/SDK."""

import argparse
import json
from pathlib import Path

from chaser.periodic_dataset import load_batch
from tools.rtems_periodic_probe_report import check_raw_status, statistics, summarize
from tools.rtems_smoke import check_inputs, file_hash


def supplementary(root: Path) -> dict:
    """Include environment failures and subsequent job-budget probes separately."""
    main, extra = root / 'main', root / 'supplementary'
    groups = {}
    specifications = []
    for stage in ('smoke', 'boundary'):
        for path in sorted((extra / 'display-unavailable/runs' / stage).glob('*/*/measurements.jsonl')):
            specifications.append(('display-unavailable', main / 'snapshots' / path.parts[-3], path.parent))
    for name in ('remote-display', 'local-sandbox', 'local-accepted'):
        specifications.append(('display-checks', main / 'snapshots/layout-packed', extra / 'checks' / name))
    budget = extra / 'job-budget'
    suite = json.loads((budget / 'suite.json').read_text())
    for config in suite['boundaries']:
        name = config['workload_id']
        snapshot = budget / 'snapshots' / name
        check_inputs(snapshot, json.loads((snapshot / 'manifest.json').read_text()))
        if json.loads((snapshot / 'configuration.json').read_text()) != config:
            raise ValueError('Supplementary configuration mismatch')
        for architecture in ('g', 'c', 'p'):
            specifications.append((name, snapshot, budget / 'runs/boundary' / name / architecture))
    for group, snapshot, directory in specifications:
        rows = load_batch(snapshot, directory)
        report = groups.setdefault(group, dict(attempted=0, successful=0, successful_jobs=0,
                                               attempts=[], wall_seconds=[]))
        for row in rows:
            plan = json.loads((snapshot / ('g', 'c', 'p')[row['architecture']] / 'plan.json').read_text())
            check_raw_status(row, plan, (directory / row['log']).read_text(errors='replace'))
            report['attempted'] += 1
            ok = row['execution_status'] == 'ok'
            report['successful'] += int(ok)
            report['successful_jobs'] += len(row['jobs']) if ok else 0
            report['wall_seconds'].append(row['wall_seconds'])
            report['attempts'].append(dict(path=str(directory.relative_to(extra)), run_id=row['run_id'],
                status=row['execution_status'], log_hash=row['log_hash'], errors=row.get('errors'),
                error=row.get('error'), returncode=row['returncode']))
    for report in groups.values():
        report['wall_seconds'] = statistics(report['wall_seconds'])
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path)
    parser.add_argument('--artifact', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.artifact / 'manifest.json').read_text())
    check_inputs(args.artifact, manifest)
    actual = summarize(args.extracted / 'main')
    if actual != json.loads((args.artifact / 'summary.json').read_text()):
        raise ValueError('Replayed primary summary differs')
    extra = supplementary(args.extracted)
    if extra != json.loads((args.artifact / 'supplementary.json').read_text()):
        raise ValueError('Replayed supplementary evidence differs')
    result = dict(status='PASS', primary_runs=actual['attempted_runs'],
                  primary_successful=actual['successful_runs'], primary_successful_jobs=actual['successful_jobs'],
                  supplementary_runs=sum(g['attempted'] for g in extra.values()),
                  supplementary_successful=sum(g['successful'] for g in extra.values()),
                  supplementary_successful_jobs=sum(g['successful_jobs'] for g in extra.values()),
                  checked_artifact_files=len(manifest['files']),
                  reporter_hash=file_hash(Path(__file__).resolve()))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
