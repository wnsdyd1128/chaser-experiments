"""Freeze audited V3 inputs and a within-family split before U or calibration."""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from chaser.dataset import Workload, freeze_split
from chaser.periodic import digest, make_plan
from chaser.periodic_registry import build_registry, taskset_signature
from chaser.splits import taskset_split, validate_taskset_split
from tools.rtems_periodic_pool_audit import input_signature
from tools.rtems_smoke import check_inputs, file_hash, write_json


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = ('tools/rtems_periodic_freeze.py', 'chaser/dataset.py', 'chaser/splits.py',
                  'chaser/periodic_registry.py', 'chaser/periodic.py',
                  'tools/rtems_periodic_pool_audit.py', 'tools/rtems_smoke.py')


def _population(source: Path) -> tuple[dict, list[Workload], dict]:
    manifest = json.loads((source / 'manifest.json').read_text())
    check_inputs(source, manifest)
    pool = json.loads((source / 'pool.json').read_text())
    registry = json.loads((source / 'registry.json').read_text())
    if pool['design']['version'] != 'periodic-candidates-v3':
        raise ValueError('Freeze requires the audited V3 population')
    if build_registry(registry['workloads']) != registry:
        raise ValueError('Registry differs from source configurations')
    rows = [r for r in registry['workloads'] if r['primary_candidate']]
    if pool['candidates'] != rows:
        raise ValueError('Candidate population differs from registry')
    workloads, records = [], {}
    for row in rows:
        name, config = row['workload_id'], row['configuration']
        if (digest(config) != row['configuration_hash'] or
                json.loads((source / 'configs' / (name + '.json')).read_text()) != config):
            raise ValueError('Candidate configuration mismatch')
        for arch in range(3):
            make_plan(config, arch)
        signature = taskset_signature(config)
        workloads.append(Workload(name, row['family_id'], {}, 'pending', signature))
        records[name] = dict(workload_id=name, family_id=row['family_id'],
            recipe_id=row['recipe_id'], configuration_hash=digest(config),
            execution_input_signature=input_signature(config), input_signature=signature)
    if len({w.input_signature for w in workloads}) != len(workloads):
        raise ValueError('Candidate tasksets must be deduplicated before freezing')
    excluded = []
    seen = set(records)
    for row in pool['duplicate_candidates']:
        original = records[row['duplicate_of']]
        name = row['configuration']['workload_id']
        if (name in seen or row['exclusion_reason'] != 'duplicate_generator_input' or
                input_signature(row['configuration']) != original['execution_input_signature'] or
                taskset_signature(row['configuration']) != original['input_signature']):
            raise ValueError('Duplicate input does not match its representative')
        seen.add(name)
        excluded.append(dict(workload_id=name, duplicate_of=row['duplicate_of'],
                             exclusion_reason=row['exclusion_reason'],
                             input_signature=original['input_signature']))
    if len(seen) != pool['design']['generated_candidate_workloads']:
        raise ValueError('Incomplete candidate accounting')
    population = dict(schema_version=1, input_version='periodic-input-freeze-v1',
        source_manifest_hash=file_hash(source / 'manifest.json'),
        source_pool_hash=file_hash(source / 'pool.json'),
        identity_rule='ordered workload inputs excluding names, eligibility, policy_id and core',
        excluded_development_workloads=[r['workload_id'] for r in registry['workloads']
                                        if not r['primary_candidate']],
        workloads=list(records.values()), excluded_duplicates=excluded)
    return population, workloads, pool


