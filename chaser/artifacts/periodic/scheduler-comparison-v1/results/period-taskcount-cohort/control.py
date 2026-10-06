"""Rerun P and C with cohort-aware placement on the main design's task sets.

Task order, arrays, periods, and sweeps come from the main run, so the
workload source and array layout stay byte-identical; only the core field
changes. G ignores that field, so the main G runs are the reference; the
g-check stage re-runs G on set 0 of every cell and requires identical TET/TAT.
Run with PYTHONPATH set to the code snapshot that the main run used.

Stages: prepare, g-check, run, summarize (needs the finished main run), stats.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import shutil

from chaser.periodic import measurement
from chaser.periodic.build import prepare
from chaser.periodic.dataset import load_batch
from tools.rtems_smoke import file_hash, write_json

import placement
import run as design
import stats
import taskset

SNAPSHOT = ('placement.py', 'control.py', 'test_placement.py')
POLICY = 'cohort-span-local-search-v1'
ARCHITECTURES = ('p', 'c', 'c2')
# ps/cs/c2s are the main run's snake-placement P/C/C2 on the same task set.
PAIRS = (('g', 'p'), ('c', 'p'), ('c2', 'p'), ('g', 'c'), ('g', 'c2'),
         ('ps', 'p'), ('cs', 'c'), ('c2s', 'c2'))


def cases():
    return [case for case in design.cases() if case[1] > 0]


def prepare_one(main, output, case):
    source = design.case_dir(main, case)
    config = json.loads((source / 'configuration.json').read_text())
    unit = taskset.unit(case[0])
    relative = [task['period_ticks'] // unit for task in config['tasks']]
    snake = [task['core'] for task in config['tasks']]
    cores = placement.cohort_cores(relative, taskset.GRID)
    control = copy.deepcopy(config)
    for task, core in zip(control['tasks'], cores):
        task['core'] = core
    control['workload_id'] = config['workload_id'].removesuffix('-v1') + '-cohort-v1'
    control['policy_id'] = POLICY
    control['placement'] = dict(
        snake_cores=snake, snake_cost=placement.cohort_cost(relative, snake, taskset.GRID),
        cohort_cost=placement.cohort_cost(relative, cores, taskset.GRID),
        restarts=placement.RESTARTS, seed=placement.SEED)
    target = design.case_dir(output, case)
    target.mkdir(parents=True)
    write_json(target / 'configuration.json', control)
    prepare(control, target / 'prepared')
    for name in ('source/workload.c', 'layout.json'):
        if (target / 'prepared' / name).read_bytes() != (source / 'prepared' / name).read_bytes():
            raise ValueError(f'{design.label(case)}: {name} differs from the main run')
    return file_hash(target / 'prepared/manifest.json')


def prepare_all(main, output, workers):
    output.mkdir(parents=True, exist_ok=False)
    for name in SNAPSHOT:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    manifests = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, main, output, case): case for case in cases()}
        for future in as_completed(futures):
            manifests[design.label(futures[future])] = future.result()
    write_json(output / 'protocol.json', dict(
        main_output=str(main), main_protocol_hash=file_hash(main / 'protocol.json'),
        policy_id=POLICY, restarts=placement.RESTARTS, seed=placement.SEED,
        measurement_module=str(Path(measurement.__file__).resolve()),
        measurement_hash=file_hash(Path(measurement.__file__)),
        prepared_manifest_hashes=dict(sorted(manifests.items())),
        snapshot_hashes={name: file_hash(output / name) for name in SNAPSHOT}))
    design.announce(f'prepared {len(manifests)} control task sets with {measurement.__file__}')


def check_protocol(output):
    protocol = json.loads((output / 'protocol.json').read_text())
    for name, expected in protocol['snapshot_hashes'].items():
        if file_hash(output / name) != expected:
            raise ValueError(f'Snapshot changed: {name}')
    for case in cases():
        path = design.case_dir(output, case) / 'prepared/manifest.json'
        if file_hash(path) != protocol['prepared_manifest_hashes'][design.label(case)]:
            raise ValueError(f'Prepared manifest changed: {design.label(case)}')
    return protocol


def g_check(main, output, workers):
    selected = [case for case in cases() if case[2] == 0]
    specs = [(f'{design.label(c)}/g-check', design.case_dir(output, c) / 'prepared',
              design.case_dir(output, c) / 'g-check', 'g', 0) for c in selected]
    failed, infra = design.run_specs(specs, workers)
    if failed or infra:
        raise RuntimeError(f'G check runs failed: {failed}, infrastructure={infra}')
    report = {}
    for case in selected:
        mine = load_batch(design.case_dir(output, case) / 'prepared',
                          design.case_dir(output, case) / 'g-check')[0]
        reference = load_batch(design.case_dir(main, case) / 'prepared',
                               design.case_dir(main, case) / 'g')[0]
        same = all(mine[k] == reference[k] for k in ('tet_ns', 'tat_ns', 'response_sum_ns'))
        report[design.label(case)] = dict(identical=same, tet_ns=[mine['tet_ns'], reference['tet_ns']],
                                          tat_ns=[mine['tat_ns'], reference['tat_ns']])
        design.announce(f'g-check {design.label(case)} identical={same}')
    write_json(output / 'g-check.json', report)
    if not all(row['identical'] for row in report.values()):
        raise RuntimeError('G changed with the core field; main G cannot be reused')


def run_all(output, workers):
    ordered = sorted(cases(), key=lambda c: (c[2], c[0], c[1]))
    specs = [(f'{design.label(c)}/{a}', design.case_dir(output, c) / 'prepared',
              design.case_dir(output, c) / a, a, 0) for c in ordered for a in ARCHITECTURES]
    failed, _ = design.run_specs(specs, workers)
    if failed:
        design.announce(f'{len(failed)} control runs finished with a failed status: {failed}')


def summarize(main, output):
    rows = []
    for case in cases():
        target = design.case_dir(output, case)
        if not all((target / a / 'measurements.jsonl').exists() for a in ARCHITECTURES):
            continue
        config = json.loads((target / 'configuration.json').read_text())
        reference = json.loads((design.case_dir(main, case) / 'summary.json').read_text())
        row = dict(mean=case[0], cv=case[1], set_id=case[2],
                   periods=[t['period_ticks'] for t in config['tasks']],
                   cores=[t['core'] for t in config['tasks']], **config['placement'],
                   g=reference['g'], ps=reference['p'], cs=reference['c'], c2s=reference['c2'])
        for architecture in ARCHITECTURES:
            result = load_batch(target / 'prepared', target / architecture)[0]
            ok = result['execution_status'] == 'ok'
            row[architecture] = dict(status=result['execution_status'],
                errors=result.get('errors', []),
                tet_ns=result['tet_ns'] if ok else None, tat_ns=result['tat_ns'] if ok else None,
                response_sum_ns=result.get('response_sum_ns') if ok else None,
                measured_jobs=result.get('measured_jobs'), cohorts=len(result.get('cohorts', [])),
                start_core_changes=design._start_core_changes(result, config) if ok else None)
        write_json(target / 'summary.json', row)
        rows.append(row)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    design.announce(f'summarized {len(rows)} control task sets')


def report(output):
    stats.PAIRS = PAIRS
    rows = stats.load(output / 'results.jsonl')
    cells = stats.cell_tests(rows)
    result = dict(alpha=stats.ALPHA, bootstrap=stats.BOOTSTRAP, task_sets=len(rows), pairs=PAIRS,
                  cells=cells, factors=stats.factor_tests(rows))
    (output / 'stats.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (output / 'stats.md').write_text(stats.markdown(cells))
    print(stats.markdown(cells))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'g-check', 'run', 'summarize', 'stats'))
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    if not 1 <= args.workers <= design.MAX_WORKERS:
        parser.error(f'workers must be between 1 and {design.MAX_WORKERS}')
    main_dir, output = args.main.resolve(), args.output.resolve()
    if args.stage == 'prepare':
        prepare_all(main_dir, output, min(args.workers, 32))
        return
    check_protocol(output)
    if args.stage == 'g-check':
        g_check(main_dir, output, args.workers)
    elif args.stage == 'run':
        run_all(output, args.workers)
    elif args.stage == 'summarize':
        summarize(main_dir, output)
    else:
        report(output)


if __name__ == '__main__':
    main()
