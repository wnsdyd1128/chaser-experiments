"""Generate a reviewable candidate population before theta or label collection.

The first version is a provisional design, not a measurement-backed final split.
All candidates are preserved; no G/C/P outcome is consulted during generation.
"""

import argparse
from collections import Counter
from math import ceil
from pathlib import Path
import json

from chaser.dataset import Workload, freeze_split
from chaser.periodic import TICK_NS, digest, make_plan
from chaser.periodic_patterns import job_access_count
from chaser.periodic_registry import build_registry
from chaser.periodic_structures import STRUCTURES
from tools.rtems_periodic_probes import configurations as development_probes
from tools.rtems_smoke import check_inputs, file_hash, write_json


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'artifacts/periodic/feasibility-v1'


def candidate_pool() -> dict:
    """Enumerate 240 candidates using explicit, provisional generation rules.

CPU estimates use twice the largest observed development ns/load. This is a
budget heuristic, not measured U, WCET, or a validated transfer model. Final
independent U must be measured from each final P ELF before main eligibility.
"""
    check_inputs(EVIDENCE, json.loads((EVIDENCE / 'manifest.json').read_text()))
    summary = json.loads((EVIDENCE / 'summary.json').read_text())
    costs = []
    for row in summary['workloads']:
        if row.get('characterization'):
            for task in row['tasks']:
                cpu = row['characterization']['tasks'][task['task_id']]['mean_cpu_ns']
                costs.append(cpu / task['loads_per_job'])
    ns_per_load = max(costs)
    design = dict(version='periodic-candidates-v1', status='provisional',
        task_counts=[4, 8, 12, 16], profiles=['layout', 'l1', 'llc'],
        target_total_u=[0.5, 1.5], u_max=0.25, U_max=2.0,
        cpu_estimate_ns_per_load=ns_per_load, cpu_estimate_margin=2.0,
        cpu_estimate_rule='2 * maximum development mean CPU ns/load * job loads',
        period_ratios=[1, 2], horizon_base_periods=4, max_jobs=64,
        sweeps_rule='max(2, ceil(10240 / loads per sweep))',
        period_rule='ceil(max(sum(C_i/r_i)/target_U, max(C_i/r_i/u_max))/tick_ns)',
        expected_runs=10, split_seed=20260921,
        evidence_summary_hash=file_hash(EVIDENCE / 'summary.json'),
        sufficiency_status='not_assessed',
        pending=['estimate transfer validation and numeric bound freeze',
                 'final ELF independent U and common G/C/P eligibility',
                 'initial/expansion family budget and sufficiency thresholds',
                 'full-pool build/analysis/runtime cost and storage budget',
                 'final membership/split freeze before theta calibration'])
    candidates = []
    for pattern in STRUCTURES:
        for count in design['task_counts']:
            for profile in design['profiles']:
                for target in design['target_total_u']:
                    name = f'candidate-{len(candidates):04d}'
                    tasks, estimates = [], []
                    for i in range(count):
                        if profile == 'layout':
                            distinct, stride = 96, (1, 32, 4096)[i % 3]
                        elif profile == 'l1':
                            distinct, stride = (504, 528)[i % 2], 32
                        else:
                            distinct, stride = (65544 if i == 0 else 96), 32
                        task = dict(task_id=f'w{len(candidates):04d}_t{i:02d}', pattern=pattern,
                                    distinct=distinct, stride=stride, sweeps=1, core=i % 4)
                        task['sweeps'] = max(2, ceil(10240 / job_access_count(task)))
                        estimates.append(job_access_count(task) * ns_per_load * 2)
                        tasks.append(task)
                    ratios = [design['period_ratios'][i % 2] for i in range(count)]
                    base = ceil(max(sum(c/r for c, r in zip(estimates, ratios)) / target,
                                    max(c/r/design['u_max'] for c, r in zip(estimates, ratios)))
                                / TICK_NS)
                    for task, ratio in zip(tasks, ratios):
                        task['period_ticks'] = base * ratio
                    config = dict(workload_id=name, family_id='pending-lineage-audit',
                        policy_id='candidate-explicit-core-order-not-calibrated-v1',
                        horizon_ticks=4*base, eligible_for_training=False, test_eligible=False,
                        tasks=tasks)
                    plan = make_plan(config, 2)
                    jobs = sum(t['job_count'] for t in plan['tasks'])
                    if jobs > design['max_jobs']:
                        raise ValueError('Candidate exceeds operating job budget')
                    candidates.append(dict(configuration=config, recipe_id='structure-' + pattern,
                        role='candidate', development_exposed=False, profile=profile,
                        target_total_u=target,
                        estimated_cpu_ns=dict(zip((t['task_id'] for t in tasks), estimates)),
                        estimated_utilization={t['task_id']: c/(t['period_ticks']*TICK_NS)
                                               for t, c in zip(tasks, estimates)},
                        measured_utilization=None, eligibility_status='pending_measurement',
                        logical_jobs=jobs, record_slots=count * max(t['job_count'] for t in plan['tasks'])))
    return dict(design=design, candidates=candidates, dataset_ready=False, split_frozen=False)


