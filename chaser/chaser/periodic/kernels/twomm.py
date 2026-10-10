"""Shape-based uint32 adaptation of PolyBench/C 2MM: D = BETA D + (ALPHA A B) C with square n x n matrices.

ALPHA and BETA are the integers 3 and 2 (the original uses 1.5 and 1.2). Each job first resets D to its initial
value, so every job computes the same result; tmp is reset per sweep; D is scaled and accumulated in place, so its
state carries across the sweeps of a job, as in the original. Constant initialization keeps tmp and D uniform, which
permits a closed-form checksum (all of D, row-major); arithmetic wraps at 32 bits.
"""

from collections.abc import Iterator
from pathlib import Path

from chaser.periodic.kernels import polybench_views as pv
from chaser.periodic.kernels.templates import render_template
from chaser.periodic.workload import ArrayRegistry, KernelMetrics, MemoryFootprint, NoParameters, ReferenceEvent, TaskSpec

ALPHA, BETA = 3, 2
ROLES = ('A', 'B', 'tmp', 'C', 'D')


def _shapes(task, registry):
    matrix = registry[task.arrays['A'].array_id]
    if matrix.shape is None or len(matrix.shape) != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError('2MM requires a square rank-2 A shape')
    return {role: matrix.shape for role in ROLES}


def validate(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> KernelMetrics:
    shapes = _shapes(task, registry)
    pv.check_views(task, registry, shapes, '2MM')
    n = shapes['A'][0]
    loads, stores = task.sweeps*(6*n**3 + n*n) + n*n, task.sweeps*(2*n**3 + 2*n*n) + n*n
    pv.check_budget(loads, stores)
    t = n*ALPHA*pv.initial(task, registry, 'A')*pv.initial(task, registry, 'B') % 2**32
    d = pv.initial(task, registry, 'D')
    for _ in range(task.sweeps):
        d = (BETA*d + n*t*pv.initial(task, registry, 'C')) % 2**32
    return KernelMetrics(source_loads=loads, source_stores=stores, expected_checksum=pv.fnv([d]*(n*n)),
                         checksum_kind='u32-word-fnv1a-output-v1',
                         loop_iterations=task.sweeps*(1 + 2*n + 2*n*n + 2*n**3) + 2*(n + n*n))


def events(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> Iterator[ReferenceEvent]:
    n = registry[task.arrays['A'].array_id].shape[0]
    e = lambda *args, **kw: pv.event(task, registry, *args, **kw)
    for i in range(n):
        for j in range(n):
            yield e('D', i, j, operation='store')
    for _ in range(task.sweeps):
        for i in range(n):
            for j in range(n):
                yield e('tmp', i, j, operation='store')
                for k in range(n):
                    yield e('tmp', i, j)
                    yield e('A', i, k)
                    yield e('B', k, j)
                    yield e('tmp', i, j, operation='store')
        for i in range(n):
            for j in range(n):
                yield e('D', i, j)
                yield e('D', i, j, operation='store')
                for k in range(n):
                    yield e('D', i, j)
                    yield e('tmp', i, k)
                    yield e('C', k, j)
                    yield e('D', i, j, operation='store')
    for i in range(n):
        for j in range(n):
            yield e('D', i, j)


def footprint(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> MemoryFootprint:
    return pv.footprint(task, registry, _shapes(task, registry))


def source(task: TaskSpec[NoParameters], registry: ArrayRegistry) -> list[str]:
    n = registry[task.arrays['A'].array_id].shape[0]
    return render_template(Path(__file__).with_suffix('.c.in'), task, registry, n=n, alpha=ALPHA, beta=BETA,
                           D_initial=pv.initial(task, registry, 'D'),
                           **{k: v for role in ROLES for k, v in pv.steps(task, registry, role).items()})
