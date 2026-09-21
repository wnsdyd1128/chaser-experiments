"""Revalidate frozen development probes and report coverage/cost without labels."""

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean, median

from chaser.periodic import parse_log
from chaser.periodic_dataset import characterize, load_batch
from chaser.periodic_patterns import job_access_count
from tools.rtems_smoke import check_inputs, file_hash


def statistics(values: list[float]) -> dict | None:
    """Describe observed costs without trimming measurements."""
    if not values:
        return None
    return dict(min=min(values), median=median(values), mean=mean(values), max=max(values))


def check_raw_status(row: dict, plan: dict, text: str) -> None:
    """Accept preserved parse failures only when the attempt was marked failed."""
    try:
        parsed = parse_log(text, plan, mode=row['mode'], trace=row['trace'], empty=row['empty'])
    except ValueError as error:
        if row['execution_status'] == 'ok':
            raise ValueError('Malformed raw output was marked successful') from error
        return
    ok = parsed['execution_status'] == 'ok' and row['returncode'] == 0
    if ok != (row['execution_status'] == 'ok'):
        raise ValueError('Stored status differs from raw execution')


def summarize(root: Path) -> dict:
    """Require every planned batch; check raw evidence and snapshot identities."""
    suite = json.loads((root / 'suite.json').read_text())
    populations = {stage: suite['probes'] for stage in ('smoke', 'repeat', 'diagnostic', 'empty')}
    populations['boundary'] = suite['boundaries']
    stages, batches = {}, {}
    for stage, configs in populations.items():
        directory = root / 'runs' / stage
        protocol = json.loads((directory / 'protocol.json').read_text())
        if (protocol['suite_hash'] != file_hash(root / 'suite.json')
                or protocol['workloads'] != [c['workload_id'] for c in configs]):
            raise ValueError('Stage population differs from the frozen suite')
        all_rows = []
        for config in configs:
            name = config['workload_id']
            snapshot = root / 'snapshots' / name
            if (json.loads((snapshot / 'configuration.json').read_text()) != config
                    or json.loads((root / 'configs' / (name + '.json')).read_text()) != config):
                raise ValueError('Snapshot/configuration differs from the frozen suite')
            expected = [('g', 0, 0), ('c', 1, 0), ('p', 2, 0)]
            if stage in ('smoke', 'repeat'):
                expected += [(f'u{i}', 2, i + 1) for i in range(len(config['tasks']))]
            elif stage == 'empty':
                expected = [('empty', 2, 1)]
            for batch, architecture, mode in expected:
                path = directory / name / batch
                rows = load_batch(snapshot, path)
                count = 10 if stage in ('repeat', 'empty') else 1
                if len(rows) != count:
                    raise ValueError('Wrong repetition count')
                plan = json.loads((snapshot / ('g', 'c', 'p')[architecture] / 'plan.json').read_text())
                for row in rows:
                    if (row['architecture'] != architecture or row['mode'] != mode
                            or row['trace'] != (stage == 'diagnostic')
                            or row['empty'] != (stage == 'empty')):
                        raise ValueError('Wrong measurement mode')
                    check_raw_status(row, plan, (path / row['log']).read_text(errors='replace'))
                batches[stage, name, batch] = rows
                all_rows.extend(rows)
        collection = json.loads((directory / 'collection.json').read_text())
        failures = [dict(workload_id=r['workload_id'], architecture=r['architecture'],
                         mode=r['mode'], run_id=r['run_id'], errors=r.get('errors'), error=r.get('error'),
                         log_hash=r['log_hash']) for r in all_rows if r['execution_status'] != 'ok']
        stages[stage] = dict(attempted=len(all_rows), successful=len(all_rows) - len(failures),
            jobs=sum(len(r.get('jobs', [])) for r in all_rows), failures=failures,
            successful_jobs=sum(len(r['jobs']) for r in all_rows if r['execution_status'] == 'ok'),
            attempt_wall_seconds=sum(r['wall_seconds'] for r in all_rows),
            run_wall_seconds=statistics([r['wall_seconds'] for r in all_rows]),
            collection_wall_seconds=collection['wall_seconds'], workers=protocol['workers'])
    workloads = []
    for config in suite['probes'] + suite['boundaries']:
        name = config['workload_id']
        snapshot, costs = root / 'snapshots' / name, root / 'costs' / name
        plan = json.loads((snapshot / 'p/plan.json').read_text())
        check_inputs(snapshot, json.loads((snapshot / 'manifest.json').read_text()))
        layout = json.loads((snapshot / 'layout.json').read_text())['p']
        task_coverage = []
        for task, entry in zip(plan['tasks'], layout, strict=True):
            lines = {(entry['address'] + i * task['stride']) // 32 for i in range(task['distinct'])}
            occupancy = {}
            for cache, sets in (('l1', 128), ('llc', 16384)):
                counts = Counter(line % sets for line in lines)
                occupancy[cache] = dict(occupied_sets=len(counts), max_lines_per_set=max(counts.values()))
            task_coverage.append(dict(task_id=task['task_id'], active_lines=len(lines),
                active_bytes=32 * len(lines), allocated_bytes=task['data_size'], occupancy=occupancy,
                loads_per_job=job_access_count(task), period_ticks=task['period_ticks'],
                job_count=task['job_count']))
        report = dict(workload_id=name, tasks=task_coverage,
            static_memory=json.loads((costs / 'static-memory.json').read_text()),
            build=json.loads((costs / 'prepare/resources.json').read_text()),
            snapshot_manifest_hash=file_hash(snapshot / 'manifest.json'))
        if config in suite['probes']:
            analysis = snapshot / 'analysis'
            check_inputs(analysis, json.loads((analysis / 'manifest.json').read_text()))
            locality = json.loads((analysis / 'locality.json').read_text())
            if locality['manifest_hash'] != report['snapshot_manifest_hash']:
                raise ValueError('Analysis/execution snapshot mismatch')
            report.update(locality=locality['cases'], analysis=json.loads((costs / 'analyze/resources.json').read_text()),
                          analysis_manifest_hash=file_hash(analysis / 'manifest.json'))
            independent = [batches['repeat', name, f'u{i}'] for i in range(len(plan['tasks']))]
            try:
                report['characterization'] = characterize(plan, independent)
            except ValueError as error:
                report['characterization_excluded_reason'] = str(error)
            empty = [j['cpu_after_ns'] - j['cpu_before_ns'] for r in batches['empty', name, 'empty']
                     if r['execution_status'] == 'ok' for j in r['jobs']]
            report['empty_job_cpu_ns'] = statistics(empty)
            if empty and 'characterization' in report:
                report['empty_to_target_cpu_ratio'] = mean(empty) / report['characterization']['tasks']['t0']['mean_cpu_ns']
            report['independent_cpu_ns'] = {task['task_id']: statistics([
                j['cpu_after_ns'] - j['cpu_before_ns'] for r in rows if r['execution_status'] == 'ok'
                for j in r['jobs']]) for task, rows in zip(plan['tasks'], independent, strict=True)}
        else:
            report['analysis_scope'] = 'build/runtime boundary only'
        workloads.append(report)
    storage = dict(logical_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
        event_bytes=sum(p.stat().st_size for p in root.glob('snapshots/*/analysis/*/*/events.json')),
        raw_log_bytes=sum(p.stat().st_size for p in root.glob('runs/*/*/*/*.log')))
    return dict(scope='development feasibility; no labels, RF, frozen policy, or training samples',
        eligible_for_training=False, test_eligible=False, suite_hash=file_hash(root / 'suite.json'),
        stages=stages, workloads=workloads, storage=storage,
        attempted_runs=sum(s['attempted'] for s in stages.values()),
        successful_runs=sum(s['successful'] for s in stages.values()),
        jobs=sum(s['jobs'] for s in stages.values()),
        successful_jobs=sum(s['successful_jobs'] for s in stages.values()),
        rss_scope=suite['rss_scope'], hardware_cache_validated=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.root.resolve())
    with args.output.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(f'{report["successful_runs"]}/{report["attempted_runs"]} runs; {report["jobs"]} jobs revalidated')


if __name__ == '__main__':
    main()
