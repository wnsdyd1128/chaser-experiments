"""Probe the laysim shared-L2 and memory path before the footprint study.

N cyclic tasks (N = 1..4) run under Partitioned, one per core, all released
together with equal jobs, so their jobs overlap completely. Each task streams
its own array of W bytes S times per job (O2 workload). Per-access job time
against N and W shows:
  - whether the shared L2 serves one L1 miss at a time (W fits L2, N grows),
  - the cost of a memory access (W larger than L2),
  - how many concurrent footprints of a size thrash the L2 (W near L2 / N).
Writes <output>/probe.json. Run with PYTHONPATH set to the c3 code copy.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.build import prepare
from chaser.periodic.dataset import load_batch
from chaser.periodic.measurement import CONTRACT
from tools.rtems_smoke import write_json

import run as design

LINE = 32
PERIOD = 100
WARMUP_JOBS, MEASURED_JOBS = 3, 5
# Array size (KiB) -> sweeps per job, sized for a few ms per job at L2-hit speed.
SIZES = {32: 64, 512: 4, 640: 3, 768: 3, 3072: 1}
COUNTS = (1, 2, 3, 4)


def configuration(kib: int, count: int) -> dict:
    tasks = [dict(task_id=f't{i}', pattern='cyclic', distinct=kib * 1024 // LINE, stride=LINE,
                  sweeps=SIZES[kib], core=i, period_ticks=PERIOD) for i in range(count)]
    return dict(workload_id=f'l2-probe-w{kib:04d}k-n{count}-v1', family_id='l2-probe-v1', policy_id='one-per-core',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization='O2',
                horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * PERIOD, warmup_ticks=WARMUP_JOBS * PERIOD,
                u_repeats=1, diagnostic_only=True, tasks=tasks)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = [(kib, count) for kib in SIZES for count in COUNTS]
    specs = []
    for kib, count in cases:
        target = output / f'w{kib:04d}k-n{count}'
        if not (target / 'prepared').exists():
            target.mkdir(parents=True, exist_ok=True)
            config = configuration(kib, count)
            write_json(target / 'configuration.json', config)
            prepare(config, target / 'prepared')
        specs.append((target.name, target / 'prepared', target / 'run', 'p', 0))
    failed, infra = design.run_specs(specs, len(specs))
    rows = []
    for kib, count in cases:
        target = output / f'w{kib:04d}k-n{count}'
        record = load_batch(target / 'prepared', target / 'run')[0]
        jobs = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in record['jobs'] if j['job'] >= WARMUP_JOBS]
        accesses = kib * 1024 // LINE * SIZES[kib]
        rows.append(dict(kib=kib, count=count, status=record['execution_status'], errors=record.get('errors', []),
                         job_ns=sum(jobs) / len(jobs) if jobs else None,
                         ns_per_access=sum(jobs) / len(jobs) / accesses if jobs else None))
    write_json(output / 'probe.json', dict(sizes=SIZES, period_ticks=PERIOD, rows=rows, failed=failed, infra=infra))
    for row in rows:
        print(row)


if __name__ == '__main__':
    main()
