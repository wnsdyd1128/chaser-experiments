"""Shape-based uint32 adaptation of PolyBench/C GESUMMV: y = ALPHA A x + BETA B x, two matrices in one pass.

ALPHA and BETA are the integers 3 and 2 (the original uses 1.5 and 1.2). Scratch and output are reset per sweep.
Constant initialization permits a closed-form checksum; arithmetic wraps at 32 bits.
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
        raise ValueError('GESUMMV requires a square rank-2 A shape')
    n = matrix.shape[0]
    return dict(A=(n, n), B=(n, n), tmp=(n,), x=(n,), y=(n,))


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'GESUMMV')
    n = shapes['x'][0]
    loads, stores = task.sweeps*(6*n*n + 2*n) + n, task.sweeps*(3*n + 2*n*n)
    pv.check_budget(loads, stores)
    xv = pv.initial(task, registry, 'x')
    t, u = n*pv.initial(task, registry, 'A')*xv, n*pv.initial(task, registry, 'B')*xv
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([ALPHA*t + BETA*u]*n),
                         checksum_kind='u32-word-fnv1a-output-v1', loop_iterations=task.sweeps*(1 + n + n*n) + n)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for i in range(n):
            yield e('tmp', i, operation='store')
            yield e('y', i, operation='store')
            for j in range(n):
                yield e('A', i, j)
                yield e('x', j)
                yield e('tmp', i)
                yield e('tmp', i, operation='store')
                yield e('B', i, j)
                yield e('x', j)
                yield e('y', i)
                yield e('y', i, operation='store')
            yield e('tmp', i)
            yield e('y', i)
            yield e('y', i, operation='store')
    for i in range(n):
        yield e('y', i)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, alpha=ALPHA, beta=BETA,
                           **{k: v for role in ('A', 'B', 'tmp', 'x', 'y') for k, v in pv.steps(task, registry, role).items()})
