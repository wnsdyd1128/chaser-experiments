"""Bind replacement membership to immutable characterization evidence paths."""

from collections import Counter
import json
from pathlib import Path

from chaser.periodic import digest
from tools.rtems_smoke import check_inputs, file_hash

ROOT = Path(__file__).resolve().parents[1]


def active_membership(frozen: Path, source: Path) -> tuple[dict, dict, dict]:
    """Validate the full split before consumers open validation-only payloads.

    Paths in the binding are workspace-relative. Original train/test members and
    retained originals must be identical; only validation replacements are allowed.
    Generation-time pending flags are historical, not a substitute for raw checks.
    """
    binding = json.loads(source.read_text())
    population_path = ROOT / binding['active_population']
    if (binding['schema_version'] != 1
            or file_hash(population_path) != binding['active_population_hash']
            or file_hash(frozen / 'population.json') != binding['original_population_hash']
            or file_hash(frozen / 'split.json') != binding['original_split_hash']):
        raise ValueError('Active membership source identity changed')
    population = json.loads(population_path.read_text())
    original = json.loads((frozen / 'population.json').read_text())['workloads']
    members = population['workloads']
    old = {m['workload_id']: m for m in original}
    active = {m['workload_id']: m for m in members}
    assignments = {n: m['split_group'] for n, m in active.items()}
    excluded = {m['workload_id'] for m in population['excluded']}
    added = set(active) - set(old)
    family_counts = lambda rows: Counter((m['family_id'], m['split_group']) for m in rows)
    if (len(active) != len(members) or len(active) != population['active_tasksets']
            or digest(members) != population['membership_hash']
            or assignments != population['assignments']
            or dict(Counter(assignments.values())) != population['active_split_counts']
            or len(active) != len(old)
            or family_counts(members) != family_counts(original)
            or excluded.intersection(active)
            or set(old) - set(active) != excluded.intersection(old)
            or added != set(population['added_workload_ids'])
            or added != set(binding['supplements'])):
        raise ValueError('Active membership accounting or family/split counts changed')
    for name, member in old.items():
        if name in active and active[name] != member:
            raise ValueError('Active membership changed an original input or split')
        if member['split_group'] != 'validation' and active.get(name) != member:
            raise ValueError('Active membership must preserve train/test identity')
    if any(active[n]['split_group'] != 'validation' for n in added):
        raise ValueError('Active supplements must be validation-only')
    check_inputs(ROOT, dict(files=binding['files']))
    identity = dict(source=str(source.resolve()), source_hash=file_hash(source),
                    population=str(population_path.resolve()), population_hash=file_hash(population_path),
                    membership_hash=population['membership_hash'], assignments_hash=digest(assignments),
                    active_tasksets=len(active), split_counts=population['active_split_counts'])
    return population, binding['supplements'], identity
