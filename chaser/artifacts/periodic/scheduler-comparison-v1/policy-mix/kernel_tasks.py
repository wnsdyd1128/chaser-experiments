"""Real-kernel periodic tasks (experiments 45, 46): one uint32 PolyBench/C adaptation per task, sized by one dimension.

A task is (kernel, n, sweeps): square n x n matrices, n-vectors (jacobi-1d uses n-vectors only) and DOITGEN's
(n*n) x n tensor, private arrays, constant initial values (the stencils share one value, as their closed-form checksum
requires). Each job runs `sweeps` kernel invocations; reductions reset their outputs per sweep, the stencils carry
their state across sweeps, and the in-place updates (2MM's D, SYRK's C, TRMM's B, DOITGEN's A) reset that array at the
start of each job and carry it across the job's sweeps.
KERNELS are experiment 45's; HELD_OUT are experiment 46's, used in neither the RF's training nor experiment 45.
LOW_LOCALITY are experiment 47's low-CLS kernels: a naive transpose and a planar complex corner turn of an R x n block
(R = ROWS, a power of two, so the column stores of the n x R output fall on a few L1 sets); n sizes the job.
"""

from math import prod

KERNELS = ('gemm-u32', 'polybench-atax-u32', 'polybench-bicg-u32', 'polybench-mvt-u32', 'polybench-gesummv-u32',
           'polybench-jacobi1d-u32', 'polybench-jacobi2d-u32')
HELD_OUT = ('polybench-2mm-u32', 'polybench-syrk-u32', 'polybench-trmm-u32', 'polybench-doitgen-u32')
LOW_LOCALITY = ('transpose-u32', 'cornerturn-u32')
SHORT = {k: k.replace('polybench-', '').replace('-u32', '') for k in KERNELS + HELD_OUT + LOW_LOCALITY}
ROWS = 256
# Columns n of the low-locality kernels: below MIN_N the output columns fit the few L1 sets they map to and HARA's CLS
# is about 0.87 (2026-10-13, R = 256: 0.475-0.481 from n = 24 transpose / 16 corner turn); MAX_N keeps a task within
# the L2-sized data of experiment 27's low-CLS tasks (transpose 512 KiB, corner turn 1 MiB).
MIN_N = {'transpose-u32': 24, 'cornerturn-u32': 16}
MAX_N = 256
SHAPES = {1: lambda n: [n], 2: lambda n: [n, n], 3: lambda n: [n * n, n], 4: lambda n: [ROWS, n], 5: lambda n: [n, ROWS]}
# role -> shape code (SHAPES) per kernel
ROLES = {
    'gemm-u32': dict(A=2, B=2, C=2),
    'polybench-atax-u32': dict(A=2, x=1, tmp=1, y=1),
    'polybench-bicg-u32': dict(A=2, s=1, q=1, p=1, r=1),
    'polybench-mvt-u32': dict(A=2, x1=1, x2=1, y1=1, y2=1),
    'polybench-gesummv-u32': dict(A=2, B=2, tmp=1, x=1, y=1),
    'polybench-jacobi1d-u32': dict(A=1, B=1),
    'polybench-jacobi2d-u32': dict(A=2, B=2),
    'polybench-2mm-u32': dict(A=2, B=2, tmp=2, C=2, D=2),
    'polybench-syrk-u32': dict(A=2, C=2),
    'polybench-trmm-u32': dict(A=2, B=2),
    'polybench-doitgen-u32': dict(A=3, C4=2, sum=1),
    'transpose-u32': dict(A=4, B=5),
    'cornerturn-u32': dict(Ar=4, Ai=4, Br=5, Bi=5),
}


def task(kernel: str, task_id: str, n: int, sweeps: int, core: int, period: int) -> tuple[list[dict], dict]:
    """(arrays, task) of one schema v2 task with private arrays named <role><task_id>."""
    arrays, bindings = [], {}
    stencil = kernel.startswith('polybench-jacobi')
    for r, (role, rank) in enumerate(ROLES[kernel].items()):
        array_id = f'{role.lower()}{task_id}'
        arrays.append(dict(array_id=array_id, element_type='uint32_t', shape=SHAPES[rank](n),
                           alignment_bytes=32, initial_value=3 if stencil else r + 2))
        bindings[role] = dict(array_id=array_id)
    return arrays, dict(task_id=task_id, pattern=kernel, arrays=bindings, sweeps=sweeps, core=core, period_ticks=period)


def data_bytes(kernel: str, n: int) -> int:
    return sum(4 * prod(SHAPES[code](n)) for code in ROLES[kernel].values())


def configuration(workload_id: str, tasks: list[tuple[list[dict], dict]], horizon: int, warmup: int,
                  optimization='O2', family='real-kernels-v1') -> dict:
    return dict(schema_version=2, workload_id=workload_id, family_id=family, policy_id='explicit-core-map-v1',
                measurement_contract_id='chaser-periodic-measurement-v3', horizon_ticks=horizon, warmup_ticks=warmup,
                u_repeats=1, workload_optimization=optimization, arrays=[a for arrays, _ in tasks for a in arrays],
                tasks=[t for _, t in tasks])
