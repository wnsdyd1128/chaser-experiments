"""Run the CLS x footprint design: prepare + yarda_cpp counts, isolated U gate, pilot, full, stats.

Per task set: mixed/ (one special task per core) and grouped/ (all special
tasks on core 0) share task order, arrays and source. G, C (1+3) and C2
(1+1+2) run on the mixed build; P runs under both placements. Deadline misses
are recorded as measured outcomes. Run with PYTHONPATH set to the c3 code copy.
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

import bimodal
import bi_run
import footprint as fp
import run as design
import stats
import yarda_counts

SNAPSHOT = ('footprint.py', 'fp_run.py', 'l2_probe.py', 'test_footprint.py')
RUNS = bi_run.RUNS_MAIN
PAIRS = bi_run.PAIRS_MAIN
CODE = {'small': 32, 'big': 768}


def cases():
    return [(kind, k) for kind in fp.KINDS for k in range(fp.SETS)]


def label(case):
    return f'{case[0]}/s{case[1]:02d}'


def case_dir(output, case):
    return output / label(case)


def model(output):
    return json.loads((output / 'calibration/model.json').read_text())['coefficients']


def prepare_one(output, case, tables, levels):
    target = case_dir(output, case)
    for placement in fp.PLACEMENTS:
        (target / placement).mkdir(parents=True)
        config = fp.configuration(*case, tables, levels, placement)
        write_json(target / placement / 'configuration.json', config)
        prepare(config, target / placement / 'prepared')
    for name in ('source/workload.c', 'layout.json'):
        if (target / 'grouped/prepared' / name).read_bytes() != (target / 'mixed/prepared' / name).read_bytes():
            raise ValueError(f'{label(case)}: placements differ in {name}')
    counts = yarda_counts.analyze(target / 'mixed/prepared', target / 'yarda')
    rows = []
    for task in json.loads((target / 'mixed/configuration.json').read_text())['tasks']:
        count = counts[task['task_id']]
        if abs(count['cls'] - task['cls_planned']) > bi_run.CLS_TOLERANCE:
            raise ValueError(f'{label(case)}/{task["task_id"]}: yarda CLS {count["cls"]} != planned')
        rows.append(dict(count, task_id=task['task_id'], role=task['role'], kind=task['kind'],
                         footprint_kib=task['footprint_kib'], u_planned=task['u_planned'],
                         l1_misses_per_kilo_ir=1e3 * count['l1_misses'] / count['ir_instructions']))
    write_json(target / 'locality.json', dict(tasks=rows))
    return {p: file_hash(target / p / 'prepared/manifest.json') for p in fp.PLACEMENTS}


def prepare_all(output, workers):
    coefficients = model(output)
    tables, levels = bimodal.solve_tables(coefficients, fp.BUDGET_NS), fp.special_levels(coefficients)
    for name in SNAPSHOT:
        shutil.copyfile(HERE / name, output / name)
    manifests = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case, tables, levels): case for case in cases()}
        for future in as_completed(futures):
            manifests[label(futures[future])] = future.result()
            design.announce(f'prepared {label(futures[future])}')
    write_json(output / 'protocol.json', dict(
        kinds=fp.KINDS, footprint_kib=fp.FOOTPRINT_KIB, cls_level=fp.CLS_LEVEL, special_levels=levels,
        sets=fp.SETS, period_ticks=fp.PERIOD, budget_ns=fp.BUDGET_NS, warmup_jobs=fp.WARMUP_JOBS,
        measured_jobs=fp.MEASURED_JOBS, workload_optimization='O2', runs=[r[2] for r in RUNS],
        model_hash=file_hash(output / 'calibration/model.json'),
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


def level_key(task):
    return (task['distinct'], *bi_run.level_key(task))


def isolated(output, workers):
    """Run every distinct level alone once (P); gate the isolated U against the budget."""
    plans, sources = {}, {}
    for case in sorted(cases(), key=lambda c: c[1]):
        plans[case] = json.loads((case_dir(output, case) / 'mixed/prepared/p/plan.json').read_text())['tasks']
        for i, task in enumerate(plans[case]):
            sources.setdefault(level_key(task), (case, i, task['task_id']))
    specs = [(f'{label(case)}/isolated/{task_id}', case_dir(output, case) / 'mixed/prepared',
              case_dir(output, case) / 'isolated' / task_id, 'p', i + 1)
             for case, i, task_id in sources.values()]
    _, infra = design.run_specs(specs, workers)
    if infra:
        raise RuntimeError(f'Isolated runs produced no header: {infra}')
    cpu, startup = {}, set()
    for key, (case, i, task_id) in sources.items():
        record = load_batch(case_dir(output, case) / 'mixed/prepared', case_dir(output, case) / 'isolated' / task_id)[0]
        if record['execution_status'] != 'ok':
            if not set(record.get('errors', [])) <= bi_run.STARTUP_ERRORS:
                raise RuntimeError(f'Isolated run failed: {label(case)}/{task_id}: {record.get("errors")}')
            startup.add(key)
            continue
        jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
                if j['task'] == i and j['job'] >= fp.WARMUP_JOBS]
        cpu[key] = sum(jobs) / len(jobs)
    report, worst = {}, 0.0
    for case, tasks in plans.items():
        config = {t['task_id']: t for t in json.loads(
            (case_dir(output, case) / 'mixed/configuration.json').read_text())['tasks']}
        job = {t['task_id']: (config[t['task_id']]['u_planned'] * fp.PERIOD * 1e6 if level_key(t) in startup
                              else cpu[level_key(t)]) for t in tasks}
        errors = {t['task_id']: job[t['task_id']] / fp.BUDGET_NS - 1 for t in tasks if level_key(t) not in startup}
        worst = max(worst, *(abs(e) for e in errors.values()), 0.0)
        report[label(case)] = dict(job_ns=job, utilization={k: v / (fp.PERIOD * 1e6) for k, v in job.items()},
                                   relative_error=errors,
                                   source={t['task_id']: 'model' if level_key(t) in startup else
                                           '/'.join((label(sources[level_key(t)][0]), sources[level_key(t)][2]))
                                           for t in tasks})
    write_json(output / 'isolated-u.json', report)
    if worst > bi_run.U_TOLERANCE:
        raise RuntimeError(f'Isolated job time error {worst:.2%} exceeds {bi_run.U_TOLERANCE:.0%}')
    design.announce(f'isolated gate passed over {len(sources) - len(startup)} measured levels '
                    f'({len(startup)} startup-failed levels use the model): worst relative error {worst:.2%}')


def specs_for(output, selected):
    return [(f'{label(c)}/{key}', case_dir(output, c) / placement / 'prepared',
             case_dir(output, c) / placement / arch, arch, 0) for c in selected for placement, arch, key in RUNS]


def special_overlap(result, config):
    """Mean number of other special jobs running during a measured special job (5 samples each)."""
    tasks = config['tasks']
    special = {i for i, t in enumerate(tasks) if t['role'] == 'special'}
    jobs = [(j['start_ns'], j['completion_ns'], j['task']) for j in result['jobs']
            if j['task'] in special and j['job'] >= config['warmup_ticks'] // tasks[j['task']]['period_ticks']
            and j.get('completion_ns') is not None]
    samples = [sum(1 for s, e, t in jobs if t != task and s <= x <= e)
               for start, end, task in jobs for x in np.linspace(start, end, 5)]
    return float(np.mean(samples)) if samples else None


def summarize(output):
    isolated_u = json.loads((output / 'isolated-u.json').read_text())
    rows = []
    for case in cases():
        target = case_dir(output, case)
        if not all((target / placement / arch / 'measurements.jsonl').exists() for placement, arch, _ in RUNS):
            continue
        kind, k = case
        locality = json.loads((target / 'locality.json').read_text())['tasks']
        job = isolated_u[label(case)]['job_ns']
        row = dict(kind=kind, set_id=k, mean=fp.FOOTPRINT_KIB[kind], cv={'low': 0, 'high': 1}[fp.CLS_LEVEL[kind]],
                   footprint_kib=fp.FOOTPRINT_KIB[kind], cls_level=fp.CLS_LEVEL[kind],
                   roles=[t['role'] for t in locality], cls=[t['cls'] for t in locality],
                   l1_misses=[t['l1_misses'] for t in locality], isolated_cpu_ns=[job[t['task_id']] for t in locality])
        for placement, arch, key in RUNS:
            config = json.loads((target / placement / 'configuration.json').read_text())
            result = load_batch(target / placement / 'prepared', target / placement / arch)[0]
            ok = result['execution_status'] == 'ok'
            row[key] = dict(status=result['execution_status'], errors=result.get('errors', []),
                tet_ns=result['tet_ns'] if ok else None, tat_ns=result['tat_ns'] if ok else None,
                response_sum_ns=result.get('response_sum_ns') if ok else None,
                measured_jobs=result.get('measured_jobs'), cohorts=len(result.get('cohorts', [])),
                start_core_changes=design._start_core_changes(result, config) if ok else None,
                task_cpu_ns=bi_run.task_cpu(result, config) if ok else None,
                state=bi_run.run_state(result), max_response_ratio=bi_run.max_response_ratio(result, config),
                core_imbalance=bi_run.core_imbalance(result, config) if ok else None,
                special_overlap=special_overlap(result, config))
        write_json(target / 'summary.json', row)
        rows.append(row)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    design.announce(f'summarized {len(rows)} task sets')


def paired_contrast(rows, metric, a, b, factor, levels, fixed_key, fixed):
    """Per-set (gap at levels[1] - gap at levels[0]) of pair a-b, other factor fixed."""
    by_set = {}
    for r in rows:
        if r[fixed_key] == fixed and r[factor] in levels:
            value = stats.gap(r, metric, a, b)
            if value is not None:
                by_set.setdefault(r['set_id'], {})[r[factor]] = value
    return [v[levels[1]] - v[levels[0]] for v in by_set.values() if len(v) == 2]


def contrasts(rows):
    """Footprint contrast (big - small gap) per CLS level and CLS contrast (low - high gap)
    per footprint, for every pair and metric; Holm over the two levels of each family."""
    out = []
    for metric in stats.METRICS:
        for a, b in PAIRS:
            for factor, levels, fixed_key, fixed_values in (
                    ('footprint_kib', (32, 768), 'cls_level', ('low', 'high')),
                    ('cls_level', ('high', 'low'), 'footprint_kib', (32, 768))):
                group = []
                for fixed in fixed_values:
                    diffs = paired_contrast(rows, metric, a, b, factor, levels, fixed_key, fixed)
                    entry = dict(metric=metric, pair=f'{a}-{b}', contrast=f'{factor}:{levels[1]}-{levels[0]}',
                                 fixed=f'{fixed_key}={fixed}', n=len(diffs))
                    if len(diffs) >= 6 and any(diffs):
                        entry.update(median=float(median(diffs)), positive=sum(d > 0 for d in diffs),
                                     median_ci95=stats.median_ci(diffs),
                                     wilcoxon_p=float(scipy_stats.wilcoxon(diffs).pvalue))
                    group.append(entry)
                tested = [e for e in group if 'wilcoxon_p' in e]
                for entry, adjusted in zip(tested, stats.holm([e['wilcoxon_p'] for e in tested])):
                    entry.update(holm_p=adjusted, significant=adjusted < stats.ALPHA)
                out.extend(group)
    return out


def report(output):
    stats.PAIRS = PAIRS
    rows = stats.load(output / 'results.jsonl')
    keys = [k for _, _, k in RUNS]
    cells = stats.cell_tests(rows)
    schedulable = {kind: {k: dict(ok=sum(r[k]['state'] == 'ok' for r in rows if r['kind'] == kind),
                                  deadline=sum(r[k]['state'] == 'deadline' for r in rows if r['kind'] == kind),
                                  excluded=sum(r[k]['state'] in ('startup', 'other') for r in rows if r['kind'] == kind))
                          for k in keys} for kind in fp.KINDS}
    tests = []
    for a, b in PAIRS:
        group = [dict(bi_run.mcnemar([r for r in rows if r['kind'] == kind], a, b), pair=f'{a}-{b}', kind=kind)
                 for kind in fp.KINDS]
        for entry, adjusted in zip(group, stats.holm([e['exact_p'] for e in group])):
            entry.update(holm_p=adjusted, significant=adjusted < stats.ALPHA)
        tests.extend(group)
    overlap = {kind: {k: float(np.median([r[k]['special_overlap'] for r in rows
                                          if r['kind'] == kind and r[k]['special_overlap'] is not None]))
                      for k in keys} for kind in fp.KINDS}
    result = dict(alpha=stats.ALPHA, task_sets=len(rows), pairs=PAIRS,
                  cell_keys=dict(mean='footprint_kib', cv='cls_level (0 low, 1 high)'), cells=cells,
                  contrasts=contrasts(rows), schedulable=schedulable, schedulability_tests=tests,
                  special_overlap_median=overlap)
    (output / 'stats-footprint.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (output / 'stats-footprint.md').write_text(stats.markdown(cells))
    design.announce('wrote footprint statistics')


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
        design.run_specs(specs_for(output, [c for c in cases() if c[1] == 0]), args.workers)
        summarize(output)
        rows = stats.load(output / 'results.jsonl')
        other = [f"{r['kind']}/{r['set_id']}/{k}" for r in rows for _, _, k in RUNS if r[k]['state'] == 'other']
        if other:
            raise RuntimeError(f'Pilot runs failed: {other}')
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[1] != 0), key=lambda c: (c[1], c[0]))
        failed, _ = design.run_specs(specs_for(output, remaining), args.workers)
        summarize(output)
        if failed:
            design.announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(output)


if __name__ == '__main__':
    main()
