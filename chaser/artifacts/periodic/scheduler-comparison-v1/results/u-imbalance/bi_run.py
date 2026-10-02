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
# Task-U imbalance: cluster domains follow the U-balanced placement.
RUNS_MAIN, PAIRS_MAIN = RUNS, PAIRS
IMBALANCE_RUNS = (('balanced', 'g', 'g'), ('balanced', 'c', 'c'), ('balanced', 'c2', 'c2'),
                  ('balanced', 'p', 'p_bal'), ('mixed', 'p', 'p'), ('grouped', 'p', 'p_grp'),
                  ('grouped-balanced', 'p', 'p_grp_bal'))
IMBALANCE_PAIRS = (('g', 'p_bal'), ('c', 'p_bal'), ('c2', 'p_bal'), ('p', 'p_bal'), ('p_grp', 'p_bal'),
                   ('p_grp_bal', 'p_bal'), ('g', 'p_grp_bal'), ('p_grp_bal', 'p_grp'))
U_TOLERANCE = 0.03
CLS_TOLERANCE = 1e-9
# Startup-only failures: the coordinator sometimes arms one tick after its
# chosen epoch. The simulator is deterministic, so the same build always fails
# the same way; such runs carry no information about the level's job time.
STARTUP_ERRORS = {'arm_phase', 'release_mismatch'}


DESIGN = 'main'
LEVEL_KEYS = {'load-level': 'period', 'u-imbalance': 'u_cv'}


def select_design(name):
    global DESIGN, RUNS, PAIRS
    DESIGN = name
    RUNS, PAIRS = (IMBALANCE_RUNS, IMBALANCE_PAIRS) if name == 'u-imbalance' else (RUNS_MAIN, PAIRS_MAIN)


def cases():
    """(low fraction, CV, traffic, period, task-U CV, set id) of every task set in the design."""
    return [(p, cv, traffic, period, u_cv, k) for p, cv, traffic in bimodal.cells(DESIGN)
            for period in bimodal.periods(DESIGN) for u_cv in bimodal.u_cvs(DESIGN)
            for k in bimodal.set_ids(p, cv)]


def label(case):
    p, cv, traffic, period, u_cv, k = case
    level_part = {'load-level': f'/t{period:03d}', 'u-imbalance': f'/u{round(u_cv * 100):03d}'}.get(DESIGN, '')
    return f'{traffic}{level_part}/p{round(p * 100):03d}/cv{round(cv * 100):02d}/s{k:02d}'


def placements_for(case):
    return bimodal.IMBALANCE_PLACEMENTS if DESIGN == 'u-imbalance' else bimodal.placements(case[0])


def case_dir(output, case):
    return output / label(case)


def runs_for(case):
    return [run for run in RUNS if run[0] in placements_for(case)]


def tables(output):
    return bimodal.solve_tables(json.loads((output / 'calibration/model.json').read_text())['coefficients'])


def prepare_one(output, case, levels):
    target = case_dir(output, case)
    for placement in placements_for(case):
        directory = target / placement
        directory.mkdir(parents=True)
        p, cv, traffic, period, u_cv, k = case
        if DESIGN == 'u-imbalance':
            config = bimodal.imbalance_configuration(u_cv, k, levels, placement)
        else:
            config = bimodal.configuration(p, cv, traffic, k, levels, placement, period=period)
        write_json(directory / 'configuration.json', config)
        prepare(config, directory / 'prepared')
    for placement in placements_for(case):
        for name in ('source/workload.c', 'layout.json'):
            if (target / placement / 'prepared' / name).read_bytes() != (target / 'mixed/prepared' / name).read_bytes():
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
    return {p: file_hash(target / p / 'prepared/manifest.json') for p in placements_for(case)}


