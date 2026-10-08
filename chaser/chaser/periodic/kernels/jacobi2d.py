"""Shape-based uint32 adaptation of PolyBench/C JACOBI-2D: one time step (B from A, then A from B) per sweep.

The five-point mean is an integer division by 5 (the original multiplies by 0.2); loads follow the original
operand order. State carries across sweeps. A and B must share one initial value v with 5v < 2^32, so every
element stays v and the checksum (all of A, row-major) is closed-form. B's four corners are never accessed.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec

NEIGHBORS = ((0, 0), (0, -1), (0, 1), (1, 0), (-1, 0))  # A[i][j] + A[i][j-1] + A[i][1+j] + A[1+i][j] + A[i-1][j]


def _shapes(task, registry):
    array = registry[task.arrays['A'].array_id]
    if array.shape is None or len(array.shape) != 2 or array.shape[0] != array.shape[1] or array.shape[0] < 3:
        raise ValueError('JACOBI-2D requires a square rank-2 A shape of at least 3 x 3')
    return dict(A=array.shape, B=array.shape)


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'JACOBI-2D')
    n = shapes['A'][0]
    v = pv.initial(task, registry, 'A')
    if pv.initial(task, registry, 'B') != v or 5*v >= 2**32:
        raise ValueError('JACOBI-2D requires A and B with one initial value v, 5v < 2^32')
    inner = (n - 2)**2
    loads, stores = task.sweeps*10*inner + n*n, task.sweeps*2*inner
    pv.check_budget(loads, stores)
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([v]*(n*n)),
                         checksum_kind='u32-word-fnv1a-output-v1',
                         loop_iterations=task.sweeps*(1 + 2*((n - 2) + inner)) + n + n*n)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for src, dst in (('A', 'B'), ('B', 'A')):
            for i in range(1, n - 1):
                for j in range(1, n - 1):
                    for di, dj in NEIGHBORS:
                        yield e(src, i + di, j + dj)
                    yield e(dst, i, j, operation='store')
    for i in range(n):
        for j in range(n):
            yield e('A', i, j)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    n = registry[task.arrays['A'].array_id].shape[0]
    corner = lambda role, index: role == 'B' and index[0] in (0, n - 1) and index[1] in (0, n - 1)
    return pv.footprint(task, registry, _shapes(task, registry), skip=corner)


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, last=n - 1,
                           **{k: v for role in ('A', 'B') for k, v in pv.steps(task, registry, role).items()})
