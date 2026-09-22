"""Replay the premeasurement supplement preview without preparing or measuring inputs."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tarfile

from chaser.periodic import digest, make_plan
from chaser.periodic_recipes import RECIPES
from chaser.periodic_registry import build_registry, taskset_signature
from tools.rtems_periodic_pool_audit import input_signature
from tools.rtems_periodic_pool_v2 import SOURCE_PATHS, recipe_candidates
from tools.rtems_periodic_pool_v3 import NEW_SOURCES
from tools.rtems_smoke import file_hash


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def preview(manifest):
    """Reconstruct four planned identities and audit them against archived inputs.

    Only static input metadata is read. This does not use U, timing, labels or
    calibration outcomes, and does not create configs or a runnable split.
    """
    for relative, expected in manifest['source_hashes'].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError(f'Source changed: {relative}')
    with tarfile.open(ROOT / manifest['source_archive']) as archive:
        pool = json.load(archive.extractfile('pool/pool.json'))
        registry = json.load(archive.extractfile('pool/registry.json'))
    population = json.loads((ROOT / manifest['population_path']).read_text())
    split = json.loads((ROOT / manifest['split_path']).read_text())
    assert digest(pool['design']) == manifest['base_design_hash']
    assert build_registry(registry['workloads']) == registry
    original = {r['workload_id']: r for r in pool['candidates']}
    assert len(original) == len(population['workloads']) == 207
    assert set(original) == set(split['assignments'])
    for row in population['workloads']:
        config = original[row['workload_id']]['configuration']
        signature = taskset_signature(config)
        assert digest(config) == row['configuration_hash']
        assert signature == row['input_signature'] == split['input_signatures'][row['workload_id']]
        assert row['split_group'] == split['assignments'][row['workload_id']]

    families = {r['family_id']: r['recipe_id'] for r in pool['candidates']}
    ranking = sorted((dict(family_id=f, recipe_id=r,
                          selection_hash=digest([manifest['version'], manifest['seed'], f]))
                      for f, r in families.items()),
                     key=lambda r: (r['selection_hash'], r['family_id']))
    chosen = ranking[:manifest['count']]
    groups = {r['recipe_id']: [p for p, g in RECIPES.items() if g == r['recipe_id']]
              for r in chosen}
    design = deepcopy(pool['design'])
    design.update(manifest['design_overrides'])
    generated = recipe_candidates(design, groups, {**SOURCE_PATHS, **NEW_SOURCES}, version=3)
    assert len(generated) == 4
    for index, row in enumerate(generated):
        config = row['configuration']
        config['workload_id'] = f"{manifest['version']}-{index + 1:04d}"
        config['policy_id'] = manifest['initial_policy_id']
        renames = {}
        for i, task in enumerate(config['tasks']):
            new_id = f'vs1w{index + 1:04d}_t{i:02d}'
            renames[task['task_id']] = new_id
            task['task_id'] = new_id
        for key in ('estimated_cpu_ns', 'estimated_utilization'):
            row[key] = {renames[k]: v for k, v in row[key].items()}
    # Joint lineage audit catches accidental merging or development exposure.
    combined = build_registry([*registry['workloads'], *generated])
    audited = {r['workload_id']: r for r in combined['workloads']}
    for name, row in original.items():
        assert audited[name]['family_id'] == row['family_id']
    old_configs = [r['configuration'] for r in registry['workloads']]
    old_configs += [r['configuration'] for r in pool['duplicate_candidates']]
    seen = {taskset_signature(c) for c in old_configs}
    old_ids = {c['workload_id'] for c in old_configs}
    old_task_ids = {t['task_id'] for c in old_configs for t in c['tasks']}
    inputs = []
    for index, generated_row in enumerate(generated):
        row = audited[generated_row['configuration']['workload_id']]
        config = row['configuration']
        signature = taskset_signature(config)
        assert signature not in seen
        seen.add(signature)
        assert config['workload_id'] not in old_ids
        assert not old_task_ids.intersection(t['task_id'] for t in config['tasks'])
        old_task_ids.update(t['task_id'] for t in config['tasks'])
        assert row['family_id'] == chosen[index]['family_id']
        assert row['primary_candidate'] and not row['family_development_exposed']
        plans = [make_plan(config, a) for a in range(3)]
        plan = plans[2]
        jobs = sum(t['job_count'] for t in plan['tasks'])
        slots = len(plan['tasks']) * max(t['job_count'] for t in plan['tasks'])
        assert max(jobs, slots) <= design['max_jobs']
        assert max(row['estimated_utilization'].values()) <= design['u_max']
        assert sum(row['estimated_utilization'].values()) <= design['U_max']
        inputs.append(dict(workload_id=config['workload_id'], family_id=row['family_id'],
            recipe_id=row['recipe_id'], split_group='validation',
            configuration_hash=digest(config), input_signature=signature,
            execution_input_signature=input_signature(config), task_count=len(config['tasks']),
            task_ids=[t['task_id'] for t in config['tasks']],
            role_templates=[{k: v for k, v in t.items() if k not in ('task_id', 'core')}
                            for t in config['tasks'][:2]],
            horizon_ticks=config['horizon_ticks'], logical_jobs=jobs, record_slots=slots,
            padded_data_bytes=sum((t['data_size'] + 4095) // 4096 * 4096 for t in plan['tasks']),
            estimated_total_u=sum(row['estimated_utilization'].values()),
            plan_hashes={str(p['architecture']): p['plan_hash'] for p in plans}))
    assignments = dict(split['assignments'])
    assignments.update({r['workload_id']: 'validation' for r in inputs})
    return dict(family_ranking=ranking, planned_inputs=inputs,
        validation=dict(original_tasksets=207, original_duplicate_aliases=93,
            original_development_inputs=len(registry['workloads']) - 207,
            original_membership_hash=split['membership_hash'],
            new_unique_tasksets=len(inputs), static_plans_checked=3 * len(inputs),
            original_split_counts=dict(Counter(split['assignments'].values())),
            projected_split_counts=dict(Counter(assignments.values())),
            projected_assignments_hash=digest(assignments),
            independent_u_runs=10 * sum(r['task_count'] for r in inputs),
            timing_runs_one_policy=30 * len(inputs),
            collision_count=0, original_family_ids_unchanged=True,
            runnable_inputs_prepared=False, runtime_runs_collected=0))


def main():
    manifest = json.loads((HERE / 'generation-manifest.json').read_text())
    result = preview(manifest)
    for key in ('family_ranking', 'planned_inputs', 'validation'):
        if result[key] != manifest[key]:
            raise ValueError(f'Preview differs from frozen manifest: {key}')
    print(json.dumps(dict(status='pass', manifest_sha256=file_hash(HERE / 'generation-manifest.json'),
                         **result['validation']), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
