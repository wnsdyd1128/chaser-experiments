"""Experiment 47 runner: CHASER's placement steps on real low-locality task sets (lowloc_set), main chaser package.

Stages (EXPERIMENTS.md 47):
  prepare    per case: build the U-balanced (wfd) mapping, analyze its P ELF with YARDA hierarchy-rd (kernel_yarda),
             check that every low task has HARA CLS <= 0.5 and every high task above (stops otherwise), then build
             cgb (balanced CLS grouping), ra (release-aware from wfd, no group) and ra-cgb (CHASER) with
             chaser.policy.pfirst on the HARA values; each build gets a configuration.json in rt_metrics' layout
  isolated   every task of set 0 of each cell and load alone (wfd build, P, mode i+1): measured U within U_TOLERANCE
             of the planned U; tasks whose ELF fails at startup are recorded and left out, as in kernel_run
  full       the four builds under P for every case
  summarize  results.jsonl rows (heaviness, load, set_id; p, p_cgb, p_ra, p_racgb with state, tet_ns, tat_ns)
Run with PYTHONPATH=<workspace>:policy-mix:period-distribution.
Usage: python3 lowloc_run.py <stage> --output <dir> [--design NAME] [--workers N]   (lowloc_set.DESIGNS)
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import kernel_yarda
import lowloc_set as ls
import run as design
from chaser.periodic.build import prepare
from chaser.policy.pfirst import inputs, placement
from tools.rtems_smoke import write_json

BUILDS = (('wfd', 'p'), ('cgb', 'p_cgb'), ('ra', 'p_ra'), ('ra-cgb', 'p_racgb'))
U_TOLERANCE = 0.03
STARTUP_ERRORS = {'arm_phase', 'release_mismatch'}


def case_dir(output: Path, case) -> Path:
    return output / ls.label(case)


def plan_tasks(planned) -> list[dict]:
    return [dict(task_id=t['task_id'], u=t['u'], period=t['period']) for t in planned]


def rt_configuration(planned, cores) -> dict:
    """The fields rt_metrics.metrics reads (hl_run's configuration layout)."""
    return dict(warmup_ticks=ls.WARMUP_HYPERPERIODS * ls.HYPERPERIOD,
                horizon_ticks=(ls.WARMUP_HYPERPERIODS + ls.MEASURED_HYPERPERIODS) * ls.HYPERPERIOD,
                tasks=[dict(task_id=t['task_id'], role=t['role'], kernel=t['kernel'], sweeps=t['sweeps'], n=t['n'],
                            period_ticks=t['period'], u_planned=t['u'], core=c) for t, c in zip(planned, cores)])


def prepare_one(output: Path, case) -> None:
    target = case_dir(output, case)
    planned = ls.tasks(*case)
    wfd = placement.wfd([dict(u=t['u'], period=t['period'], cls=1.0) for t in planned])
    prepare(ls.configuration(case, wfd), target / 'wfd' / 'prepared')
    kernel_yarda.analyze(target / 'wfd' / 'prepared')
    values = inputs.load_analysis(target / 'wfd' / 'prepared', plan_tasks(planned))
    wrong = [t['task_id'] for t, v in zip(planned, values) if (v['cls'] <= placement.CLS_LOW) != (t['role'] == 'low')]
    if wrong:
        raise RuntimeError(f'{ls.label(case)}: HARA CLS disagrees with the planned role for {wrong}')
    seed = ls.SEED_BASE + case[2]
    mappings = {'wfd': wfd, 'cgb': placement.grouped_balanced(values),
                'ra': placement.release_aware_grouped([dict(v, cls=1.0) for v in values], seed),
                'ra-cgb': placement.release_aware_grouped(values, seed)}
    for build, cores in mappings.items():
        if build != 'wfd':
            prepare(ls.configuration(case, cores), target / build / 'prepared')
        write_json(target / build / 'configuration.json', rt_configuration(planned, cores))
    write_json(target / 'design.json', dict(period_cv=case[0], load=case[1], set_id=case[2], seed=seed, tasks=planned,
                                            realized=ls.realized(case), mappings=mappings,
                                            task_values=[{k: v[k] for k in ('task_id', 'cls', 'rate', 'p_mem', 'working_set_kib')}
                                                         for v in values]))


def prepare_all(output: Path, workers: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    todo = [c for c in ls.cases() if not (case_dir(output, c) / 'design.json').exists()]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case): case for case in todo}
        for future in as_completed(futures):
            future.result()
            design.announce(f'prepared {ls.label(futures[future])}')


