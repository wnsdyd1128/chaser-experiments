"""Run the thesis' synthetic designs through high-load/hl_run.py: prepare, isolated, pilot, full, stats.

--design task-count (taskcount_set): experiment 20, 12-20 tasks x memory share x load; wfd/, cgb/, ra/ and
ra-cgb/ builds, P on each (p, p_cgb, p_ra, p_racgb) and G, C2 (1+1+2) on wfd.
--design small-memory-load (loadmem_set): experiment 24, 12-20 tasks x period CV x 32 KiB low-CLS share x
per-core load 0.45-0.6; runs as task-count.
--design deadline-small / deadline-big (deadline_set, deadline_big_set): experiment 27's
pre-registered sets (32 KiB low-CLS at 50 % of U, 768 KiB at 25 %); runs as task-count plus P on
the three random placements (p_rnd0-2). deadline_analysis.py is snapshot with the scripts.
--design deadline-small-caas / deadline-big-caas (deadline_caas_set, deadline_big_caas_set):
experiment 28, CAAS Algorithm 1 on experiment 27's sets; P on algorithm1's caas (p_caas), cls-a1
(p_clsa1) and cls-a1-cal (p_clsa1cal), to pair with experiment 27's results.
--design memory-cost (memcost_set): experiment 41, pre-registered; the memory tasks hit L2 (l2) or go to
memory (mem, mem_calibrate.py's shape) at the same CLS and U, same tasks and cores; wfd and cgb only.
--design confirm-small / confirm-big / confirm-mem (confirm_set): experiment 44, pre-registered; CHASER (ra-cgb)
under P and the wfd build under G4, C1+3 and C1+1+2 on every set. confirm_decide.py runs between isolated and pilot.
The designs of the development experiments (17-26, 33, 38; their sets are in results/) were removed from this
runner on 2026-10-07; their snapshots stay in the results bundles.
On top of hl_run's prepare, every case runs yarda_cpp on the wfd build (locality.json:
counts, CLS, IR instructions per task; CLS must equal the planned closed form) and the
policy-mix scripts are snapshot next to hl_run's. Run pm_check.py first (its shapes are
the same for every design); run with PYTHONPATH set to the c3 code copy. Stages and
options are hl_run's.
"""

import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

from tools.rtems_smoke import file_hash, write_json

import bi_run
import confirm_set
import deadline_big_caas_set
import deadline_big_set
import deadline_caas_set
import deadline_set
import hl_run
import loadmem_set
import memcost_set
import placement_lib
import taskcount_set
import yarda_counts

BOUNDARY_RUNS = (('wfd', 'p', 'p'), ('cgb', 'p', 'p_cgb'), ('ra', 'p', 'p_ra'), ('ra-cgb', 'p', 'p_racgb'))
BOUNDARY_PAIRS = (('p_cgb', 'p_ra'), ('p_racgb', 'p_ra'), ('p_racgb', 'p_cgb'), ('p_cgb', 'p'), ('p_ra', 'p'))
TASKCOUNT_RUNS = (('wfd', 'g', 'g'), ('wfd', 'c2', 'c2')) + BOUNDARY_RUNS
TASKCOUNT_PAIRS = BOUNDARY_PAIRS + (('g', 'p_racgb'), ('c2', 'p_racgb'), ('g', 'p_ra'))
RANDOM_RUNS = tuple((policy, 'p', f'p_{policy}') for policy in placement_lib.RANDOM_POLICIES)
DEADLINE_RUNS = TASKCOUNT_RUNS + RANDOM_RUNS
DEADLINE_PAIRS = TASKCOUNT_PAIRS + tuple(('p_racgb', key) for _, _, key in RANDOM_RUNS)
CAAS_RUNS = (('caas', 'p', 'p_caas'), ('cls-a1', 'p', 'p_clsa1'), ('cls-a1-cal', 'p', 'p_clsa1cal'))
CAAS_PAIRS = (('p_clsa1', 'p_caas'), ('p_clsa1cal', 'p_caas'), ('p_clsa1cal', 'p_clsa1'))
MEMCOST_RUNS = (('wfd', 'p', 'p'), ('cgb', 'p', 'p_cgb'))
MEMCOST_PAIRS = (('p_cgb', 'p'),)
CONFIRM_RUNS = (('ra-cgb', 'p', 'p_racgb'), ('wfd', 'g', 'g'), ('wfd', 'c', 'c'), ('wfd', 'c2', 'c2'))
CONFIRM_PAIRS = (('g', 'p_racgb'),)
SNAPSHOT = ('placement_lib.py', 'mix_set.py', 'taskcount_set.py', 'loadmem_set.py', 'pm_check.py', 'pm_run.py',
            'deadline_set.py', 'deadline_big_set.py', 'deadline_analysis.py', 'rt_metrics.py', 'algorithm1.py',
            'ca_table.py', 'deadline_caas_set.py', 'deadline_big_caas_set.py', 'ladder_analysis.py',
            'mem_calibrate.py', 'memcost_set.py', 'memcost_analysis.py', 'confirm_set.py', 'confirm_decide.py',
            'confirm_analysis.py')