def _reports(population: dict, pool: dict, split: dict) -> tuple[dict, dict]:
    for row in population['workloads']:
        row['split_group'] = split['assignments'][row['workload_id']]
    for row in population['excluded_duplicates']:
        row['split_group'] = split['assignments'][row['duplicate_of']]
    design = pool['design']
    rows = pool['candidates']
    counts = dict(Counter(split['assignments'].values()))
    report = dict(schema_version=1, input_version=population['input_version'],
        candidate_workloads=len(rows), primary_families=len(split['family_counts']),
        workload_counts=counts,
        family_counts={g: sum(c[g] > 0 for c in split['family_counts'].values()) for g in counts},
        per_family=[dict(family_id=f, recipe_id=next(r['recipe_id'] for r in rows
                                                   if r['family_id'] == f), **c)
                    for f, c in split['family_counts'].items()],
        excluded_duplicate_workloads=len(population['excluded_duplicates']),
        excluded_development_workloads=len(population['excluded_development_workloads']),
        split_policy=split['policy_id'], seed=split['seed'],
        split_hash=digest(split), membership_hash=split['membership_hash'],
        population_hash=digest(population), plans_validated=3 * len(rows),
        independent_u_runs=design['expected_runs'] * sum(len(r['tasks']) for r in rows),
        timing_runs_one_policy=3 * design['expected_runs'] * len(rows),
        expected_runs=design['expected_runs'], u_max=design['u_max'], U_max=design['U_max'],
        inputs_frozen=True, split_frozen=True, dataset_ready=False, measured_workloads=0,
        sufficiency_status='not_assessed',
        population_rule='fixed V3 tasksets; preserve failures and exclusions; no replacement',
        bound_rule='measured independent U must meet u_max/U_max; estimates do not establish feasibility',
        pending=['final ELF analysis and independent U', 'wall-time/storage and calibration budget',
                 'validation theta/policy calibration', 'common G/C/P eligibility and final labels',
                 'RF learning and sufficiency assessment'],
        limitations=['LLC high-load coverage', 'role/core/period confounding',
                     'no target hardware cache validation'])
    return population, report


def freeze(source: Path, output: Path) -> dict:
    """Create a new immutable input snapshot; keep old eligibility and proposal evidence.

    The frozen source configurations retain provisional core placement and false
    training flags. Subsequent measured policies get separate snapshots; split
    membership is joined through workload ID and policy-independent input signature.
    This freezes inputs, not runtime eligibility, statistical sufficiency or a model.
    """
    if output.exists():
        raise FileExistsError(output)
    population, workloads, pool = _population(source)
    # Validate all identities and small-family constraints before creating output.
    taskset_split({w.workload_id: w.family_id for w in workloads},
                  {w.workload_id: w.input_signature for w in workloads},
                  seed=pool['design']['split_seed'])
    output.mkdir(parents=True)
    split = freeze_split(output / 'split.json', workloads, seed=pool['design']['split_seed'])
    population, report = _reports(population, pool, split)
    source_manifest = json.loads((source / 'manifest.json').read_text())
    for relative in [*source_manifest['files'], 'manifest.json']:
        destination = output / 'source' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, destination)
    write_json(output / 'population.json', population)
    write_json(output / 'summary.json', report)
    for relative in IMPLEMENTATION:
        destination = output / 'implementation' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    files = {str(p.relative_to(output)): file_hash(p)
             for p in sorted(output.rglob('*')) if p.is_file()}
    write_json(output / 'manifest.json', dict(schema_version=1, files=files))
    return verify(output)


def verify(directory: Path) -> dict:
    """Replay input hashes, lineage, plans, duplicate aliases and split assignment."""
    check_inputs(directory, json.loads((directory / 'manifest.json').read_text()))
    population, workloads, pool = _population(directory / 'source')
    split = json.loads((directory / 'split.json').read_text())
    validate_taskset_split(split, {w.workload_id: w.family_id for w in workloads},
                          {w.workload_id: w.input_signature for w in workloads})
    if split['seed'] != pool['design']['split_seed']:
        raise ValueError('Frozen split seed differs from predeclared design')
    population, report = _reports(population, pool, split)
    if (population != json.loads((directory / 'population.json').read_text()) or
            report != json.loads((directory / 'summary.json').read_text())):
        raise ValueError('Frozen population or summary differs from source and split')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('freeze')
    prepare.add_argument('--pool', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    replay = commands.add_parser('verify')
    replay.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        report = freeze(args.pool, args.output) if args.command == 'freeze' else verify(args.directory)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
