"""CAAS Algorithm 1 placements on a finished design's sets (experiment 28).

chaser.policy.allocator.allocate, the CAAS Algorithm 1 implementation the calibration-v2 policies
froze: tasks by descending U; a task whose locality scalar is at or below the threshold goes to
the least-loaded isolated core (core 0), the others worst-fit over the non-isolated cores 1-3;
capacity 1 per core, no spill between the groups. Variants:
  caas        CA-CSRD (L1 CSRD affinity, from ca_table.py), frozen calibrated threshold
  cls-a1      CLS, threshold 0.5 (placement_lib.CLS_LOW, the cut of the balanced CLS grouping)
  cls-a1-cal  CLS, the frozen calibrated CLS threshold of the same calibration (sensitivity)
A task the allocator cannot place (its group is full) still needs a core to build the workload:
it goes to the least-loaded core overall and the configuration is flagged placeable=False with
the unplaced tasks listed. That fallback is not part of CAAS; analyses treat such runs apart.
configuration() takes a design's wfd configuration and changes only the cores and the ids.
"""

import json
from pathlib import Path

from chaser.policy.allocator import CoreGroups, allocate

FROZEN = Path(__file__).resolve().parent.parent.parent / 'calibration-v2/frozen-policies.json'
_FROZEN = json.loads(FROZEN.read_text())['policies']
POLICIES = {'caas': ('ca-csrd', _FROZEN['ca-csrd']['threshold']),
            'cls-a1': ('cls', 0.5),
            'cls-a1-cal': ('cls', _FROZEN['cls']['threshold'])}
CORE_GROUPS = CoreGroups(isolated=tuple(_FROZEN['ca-csrd']['cores']['isolated']),
                         non_isolated=tuple(_FROZEN['ca-csrd']['cores']['non_isolated']))
CLS_ALPHA = 0.5  # yarda_counts.ALPHA: the CLS the designs plan and check


def place(policy: str, tasks: list[dict], ca: dict[str, float]) -> tuple[list[int], list[str]]:
    kind, threshold = POLICIES[policy]
    records = {t['task_id']: dict(ca_csrd_l1=ca[t['task_id']], cls={str(CLS_ALPHA): t['cls_planned']}) for t in tasks}
    placement = allocate(records, {t['task_id']: t['u_planned'] for t in tasks}, CORE_GROUPS, kind=kind,
                         threshold=threshold, alpha=CLS_ALPHA if kind == 'cls' else None)
    load = {core: 1.0 - left for core, left in placement.residual.items()}
    cores = {}
    for t in sorted(tasks, key=lambda t: (-t['u_planned'], t['task_id'])):
        if t['task_id'] in placement.mapping:
            cores[t['task_id']] = placement.mapping[t['task_id']]
        else:
            core = min(load, key=lambda c: (load[c], c))
            cores[t['task_id']] = core
            load[core] += t['u_planned']
    return [cores[t['task_id']] for t in tasks], sorted(placement.infeasible)


def configuration(base, ca_table: Path, load: float, heaviness: str, set_id: int, placement: str) -> dict:
    config = base.configuration(load, heaviness, set_id, 'wfd')
    if placement == 'wfd':
        return config
    key = f'{heaviness}/u{round(load * 100):03d}/s{set_id:02d}'
    cores, unplaced = place(placement, config['tasks'], json.loads(ca_table.read_text())['cases'][key])
    tasks = [dict(t, core=c) for t, c in zip(config['tasks'], cores)]
    core_u = [sum(t['u_planned'] for t in tasks if t['core'] == core) for core in range(len(config['high_load']['core_u']))]
    kind, threshold = POLICIES[placement]
    return dict(config, tasks=tasks,
                workload_id=config['workload_id'].removesuffix('-wfd-v1') + f'-{placement}-v1',
                policy_id=config['policy_id'].removesuffix('-wfd-v1') + f'-{placement}-v1',
                high_load=dict(config['high_load'], placement=placement, core_u=core_u, core_cap=1.0,
                               placeable=not unplaced, unplaced=unplaced, scalar=kind, threshold=threshold))
