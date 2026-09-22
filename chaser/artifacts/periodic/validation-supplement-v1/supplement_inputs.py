"""Materialize only the four preregistered inputs, preserving the parent split."""

from copy import deepcopy
import json
from pathlib import Path
import shutil

from chaser.periodic import digest, make_plan
from chaser.periodic_registry import taskset_signature
from tools.rtems_smoke import check_inputs, file_hash, write_json
from revalidate import HERE, ROOT, preview


def configurations(manifest):
    """Reconstruct literal configs and require the preregistered identities."""
    configs = []
    for row in manifest['planned_inputs']:
        tasks = []
        for i, task_id in enumerate(row['task_ids']):
            tasks.append(dict(deepcopy(row['role_templates'][i % 2]), task_id=task_id, core=i % 4))
        config = dict(workload_id=row['workload_id'], family_id=row['family_id'],
            policy_id=manifest['initial_policy_id'], horizon_ticks=row['horizon_ticks'],
            eligible_for_training=False, test_eligible=False, tasks=tasks)
        if digest(config) != row['configuration_hash'] or taskset_signature(config) != row['input_signature']:
            raise ValueError('Planned configuration identity differs')
        for arch in range(3):
            if make_plan(config, arch)['plan_hash'] != row['plan_hashes'][str(arch)]:
                raise ValueError('Planned architecture identity differs')
        configs.append(config)
    return configs


def metadata(manifest):
    """Describe an explicit validation extension, not a resampled schema2 split."""
    parent = json.loads((ROOT / manifest['split_path']).read_text())
    assignments = dict(parent['assignments'])
    assignments.update({r['workload_id']: 'validation' for r in manifest['planned_inputs']})
    return dict(schema_version=1, policy_id='validation-only-supplement-v1',
        input_version=manifest['version'], generation_manifest_hash=file_hash(HERE / 'generation-manifest.json'),
        parent_split_hash=file_hash(ROOT / manifest['split_path']),
        parent_population_hash=file_hash(ROOT / manifest['population_path']),
        original_membership_hash=parent['membership_hash'], assignments=assignments,
        projected_split_counts=manifest['validation']['projected_split_counts'],
        workloads=[{k: r[k] for k in ('workload_id', 'family_id', 'recipe_id', 'split_group',
                   'configuration_hash', 'input_signature', 'execution_input_signature')}
                   for r in manifest['planned_inputs']],
        dataset_ready=False, theta_policy_frozen=False)


def materialize(output: Path):
    """Create a new directory; existing inputs are never rewritten."""
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((HERE / 'generation-manifest.json').read_text())
    replay = preview(manifest)
    if any(replay[k] != manifest[k] for k in replay):
        raise ValueError('Generation preview differs')
    configs = configurations(manifest)
    report = metadata(manifest)
    (output / 'configs').mkdir(parents=True)
    for config in configs:
        write_json(output / 'configs' / (config['workload_id'] + '.json'), config)
    shutil.copyfile(HERE / 'generation-manifest.json', output / 'generation-manifest.json')
    shutil.copyfile(ROOT / manifest['split_path'], output / 'parent-split.json')
    shutil.copyfile(ROOT / manifest['population_path'], output / 'parent-population.json')
    write_json(output / 'extension.json', report)
    write_json(output / 'manifest.json', dict(files={str(p.relative_to(output)): file_hash(p)
        for p in sorted(output.rglob('*')) if p.is_file()}))
    return verify_inputs(output)


def verify_inputs(output: Path):
    """Check both file hashes and their independent preregistered identities."""
    manifest = json.loads((HERE / 'generation-manifest.json').read_text())
    replay = preview(manifest)
    if any(replay[k] != manifest[k] for k in replay):
        raise ValueError('Generation preview differs')
    check_inputs(output, json.loads((output / 'manifest.json').read_text()))
    for local, source in [('generation-manifest.json', HERE / 'generation-manifest.json'),
                          ('parent-split.json', ROOT / manifest['split_path']),
                          ('parent-population.json', ROOT / manifest['population_path'])]:
        if file_hash(output / local) != file_hash(source):
            raise ValueError(f'Parent or rule identity differs: {local}')
    for config in configurations(manifest):
        actual = json.loads((output / 'configs' / (config['workload_id'] + '.json')).read_text())
        if actual != config:
            raise ValueError('Materialized configuration differs')
    report = metadata(manifest)
    if json.loads((output / 'extension.json').read_text()) != report:
        raise ValueError('Extension membership differs')
    return report
