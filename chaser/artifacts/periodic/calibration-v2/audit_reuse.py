"""Audit the pinned v2 plan against original P evidence without changing either.

Run from the workspace with ``PYTHONPATH=. python3
artifacts/periodic/calibration-v2/audit_reuse.py``. Reports go to calibration-v2;
this audit does not link snapshots, run the simulator, or select thresholds.
"""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from chaser.periodic_calibration import ROOT, check_mapping_snapshot, read_json
from tools.rtems_periodic_calibrate import measured_tat
from tools.rtems_smoke import check_inputs, file_hash, write_json


def main():
    old_root = ROOT / '.cache/calibration-v1'
    new_root = ROOT / '.cache/calibration-v2'
    old = read_json(old_root / 'plan.json')
    plan = read_json(new_root / 'plan.json')
    for root, pinned in ((old_root, old), (new_root, plan)):
        check_inputs(root / 'implementation', {'files': pinned['implementation_hashes']})
    check_inputs(ROOT, {'files': plan['implementation_hashes']})
    assert old['tool_identity'] == plan['tool_identity']
    excluded = {'candidate-v3-0112', 'candidate-v3-0135', 'candidate-v3-0136',
                'candidate-v3-0207', 'validation-supplement-v1-0001'}
    assert not excluded.intersection(plan['inputs'])
    assert all(row['member']['split_group'] == 'validation' for row in plan['inputs'].values())
    evidence, pending = [], []
    protected = {str(root / 'plan.json'): file_hash(root / 'plan.json')
                 for root in (old_root, new_root)}
    for identity, entry in sorted(plan['mappings'].items()):
        name = entry['workload_id']
        origin = plan['inputs'][name]
        if identity not in old['mappings']:
            original = origin['configuration']
            pending.append(dict(mapping_id=identity, workload_id=name,
                original_assignment_matches=entry['mapping'] == {
                    task['task_id']: task['core'] for task in original['tasks']},
                original_policy_id=original['policy_id'],
                planned_policy_id=entry['configuration']['policy_id'],
                reason='No exact calibration snapshot; original policy/plan/ELF identity differs'))
            continue
        assert entry == old['mappings'][identity]
        historical_origin = dict(old['inputs'][name])
        # V1 used the implicit characterized/runs/<workload> U path.
        historical_origin.setdefault('u_directory', str(Path(old['characterized']) / 'runs' / name))
        assert origin == historical_origin
        snapshot = old_root / 'prepared' / identity
        directory = old_root / 'runs' / identity
        paths = [snapshot / 'manifest.json', snapshot / 'analysis/manifest.json',
                 directory / 'protocol.json', directory / 'measurements.jsonl']
        hashes = {str(path): file_hash(path) for path in paths}
        check_mapping_snapshot(snapshot, entry, origin)
        tat = measured_tat(snapshot, directory, plan['timeout_seconds'],
                           plan['tool_identity']['simulator_hash'])
        rows = [json.loads(line) for line in (directory / 'measurements.jsonl').read_text().splitlines()]
        hashes.update({str(directory / row['log']): row['log_hash'] for row in rows})
        protected.update(hashes)
        evidence.append(dict(mapping_id=identity, workload_id=name,
            snapshot=str(snapshot.relative_to(ROOT)), runs=str(directory.relative_to(ROOT)),
            status='exact-reuse-validated', successful_runs=len(rows), median_tat_ns=tat,
            original_u_characterization_id=origin['utilization']['characterization_id'],
            original_u_elf_hash=origin['utilization']['elf_hash'],
            p_elf_hash=rows[0]['elf_hash'], p_plan_hash=rows[0]['plan_hash'],
            evidence_hashes={str(Path(path).relative_to(ROOT)): value for path, value in hashes.items()}))
        if len(evidence) % 25 == 0:
            print(f'validated {len(evidence)} existing P batches', flush=True)
    assert all(file_hash(Path(path)) == expected for path, expected in protected.items())
    audit = dict(status='pass', recorded_utc=datetime.now(timezone.utc).isoformat(),
        plan_hash=file_hash(new_root / 'plan.json'), historical_plan_hash=file_hash(old_root / 'plan.json'),
        auditor_hash=file_hash(Path(__file__)), scope='validation P only; no theta selection',
        existing_evidence_unchanged=True, reused_batches=len(evidence), reused_runs=10 * len(evidence),
        additional_batches=len(pending), additional_runs=10 * len(pending),
        reusable=evidence, pending=pending,
        historical_mappings_not_in_new_plan=sorted(set(old['mappings']) - set(plan['mappings'])))
    budget = dict(plan_hash=audit['plan_hash'], validation_workloads=len(plan['inputs']),
        validation_tasks=sum(len(row['configuration']['tasks']) for row in plan['inputs'].values()),
        theta_candidates={kind: len(row['candidates']) for kind, row in plan['representations'].items()},
        representation_mappings={kind: len(row['mappings']) for kind, row in plan['representations'].items()},
        planned_batches=plan['planned_batches'], planned_runs=plan['planned_runs'],
        reusable_batches=len(evidence), reusable_runs=10 * len(evidence),
        additional_batches=len(pending), additional_runs=10 * len(pending),
        additional_by_workload=dict(Counter(row['workload_id'] for row in pending)),
        new_snapshot_elf_count=3 * len(pending), prepare_workers=plan['prepare_workers'],
        timing_workers=plan['workers'], per_process_timeout_seconds=plan['timeout_seconds'],
        additional_serial_timeout_budget_seconds=len(pending) * 10 * plan['timeout_seconds'],
        limitations='Timeout budget is not a wall-time forecast. Supplement basic P identity differs; '
                     'all pending mappings require fresh snapshots and ten fresh P runs. '
                     'G/C final labels and alpha sensitivity are outside this budget.')
    write_json(new_root / 'reuse-audit.json', audit)
    write_json(new_root / 'budget.json', budget)
    print(json.dumps(budget, indent=2), flush=True)


if __name__ == '__main__':
    main()
