"""Experiment 44: the pre-run decisions, made before any measured run and frozen in decisions.json.

For every prepared case of a confirm-* output this reads the plan (wfd/configuration.json: task ids, planned U,
periods) and the YARDA outputs (locality.json, yarda/), runs chaser.policy.pfirst.decision.decide with the frozen
policy, and checks that pfirst's CHASER and U-balanced mappings equal the prepared ra-cgb and wfd configurations
(a mismatch stops the run). It refuses to run once any measured run exists (isolated runs do not count).
Writes <output>/decisions.json and <output>/decisions.sha256.
Run with PYTHONPATH holding the workspace root (main chaser package) and policy-mix.
Usage: python3 confirm_decide.py --output <confirm output> --policy <frozen policy dir>
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from chaser.policy.pfirst import decision, features, inputs


def measured_runs(output: Path) -> list[Path]:
    return [p for p in output.glob('*/u*/s*/*/*/measurements.jsonl') if p.parent.parent.name != 'isolated']


def cores(case: Path, build: str) -> list[int]:
    return [t['core'] for t in json.loads((case / build / 'configuration.json').read_text())['tasks']]


def decide_case(case: Path, policy) -> dict:
    config = json.loads((case / 'wfd/configuration.json').read_text())
    plan = [dict(task_id=t['task_id'], u=t['u_planned'], period=t['period_ticks']) for t in config['tasks']]
    tasks = inputs.load_case(case, plan)
    start = time.perf_counter()
    record = decision.decide(tasks, policy, config['high_load']['seed'])
    seconds = time.perf_counter() - start
    mappings = record['mappings']
    if decision.CHASER in mappings and mappings[decision.CHASER] != cores(case, 'ra-cgb'):
        raise RuntimeError(f'{case}: pfirst CHASER mapping differs from the prepared ra-cgb configuration')
    if 'g' in mappings and mappings['g'] != cores(case, 'wfd'):
        raise RuntimeError(f'{case}: pfirst U-balanced mapping differs from the prepared wfd configuration')
    demand = features.set_features(tasks)
    return dict(status=record['status'], choice=record['choice'], probabilities=record['probabilities'],
                nominal=record['nominal'], static_rule=record['static_rule'], reasons=record['reasons'],
                cache_demand=demand['cache_demand'], memory_demand=demand['memory_demand'],
                occupancy=demand['occupancy'], decide_seconds=seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if measured_runs(output):
        raise SystemExit(f'{output}: measured runs exist; decisions must precede every run')
    policy = decision.Policy(args.policy.resolve())
    cases = {str(case.relative_to(output)): decide_case(case, policy) for case in sorted(output.glob('*/u*/s*'))}
    result = dict(policy=str(args.policy), model_sha256=policy.spec['model_sha256'],
                  prediction_fingerprint=policy.spec['prediction_fingerprint'], tau=policy.tau,
                  static_threshold=decision.STATIC_THRESHOLD, decided_utc=datetime.now(timezone.utc).isoformat(),
                  cases=cases)
    path = output / 'decisions.json'
    path.write_text(json.dumps(result, indent=1) + '\n')
    (output / 'decisions.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '\n')
    counts = {}
    for c in cases.values():
        counts[c['status']] = counts.get(c['status'], 0) + 1
    print('wrote', path, len(cases), 'cases', counts)


if __name__ == '__main__':
    main()
