"""Run the CLS-distribution design: prepare + yarda_cpp CLS, U gate, pilot, full.

Per task set: zigzag/ and grouped/ builds share task order, arrays, and
workload source and differ only in cores. G runs once (zigzag build, it ignores
cores); C, C2, and P run under both placements. Run with PYTHONPATH set to the
4d03b93 + C2 code copy.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from statistics import mean, pstdev
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.analysis import analyze
from chaser.periodic.build import prepare
from chaser.periodic.dataset import characterize, load_batch
from tools.rtems_smoke import file_hash, write_json

import clsset
import run as design
import stats

SNAPSHOT = ('clsset.py', 'calibrate.py', 'cls_run.py', 'test_clsset.py')
RUNS = (('zigzag', 'g', 'g'), ('zigzag', 'c', 'c'), ('zigzag', 'c2', 'c2'), ('zigzag', 'p', 'p'),
        ('grouped', 'c', 'c_grp'), ('grouped', 'c2', 'c2_grp'), ('grouped', 'p', 'p_grp'))
PAIRS = (('g', 'p'), ('c', 'p'), ('c2', 'p'), ('g', 'c'), ('g', 'c2'),
         ('g', 'p_grp'), ('c_grp', 'p_grp'), ('c2_grp', 'p_grp'),
         ('p_grp', 'p'), ('c_grp', 'c'), ('c2_grp', 'c2'))
U_TOLERANCE = 0.05


def cases():
    return [(period, m, cv, k) for period in clsset.PERIODS for m in clsset.MEANS
            for cv in clsset.CVS for k in clsset.set_ids(cv)]


def label(case):
    period, m, cv, k = case
    return f'p{period:03d}/m{round(m * 100):02d}/cv{round(cv * 100):02d}/s{k:02d}'


def case_dir(output, case):
    return output / label(case)


def tables(output):
    calibration = json.loads((output / 'calibration/calibration.json').read_text())
    return {int(p): rows for p, rows in calibration['tables'].items()}


def prepare_one(output, case, levels):
    target = case_dir(output, case)
    for placement in clsset.PLACEMENTS:
        directory = target / placement
        directory.mkdir(parents=True)
        config = clsset.configuration(*case, levels, placement)
        write_json(directory / 'configuration.json', config)
        prepare(config, directory / 'prepared')
    for name in ('source/workload.c', 'layout.json'):
        if ((target / 'zigzag/prepared' / name).read_bytes()
                != (target / 'grouped/prepared' / name).read_bytes()):
            raise ValueError(f'{label(case)}: placements differ in {name}')
    report = analyze(target / 'zigzag/prepared', compress_events=True)
    config = json.loads((target / 'zigzag/configuration.json').read_text())
    realized = [report['cases'][t['task_id']]['cls'][clsset.ALPHA] for t in config['tasks']]
    write_json(target / 'cls.json', dict(
        realized=realized, calibrated=[t['cls_calibrated'] for t in config['tasks']],
        targets=[t['cls_target'] for t in config['tasks']], mean=mean(realized),
        cv=pstdev(realized) / mean(realized), clp=[report['cases'][t['task_id']]['clp'] for t in config['tasks']]))
    return {p: file_hash(target / p / 'prepared/manifest.json') for p in clsset.PLACEMENTS}


def prepare_all(output, workers):
    levels = tables(output)
    for name in SNAPSHOT:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    manifests = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case, levels): case for case in cases()}
        for future in as_completed(futures):
            manifests[label(futures[future])] = future.result()
            design.announce(f'prepared {label(futures[future])}')
    write_json(output / 'protocol.json', dict(
        periods=clsset.PERIODS, means=clsset.MEANS, cvs=clsset.CVS, sets=clsset.SETS,
        tasks=clsset.TASKS, task_u=clsset.TASK_U, alpha=clsset.ALPHA, placements=clsset.PLACEMENTS,
        calibration_hash=file_hash(output / 'calibration/calibration.json'),
        prepared_manifest_hashes=dict(sorted(manifests.items())),
        snapshot_hashes={name: file_hash(output / name) for name in SNAPSHOT}))
    design.announce(f'prepared {len(manifests)} task sets')


def check_protocol(output):
    protocol = json.loads((output / 'protocol.json').read_text())
    for name, expected in protocol['snapshot_hashes'].items():
        if file_hash(output / name) != expected:
            raise ValueError(f'Snapshot changed: {name}')
    for case in cases():
        for placement, expected in protocol['prepared_manifest_hashes'][label(case)].items():
            if file_hash(case_dir(output, case) / placement / 'prepared/manifest.json') != expected:
                raise ValueError(f'Prepared manifest changed: {label(case)}/{placement}')


def u_check(output, workers):
    selected = [(p, m, max(clsset.CVS), 0) for p in clsset.PERIODS for m in clsset.MEANS]
    specs = []
    for case in selected:
        prepared = case_dir(output, case) / 'zigzag/prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        specs += [(f'{label(case)}/isolated/{t["task_id"]}', prepared,
                   case_dir(output, case) / 'isolated' / t['task_id'], 'p', i + 1)
                  for i, t in enumerate(plan['tasks'])]
    failed, infra = design.run_specs(specs, workers)
    if failed or infra:
        raise RuntimeError(f'Isolated U runs failed: {failed}, infrastructure={infra}')
    report, worst = {}, 0.0
    for case in selected:
        prepared = case_dir(output, case) / 'zigzag/prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        batches = [load_batch(prepared, case_dir(output, case) / 'isolated' / t['task_id'])
                   for t in plan['tasks']]
        u = characterize(plan, batches)['utilization']
        errors = {k: v / clsset.TASK_U - 1 for k, v in u.items()}
        worst = max(worst, *(abs(e) for e in errors.values()))
        report[label(case)] = dict(utilization=u, relative_error=errors)
        design.announce(f'{label(case)} isolated U error range '
                        f'{min(errors.values()):+.2%}..{max(errors.values()):+.2%}')
    write_json(output / 'isolated-u.json', report)
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    design.announce(f'isolated U gate passed: worst relative error {worst:.2%}')


def specs_for(output, selected):
    return [(f'{label(c)}/{key}', case_dir(output, c) / placement / 'prepared',
             case_dir(output, c) / placement / arch, arch, 0)
            for c in selected for placement, arch, key in RUNS]


def summarize(output):
    rows = []
    for case in cases():
        target = case_dir(output, case)
        if not all((target / placement / arch / 'measurements.jsonl').exists()
                   for placement, arch, _ in RUNS):
            continue
        cls = json.loads((target / 'cls.json').read_text())
        row = dict(period=case[0], mean=case[1], cv=case[2], set_id=case[3],
                   cls_mean=cls['mean'], cls_cv=cls['cv'], cls_realized=cls['realized'])
        for placement, arch, key in RUNS:
            config = json.loads((target / placement / 'configuration.json').read_text())
            result = load_batch(target / placement / 'prepared', target / placement / arch)[0]
            ok = result['execution_status'] == 'ok'
            row[key] = dict(status=result['execution_status'], errors=result.get('errors', []),
                tet_ns=result['tet_ns'] if ok else None, tat_ns=result['tat_ns'] if ok else None,
                response_sum_ns=result.get('response_sum_ns') if ok else None,
                measured_jobs=result.get('measured_jobs'), cohorts=len(result.get('cohorts', [])),
                start_core_changes=design._start_core_changes(result, config) if ok else None)
        write_json(target / 'summary.json', row)
        rows.append(row)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    design.announce(f'summarized {len(rows)} task sets')


def report(output):
    stats.PAIRS = PAIRS
    rows = stats.load(output / 'results.jsonl')
    for period in clsset.PERIODS:
        subset = [r for r in rows if r['period'] == period]
        cells = stats.cell_tests(subset)
        result = dict(period=period, alpha=stats.ALPHA, task_sets=len(subset), pairs=PAIRS,
                      cells=cells, factors=stats.factor_tests(subset))
        (output / f'stats-p{period:03d}.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        (output / f'stats-p{period:03d}.md').write_text(stats.markdown(cells))
    design.announce('wrote per-period statistics')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'u-check', 'pilot', 'full', 'summarize', 'stats'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == 'prepare':
        prepare_all(output, min(args.workers, 32))
        return
    if args.stage == 'stats':
        report(output)
        return
    check_protocol(output)
    if args.stage == 'u-check':
        u_check(output, args.workers)
    elif args.stage == 'pilot':
        failed, _ = design.run_specs(specs_for(output, [c for c in cases() if c[3] == 0]), args.workers)
        summarize(output)
        if failed:
            raise RuntimeError(f'Pilot runs failed: {failed}')
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[3] != 0), key=lambda c: (c[3], c[0], c[1], c[2]))
        failed, _ = design.run_specs(specs_for(output, remaining), args.workers)
        summarize(output)
        if failed:
            design.announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(output)


if __name__ == '__main__':
    main()
