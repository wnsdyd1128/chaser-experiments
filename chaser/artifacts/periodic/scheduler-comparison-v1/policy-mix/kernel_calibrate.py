"""Calibrate the isolated job time of the real-kernel tasks (experiment 45) before any set is generated.

Grid: per kernel and sweeps in SWEEPS, GRID_POINTS dimensions n spaced geometrically between bounds that give about
MIN_ACCESSES to MAX_ACCESSES source accesses per job. Validation: VALIDATION_LEVELS seeded random (kernel, sweeps, n)
inside the same bounds. Each level runs alone (P ELF, mode i+1) with period PERIOD, horizon 4 periods and one period of
warm-up; its job time is the mean measured job CPU (chaser.periodic.dataset.characterize), as in the isolated U gates.
Fit: per (kernel, sweeps), log-log linear interpolation of job time over n. Real kernels are not smooth in n (column
passes meet L1 set conflicts at some n; validation found 19.5 % at MVT n = 87), so the model only chooses n; the
planned U of every task comes from the tasks stage, which runs each needed (kernel, sweeps, n) alone the same way.
Stages:
  measure   run the grid and validation levels, write <output>/measured.json
  fit       write <output>/kernel-model.json with the validation errors (reported, not a gate)
  tasks     run every (kernel, sweeps, n) the design's sets need (kernel_set.needed), write <output>/task-times.json
--design selects kernel_set's design: real-kernels (experiment 45, default), heldout-kernels (experiment 46) or
lowloc-kernels (experiment 47: measure fits the low-locality kernels; tasks measures every size lowloc_set needs),
or a capped lowloc_set design (tasks only).
Usage: python3 kernel_calibrate.py measure|fit|tasks --output <dir> [--design NAME] [--workers N]
Run with PYTHONPATH=<workspace>:policy-mix:period-distribution (the main chaser package).
"""

import argparse
import bisect
from functools import cache
import json
import math
from pathlib import Path
import random

import kernel_tasks as kt

SWEEPS = (1, 2, 4)
GRID_POINTS = 12
MIN_ACCESSES, MAX_ACCESSES = 4_000, 2_000_000
VALIDATION_LEVELS, VALIDATION_SEED = 42, 20264501
PERIOD = 100
MAX_ERROR = 0.02
CHUNK_BYTES, CHUNK_TASKS, CHUNK_ARRAYS = 14 * 1024 ** 2, 24, 96  # the workload limits: 16 MiB, 32 tasks, 96 arrays


def accesses(kernel: str, n: int, sweeps: int) -> int:
    """Approximate source accesses of one job (bounds only; the plan holds the exact count)."""
    per = {'gemm-u32': 2 * n ** 3, 'polybench-jacobi1d-u32': 8 * n, 'polybench-jacobi2d-u32': 12 * n * n,
           'polybench-2mm-u32': 8 * n ** 3, 'polybench-syrk-u32': 2 * n ** 3, 'polybench-trmm-u32': 2 * n ** 3,
           'polybench-doitgen-u32': 4 * n ** 4, 'transpose-u32': 2 * kt.ROWS * n,
           'cornerturn-u32': 4 * kt.ROWS * n}.get(kernel, 8 * n * n)
    return sweeps * per


@cache
def bounds(kernel: str, sweeps: int) -> tuple[int, int]:
    lo = next(n for n in range(3, 10 ** 6) if accesses(kernel, n, sweeps) >= MIN_ACCESSES)
    hi = max(n for n in range(lo, 300_000) if accesses(kernel, n, sweeps) <= MAX_ACCESSES) if kernel != 'polybench-jacobi1d-u32' \
        else MAX_ACCESSES // (8 * sweeps)
    if kernel in kt.LOW_LOCALITY:
        lo, hi = max(lo, kt.MIN_N[kernel]), min(hi, kt.MAX_N)
    return lo, hi


def grid(kernel: str, sweeps: int) -> list[int]:
    lo, hi = bounds(kernel, sweeps)
    return sorted({round(lo * (hi / lo) ** (i / (GRID_POINTS - 1))) for i in range(GRID_POINTS)})


def levels(kernels) -> list[dict]:
    out = [dict(group='fit', kernel=k, sweeps=s, n=n) for k in kernels for s in SWEEPS for n in grid(k, s)]
    rng = random.Random(VALIDATION_SEED)
    for _ in range(VALIDATION_LEVELS):
        k, s = rng.choice(kernels), rng.choice(SWEEPS)
        lo, hi = bounds(k, s)
        out.append(dict(group='validation', kernel=k, sweeps=s, n=round(lo * (hi / lo) ** rng.random())))
    return out


def chunks(rows):
    chunk, size, arrays = [], 0, 0
    for row in rows:
        b, a = kt.data_bytes(row['kernel'], row['n']), len(kt.ROLES[row['kernel']])
        if chunk and (size + b > CHUNK_BYTES or len(chunk) == CHUNK_TASKS or arrays + a > CHUNK_ARRAYS):
            yield chunk
            chunk, size, arrays = [], 0, 0
        chunk.append(row)
        size += b
        arrays += a
    if chunk:
        yield chunk


def interpolate(table: list[tuple[int, float]], n: float) -> float:
    """Log-log linear interpolation (and extrapolation from the nearest pair) of job time over n."""
    ns = [x for x, _ in table]
    i = min(max(bisect.bisect_left(ns, n), 1), len(ns) - 1)
    (n0, t0), (n1, t1) = table[i - 1], table[i]
    return math.exp(math.log(t0) + (math.log(t1) - math.log(t0)) * (math.log(n) - math.log(n0)) / (math.log(n1) - math.log(n0)))


