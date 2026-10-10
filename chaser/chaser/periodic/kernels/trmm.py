"""Shape-based uint32 adaptation of PolyBench/C TRMM: B = ALPHA A^T B with A unit lower triangular (square n x n).

ALPHA is the integer 3 (the original uses 1.5). Each job first resets B to its initial value, so every job computes
the same result; B is updated in place in the original order (row i reads the rows below it before they are
updated), so its state carries across the sweeps of a job; only A's strictly lower triangle is read. Constant initialization keeps each row of B uniform, which permits a closed-form checksum (all of B,
row-major); arithmetic wraps at 32 bits.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec

ALPHA = 3


def _shapes(task, registry):
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] < 2:
        raise ValueError('TRMM requires a square rank-2 A shape of at least 2 x 2')
    return dict(A=matrix.shape, B=matrix.shape)


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'TRMM')
    n = shapes['A'][0]
    below = n*(n - 1)//2
    loads, stores = task.sweeps*(3*n*below + n*n) + n*n, task.sweeps*(n*below + n*n) + n*n
    pv.check_budget(loads, stores)
    a, rows = pv.initial(task, registry, 'A'), [pv.initial(task, registry, 'B')]*n
    for _ in range(task.sweeps):
        suffix, new = 0, [0]*n
        for i in reversed(range(n)):
            new[i] = ALPHA*(rows[i] + a*suffix) % 2**32
            suffix += rows[i]
        rows = new
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([v for v in rows for _ in range(n)]),
                         checksum_kind='u32-word-fnv1a-output-v1',
                         loop_iterations=task.sweeps*(1 + n + n*n + n*below) + 2*(n + n*n))


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for i in range(n):
        for j in range(n):
            yield e('B', i, j, operation='store')
    for _ in range(task.sweeps):
        for i in range(n):
            for j in range(n):
                for k in range(i + 1, n):
                    yield e('B', i, j)
                    yield e('A', k, i)
                    yield e('B', k, j)
                    yield e('B', i, j, operation='store')
                yield e('B', i, j)
                yield e('B', i, j, operation='store')
    for i in range(n):
        for j in range(n):
            yield e('B', i, j)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    upper = lambda role, index: role == 'A' and index[0] <= index[1]
    return pv.footprint(task, registry, _shapes(task, registry), skip=upper)


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, alpha=ALPHA,
                           B_initial=pv.initial(task, registry, 'B'),
                           **{k: v for role in ('A', 'B') for k, v in pv.steps(task, registry, role).items()})
