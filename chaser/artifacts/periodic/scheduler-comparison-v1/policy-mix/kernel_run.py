"""Experiment 45 runner: real-kernel task sets on the main chaser package, with the frozen pre-run check.

Stages (EXPERIMENTS.md 45):
  prepare    per case: build the U-balanced (wfd) mapping, analyze it with YARDA (chaser.periodic.analysis), place
             CHASER's ra-cgb with chaser.policy.pfirst on the YARDA CLS, build that mapping too
  isolated   every task of set 0 of each load alone (P, mode i+1): measured U within U_TOLERANCE of the planned U
  decide     chaser.policy.pfirst.decision.decide per case before any measured run -> decisions.json (+ sha256)
  full       CHASER under P and the wfd build under G4, C1+3, C1+1+2 for every case
  summarize  results.jsonl rows (heaviness 'real', load, set_id, p_racgb, g, c, c2 states) for confirm_analysis
Run with PYTHONPATH=<workspace>:policy-mix:period-distribution.
Usage: python3 kernel_run.py <stage> --output <dir> [--policy <frozen policy dir>] [--workers N]
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import kernel_set as ks
import run as design
from chaser.periodic.analysis import analyze
from chaser.periodic.build import prepare
from chaser.policy.pfirst import decision, features, inputs, placement
from tools.rtems_smoke import write_json

RUNS = (('ra-cgb', 'p', 'p_racgb'), ('wfd', 'g', 'g'), ('wfd', 'c', 'c'), ('wfd', 'c2', 'c2'))
U_TOLERANCE = 0.03
STARTUP_ERRORS = {'arm_phase', 'release_mismatch'}


def case_dir(output: Path, case) -> Path:
    return output / ks.label(case)


def plan_tasks(planned) -> list[dict]:
    return [dict(task_id=t['task_id'], u=t['u'], period=t['period']) for t in planned]


def prepare_one(output: Path, case) -> None:
    load, k = case
    target = case_dir(output, case)
    planned = ks.tasks(load, k)
    wfd = placement.wfd([dict(u=t['u'], period=t['period'], cls=1.0) for t in planned])
    prepare(ks.configuration(load, k, wfd), target / 'wfd' / 'prepared')
    analyze(target / 'wfd' / 'prepared')
    values = inputs.load_analysis(target / 'wfd' / 'prepared', plan_tasks(planned))
    chaser = placement.release_aware_grouped(values, ks.SEED_BASE + k)
    prepare(ks.configuration(load, k, chaser), target / 'ra-cgb' / 'prepared')
    write_json(target / 'design.json', dict(load=load, set_id=k, seed=ks.SEED_BASE + k, tasks=planned,
                                            realized=ks.realized(load, k), mappings=dict(wfd=wfd, chaser=chaser)))


def prepare_all(output: Path, workers: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one, output, case): case for case in ks.cases()}
        for future in as_completed(futures):
            future.result()
            design.announce(f'prepared {ks.label(futures[future])}')


def isolated(output: Path, workers: int) -> None:
    sample = [c for c in ks.cases() if c[1] == 0]
    specs = []
    for case in sample:
        prepared = case_dir(output, case) / 'wfd/prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        specs += [(f'{ks.label(case)}/isolated/{t["task_id"]}', prepared, case_dir(output, case) / 'isolated' / t['task_id'], 'p', i + 1)
                  for i, t in enumerate(plan['tasks'])]
    failed, infra = design.run_specs(specs, workers)
    if infra:
        raise RuntimeError(f'Isolated runs produced no run header: {infra}')
    report, worst = {}, 0.0
    for case in sample:
        prepared = case_dir(output, case) / 'wfd/prepared'
        plan = json.loads((prepared / 'p/plan.json').read_text())
        planned = {t['task_id']: t['u'] for t in json.loads((case_dir(output, case) / 'design.json').read_text())['tasks']}
        u, startup = {}, []
        for i, t in enumerate(plan['tasks']):
            directory = case_dir(output, case) / 'isolated' / t['task_id']
            record = json.loads((directory / 'measurements.jsonl').read_text().splitlines()[0])
            if state(record) == 'startup':  # arming crossed a tick in this ELF: missing, as in hl_run's gate
                startup.append(t['task_id'])
                continue
            if record['execution_status'] != 'ok':
                raise RuntimeError(f'Isolated run failed: {ks.label(case)}/{t["task_id"]}: {record.get("errors")}')
            jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs']
                    if j['task'] == i and j['job'] >= plan['warmup_ticks'] // t['period_ticks']]
            u[t['task_id']] = sum(jobs) / len(jobs) / (t['period_ticks'] * 1e6)
        errors = {tid: u[tid] / planned[tid] - 1 for tid in u}
        worst = max(worst, *(abs(e) for e in errors.values()), 0.0)
        report[ks.label(case)] = dict(utilization=u, relative_error=errors, startup_failed=startup)
    write_json(output / 'isolated-u.json', report)
    if worst > U_TOLERANCE:
        raise RuntimeError(f'Isolated U error {worst:.2%} exceeds {U_TOLERANCE:.0%}')
    design.announce(f'isolated U gate passed on set 0 of every load: worst relative error {worst:.2%}')


def measured_runs(output: Path) -> list[Path]:
    return [p for p in output.glob('*/u*/s*/*/*/measurements.jsonl') if p.parent.parent.name != 'isolated']


def decide(output: Path, policy_dir: Path) -> None:
    if measured_runs(output):
        raise SystemExit(f'{output}: measured runs exist; decisions must precede every run')
    policy = decision.Policy(policy_dir.resolve())
    cases = {}
    for case in ks.cases():
        target = case_dir(output, case)
        meta = json.loads((target / 'design.json').read_text())
        values = inputs.load_analysis(target / 'wfd/prepared', plan_tasks(meta['tasks']))
        start = time.perf_counter()
        record = decision.decide(values, policy, meta['seed'])
        seconds = time.perf_counter() - start
        prepared = {b: [t['core'] for t in json.loads((target / b / 'prepared/p/plan.json').read_text())['tasks']]
                    for b in ('wfd', 'ra-cgb')}
        if decision.CHASER in record['mappings'] and record['mappings'][decision.CHASER] != prepared['ra-cgb']:
            raise RuntimeError(f'{target}: pfirst CHASER mapping differs from the prepared ra-cgb build')
        if 'g' in record['mappings'] and record['mappings']['g'] != prepared['wfd']:
            raise RuntimeError(f'{target}: pfirst U-balanced mapping differs from the prepared wfd build')
        demand = features.set_features(values)
        cases[ks.label(case)] = dict(status=record['status'], choice=record['choice'], probabilities=record['probabilities'],
                                     nominal=record['nominal'], static_rule=record['static_rule'], reasons=record['reasons'],
                                     cache_demand=demand['cache_demand'], memory_demand=demand['memory_demand'],
                                     occupancy=demand['occupancy'], decide_seconds=seconds,
                                     task_values=[{k: v[k] for k in ('task_id', 'cls', 'rate', 'p_mem', 'working_set_kib')} for v in values])
    path = output / 'decisions.json'
    write_json(path, dict(policy=str(policy_dir), model_sha256=policy.spec['model_sha256'], tau=policy.tau,
                          static_threshold=decision.STATIC_THRESHOLD, decided_utc=datetime.now(timezone.utc).isoformat(), cases=cases))
    (output / 'decisions.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '\n')
    counts = {}
    for c in cases.values():
        counts[c['status']] = counts.get(c['status'], 0) + 1
    design.announce(f'wrote {path} {len(cases)} cases {counts}')


def full(output: Path, workers: int) -> None:
    specs = [(f'{ks.label(case)}/{key}', case_dir(output, case) / build / 'prepared', case_dir(output, case) / build / arch, arch, 0)
             for case in sorted(ks.cases(), key=lambda c: (c[1], c[0])) for build, arch, key in RUNS]
    failed, _ = design.run_specs(specs, workers)
    if failed:
        design.announce(f'{len(failed)} runs finished with a failed status')


def state(record: dict) -> str:
    errors = set(record.get('errors', []))
    if record['execution_status'] == 'ok':
        return 'ok'
    if 'deadline_miss' in errors:
        return 'deadline'
    return 'startup' if errors <= STARTUP_ERRORS else 'other'


def summarize(output: Path) -> None:
    rows = []
    for case in ks.cases():
        load, k = case
        row = dict(heaviness=ks.HEAVINESS, load=load, set_id=k)
        for build, arch, key in RUNS:
            path = case_dir(output, case) / build / arch / 'measurements.jsonl'
            record = json.loads(path.read_text().splitlines()[0]) if path.exists() else None
            row[key] = dict(state='absent') if record is None or 'header' not in record else \
                dict(state=state(record), status=record['execution_status'], errors=record.get('errors', []))
        rows.append(row)
    (output / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    counts = {key: {} for _, _, key in RUNS}
    for r in rows:
        for _, _, key in RUNS:
            counts[key][r[key]['state']] = counts[key].get(r[key]['state'], 0) + 1
    design.announce(f'summarized {len(rows)} cases {counts}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('prepare', 'isolated', 'decide', 'full', 'summarize'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == 'prepare':
        prepare_all(output, min(args.workers, 32))
    elif args.stage == 'isolated':
        isolated(output, args.workers)
    elif args.stage == 'decide':
        decide(output, args.policy)
    elif args.stage == 'full':
        full(output, args.workers)
    else:
        summarize(output)


if __name__ == '__main__':
    main()