def prepare_all(output, workers):
    levels = tables(output)
    if DESIGN == 'u-imbalance':
        model = json.loads((output / 'calibration/model.json').read_text())['coefficients']
        budgets = {b for case in cases() for b in bimodal.imbalance_budgets(case[4], case[5])}
        by_budget = {b: bimodal.solve_tables(model, b) for b in sorted(budgets)}
        levels = by_budget.__getitem__
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
        periods=bimodal.periods(DESIGN), u_cvs=bimodal.u_cvs(DESIGN), job_ns=bimodal.JOB_NS,
        high_center=bimodal.HIGH_CENTER,
        low_center=bimodal.LOW_CENTER, workload_optimization='O2', runs=[r[2] for r in RUNS],
        center_l1_misses=float(tables(output)['center_l1_misses']), design=DESIGN,
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
    so tasks with the same level share one run. A level whose run failed only
    at startup (STARTUP_ERRORS) takes the time model's planned U instead and is
    marked 'model' in the report; any other failure stops the stage.
    """
    plans, sources = {}, {}
    for case in sorted(cases(), key=lambda c: c[5]):
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
        record = load_batch(case_dir(output, case) / 'mixed/prepared',
                            case_dir(output, case) / 'isolated' / task_id)[0]
        if record['execution_status'] != 'ok':
            if not set(record.get('errors', [])) <= STARTUP_ERRORS:
                raise RuntimeError(f'Isolated run failed: {label(case)}/{task_id}: {record.get("errors")}')
            startup.add(key)
            continue
        jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
                if j['task'] == i and j['job'] >= bimodal.WARMUP_JOBS]
        cpu[key] = sum(jobs) / len(jobs)
    report, worst = {}, 0.0
    for case, tasks in plans.items():
        config = {t['task_id']: t for t in json.loads(
            (case_dir(output, case) / 'mixed/configuration.json').read_text())['tasks']}
        period_ns = case[3] * 1e6
        u = {t['task_id']: (config[t['task_id']]['u_planned'] if level_key(t) in startup
                            else cpu[level_key(t)] / period_ns) for t in tasks}
        errors = {t['task_id']: u[t['task_id']] / config[t['task_id']].get('u_target', bimodal.JOB_NS / period_ns) - 1
                  for t in tasks if level_key(t) not in startup}
        worst = max(worst, *(abs(e) for e in errors.values()), 0.0)
        report[label(case)] = dict(utilization=u, relative_error=errors, source={
            t['task_id']: 'model' if level_key(t) in startup else
            '/'.join((label(sources[level_key(t)][0]), sources[level_key(t)][2])) for t in tasks})
    write_json(output / 'isolated-u.json', report)
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    design.announce(f'isolated U gate passed over {len(sources) - len(startup)} measured levels '
                    f'({len(startup)} startup-failed levels use the model): worst relative error {worst:.2%}')


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


def run_state(result):
    """'ok', 'deadline' (any deadline miss), 'startup' (STARTUP_ERRORS only) or 'other'."""
    errors = set(result.get('errors', []))
    if result['execution_status'] == 'ok':
        return 'ok'
    if 'deadline_miss' in errors:
        return 'deadline'
    return 'startup' if errors <= STARTUP_ERRORS else 'other'


def max_response_ratio(result, config):
    """Largest (completion - release) / period over the recorded measured jobs."""
    tasks = config['tasks']
    ratios = [(j['completion_ns'] - j['release_ns']) / (tasks[j['task']]['period_ticks'] * 1e6)
              for j in result['jobs'] if j['job'] >= config['warmup_ticks'] // tasks[j['task']]['period_ticks']
              and j.get('completion_ns') is not None]
    return max(ratios) if ratios else None


def core_imbalance(result, config):
    """Largest over mean of the per-core sums of measured job CPU (by start core)."""
    tasks, load = config['tasks'], [0.0] * bimodal.CORES
    for job in result['jobs']:
        if job['job'] >= config['warmup_ticks'] // tasks[job['task']]['period_ticks']:
            load[job['start_core']] += job['cpu_after_ns'] - job['cpu_before_ns']
    return max(load) / (sum(load) / len(load))


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
        row = dict(mean=case[0], cv=case[1], traffic=case[2], period=case[3], u_cv=case[4], set_id=case[5],
                   modes=[t['mode'] for t in locality], cls=[t['cls'] for t in locality],
                   l1_misses=[t['l1_misses'] for t in locality],
                   isolated_cpu_ns=[u[t['task_id']] * case[3] * 1e6 for t in locality],
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
                task_cpu_ns=task_cpu(result, config) if ok else None,
                state=run_state(result), max_response_ratio=max_response_ratio(result, config),
                core_imbalance=core_imbalance(result, config) if ok else None)
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
    """Paired per-set (as-is gap - matched gap) for every p with matched cells, per CV;
    Holm per metric and pair."""
    fractions = sorted({r['mean'] for r in rows if r['traffic'] == 'matched'})
    out = []
    for metric in stats.METRICS:
        for a, b in PAIRS:
            group = []
            for fraction, cv in ((p, cv) for p in fractions for cv in bimodal.CVS):
                pairs = {}
                for r in rows:
                    if r['mean'] == fraction and r['cv'] == cv:
                        value = stats.gap(r, metric, a, b)
                        if value is not None:
                            pairs.setdefault(r['set_id'], {})[r['traffic']] = value
                diffs = [v['as-is'] - v['matched'] for v in pairs.values() if len(v) == 2]
                entry = dict(metric=metric, pair=f'{a}-{b}', mean=fraction, cv=cv, n=len(diffs))
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


def mcnemar(rows, a, b):
    """Exact McNemar test of schedulability between two configurations on the same sets."""
    pairs = [(r[a]['state'], r[b]['state']) for r in rows
             if {r[a]['state'], r[b]['state']} <= {'ok', 'deadline'}]
    only_a = sum(x == 'ok' and y == 'deadline' for x, y in pairs)
    only_b = sum(x == 'deadline' and y == 'ok' for x, y in pairs)
    p = scipy_stats.binomtest(min(only_a, only_b), only_a + only_b).pvalue if only_a + only_b else 1.0
    return dict(sets=len(pairs), only_a_schedulable=only_a, only_b_schedulable=only_b, exact_p=float(p))


def level_report(output, key):
    """Per-level statistics of the load-level (key 'period') and task-U imbalance (key 'u_cv')
    designs; rows are keyed by the level as 'mean', ordered by increasing load or spread."""
    stats.PAIRS = PAIRS
    rows = [dict(r, mean=r[key]) for r in stats.load(output / 'results.jsonl')]
    levels = sorted({r[key] for r in rows}, reverse=key == 'period')
    keys = [k for _, _, k in RUNS]
    schedulable = {str(level): {k: dict(
        ok=sum(r[k]['state'] == 'ok' for r in rows if r[key] == level),
        deadline=sum(r[k]['state'] == 'deadline' for r in rows if r[key] == level),
        excluded=sum(r[k]['state'] in ('startup', 'other') for r in rows if r[key] == level))
        for k in keys} for level in levels}
    tests = []
    for a, b in PAIRS:
        group = [dict(mcnemar([r for r in rows if r[key] == level], a, b), pair=f'{a}-{b}', level=level)
                 for level in levels]
        for entry, adjusted in zip(group, stats.holm([e['exact_p'] for e in group])):
            entry.update(holm_p=adjusted, significant=adjusted < stats.ALPHA)
        tests.extend(group)
    response = []
    for a, b in PAIRS:
        for level in levels:
            diffs = [r[a]['max_response_ratio'] - r[b]['max_response_ratio'] for r in rows
                     if r[key] == level and r[a]['state'] == r[b]['state'] == 'ok']
            entry = dict(pair=f'{a}-{b}', level=level, n=len(diffs))
            if len(diffs) >= 6 and any(diffs):
                entry.update(median=float(median(diffs)), wilcoxon_p=float(scipy_stats.wilcoxon(diffs).pvalue))
            response.append(entry)
    trends = []
    for metric in stats.METRICS:
        for a, b in PAIRS:
            data = stats.blocked(rows, metric, a, b, 'cv', 0.1, 'mean', levels)
            entry = dict(metric=metric, pair=f'{a}-{b}', levels=levels, blocks=len(data))
            if len(data) >= 5:
                entry.update(friedman_p=float(scipy_stats.friedmanchisquare(*zip(*data)).pvalue),
                             page_increasing_p=float(scipy_stats.page_trend_test(data).pvalue),
                             page_decreasing_p=float(scipy_stats.page_trend_test(
                                 [row[::-1] for row in data]).pvalue))
            trends.append(entry)
    cells = stats.cell_tests(rows)
    result = dict(design=DESIGN, alpha=stats.ALPHA, task_sets=len(rows), pairs=PAIRS,
                  cell_keys=dict(mean=key, cv='cls_cv'), level_order=levels, cells=cells, schedulable=schedulable,
                  schedulability_tests=tests, max_response_ratio_tests=response, trends=trends)
    (output / f'stats-{DESIGN}.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (output / f'stats-{DESIGN}.md').write_text(stats.markdown(cells))
    design.announce(f'wrote {DESIGN} statistics')


def report(output, baseline=None):
    """Write statistics; with a baseline output, its rows join this run's (no overlap)."""
    if DESIGN in LEVEL_KEYS:
        level_report(output, LEVEL_KEYS[DESIGN])
        return
    stats.PAIRS = PAIRS
    rows = stats.load(output / 'results.jsonl')
    if baseline is not None:
        rows += stats.load(baseline / 'results.jsonl')
        with (output / 'results-combined.jsonl').open('w') as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + '\n')
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
    parser.add_argument('--design', choices=tuple(bimodal.DESIGNS), default='main')
    parser.add_argument('--baseline', type=Path, help='stats: output whose rows join this one')
    args = parser.parse_args()
    select_design(args.design)
    output = args.output.resolve()
    if args.stage == 'prepare':
        prepare_all(output, min(args.workers, 32))
        return
    if args.stage == 'stats':
        report(output, args.baseline.resolve() if args.baseline else None)
        return
    check_protocol(output)
    if args.stage == 'isolated':
        isolated(output, args.workers)
    elif args.stage == 'pilot':
        failed, _ = design.run_specs(specs_for(output, [c for c in cases() if c[5] == 0]), args.workers)
        summarize(output)
        if DESIGN in LEVEL_KEYS:
            # Deadline misses are measured outcomes here; stop only on other failures.
            rows = stats.load(output / 'results.jsonl')
            failed = [f"{r[LEVEL_KEYS[DESIGN]]}/{r['set_id']}/{k}" for r in rows for _, _, k in RUNS
                      if r[k].get('state') == 'other']
        if failed:
            raise RuntimeError(f'Pilot runs failed: {failed}')
    elif args.stage == 'full':
        remaining = sorted((c for c in cases() if c[5] != 0), key=lambda c: (c[5], c[2], c[3], c[4], c[0], c[1]))
        failed, _ = design.run_specs(specs_for(output, remaining), args.workers)
        summarize(output)
        if failed:
            design.announce(f'{len(failed)} runs finished with a failed status: {failed}')
    else:
        summarize(output)


if __name__ == '__main__':
    main()
