"""Shape-based uint32 adaptation of PolyBench/C BICG: s = A^T r and q = A p in one pass over A.

The C template fixes volatile load order and resets both outputs per sweep. Constant initialization permits a
closed-form checksum; arithmetic wraps at 32 bits.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec


def _shapes(task, registry):
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2:
        raise ValueError('BICG requires a rank-2 A shape')
    n, m = matrix.shape
    return dict(A=(n, m), s=(m,), q=(n,), p=(m,), r=(n,))


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'BICG')
    n, m = shapes['A']
    loads, stores = task.sweeps*6*n*m + m + n, task.sweeps*(m + n + 2*n*m)
    pv.check_budget(loads, stores)
    a = pv.initial(task, registry, 'A')
    s = n*pv.initial(task, registry, 'r')*a
    q = m*a*pv.initial(task, registry, 'p')
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([s]*m + [q]*n),
                         checksum_kind='u32-word-fnv1a-output-v1', loop_iterations=task.sweeps*(1 + m + n + n*m) + m + n)


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n, m = registry[task.arrays['A'].array_id].shape
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for _ in range(task.sweeps):
        for j in range(m):
            yield e('s', j, operation='store')
        for i in range(n):
            yield e('q', i, operation='store')
            for j in range(m):
                yield e('s', j)
                yield e('r', i)
                yield e('A', i, j)
                yield e('s', j, operation='store')
                yield e('q', i)
                yield e('A', i, j)
                yield e('p', j)
                yield e('q', i, operation='store')
    for j in range(m):
        yield e('s', j)
    for i in range(n):
        yield e('q', i)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n, m = registry[task.arrays['A'].array_id].shape
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, m=m,
                           **{k: v for role in ('A', 's', 'q', 'p', 'r') for k, v in pv.steps(task, registry, role).items()})
