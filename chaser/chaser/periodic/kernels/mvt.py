"""Shape-based uint32 adaptation of PolyBench/C MVT: x1 = A y1 (row pass) and x2 = A^T y2 (column pass).

Both outputs are reset per sweep (the original accumulates into its inputs); the column pass reads A with the
row stride, as the original does. Constant initialization permits a closed-form checksum.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec


def _shapes(task, registry):
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError('MVT requires a square rank-2 A shape')
    n = matrix.shape[0]
    return dict(A=(n, n), x1=(n,), x2=(n,), y1=(n,), y2=(n,))


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'MVT')
    n = shapes['x1'][0]
    loads, stores = task.sweeps*6*n*n + 2*n, task.sweeps*(2*n + 2*n*n)
    pv.check_budget(loads, stores)
    a = pv.initial(task, registry, 'A')
    x1, x2 = n*a*pv.initial(task, registry, 'y1'), n*a*pv.initial(task, registry, 'y2')
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([x1]*n + [x2]*n),
                         checksum_kind='u32-word-fnv1a-output-v1', loop_iterations=task.sweeps*(1 + 4*n + 2*n*n) + 2*n)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for i in range(n):
            yield e('x1', i, operation='store')
        for i in range(n):
            yield e('x2', i, operation='store')
        for i in range(n):
            for j in range(n):
                yield e('x1', i)
                yield e('A', i, j)
                yield e('y1', j)
                yield e('x1', i, operation='store')
        for i in range(n):
            for j in range(n):
                yield e('x2', i)
                yield e('A', j, i)
                yield e('y2', j)
                yield e('x2', i, operation='store')
    for role in ('x1', 'x2'):
        for i in range(n):
            yield e(role, i)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n,
                           **{k: v for role in ('A', 'x1', 'x2', 'y1', 'y2') for k, v in pv.steps(task, registry, role).items()})
