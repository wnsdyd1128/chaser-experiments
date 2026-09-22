"""Reproduce the family-corrected input and membership; never overwrite evidence."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tarfile

from chaser.periodic import digest, make_plan
from chaser.periodic_recipes import RECIPES
from chaser.periodic_registry import build_registry, taskset_signature
from tools.rtems_periodic_pool_v2 import recipe_candidates, SOURCE_PATHS
from tools.rtems_periodic_pool_audit import input_signature
from tools.rtems_smoke import file_hash

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def artifacts():
    """Derive the single new input using a fixed cell, without reading timing results."""
    parent_path = ROOT / 'artifacts/periodic/validation-supplement-v1/history/active-population-before-family-correction.json'
    parent = json.loads(parent_path.read_text())
    original_path = ROOT / 'artifacts/periodic/input-freeze-v1/population.json'
    original = json.loads(original_path.read_text())
    archive_path = ROOT / 'artifacts/periodic/candidates-v3/input-pool.tar.gz'
    with tarfile.open(archive_path) as archive:
        pool = json.load(archive.extractfile('pool/pool.json'))
        registry = json.load(archive.extractfile('pool/registry.json'))
    design = deepcopy(pool['design'])
    design.update(task_counts=[10], profiles=['l1-half'], target_total_u=[0.5])
    groups = {'block-phase': [p for p, g in RECIPES.items() if g == 'block-phase']}
    row = recipe_candidates(design, groups, SOURCE_PATHS, version=3)[0]
    config = row['configuration']
    config.update(workload_id='validation-supplement-v2-0001',
                  policy_id='validation-supplement-v2-explicit-core-order-not-calibrated')
    for i, task in enumerate(config['tasks']):
        task['task_id'] = f'vs2w0001_t{i:02d}'
    # Registry uses config/lineage only; remove estimate maps keyed by temporary IDs.
    row.pop('estimated_cpu_ns')
    row.pop('estimated_utilization')
    audited = build_registry([*registry['workloads'], row])
    new = next(r for r in audited['workloads'] if r['workload_id'] == config['workload_id'])
    config = new['configuration']
    assert new['primary_candidate'] and not new['family_development_exposed']
    prior_configs = [r['configuration'] for r in registry['workloads'] + pool['duplicate_candidates']]
    prior_signatures = {taskset_signature(c) for c in prior_configs}
    prior_signatures.update(r['input_signature'] for r in parent['workloads'])
    assert taskset_signature(config) not in prior_signatures
    plans = [make_plan(config, a) for a in range(3)]
    member = dict(workload_id=config['workload_id'], family_id=config['family_id'],
        recipe_id='block-phase', split_group='validation', configuration_hash=digest(config),
        input_signature=taskset_signature(config), execution_input_signature=input_signature(config))
    removed = 'validation-supplement-v1-0001'
    old = next(r for r in parent['workloads'] if r['workload_id'] == removed)
    assert old['recipe_id'] == 'window-coefficient'
    active = sorted([r for r in parent['workloads'] if r['workload_id'] != removed] + [member],
                    key=lambda r: r['workload_id'])
    assert len(active) == len({r['input_signature'] for r in active}) == 207
    assignments = {r['workload_id']: r['split_group'] for r in active}
    counts = dict(Counter(assignments.values()))
    assert counts == {'train':126, 'validation':41, 'test':40}
    family_counts = lambda rows: {recipe: dict(Counter(r['split_group'] for r in rows if r['recipe_id']==recipe))
                                 for recipe in sorted({r['recipe_id'] for r in rows})}
    assert family_counts(active) == family_counts(original['workloads'])
    for group in ('train','test'):
        assert {n for n,g in assignments.items() if g==group} == {n for n,g in parent['assignments'].items() if g==group}
    membership = dict(schema_version=1, dataset_version='active-population-replacement-v2',
        supersedes=str(parent_path.relative_to(ROOT)), assignments=assignments, workloads=active,
        excluded=[*parent['excluded'],dict(old,reason='family_balance_correction_not_measurement_failure',
            exclusion_scope='entire taskset from active calibration/training/labels/primary evaluation',
            raw_evidence_preserved=True)], active_tasksets=207, archived_tasksets=212, excluded_tasksets=5,
        active_split_counts=counts, per_recipe=family_counts(active), membership_hash=digest(active),
        added_workload_ids=sorted([n for n in parent['added_workload_ids'] if n!=removed]+[config['workload_id']]),
        pending_measurement_workload_ids=[config['workload_id']], theta_policy_frozen=False,
        final_labels_ready=False, consumer_integration='pending calibration loader integration',
        family_counts_match_original=True,
        limitations=['Family counts restored; task count, role mix and parameters are not pairwise matched to failed originals',
                     'New input is statically validated only; final ELF, U and G/C/P are pending'])
    sources = [parent_path, original_path, archive_path, Path(__file__).resolve(),
        *[ROOT/p for p in ('tools/rtems_periodic_pool_v2.py','chaser/periodic.py',
            'chaser/periodic_registry.py','chaser/periodic_recipes.py','chaser/periodic_patterns.py',
            'chaser/periodic_structures.py','chaser/periodic_staged_recipes.py',
            'tools/rtems_periodic_pool_audit.py')]]
    generation = dict(schema_version=1, version='validation-supplement-v2',
        replaces_active_workload=removed, seed=None, selection='fixed block-phase cell; no random selection or outcome-based retries',
        design=design, generator='tools.rtems_periodic_pool_v2.recipe_candidates',
        id_rule='workload validation-supplement-v2-0001; tasks vs2w0001_t00..t09',
        source_hashes={str(p.relative_to(ROOT)):file_hash(p) for p in sources},
        configuration_hash=digest(config), input_signature=member['input_signature'],
        plan_hashes={str(a):p['plan_hash'] for a,p in enumerate(plans)},
        static_plans_checked=3, duplicate_count=0, runtime_runs=0,
        expected_u_runs=100, expected_gcp_runs=30,
        rule='ten tasks, l1-half, target U 0.5; preserve V3 sweeps/period formula; no candidate replacement on failure')
    return {'configuration.json':config,'generation-manifest.json':generation,'active-population.json':membership}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    generated=artifacts()
    if args.output:
        args.output.mkdir(parents=True,exist_ok=False)
        for name,data in generated.items():
            (args.output/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    else:
        for name,data in generated.items():
            assert json.loads((HERE/name).read_text())==data, name
        print('PASS: input replay, 3 plans, no duplicates, original family counts, 207 active inputs, train/test unchanged')


if __name__=='__main__':
    main()
