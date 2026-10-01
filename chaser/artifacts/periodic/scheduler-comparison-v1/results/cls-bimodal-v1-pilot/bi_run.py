"""Run the bimodal CLS design: prepare + yarda_cpp counts, isolated U gate, pilot, full, stats.

Per task set: mixed/ and, when 0 < p < 1, grouped/ builds share task order,
arrays and workload source and differ only in cores. G, C (1+3) and C2
(1+1+2) run on the mixed build, whose cores define the cluster domains; P runs
under both placements. Every distinct level also runs alone (P) once, which
gates U and gives the co-run CPU baseline. Run with PYTHONPATH set to the 4d03b93 + C2 +
padding code copy.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
from statistics import median
import sys

from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.build import prepare
from chaser.periodic.dataset import load_batch
from tools.rtems_smoke import file_hash, write_json

import bimodal
import run as design
import stats
import yarda_counts

SNAPSHOT = ('bimodal.py', 'bi_calibrate.py', 'bi_run.py', 'yarda_counts.py', 'test_bimodal.py',
            'test_padding.py')
RUNS = (('mixed', 'g', 'g'), ('mixed', 'c', 'c'), ('mixed', 'c2', 'c2'), ('mixed', 'p', 'p'),
        ('grouped', 'p', 'p_grp'))
PAIRS = (('g', 'p'), ('c', 'p'), ('c2', 'p'), ('g', 'c'), ('g', 'c2'), ('c', 'c2'),
         ('p_grp', 'p'), ('g', 'p_grp'), ('c', 'p_grp'), ('c2', 'p_grp'))
U_TOLERANCE = 0.03
CLS_TOLERANCE = 1e-9


def cases():
    return [(p, cv, traffic, k) for p, cv, traffic in bimodal.cells() for k in bimodal.set_ids(p, cv)]


def label(case):
    p, cv, traffic, k = case
    return f'{traffic}/p{round(p * 100):03d}/cv{round(cv * 100):02d}/s{k:02d}'


def case_dir(output, case):
    return output / label(case)


def runs_for(case):
    return [run for run in RUNS if run[0] in bimodal.placements(case[0])]


def tables(output):
    return bimodal.solve_tables(json.loads((output / 'calibration/model.json').read_text())['coefficients'])


def prepare_one(output, case, levels):
    target = case_dir(output, case)
    for placement in bimodal.placements(case[0]):
        directory = target / placement
        directory.mkdir(parents=True)
        config = bimodal.configuration(*case, levels, placement)
        write_json(directory / 'configuration.json', config)
        prepare(config, directory / 'prepared')
        if placement != 'mixed':
            for name in ('source/workload.c', 'layout.json'):
                if (directory / 'prepared' / name).read_bytes() != (target / 'mixed/prepared' / name).read_bytes():
                    raise ValueError(f'{label(case)}: placements differ in {name}')
    counts = yarda_counts.analyze(target / 'mixed/prepared', target / 'yarda')
    config = json.loads((target / 'mixed/configuration.json').read_text())
    rows = []
    for task in config['tasks']:
        count = counts[task['task_id']]
        if abs(count['cls'] - task['cls_planned']) > CLS_TOLERANCE:
            raise ValueError(f'{label(case)}/{task["task_id"]}: yarda CLS {count["cls"]} != planned')
        rows.append(dict(count, task_id=task['task_id'], mode=task['mode'], cls_target=task['cls_target'],
                         u_planned=task['u_planned'], l1_misses_per_kilo_ir=1e3 * count['l1_misses']
                         / count['ir_instructions']))
    write_json(target / 'locality.json', dict(tasks=rows))
    return {p: file_hash(target / p / 'prepared/manifest.json') for p in bimodal.placements(case[0])}


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
        low_fractions=bimodal.LOW_FRACTIONS, cvs=bimodal.CVS, sets=bimodal.SETS, tasks=bimodal.TASKS,
        period_ticks=bimodal.PERIOD, task_u=bimodal.TASK_U, high_center=bimodal.HIGH_CENTER,
        low_center=bimodal.LOW_CENTER, workload_optimization='O2', runs=[r[2] for r in RUNS],
        center_l1_misses=float(levels['center_l1_misses']),
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
    return tuple(task.get(k, 0) for k in ('hot_distinct', 'hot_repeats', 'sweeps', 'pad_rounds', 'pad_tail'))


def isolated(output, workers):
    """Run every distinct level alone once (P); gate the isolated U of all levels.

    Common random numbers repeat a level across cells. Its isolated job time
    depends only on the level (the calibration validates the level-only model),
    so tasks with the same level share one run.
    """
    plans, sources = {}, {}
    for case in sorted(cases(), key=lambda c: c[3]):
        plans[case] = json.loads((case_dir(output, case) / 'mixed/prepared/p/plan.json').read_text())['tasks']
        for i, task in enumerate(plans[case]):
            sources.setdefault(level_key(task), (case, i, task['task_id']))
    specs = [(f'{label(case)}/isolated/{task_id}', case_dir(output, case) / 'mixed/prepared',
              case_dir(output, case) / 'isolated' / task_id, 'p', i + 1)
             for case, i, task_id in sources.values()]
    failed, infra = design.run_specs(specs, workers)
    if failed or infra:
        raise RuntimeError(f'Isolated runs failed: {failed}, infrastructure={infra}')
    cpu = {}
    for key, (case, i, task_id) in sources.items():
        record = load_batch(case_dir(output, case) / 'mixed/prepared',
                            case_dir(output, case) / 'isolated' / task_id)[0]
        jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
                if j['task'] == i and j['job'] >= bimodal.WARMUP_JOBS]
        cpu[key] = sum(jobs) / len(jobs)
    report, worst = {}, 0.0
    for case, tasks in plans.items():
        u = {t['task_id']: cpu[level_key(t)] / (bimodal.PERIOD * 1e6) for t in tasks}
        errors = {k: v / bimodal.TASK_U - 1 for k, v in u.items()}
        worst = max(worst, *(abs(e) for e in errors.values()))
        report[label(case)] = dict(utilization=u, relative_error=errors, source={
            t['task_id']: '/'.join((label(sources[level_key(t)][0]), sources[level_key(t)][2])) for t in tasks})
    write_json(output / 'isolated-u.json', report)
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    design.announce(f'isolated U gate passed over {len(sources)} levels: worst relative error {worst:.2%}')


def specs_for(output, selected):
    return [(f'{label(c)}/{key}', case_dir(output, c) / placement / 'prepared',
             case_dir(output, c) / placement / arch, arch, 0)
            for c in selected for placement, arch, key in runs_for(c)]


def task_cpu(record, config):
    """Mean measured-job CPU (ns) per task, in configuration order."""
    cpu = {i: [] for i in range(len(config['tasks']))}
    for job in record['jobs']:
        if job['job'] >= config['warmup_ticks'] // config['tasks'][job['task']]['period_ticks']:
            cpu[job['task']].append(job['cpu_after_ns'] - job['cpu_before_ns'])
    return [sum(v) / len(v) for v in cpu.values()]


def summarize(output):
    isolated_u = json.loads((output / 'isolated-u.json').read_text())
    rows = []
    for case in cases():
        target = case_dir(output, case)
        if not all((target / placement / arch / 'measurements.jsonl').exists()
                   for placement, arch, _ in runs_for(case)):
            continue
        locality = json.loads((target / 'locality.json').read_text())['tasks']
        u = isolated_u[label(case)]['utilization']
        row = dict(mean=case[0], cv=case[1], traffic=case[2], set_id=case[3],
                   modes=[t['mode'] for t in locality], cls=[t['cls'] for t in locality],
                   l1_misses=[t['l1_misses'] for t in locality],
                   isolated_cpu_ns=[u[t['task_id']] * bimodal.PERIOD * 1e6 for t in locality],
                   p_grp=dict(status='absent'))
        for placement, arch, key in runs_for(case):
            config = json.loads((target / placement / 'configuration.json').read_text())
            result = load_batch(target / placement / 'prepared', target / placement / arch)[0]
            ok = result['execution_status'] == 'ok'
            row[key] = dict(status=result['execution_status'], errors=result.get('errors', []),
                tet_ns=result['tet_ns'] if ok else None, tat_ns=result['tat_ns'] if ok else None,
                response_sum_ns=result.get('response_sum_ns') if ok else None,
                measured_jobs=result.get('measured_jobs'), cohorts=len(result.get('cohorts', [])),
                start_core_changes=design._start_core_changes(result, config) if ok else None,
                task_cpu_ns=task_cpu(result, config) if ok else None)
        write_json(target / 'summary.json', row)
        rows.append(row)
    with (output / 'results.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    design.announce(f'summarized {len(rows)} task sets')


def trend_tests(rows):
    """Friedman and two-sided Page trends over p (fixed CV > 0) and over CV (fixed p)."""
    out = []
    for metric in stats.METRICS:
        for a, b in PAIRS:
            fractions = [p for p in bimodal.LOW_FRACTIONS if 'p_grp' not in (a, b) or 0 < p < 1]
            for fixed_key, fixed_values, factor, levels in (
                    ('mean', fractions, 'cv', [cv for cv in bimodal.CVS if cv > 0]),
                    ('cv', [cv for cv in bimodal.CVS if cv > 0], 'mean', fractions)):
                for fixed in fixed_values:
                    data = stats.blocked(rows, metric, a, b, fixed_key, fixed, factor, levels)
                    entry = dict(metric=metric, pair=f'{a}-{b}', fixed=f'{fixed_key}={fixed}',
                                 factor=factor, levels=levels, blocks=len(data))
                    if len(data) >= 5 and len(levels) >= 3:
                        columns = list(zip(*data))
                        entry.update(friedman_p=float(scipy_stats.friedmanchisquare(*columns).pvalue),
                                     page_increasing_p=float(scipy_stats.page_trend_test(data).pvalue),
                                     page_decreasing_p=float(scipy_stats.page_trend_test(
                                         [row[::-1] for row in data]).pvalue),
                                     level_medians=[float(median(c)) for c in columns])
                    out.append(entry)
    return out


def traffic_contrast(rows):
    """Paired per-set (as-is gap - matched gap) at p = 0.5, per CV; Holm per metric and pair."""
    out = []
    for metric in stats.METRICS:
        for a, b in PAIRS:
            group = []
            for cv in bimodal.CVS:
                pairs = {}
                for r in rows:
                    if r['mean'] == 0.5 and r['cv'] == cv:
                        value = stats.gap(r, metric, a, b)
                        if value is not None:
                            pairs.setdefault(r['set_id'], {})[r['traffic']] = value
                diffs = [v['as-is'] - v['matched'] for v in pairs.values() if len(v) == 2]
                entry = dict(metric=metric, pair=f'{a}-{b}', cv=cv, n=len(diffs))
                if len(diffs) >= 6:
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
    for traffic in ('as-is', 'matched'):
        subset = [r for r in rows if r['traffic'] == traffic]
        cells = stats.cell_tests(subset)
        result = dict(traffic=traffic, alpha=stats.ALPHA, task_sets=len(subset), pairs=PAIRS,
                      cell_keys=dict(mean='low_fraction', cv='cv'), cells=cells,
                      trends=trend_tests(subset))
        (output / f'stats-{traffic}.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        (output / f'stats-{traffic}.md').write_text(stats.markdown(cells))
    contrast = traffic_contrast(rows)
    (output / 'stats-traffic-contrast.json').write_text(json.dumps(contrast, indent=2, sort_keys=True) + '\n')
    design.announce('wrote statistics')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
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
        failed, _ = design.run_specs(specs_for(output, [c for c in cases() if c[3] == 0]), args.workers)
        summarize(output)
        if failed:
            raise RuntimeError(f'Pilot runs failed: {failed}')
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[3] != 0), key=lambda c: (c[3], c[2], c[0], c[1]))
        failed, _ = design.run_specs(specs_for(output, remaining), args.workers)
        summarize(output)
        if failed:
            design.announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(output)


if __name__ == '__main__':
    main()