HL_SNAPSHOT = ('hl_run.py', 'hl_set.py', 'mem_set.py')

_hl_prepare_one, _hl_prepare_all = hl_run.prepare_one, hl_run.prepare_all


def prepare_one(output, case):
    manifests = _hl_prepare_one(output, case)
    target = hl_run.case_dir(output, case)
    counts = yarda_counts.analyze(target / 'wfd/prepared', target / 'yarda')
    rows = []
    for task in json.loads((target / 'wfd/configuration.json').read_text())['tasks']:
        count = counts[task['task_id']]
        if abs(count['cls'] - task['cls_planned']) > bi_run.CLS_TOLERANCE:
            raise ValueError(f'{hl_run.label(case)}/{task["task_id"]}: yarda CLS {count["cls"]} != planned')
        rows.append(dict(count, task_id=task['task_id'], role=task['role'], period_ticks=task['period_ticks'],
                         u_planned=task['u_planned'], footprint_kib=task['footprint_kib'],
                         traffic_planned=task['traffic_planned']))
    write_json(target / 'locality.json', dict(tasks=rows))
    return manifests


def prepare_all(output, workers):
    _hl_prepare_all(output, workers)
    for name in SNAPSHOT:
        if (HERE / name).exists():
            shutil.copyfile(HERE / name, output / name)
    protocol = json.loads((output / 'protocol.json').read_text())
    protocol['snapshot_hashes'].update({name: file_hash(output / name) for name in SNAPSHOT
                                        if (output / name).exists()})
    protocol.update(hl_run.hl.protocol_extra())
    protocol.update(placements=hl_run.hl.PLACEMENTS, pairs=hl_run.PAIRS)
    write_json(output / 'protocol.json', protocol)


DESIGNS = {'task-count': (taskcount_set, TASKCOUNT_RUNS, TASKCOUNT_PAIRS),
           'small-memory-load': (loadmem_set, TASKCOUNT_RUNS, TASKCOUNT_PAIRS),
           'deadline-small': (deadline_set, DEADLINE_RUNS, DEADLINE_PAIRS),
           'deadline-big': (deadline_big_set, DEADLINE_RUNS, DEADLINE_PAIRS),
           'deadline-small-caas': (deadline_caas_set, CAAS_RUNS, CAAS_PAIRS),
           'deadline-big-caas': (deadline_big_caas_set, CAAS_RUNS, CAAS_PAIRS),
           'memory-cost': (memcost_set, MEMCOST_RUNS, MEMCOST_PAIRS),
           **{name: (design, CONFIRM_RUNS, CONFIRM_PAIRS) for name, design in confirm_set.DESIGNS.items()}}


def main():
    if '--design' not in sys.argv:
        raise SystemExit(f"pm_run.py needs --design, one of {', '.join(DESIGNS)}")
    hl_run.DESIGNS.update(DESIGNS)
    hl_run.SNAPSHOT = HL_SNAPSHOT
    # hl_run's stages look these up as module globals.
    hl_run.prepare_one, hl_run.prepare_all = prepare_one, prepare_all
    hl_run.main()


if __name__ == '__main__':
    main()