def measure_levels(output: Path, rows: list[dict], workers: int, prefix: str) -> list[dict]:
    """Run every level alone (chunks prepared in parallel, all isolated runs together); add job_ns.
    A chunk whose ELF fails at startup (arm_phase/release_mismatch: arming crossed a tick) is rebuilt as two halves,
    each its own ELF (2026-10-08: the reversed chunk failed again, both halves ran). Existing chunks and runs are reused."""
    from concurrent.futures import ThreadPoolExecutor
    import run as design
    from chaser.periodic.build import prepare
    from chaser.periodic.dataset import characterize, load_batch
    groups = list(chunks(rows))

    def build(name, group):
        directory = output / name
        if not (directory / 'prepared/p/plan.json').exists():
            tasks = [kt.task(r['kernel'], f'k{i:02d}', r['n'], r['sweeps'], 0, PERIOD) for i, r in enumerate(group)]
            prepare(kt.configuration(f'kernel-{name}', tasks, 4 * PERIOD, PERIOD), directory / 'prepared')
        return directory, json.loads((directory / 'prepared/p/plan.json').read_text())

    def run(built):
        specs = [(f'{d.name}/{t["task_id"]}', d / 'prepared', d / 'isolated' / t['task_id'], 'p', i + 1)
                 for d, plan in built for i, t in enumerate(plan['tasks'])]
        failed, infra = design.run_specs(specs, workers)
        if infra:
            raise RuntimeError(f'{infra} calibration runs produced no run header')
        return {name.split('/')[0] for name in failed}

    names = [f'{prefix}-{c:03d}' for c in range(len(groups))]
    with ThreadPoolExecutor(max_workers=16) as pool:
        built = list(pool.map(build, names, groups))
    for c in [c for c, name in enumerate(names) if name in run(built)]:
        half = len(groups[c]) // 2
        parts = [(names[c] + '-a', groups[c][:half]), (names[c] + '-b', groups[c][half:])]
        rebuilt = [build(name, group) for name, group in parts]
        if run(rebuilt):
            raise RuntimeError(f'Isolated calibration runs failed again in the halves of {names[c]}')
        built[c], groups[c] = rebuilt, [g for _, g in parts]
    built = [b for item in built for b in (item if isinstance(item, list) else [item])]
    groups = [g for item in groups for g in (item if item and isinstance(item[0], list) else [item])]
    out = []
    for (d, plan), group in zip(built, groups):
        u = characterize(plan, [load_batch(d / 'prepared', d / 'isolated' / t['task_id']) for t in plan['tasks']])['utilization']
        out += [dict(r, task_id=t['task_id'], accesses=t['source_accesses'], job_ns=u[t['task_id']] * PERIOD * 1e6)
                for r, t in zip(group, plan['tasks'])]
    return out


def measure(output: Path, workers: int) -> None:
    import kernel_set
    rows = measure_levels(output, levels(kernel_set.KERNELS), workers, 'chunk')
    (output / 'measured.json').write_text(json.dumps(dict(period=PERIOD, rows=rows), indent=1) + '\n')


def measure_tasks(output: Path, workers: int) -> None:
    import kernel_set
    if kernel_set.DESIGN.startswith('lowloc'):
        import lowloc_set
        lowloc_set.select(kernel_set.DESIGN)
        needed = lowloc_set.needed()
    else:
        needed = kernel_set.needed()
    rows = [dict(group='task', kernel=k, sweeps=s, n=n) for k, s, n in sorted(needed)]
    rows = measure_levels(output, rows, workers, 'tasks')
    (output / 'task-times.json').write_text(json.dumps(dict(period=PERIOD, times={
        f"{r['kernel']} {r['sweeps']} {r['n']}": r['job_ns'] for r in rows}), indent=1) + '\n')


def tables(rows) -> dict:
    out = {}
    for r in rows:
        if r['group'] == 'fit':
            out.setdefault(f"{r['kernel']} {r['sweeps']}", []).append((r['n'], r['job_ns']))
    return {k: sorted(v) for k, v in out.items()}


def fit(output: Path) -> None:
    rows = json.loads((output / 'measured.json').read_text())['rows']
    model = tables(rows)
    errors = [interpolate(model[f"{r['kernel']} {r['sweeps']}"], r['n']) / r['job_ns'] - 1 for r in rows if r['group'] == 'validation']
    worst = max(abs(e) for e in errors)
    (output / 'kernel-model.json').write_text(json.dumps(dict(
        period=PERIOD, sweeps=SWEEPS, tables={k: [[n, t] for n, t in v] for k, v in model.items()},
        validation_errors=errors, validation_max_error=worst, max_error=MAX_ERROR), indent=1) + '\n')
    print(f'kernel model: validation max error {worst:.2%} over {len(errors)} levels (guides n only; U is measured)')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('measure', 'fit', 'tasks'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=48)
    parser.add_argument('--design', default='real-kernels')
    args = parser.parse_args()
    import kernel_set
    kernel_set.select(args.design)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.stage == 'measure':
        measure(output, args.workers)
    elif args.stage == 'fit':
        fit(output)
    else:
        measure_tasks(output, args.workers)


if __name__ == '__main__':
    main()
