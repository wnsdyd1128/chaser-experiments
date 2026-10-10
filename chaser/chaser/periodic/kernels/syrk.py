"""Shape-based uint32 adaptation of PolyBench/C SYRK: lower triangle of C = BETA C + ALPHA A A^T (square n x n).

ALPHA and BETA are the integers 3 and 2 (the original uses 1.5 and 1.2). The loop order is the original's (k
outside j), so A[j][k] walks a column. Each job first resets C to its initial value, so every job computes the same
result; C's state carries across the sweeps of a job, and its upper triangle keeps the initial value. Constant initialization permits a closed-form checksum (all of C, row-major); arithmetic wraps at 32 bits.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec

ALPHA, BETA = 3, 2


def _shapes(task, registry):
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError('SYRK requires a square rank-2 A shape')
    return dict(A=matrix.shape, C=matrix.shape)


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'SYRK')
    n = shapes['A'][0]
    triangle = n*(n + 1)//2
    loads, stores = task.sweeps*(triangle + 3*n*triangle) + n*n, task.sweeps*(triangle + n*triangle) + n*n
    pv.check_budget(loads, stores)
    a, upper = pv.initial(task, registry, 'A'), pv.initial(task, registry, 'C')
    lower = upper
    for _ in range(task.sweeps):
        lower = (BETA*lower + n*ALPHA*a*a) % 2**32
    return KernelMetrics(source_loads=loads, source_stores=stores,
                         expected_checksum=pv.fnv([lower if j <= i else upper for i in range(n) for j in range(n)]),
                         checksum_kind='u32-word-fnv1a-output-v1',
                         loop_iterations=task.sweeps*(1 + n + triangle + n*n + n*triangle) + 2*(n + n*n))


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for i in range(n):
        for j in range(n):
            yield e('C', i, j, operation='store')
    for _ in range(task.sweeps):
        for i in range(n):
            for j in range(i + 1):
                yield e('C', i, j)
                yield e('C', i, j, operation='store')
            for k in range(n):
                for j in range(i + 1):
                    yield e('C', i, j)
                    yield e('A', i, k)
                    yield e('A', j, k)
                    yield e('C', i, j, operation='store')
    for i in range(n):
        for j in range(n):
            yield e('C', i, j)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, alpha=ALPHA, beta=BETA,
                           C_initial=pv.initial(task, registry, 'C'),
                           **{k: v for role in ('A', 'C') for k, v in pv.steps(task, registry, role).items()})
