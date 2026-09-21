"""Build mixed read-side recipe candidates without consulting evaluation data."""

from math import ceil
import json

from chaser.periodic import TICK_NS, make_plan
from chaser.periodic_patterns import job_access_count
from chaser.periodic_recipes import RECIPES, block_size
from tools.rtems_periodic_pool import candidate_pool as legacy_pool
from tools.rtems_periodic_pool import ROOT
from tools.rtems_smoke import file_hash


REVISION = 'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08'
SOURCE_PATHS = {
    'window-coefficient': ['bench/kernel/fir2dim/fir2dim.c',
                          'bench/kernel/filterbank/filterbank.c',
                          'bench/sequential/fmref/fmref.c'],
    'multi-array-reuse': ['bench/kernel/st/st.c', 'bench/kernel/matrix1/matrix1.c'],
    'block-phase': ['bench/kernel/jfdctint/jfdctint.c'],
}


def candidate_pool() -> dict:
    """Enumerate 180 new inputs; inherited CPU costs remain only estimates.

The five coverage cells are selected contrasts, not a Cartesian product of every
role ratio, period and memory layout. V1 inputs are not relabelled or overwritten.
"""
    design = legacy_pool()['design']
    source_path = ROOT / 'rtems/periodic/recipe-sources.json'
    source_manifest = json.loads(source_path.read_text())
    if (source_manifest['revision'] != REVISION
            or {r['path'] for r in source_manifest['files']} !=
               {p for paths in SOURCE_PATHS.values() for p in paths}):
        raise ValueError('Recipe source manifest does not match the declared corpus')
    design.update(version='periodic-candidates-v2',
        profiles=['layout-half', 'l1-half', 'l1-skew', 'llc-one', 'llc-two'],
        target_total_u=[0.5, 1.0, 1.5], widths=[8],
        period_ratios_by_profile={
            'layout-half': [1, 2], 'l1-half': [1, 2], 'l1-skew': [1, 2, 4, 2],
            'llc-one': [1, 2], 'llc-two': [1, 2, 4, 2]},
        role_mix_by_profile={'layout-half': [1, 1], 'l1-half': [1, 1],
                             'l1-skew': [3, 1], 'llc-one': [1, 1], 'llc-two': [1, 1]},
        source_revision=REVISION, pattern_sources=['TACLeBench'],
        source_manifest_hash=file_hash(source_path),
        excluded_pattern_sources=['PolyBench'], recipe_contract='rtems/periodic/RECIPES.md',
        lineage_limit='three conservative recipe groups; one family per proposed split',
        memory_rule='complete blocks; below/above L1, one/two arrays above LLC',
        pending=[*design['pending'], 'only three recipe families; external evaluation is separate'])
    design.pop('period_ratios')
    groups = {group: [p for p, g in RECIPES.items() if g == group] for group in SOURCE_PATHS}
    candidates = []
    for group, patterns in groups.items():
        for count in design['task_counts']:
            for profile in design['profiles']:
                for target in design['target_total_u']:
                    index = len(candidates)
                    tasks, costs = [], []
                    for i in range(count):
                        role = int(i % 4 == 3) if profile == 'l1-skew' else i % 2
                        pattern, width = patterns[role], 8
                        block = block_size(pattern, width)
                        if profile == 'layout-half':
                            blocks, stride = 2, (1, 32, 4096)[i % 3]
                        elif profile in ('l1-half', 'l1-skew'):
                            blocks = max(1, 480 // block) if i % 2 == 0 else ceil(544 / block)
                            stride = 32
                        else:
                            large = i < (1 if profile == 'llc-one' else 2)
                            blocks, stride = (65536 // block + 1 if large else 2), 32
                        task = dict(task_id=f'v2w{index:04d}_t{i:02d}', pattern=pattern,
                                    width=width, distinct=blocks*block, stride=stride,
                                    sweeps=1, core=i % 4)
                        task['sweeps'] = max(2, ceil(10240 / job_access_count(task)))
                        costs.append(job_access_count(task) * design['cpu_estimate_ns_per_load']
                                     * design['cpu_estimate_margin'])
                        tasks.append(task)
                    schedule = design['period_ratios_by_profile'][profile]
                    ratios = [schedule[i % len(schedule)] for i in range(count)]
                    base = ceil(max(sum(c/r for c, r in zip(costs, ratios)) / target,
                                    max(c/r/design['u_max'] for c, r in zip(costs, ratios)))
                                / TICK_NS)
                    for task, ratio in zip(tasks, ratios):
                        task['period_ticks'] = base * ratio
                    config = dict(workload_id=f'candidate-v2-{index:04d}',
                        family_id='pending-lineage-audit',
                        policy_id='candidate-explicit-core-order-not-calibrated-v2',
                        horizon_ticks=4*base, eligible_for_training=False,
                        test_eligible=False, tasks=tasks)
                    plan = make_plan(config, 2)
                    jobs = sum(t['job_count'] for t in plan['tasks'])
                    slots = count * max(t['job_count'] for t in plan['tasks'])
                    if max(jobs, slots) > design['max_jobs']:
                        raise ValueError('Candidate exceeds operating job/slot budget')
                    candidates.append(dict(configuration=config, recipe_id=group,
                        role='candidate', development_exposed=False, profile=profile,
                        source_basis=[f'https://github.com/tacle/tacle-bench/blob/{REVISION}/{p}'
                                      for p in SOURCE_PATHS[group]],
                        target_total_u=target,
                        estimated_cpu_ns=dict(zip((t['task_id'] for t in tasks), costs)),
                        estimated_utilization={t['task_id']: c/(t['period_ticks']*TICK_NS)
                                               for t, c in zip(tasks, costs)},
                        measured_utilization=None, eligibility_status='pending_measurement',
                        logical_jobs=jobs, record_slots=slots))
    return dict(design=design, candidates=candidates, dataset_ready=False, split_frozen=False)