def state(record: dict) -> str:
    errors = set(record.get('errors', []))
    if record['execution_status'] == 'ok':
        return 'ok'
    if 'deadline_miss' in errors:
        return 'deadline'
    return 'startup' if errors <= STARTUP_ERRORS else 'other'


def isolated(output: Path, workers: int) -> None:
    sample = [c for c in ls.cases() if c[2] == 0]
    specs = []
    for case in sample:
        prepared = case_dir(output, case) / 'wfd/prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        specs += [(f'{ls.label(case)}/isolated/{t["task_id"]}', prepared, case_dir(output, case) / 'isolated' / t['task_id'],
                   'p', i + 1) for i, t in enumerate(plan['tasks'])]
    _, infra = design.run_specs(specs, workers)
    if infra:
        raise RuntimeError(f'Isolated runs produced no run header: {infra}')
    report, worst = {}, 0.0
    for case in sample:
        prepared = case_dir(output, case) / 'wfd/prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        planned = {t['task_id']: t['u'] for t in json.loads((case_dir(output, case) / 'design.json').read_text())['tasks']}
        u, startup = {}, []
        for i, t in enumerate(plan['tasks']):
            record = json.loads((case_dir(output, case) / 'isolated' / t['task_id'] / 'measurements.jsonl').read_text().splitlines()[0])
            if state(record) == 'startup':
                startup.append(t['task_id'])
                continue
            if record['execution_status'] != 'ok':
                raise RuntimeError(f'Isolated run failed: {ls.label(case)}/{t["task_id"]}: {record.get("errors")}')
            jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
                    if j['task'] == i and j['job'] >= plan['warmup_ticks'] // t['period_ticks']]
            u[t['task_id']] = sum(jobs) / len(jobs) / (t['period_ticks'] * 1e6)
        errors = {tid: u[tid] / planned[tid] - 1 for tid in u}
        worst = max(worst, *(abs(e) for e in errors.values()), 0.0)
        report[ls.label(case)] = dict(utilization=u, relative_error=errors, startup_failed=startup)
    write_json(output / 'isolated-u.json', report)
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    design.announce(f'isolated U gate passed on set 0 of every cell and load: worst relative error {worst:.2%}')


def full(output: Path, workers: int) -> None:
    specs = [(f'{ls.label(case)}/{key}', case_dir(output, case) / build / 'prepared', case_dir(output, case) / build / 'p', 'p', 0)
             for case in sorted(ls.cases(), key=lambda c: (c[2], c[1], c[0])) for build, key in BUILDS]
    failed, _ = design.run_specs(specs, workers)
    if failed:
        design.announce(f'{len(failed)} runs finished with a failed status')


def summarize(output: Path) -> None:
    rows = []
    for case in ls.cases():
        cv, load, k = case
        row = dict(heaviness=ls.heaviness(cv), load=load, set_id=k)
        for build, key in BUILDS:
            path = case_dir(output, case) / build / 'p' / 'measurements.jsonl'
            record = json.loads(path.read_text().splitlines()[0]) if path.exists() else None
            row[key] = dict(state='absent') if record is None or 'header' not in record else \
                dict(state=state(record), status=record['execution_status'], errors=record.get('errors', []),
                     tet_ns=record.get('tet_ns'), tat_ns=record.get('tat_ns'))
        rows.append(row)
    (output / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    counts = {key: {} for _, key in BUILDS}
    for r in rows:
        for _, key in BUILDS:
            counts[key][r[key]['state']] = counts[key].get(r[key]['state'], 0) + 1
    design.announce(f'summarized {len(rows)} cases {counts}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'isolated', 'full', 'summarize'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    parser.add_argument('--design', default='lowloc-kernels', choices=sorted(ls.DESIGNS))
    args = parser.parse_args()
    ls.select(args.design)
    output = args.output.resolve()
    if args.stage == 'prepare':
        prepare_all(output, min(args.workers, 32))
    elif args.stage == 'isolated':
        isolated(output, args.workers)
    elif args.stage == 'full':
        full(output, args.workers)
    else:
        summarize(output)


if __name__ == '__main__':
    main()
