"""Audit candidate input duplication, coverage and collection cost before freezing."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from chaser.dataset import Workload, freeze_split
from chaser.periodic import digest
from chaser.periodic_registry import build_registry
from tools.rtems_smoke import check_inputs, file_hash, write_json


def input_signature(config: dict) -> str:
    """Hash generator inputs without naming or eligibility metadata.

    Preserve task order, policy, placement, shape, sweep, period and horizon.
    Equality is at the generator-input level; distinct builds still need their
    own ELF identities and cannot share measured U or timing evidence.
    """
    ignored = {'workload_id', 'family_id', 'eligible_for_training', 'test_eligible', 'tasks'}
    payload = {k: v for k, v in config.items() if k not in ignored}
    payload['tasks'] = [{k: v for k, v in task.items() if k != 'task_id'}
                        for task in config['tasks']]
    return digest(payload)


def audit_pool(pool: dict) -> dict:
    """Report all inputs without changing membership, collecting runs or freezing.

    Unique-input budgets describe a possible future pool, not permission to
    discard archived candidates. Estimated utilization is never measured U.
    """
    rows = pool['candidates']
    if not rows:
        raise ValueError('Candidate pool is empty')
    registry = build_registry(rows)
    primary = [r for r in registry['workloads'] if r['primary_candidate']]
    split_counts = None
    if registry['primary_family_count'] >= 3:
        with TemporaryDirectory(prefix='chaser-audit-split-') as tmp:
            split = freeze_split(Path(tmp) / 'proposal.json', [
                Workload(r['workload_id'], r['family_id'], {}, 'pending') for r in primary],
                seed=pool['design']['split_seed'])
        split_counts = dict(Counter(split['families'].values()))
    groups, cells, roles = defaultdict(list), defaultdict(list), defaultdict(Counter)
    for row in rows:
        config = row['configuration']
        groups[input_signature(config)].append(row)
        cells[(row['recipe_id'], row['profile'], len(config['tasks']))].append(row)
        base = min(t['period_ticks'] for t in config['tasks'])
        for task in config['tasks']:
            # Report roles jointly with placement/period; marginal counts hide confounding.
            roles[task['pattern']][(task['core'], task['period_ticks'] // base)] += 1

    def runs(records):
        return 10 * sum(len(r['configuration']['tasks']) + 3 for r in records)

    unique = [group[0] for group in groups.values()]
    coverage = []
    for (recipe, profile, count), records in sorted(cells.items()):
        us = [sum(r['estimated_utilization'].values()) for r in records]
        signatures = {input_signature(r['configuration']) for r in records}
        coverage.append(dict(recipe_id=recipe, profile=profile, task_count=count,
            candidate_workloads=len(records), unique_inputs=len(signatures),
            target_total_u=sorted({r['target_total_u'] for r in records}),
            estimated_total_u_range=[min(us), max(us)]))
    duplicates = [dict(input_signature=key,
        workload_ids=[r['configuration']['workload_id'] for r in group],
        target_total_u=[r['target_total_u'] for r in group],
        estimated_total_u=[sum(r['estimated_utilization'].values()) for r in group])
        for key, group in sorted(groups.items()) if len(group) > 1]
    return dict(schema_version=1, scope='static candidate audit; no membership changes',
        candidate_workloads=len(rows), unique_inputs=len(groups),
        redundant_candidates=len(rows) - len(groups),
        primary_candidate_workloads=len(primary),
        primary_families=registry['primary_family_count'],
        proposed_split_family_counts=split_counts,
        all_candidates_runs_one_policy=runs(rows), unique_inputs_runs_one_policy=runs(unique),
        avoidable_runs_one_policy=runs(rows) - runs(unique),
        unique_inputs_independent_u_runs=10 * sum(len(r['configuration']['tasks']) for r in unique),
        unique_inputs_timing_runs_one_policy=30 * len(unique),
        budget_excludes=['theta mapping search', 'other policies/alpha', 'builds', 'analysis',
                         'diagnostics'],
        coverage=coverage, duplicate_groups=duplicates,
        role_core_period_counts={pattern: [dict(core=core, period_ratio=ratio, tasks=count)
            for (core, ratio), count in sorted(counts.items())]
            for pattern, counts in sorted(roles.items())},
        dataset_ready=False, split_frozen=False, runtime_runs_collected=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pool', type=Path, required=True,
                        help='Prepared pool directory containing pool.json and manifest.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads((args.pool / 'manifest.json').read_text())
    check_inputs(args.pool, manifest)
    report = audit_pool(json.loads((args.pool / 'pool.json').read_text()))
    report['source_pool_hash'] = file_hash(args.pool / 'pool.json')
    report['source_manifest_hash'] = file_hash(args.pool / 'manifest.json')
    root = Path(__file__).resolve().parents[1]
    sources = ['tools/rtems_periodic_pool_audit.py', 'chaser/periodic_registry.py',
               'chaser/periodic.py', 'chaser/periodic_patterns.py', 'chaser/periodic_structures.py',
               'chaser/periodic_recipes.py', 'chaser/dataset.py', 'tools/rtems_smoke.py']
    sources.append('chaser/periodic_staged_recipes.py')
    report['implementation_hashes'] = {p: file_hash(root / p) for p in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ('coverage', 'duplicate_groups', 'role_core_period_counts',
                                   'implementation_hashes')}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
