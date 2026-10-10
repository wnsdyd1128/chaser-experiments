"""Shape-based uint32 adaptation of PolyBench/C DOITGEN: A[r][q][:] = A[r][q][:] C4 for every (r, q), with n = NR =
NQ = NP.

The rank-3 A is bound as an (n*n) x n matrix whose row r*n + q is A[r][q][:]. Each job first resets A to its initial
value, so every job computes the same result; A is updated in place, so its state carries across the sweeps of a
job; sum is scratch. Constant initialization keeps A uniform, which permits a closed-form
checksum (all of A, row-major); arithmetic wraps at 32 bits.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec


def _shapes(task, registry):
    c4 = registry[task.arrays['C4'].array_id]
    if c4.shape is None or len(c4.shape) != 2 or c4.shape[0] != c4.shape[1]:
        raise ValueError('DOITGEN requires a square rank-2 C4 shape')
    n = c4.shape[0]
    return dict(A=(n*n, n), C4=(n, n), sum=(n,))


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, 'DOITGEN')
    n = shapes['C4'][0]
    loads, stores = task.sweeps*n*n*(3*n*n + n) + n**3, task.sweeps*n*n*(n*n + 2*n) + n**3
    pv.check_budget(loads, stores)
    v = pv.initial(task, registry, 'A')
    for _ in range(task.sweeps):
        v = n*v*pv.initial(task, registry, 'C4') % 2**32
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([v]*n**3),
                         checksum_kind='u32-word-fnv1a-output-v1',
                         loop_iterations=task.sweeps*(1 + n + n*n + 2*n**3 + n**4) + 2*(n*n + n**3))


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['C4'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for row in range(n*n):
        for p in range(n):
            yield e('A', row, p, operation='store')
    for _ in range(task.sweeps):
        for row in range(n*n):
            for p in range(n):
                yield e('sum', p, operation='store')
                for s in range(n):
                    yield e('sum', p)
                    yield e('A', row, s)
                    yield e('C4', s, p)
                    yield e('sum', p, operation='store')
            for p in range(n):
                yield e('sum', p)
                yield e('A', row, p, operation='store')
    for row in range(n*n):
        for p in range(n):
            yield e('A', row, p)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['C4'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, A_initial=pv.initial(task, registry, 'A'),
                           **{k: v for role in ('A', 'C4', 'sum') for k, v in pv.steps(task, registry, role).items()})
