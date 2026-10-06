"""Run experiments 1 and 2 on the 12-20 task design (tc_taskset) through run.py and control.py.

  tc_run.py main <run.py stage> --output <O>                      G, C (1+3), P, C2 (1+1+2), snake P
  tc_run.py control <control.py stage> --main <O> --output <O2>   P', C', C2' (cohort-aware P)

run.py and control.py read the design from their module global `taskset`; this swaps in
tc_taskset, adds the tc files to both snapshots and records every set's task count in the
main protocol. Stages and options are theirs; run with PYTHONPATH set to the c2 code copy,
as experiments 1 and 2 did.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.rtems_smoke import write_json

import control
import run
import tc_taskset

TC_SNAPSHOT = ('tc_taskset.py', 'tc_run.py', 'test_tc_taskset.py')
_run_prepare_all = run.prepare_all


def prepare_all(output, workers):
    _run_prepare_all(output, workers)
    protocol = json.loads((output / 'protocol.json').read_text())
    protocol.update(task_range=tc_taskset.TASK_RANGE, per_core_u=tc_taskset.PER_CORE_U,
                    task_counts=[tc_taskset.task_count(k) for k in range(tc_taskset.SETS)],
                    task_u_by_set=[tc_taskset.task_u(k) for k in range(tc_taskset.SETS)])
    write_json(output / 'protocol.json', protocol)


def main():
    which = sys.argv.pop(1) if len(sys.argv) > 1 else None
    if which not in ('main', 'control'):
        raise SystemExit(__doc__)
    run.taskset = tc_taskset
    run.SNAPSHOT += TC_SNAPSHOT
    control.SNAPSHOT += TC_SNAPSHOT
    # run.main looks prepare_all up as a module global.
    run.prepare_all = prepare_all
    (run.main if which == 'main' else control.main)()


if __name__ == '__main__':
    main()
