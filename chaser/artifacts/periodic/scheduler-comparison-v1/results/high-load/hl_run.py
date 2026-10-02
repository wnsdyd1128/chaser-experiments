"""Run the high-load design: prepare, isolated U sample gate, pilot, full, stats.

Per task set: wfd/, informed/ and c-informed/ builds share task order and
source and differ only in cores. G, C (1+3), C2 (1+1+2) and P run on wfd;
P runs on informed (p_inf); C (1+3) runs on c-informed (c_inf). Deadline
misses are measured outcomes. The isolated gate runs every task of set 0 of
each cell alone (the O0 cyclic job-time model was validated in experiment 1).
Run with PYTHONPATH set to the c3 code copy.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
from statistics import median
import sys

import numpy as np
from scipy import stats as scipy_stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'period-distribution'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

from chaser.periodic.build import prepare
from chaser.periodic.dataset import load_batch
from tools.rtems_smoke import file_hash, write_json

import bi_run
import hl_set as hl
import run as design
import stats

SNAPSHOT = ('hl_set.py', 'hl_run.py', 'test_hl.py')
RUNS = (('wfd', 'g', 'g'), ('wfd', 'c', 'c'), ('wfd', 'c2', 'c2'), ('wfd', 'p', 'p'),
        ('informed', 'p', 'p_inf'), ('c-informed', 'c', 'c_inf'))
PAIRS = (('g', 'p'), ('c', 'p'), ('c2', 'p'), ('p_inf', 'p'), ('c_inf', 'p'), ('g', 'p_inf'), ('c', 'p_inf'),
         ('c2', 'p_inf'), ('c_inf', 'p_inf'), ('g', 'c_inf'), ('c_inf', 'c'))
U_TOLERANCE = 0.03
HEAVINESS_CODE = {'light': 1, 'heavy': 2}


def cases():
    return [(load, heaviness, k) for heaviness in hl.HEAVINESS for load in hl.LOADS for k in range(hl.SETS)]


def label(case):
    load, heaviness, k = case
    return f'{heaviness}/u{round(load * 100):03d}/s{k:02d}'


def case_dir(output, case):
    return output / label(case)


def prepare_one(output, case):
    target = case_dir(output, case)
    for placement in hl.PLACEMENTS:
        (target / placement).mkdir(parents=True)
        config = hl.configuration(*case, placement)
        write_json(target / placement / 'configuration.json', config)
        prepare(config, target / placement / 'prepared')
    for placement in hl.PLACEMENTS:
        for name in ('source/workload.c', 'layout.json'):
            if (target / placement / 'prepared' / name).read_bytes() != (target / 'wfd/prepared' / name).read_bytes():
                raise ValueError(f'{label(case)}: placements differ in {name}')
    return {p: file_hash(target / p / 'prepared/manifest.json') for p in hl.PLACEMENTS}


def prepare_all(output, workers):
    output.mkdir(parents=True, exist_ok=True)
    for name in SNAPSHOT:
        shutil.copyfile(HERE / name, output / name)
    manifests = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case): case for case in cases()}
        for future in as_completed(futures):
            manifests[label(futures[future])] = future.result()
            design.announce(f'prepared {label(futures[future])}')
    write_json(output / 'protocol.json', dict(
        loads=hl.LOADS, heaviness=hl.HEAVINESS, sets=hl.SETS, tasks=hl.TASKS, periods=hl.PERIODS,
        hyperperiod=hl.HYPERPERIOD, warmup_hyperperiods=hl.WARMUP_HYPERPERIODS,
        measured_hyperperiods=hl.MEASURED_HYPERPERIODS, alpha=hl.ALPHA, light_cap=hl.LIGHT_CAP, u_min=hl.U_MIN,
        heavy=hl.HEAVY, heavy_range=hl.HEAVY_RANGE, core_cap=hl.CORE_CAP, workload_optimization='O0',
        runs=[r[2] for r in RUNS], prepared_manifest_hashes=dict(sorted(manifests.items())),
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


def isolated(output, workers):
    """Run every task of set 0 of each cell alone (P) and gate its U against the plan."""
    sample = [c for c in cases() if c[2] == 0]
    specs = []
    for case in sample:
        plan = json.loads((case_dir(output, case) / 'wfd/prepared/p/plan.json').read_text())
        specs += [(f'{label(case)}/isolated/{t["task_id"]}', case_dir(output, case) / 'wfd/prepared',
                   case_dir(output, case) / 'isolated' / t['task_id'], 'p', i + 1)
                  for i, t in enumerate(plan['tasks'])]
    _, infra = design.run_specs(specs, workers)
    if infra:
        raise RuntimeError(f'Isolated runs produced no header: {infra}')
    report, worst = {}, 0.0
    for case in sample:
        config = json.loads((case_dir(output, case) / 'wfd/configuration.json').read_text())
        warm = config['warmup_ticks']
        u, errors, startup = {}, {}, []
        for i, task in enumerate(config['tasks']):
            record = load_batch(case_dir(output, case) / 'wfd/prepared', case_dir(output, case) / 'isolated' / task['task_id'])[0]
            if record['execution_status'] != 'ok':
                if not set(record.get('errors', [])) <= bi_run.STARTUP_ERRORS:
                    raise RuntimeError(f'Isolated run failed: {label(case)}/{task["task_id"]}: {record.get("errors")}')
                startup.append(task['task_id'])
                continue
            jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
                    if j['task'] == i and j['job'] >= warm // task['period_ticks']]
            u[task['task_id']] = sum(jobs) / len(jobs) / (task['period_ticks'] * 1e6)
            errors[task['task_id']] = u[task['task_id']] / task['u_planned'] - 1
        worst = max(worst, *(abs(e) for e in errors.values()), 0.0)
        report[label(case)] = dict(utilization=u, relative_error=errors, startup_failed=startup)
    write_json(output / 'isolated-u.json', report)
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    design.announce(f'isolated U gate passed on set 0 of every cell: worst relative error {worst:.2%}')


def specs_for(output, selected):
    return [(f'{label(c)}/{key}', case_dir(output, c) / placement / 'prepared',
             case_dir(output, c) / placement / arch, arch, 0) for c in selected for placement, arch, key in RUNS]


def summarize(output):
    rows = []
    for case in cases():
        target = case_dir(output, case)
        if not all((target / placement / arch / 'measurements.jsonl').exists() for placement, arch, _ in RUNS):
            continue
        load, heaviness, k = case
        row = dict(load=load, heaviness=heaviness, set_id=k, mean=load, cv=HEAVINESS_CODE[heaviness])
        for placement, arch, key in RUNS:
            config = json.loads((target / placement / 'configuration.json').read_text())
            result = load_batch(target / placement / 'prepared', target / placement / arch)[0]
            ok = result['execution_status'] == 'ok'
            row[key] = dict(status=result['execution_status'], errors=result.get('errors', []),
                tet_ns=result['tet_ns'] if ok else None, tat_ns=result['tat_ns'] if ok else None,
                response_sum_ns=result.get('response_sum_ns') if ok else None,
                measured_jobs=result.get('measured_jobs'), cohorts=len(result.get('cohorts', [])),
                state=bi_run.run_state(result), max_response_ratio=bi_run.max_response_ratio(result, config),
                core_imbalance=bi_run.core_imbalance(result, config) if ok else None,
                planned_core_u=config['high_load']['core_u'])
        write_json(target / 'summary.json', row)
        rows.append(row)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    design.announce(f'summarized {len(rows)} task sets')


def load_trends(rows):
    """Friedman and two-sided Page tests of per-set gaps over the load levels, per heaviness."""
    out = []
    for heaviness in hl.HEAVINESS:
        for metric in stats.METRICS:
            for a, b in PAIRS:
                table = {}
                for r in rows:
                    if r['heaviness'] == heaviness:
                        value = stats.gap(r, metric, a, b)
                        if value is not None:
                            table.setdefault(r['set_id'], {})[r['load']] = value
                data = [[v[l] for l in hl.LOADS] for v in table.values() if len(v) == len(hl.LOADS)]
                entry = dict(heaviness=heaviness, metric=metric, pair=f'{a}-{b}', loads=hl.LOADS, blocks=len(data))
                if len(data) >= 5:
                    entry.update(friedman_p=float(scipy_stats.friedmanchisquare(*zip(*data)).pvalue),
                                 page_increasing_p=float(scipy_stats.page_trend_test(data).pvalue),
                                 page_decreasing_p=float(scipy_stats.page_trend_test([d[::-1] for d in data]).pvalue),
                                 level_medians=[float(median(c)) for c in zip(*data)])
                out.append(entry)
    return out


def report(output):
    stats.PAIRS = PAIRS
    rows = stats.load(output / 'results.jsonl')
    keys = [k for _, _, k in RUNS]
    cell_of = lambda r: f"{r['heaviness']}/u{round(r['load'] * 100):03d}"
    cells = sorted({cell_of(r) for r in rows})
    schedulable = {cell: {k: dict(ok=sum(r[k]['state'] == 'ok' for r in rows if cell_of(r) == cell),
                                  deadline=sum(r[k]['state'] == 'deadline' for r in rows if cell_of(r) == cell),
                                  excluded=sum(r[k]['state'] in ('startup', 'other') for r in rows if cell_of(r) == cell))
                          for k in keys} for cell in cells}
    tests = []
    for a, b in PAIRS:
        group = [dict(bi_run.mcnemar([r for r in rows if cell_of(r) == cell], a, b), pair=f'{a}-{b}', cell=cell)
                 for cell in cells]
        for entry, adjusted in zip(group, stats.holm([e['exact_p'] for e in group])):
            entry.update(holm_p=adjusted, significant=adjusted < stats.ALPHA)
        tests.extend(group)
    response = []
    for a, b in PAIRS:
        group = []
        for cell in cells:
            diffs = [r[a]['max_response_ratio'] - r[b]['max_response_ratio'] for r in rows
                     if cell_of(r) == cell and r[a]['state'] == r[b]['state'] == 'ok']
            entry = dict(pair=f'{a}-{b}', cell=cell, n=len(diffs))
            if len(diffs) >= 6 and any(diffs):
                entry.update(median=float(median(diffs)), wilcoxon_p=float(scipy_stats.wilcoxon(diffs).pvalue))
            group.append(entry)
        tested = [e for e in group if 'wilcoxon_p' in e]
        for entry, adjusted in zip(tested, stats.holm([e['wilcoxon_p'] for e in tested])):
            entry.update(holm_p=adjusted, significant=adjusted < stats.ALPHA)
        response.extend(group)
    result = dict(alpha=stats.ALPHA, task_sets=len(rows), pairs=PAIRS,
                  cell_keys=dict(mean='per-core load', cv='heaviness (1 light, 2 heavy)'),
                  cells=stats.cell_tests(rows), schedulable=schedulable, schedulability_tests=tests,
                  max_response_ratio_tests=response, load_trends=load_trends(rows))
    (output / 'stats-high-load.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (output / 'stats-high-load.md').write_text(stats.markdown(result['cells']))
    design.announce('wrote high-load statistics')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'isolated', 'pilot', 'full', 'summarize', 'stats'))
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
    if args.stage == 'isolated':
        isolated(output, args.workers)
    elif args.stage == 'pilot':
        design.run_specs(specs_for(output, [c for c in cases() if c[2] == 0]), args.workers)
        summarize(output)
        rows = stats.load(output / 'results.jsonl')
        other = [f"{label((r['load'], r['heaviness'], r['set_id']))}/{k}" for r in rows for _, _, k in RUNS
                 if r[k]['state'] == 'other']
        if other:
            raise RuntimeError(f'Pilot runs failed: {other}')
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[2] != 0), key=lambda c: (c[2], c[1], c[0]))
        failed, _ = design.run_specs(specs_for(output, remaining), args.workers)
        summarize(output)
        if failed:
            design.announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(output)


if __name__ == '__main__':
    main()