def initialize(output: Path, *, version: int = 1) -> dict:
    """Save inputs, audited registry and a split proposal in a fresh directory.

The proposal uses the existing deterministic family splitter but is not a final
experiment freeze. No labels, calibration, build or runtime results are invented.
"""
    if output.exists():
        raise FileExistsError(output)
    if version == 1:
        pool = candidate_pool()
    elif version == 2:
        from tools.rtems_periodic_pool_v2 import candidate_pool as recipe_pool
        pool = recipe_pool()
    else:
        raise ValueError('Unknown candidate pool version')
    history = [dict(configuration=c, recipe_id='development-feasibility-v1',
                    role='development', development_exposed=True) for c in development_probes()]
    registry = build_registry([*history, *pool['candidates']])
    candidates = [r for r in registry['workloads'] if r['primary_candidate']]
    pool['candidates'] = candidates
    output.mkdir(parents=True, exist_ok=False)
    split = freeze_split(output / 'split-proposal.json', [
        Workload(r['workload_id'], r['family_id'], {}, 'pending') for r in candidates],
        seed=pool['design']['split_seed'])
    report = dict(candidate_workloads=len(candidates),
        primary_families=registry['primary_family_count'],
        development_workloads=len(history),
        family_counts=dict(Counter(split['families'].values())),
        workload_counts=dict(Counter(split['families'][r['family_id']] for r in candidates)),
        base_runs_one_policy=10 * sum(len(r['tasks']) + 3 for r in candidates),
        independent_u_runs=10 * sum(len(r['tasks']) for r in candidates),
        timing_runs_one_policy=30 * len(candidates),
        additional_costs='theta mapping search, other policies/alpha, builds, analysis, diagnostics',
        max_jobs=max(r['logical_jobs'] for r in candidates),
        max_record_slots=max(r['record_slots'] for r in candidates),
        pattern_counts=dict(Counter(p for r in candidates
                                    for p in sorted({t['pattern'] for t in r['configuration']['tasks']}))),
        pattern_count_unit='workloads containing pattern; mixed workloads count in both roles',
        recipe_counts=dict(Counter(r['recipe_id'] for r in candidates)),
        max_padded_bytes=max(sum((t['allocated_bytes'] + 4095)//4096*4096
                                 for t in r['tasks']) for r in candidates),
        profile_counts=dict(Counter(r['profile'] for r in candidates)),
        estimated_total_u_range=[min(sum(r['estimated_utilization'].values()) for r in candidates),
                                 max(sum(r['estimated_utilization'].values()) for r in candidates)],
        split_hash=digest(split), dataset_ready=False, split_frozen=False,
        measured_workloads=0, sufficiency_status='not_assessed')
    write_json(output / 'pool.json', pool)
    write_json(output / 'registry.json', registry)
    write_json(output / 'summary.json', report)
    (output / 'configs').mkdir()
    for row in candidates:
        write_json(output / 'configs' / (row['workload_id'] + '.json'), row['configuration'])
    (output / 'implementation').mkdir()
    sources = ['tools/rtems_periodic_pool.py', 'tools/rtems_periodic_probes.py',
               'chaser/periodic.py', 'chaser/periodic_patterns.py',
               'chaser/periodic_structures.py', 'chaser/periodic_recipes.py',
               'chaser/periodic_registry.py', 'chaser/dataset.py',
               'tools/rtems_smoke.py']
    if version == 2:
        sources.extend(['tools/rtems_periodic_pool_v2.py', 'rtems/periodic/RECIPES.md',
                        'rtems/periodic/recipe-sources.json'])
    for source in sources:
        (output / 'implementation' / Path(source).name).write_bytes((ROOT / source).read_bytes())
    files = {str(p.relative_to(output)): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = dict(schema_version=1, files=files, registry_hash=digest(registry),
                    source_evidence={'artifacts/periodic/feasibility-v1/summary.json':
                                     pool['design']['evidence_summary_hash']})
    write_json(output / 'manifest.json', manifest)
    check_inputs(output, manifest)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    print(json.dumps(initialize(args.output, version=args.version), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
